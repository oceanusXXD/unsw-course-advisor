import React, { useState, useRef, useEffect } from 'react'
import MessageBubble from './MessageBubble'
import EmptyState from './EmptyState'
import { Send, Square } from 'lucide-react'

export default function ChatWindow({ messages, streaming, onSuggestionClick, onSend, loading, onStop }) {
    const [input, setInput] = useState('')
    const textareaRef = useRef(null)

    const handleSubmit = () => {
        if (!input.trim() || loading) return
        onSend(input)
        setInput('')
    }

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            handleSubmit()
        }
    }
    // !!!!不要动行距调整
    useEffect(() => {
        const textarea = textareaRef.current
        if (!textarea) return

        const initialHeight = 52
        const maxHeight = 500
        textarea.style.height = 'auto'

        // 计算行数
        const lineCount = textarea.value.split('\n').length

        if (lineCount <= 1) {
            // 空或一行 → 高度固定
            textarea.style.height = `${initialHeight}px`
        } else {
            // 超过一行 → 动态高度，限制最大值
            const newHeight = Math.min(textarea.scrollHeight, maxHeight)
            console.log('Adjusting height to:', newHeight)
            textarea.style.height = `${newHeight}px`
        }
    }, [input])


    return (
        <div className="flex flex-col h-full">
            <div className="flex-1 overflow-y-auto scrollbar-thin px-6 py-8">
                <div className="max-w-4xl mx-auto space-y-6">
                    {messages.length === 0 ? (
                        <EmptyState onSuggestionClick={onSuggestionClick} />
                    ) : (
                        messages.map((msg, i) => (
                            <MessageBubble key={i} message={msg} streaming={streaming && i === messages.length - 1} />
                        ))
                    )}
                </div>
            </div>

            {/* Composer */}
            <div className="px-6 py-4">
                <div className="max-w-4xl mx-auto relative flex items-center">
                    <textarea
                        ref={textareaRef}
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="Ask me anything about UNSW courses..."
                        className="flex-1 px-5 py-3 pr-16 bg-[#212121] text-white placeholder-gray-400 resize-none
                                   focus:outline-none focus:ring-2 focus:ring-blue-600/30 transition-all
                                   text-[18px] leading-[1.75rem] tracking-wide rounded-xl"
                        style={{
                            height: '52px',
                            maxHeight: '500px',
                            overflowY: 'auto',
                            lineHeight: '1.75rem',
                        }}
                    />
                    <button
                        type="button"
                        onClick={loading ? onStop : handleSubmit}
                        disabled={!loading && !input.trim()}
                        className="absolute right-3 bottom-3 flex items-center justify-center p-0 text-white"
                    >
                        {loading ? <Square className="w-6 h-6" /> : <Send className="w-6 h-6" />}
                    </button>
                </div>
                <p className="text-xs text-text-muted text-center mt-3">
                    Shift+Enter for newline. Enter to send. Cmd+Ctrl+K to focus composer.
                </p>
            </div>
        </div>
    )
}
export { ChatWindow }
