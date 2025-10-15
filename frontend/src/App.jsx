import React, { useRef, useState } from 'react'
import { streamChatSSE } from './services/api'
import { Header } from './components/Header/Header'
import { ChatWindow } from './components/Chat/ChatWindow'
import Composer from './components/Composer/Composer'
import Toaster from './components/Toaster/Toaster'
import Sidebar from './components/Sidebar/Sidebar'

const API_URL = 'http://127.0.0.1:8000/api/chat_multiround/'
const DEFAULT_USER_ID = 'test_user_v3.3_fixed'

export default function App() {
  const [messages, setMessages] = useState([])
  const [sources, setSources] = useState([])
  const [loading, setLoading] = useState(false)
  const [responseTime, setResponseTime] = useState(null)
  const [userId, setUserId] = useState(DEFAULT_USER_ID)
  const [sourcesOpen, setSourcesOpen] = useState(true)
  const [toasts, setToasts] = useState([])

  const abortRef = useRef(null)

  const addToast = (title, message) => {
    const id = Math.random().toString(36).slice(2)
    setToasts((t) => [...t, { id, title, message }])
    setTimeout(() => {
      setToasts((t) => t.filter((x) => x.id !== id))
    }, 4000)
  }

  // handleSend 函数正是我们需要的，它接收一个查询字符串并启动整个流程
  const handleSend = async (query) => {
    if (!query) return; // 防止空消息发送
    
    const time = new Date().toLocaleTimeString()
    setMessages((prev) => [
      ...prev,
      { role: 'user', content: query, time },
      { role: 'assistant', content: '', time: new Date().toLocaleTimeString() },
    ])
    setLoading(true)
    setSources([])
    setResponseTime(null)
    const controller = new AbortController()
    abortRef.current = controller

    let full = ''
    const start = performance.now()

    try {
      await streamChatSSE({
        apiUrl: API_URL,
        query,
        history: [], // 注意：这里的 history 是空的，如果需要多轮对话，你需要传递之前的 messages
        userId,
        signal: controller.signal,
        onToken: (token) => {
          try {
            const obj = JSON.parse(token)
            if (obj.type === 'history') return
          } catch (e) {}

          full += token

          setMessages((prev) => {
            const newMessages = [...prev]
            for (let i = newMessages.length - 1; i >= 0; i--) {
              if (newMessages[i].role === 'assistant') {
                newMessages[i] = { ...newMessages[i], content: full }
                break
              }
            }
            return newMessages
          })
        },
        onSources: (data) => setSources(data),
        onError: (err) => {
          setLoading(false)
          addToast('Error', String(err))
        },
      })
    } catch (err) {
      if (err.name !== 'AbortError') {
        addToast('Error', err.message || String(err))
      }
    } finally {
      const elapsed = (performance.now() - start) / 1000
      setResponseTime(elapsed)
      setLoading(false)
      abortRef.current = null
    }
  }

  const handleStop = () => {
    if (abortRef.current) {
      abortRef.current.abort()
      abortRef.current = null
      setLoading(false)
      setMessages((prev) => {
        const newMessages = [...prev]
        for (let i = newMessages.length - 1; i >= 0; i--) {
          if (newMessages[i].role === 'assistant') {
            newMessages[i] = {
              ...newMessages[i],
              content: (newMessages[i].content || '') + '\n\n[stopped]'
            }
            break
          }
        }
        return newMessages
      })
    }
  }

  const clearAll = () => {
    setMessages([])
    setSources([])
    setResponseTime(null)
    if (abortRef.current) {
      abortRef.current.abort()
      abortRef.current = null
    }
    setLoading(false)
  }

  return (
    <div className="h-full flex flex-col bg-gradient-to-br from-bg-base via-bg-surface to-bg-base">
      <Header
        userId={userId}
        setUserId={setUserId}
        onNewChat={clearAll}
        onToggleSources={() => setSourcesOpen((s) => !s)}
        sourcesOpen={sourcesOpen}
        loading={loading}
      />
      
      <div className="flex-1 min-h-0 flex">
        <div className="flex-1 flex flex-col min-h-0">
          <ChatWindow 
            messages={messages} 
            streaming={loading} 
            // ✨ 主要改动：将 handleSend 函数作为 onSuggestionClick 属性传递给 ChatWindow
            onSuggestionClick={handleSend} 
          />
          <Composer onSend={handleSend} loading={loading} onStop={handleStop} />
        </div>

        <div className={`transition-all duration-300 ${sourcesOpen ? 'w-full md:w-[320px] xl:w-[360px]' : 'w-0 overflow-hidden'}`}>
          <Sidebar sources={sources} responseTime={responseTime} userId={userId} />
        </div>
      </div>

      <Toaster toasts={toasts} onRemove={(id) => setToasts((t) => t.filter((x) => x.id !== id))} />
    </div>
  )
}