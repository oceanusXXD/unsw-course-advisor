// src/App.jsx
import React, { useRef, useState } from 'react'
import { streamChatSSE } from './services/api'
import { ChatWindow } from './components/Chat/ChatWindow'
import Toaster from './components/Toaster/Toaster'
import { PlusCircle, PanelLeftClose, PanelLeftOpen } from 'lucide-react'

const API_URL = 'http://127.0.0.1:8000/api/chat_multiround/'
const DEFAULT_USER_ID = 'test_user_v3.3_fixed'

export default function App() {
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  const [userId] = useState(DEFAULT_USER_ID)
  const [leftExpanded, setLeftExpanded] = useState(true)
  const [draft, setDraft] = useState('')
  const [toasts, setToasts] = useState([])
  const abortRef = useRef(null)

  // 模拟历史会话数据
  const [sessions, setSessions] = useState([
    { id: 's1', title: 'AI 课程推荐', preview: '推荐哪些 UNSW AI 相关课程？' },
    { id: 's2', title: 'COMP1511 简介', preview: 'COMP1511 适合什么背景的学生？' },
  ])
  const [currentSession, setCurrentSession] = useState('s1')

  const addToast = (title, message) => {
    const id = Math.random().toString(36).slice(2)
    setToasts((t) => [...t, { id, title, message }])
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3500)
  }

  const handleSend = async (query) => {
    if (!query) return
    const time = new Date().toLocaleTimeString()
    setMessages((prev) => [
      ...prev,
      { role: 'user', content: query, time },
      { role: 'assistant', content: '', time },
    ])
    setLoading(true)
    const controller = new AbortController()
    abortRef.current = controller
    let full = ''

    try {
      await streamChatSSE({
        apiUrl: API_URL,
        query,
        history: [],
        userId,
        signal: controller.signal,
        onToken: (token) => {
          try {
            const obj = JSON.parse(token)
            if (obj.type === 'history') return
          } catch {}
          full += token
          setMessages((prev) => {
            const newMsgs = [...prev]
            for (let i = newMsgs.length - 1; i >= 0; i--) {
              if (newMsgs[i].role === 'assistant') {
                newMsgs[i] = { ...newMsgs[i], content: full }
                break
              }
            }
            return newMsgs
          })
        },
        onError: (err) => addToast('Error', String(err)),
      })
    } catch (err) {
      if (err.name !== 'AbortError') addToast('Error', err.message || String(err))
    } finally {
      setLoading(false)
      abortRef.current = null
    }
  }

  const handleStop = () => {
    if (abortRef.current) {
      abortRef.current.abort()
      abortRef.current = null
      setLoading(false)
    }
  }

  const clearChat = () => {
    setMessages([])
    setDraft('')
    addToast('新会话', '已开始新的聊天')
  }

  const createNewSession = () => {
    const id = Math.random().toString(36).slice(2)
    const newSession = { id, title: '新对话', preview: '' }
    setSessions((prev) => [newSession, ...prev])
    setCurrentSession(id)
    clearChat()
  }

  return (
    <div className="h-screen w-screen flex bg-[#0d1117] text-white">
      {/* 左侧栏：会话列表 */}
      {leftExpanded ? (
        <aside className="w-64 bg-[#0b0e13] flex flex-col p-3 transition-all duration-300">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-gray-300 tracking-wide">Chat Sessions</h2>
            <button
              onClick={() => setLeftExpanded(false)}
              className="p-1.5 rounded-md hover:bg-[#1a1f27] transition"
              title="收起"
            >
              <PanelLeftClose className="w-5 h-5" />
            </button>
          </div>

          <button
            onClick={createNewSession}
            className="flex items-center gap-2 px-3 py-2 rounded-md bg-[#1a1f27] hover:bg-[#232a36] text-sm font-medium text-gray-200 transition mb-3"
          >
            <PlusCircle className="w-4 h-4" />
            New Chat
          </button>

          <div className="flex-1 overflow-auto scrollbar-thin scrollbar-thumb-[#2a313d] scrollbar-track-transparent">
            {sessions.map((s) => (
              <button
                key={s.id}
                onClick={() => setCurrentSession(s.id)}
                className={`w-full text-left px-3 py-2 rounded-md text-sm mb-1 transition ${
                  s.id === currentSession
                    ? 'bg-[#1f2631] text-white'
                    : 'text-gray-400 hover:bg-[#1a1f27]'
                }`}
              >
                <div className="font-medium truncate">{s.title}</div>
                {s.preview && (
                  <div className="text-xs text-gray-500 truncate">{s.preview}</div>
                )}
              </button>
            ))}
          </div>
        </aside>
      ) : (
        <div className="w-14 bg-[#0b0e13] flex flex-col items-center py-3 gap-3 transition-all duration-300">
          <button
            onClick={() => setLeftExpanded(true)}
            title="展开左侧"
            className="w-10 h-10 rounded-lg flex items-center justify-center hover:bg-[#1a1f27] transition"
          >
            <PanelLeftOpen className="w-5 h-5" />
          </button>

          <button
            onClick={createNewSession}
            title="New chat"
            className="w-10 h-10 rounded-lg flex items-center justify-center hover:bg-[#1a1f27] transition"
          >
            <PlusCircle className="w-5 h-5" />
          </button>
        </div>
      )}

      {/* 右侧：整体深灰色聊天区 */}
      <main className="flex-1 flex flex-col bg-[#0d1117]">
        <div className="flex-1 overflow-hidden p-6">
      <ChatWindow
        messages={messages}
        streaming={loading}
        onSuggestionClick={handleSend}
        onSend={handleSend}
        loading={loading}
        onStop={handleStop}
      />
    </div>

      </main>

      <Toaster
        toasts={toasts}
        onRemove={(id) => setToasts((t) => t.filter((x) => x.id !== id))}
      />

      <style>{`
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-thumb { background-color: #2a313d; border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background-color: #3a4351; }
      `}</style>
    </div>
  )
}
