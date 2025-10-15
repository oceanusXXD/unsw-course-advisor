export async function streamChatSSE({
    apiUrl,
    query,
    history,
    userId,
    signal,
    onToken,
    onSources,
    onError,
}) {
    try {
        const res = await fetch(apiUrl, {
            method: 'POST',
            signal,
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                query,
                history,
                user_id: userId,
                stream: true,
            }),
        })
        if (!res.ok || !res.body) {
            throw new Error(`HTTP ${res.status}`)
        }

        const reader = res.body.getReader()
        const decoder = new TextDecoder('utf-8')
        let buf = ''

        while (true) {
            const { value, done } = await reader.read()
            if (done) break
            buf += decoder.decode(value, { stream: true })

            const parts = buf.split('\n\n')
            // Keep last partial chunk in buffer
            buf = parts.pop() || ''

            for (const chunk of parts) {
                // Expecting server-sent style lines like: "data: ...."
                const lines = chunk.split('\n')
                for (const line of lines) {
                    const trimmed = line.trim()
                    if (!trimmed) continue
                    const prefix = 'data:'
                    if (trimmed.startsWith(prefix)) {
                        const payload = trimmed.slice(prefix.length).trim()
                        if (payload === '[DONE]') continue
                        try {
                            const obj = JSON.parse(payload)
                            if (obj.type === 'token' && typeof obj.data === 'string') {
                                onToken?.(obj.data)
                            } else if (obj.type === 'sources' && Array.isArray(obj.data)) {
                                onSources?.(obj.data)
                            } else if (obj.type === 'history') {
                                // optional history payloads
                                onToken?.(JSON.stringify({ type: 'history' }))
                            } else if (typeof obj === 'string') {
                                onToken?.(obj)
                            }
                        } catch {
                            // If server sometimes sends raw tokens, pass-through
                            onToken?.(payload)
                        }
                    }
                }
            }
        }
    } catch (err) {
        if (onError) onError(err)
        else throw err
    }
}