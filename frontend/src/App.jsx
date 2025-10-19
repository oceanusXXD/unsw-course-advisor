// src/App.jsx
import React, { useState, useEffect, useRef } from 'react'

// 认证 & 许可证
import AuthForm from './components/Auth/AuthForm'
import LicensePanel from './components/Auth/LicensePanel'
import { getCurrentUser, logoutUser, streamChat } from './services/api'

// 聊天相关组件
import { ChatWindow } from './components/Chat/ChatWindow'
import Toaster from './components/Toaster/Toaster'

// Icons
import { PlusCircle, PanelLeftClose, PanelLeftOpen } from 'lucide-react'

const DEFAULT_USER_ID = 'test_user_v3.3_fixed'

export default function App() {
  // --- 认证相关 state ---
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [user, setUser] = useState(null)
  const [showAuth, setShowAuth] = useState(false)
  const [showLicense, setShowLicense] = useState(false)
  const [authLoading, setAuthLoading] = useState(true) // 初始检查 token 的 loading

  // --- 聊天 / UI 相关 state ---
  const [messages, setMessages] = useState([])
  const [streamingLoading, setStreamingLoading] = useState(false)
  const [userId] = useState(DEFAULT_USER_ID)
  const [leftExpanded, setLeftExpanded] = useState(true)
  const [draft, setDraft] = useState('')
  const [toasts, setToasts] = useState([])
  const abortRef = useRef(null)

  const [sessions, setSessions] = useState([
    { id: 's1', title: 'AI 课程推荐', preview: '推荐哪些 UNSW AI 相关课程？' },
    { id: 's2', title: 'COMP1511 简介', preview: 'COMP1511 适合什么背景的学生？' },
  ])
  const [currentSession, setCurrentSession] = useState('s1')

  // --- 初始检查 token ---
  useEffect(() => {
    checkAuth()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const checkAuth = async () => {
    const token = localStorage.getItem('access')
    if (token) {
      try {
        const data = await getCurrentUser()
        setUser(data.user)
        setIsAuthenticated(true)
      } catch (err) {
        console.error('Token invalid:', err)
        localStorage.removeItem('access')
        localStorage.removeItem('refresh')
      }
    }
    setAuthLoading(false)
  }

  // --- 认证成功回调（供 AuthForm 调用）---
  const handleAuthSuccess = (data) => {
    // 假定 data.user 存在
    setUser(data.user)
    setIsAuthenticated(true)
    setShowAuth(false)
    // 可选：把用户写入 localStorage（如果后端返回了）
    if (data.access) localStorage.setItem('access', data.access)
    if (data.refresh) localStorage.setItem('refresh', data.refresh)
  }

  // --- 登出 ---
  const handleLogout = async () => {
    try {
      const refreshToken = localStorage.getItem('refresh')
      if (refreshToken) {
        await logoutUser(refreshToken)
      }
    } catch (err) {
      console.error('Logout error:', err)
    } finally {
      localStorage.removeItem('access')
      localStorage.removeItem('refresh')
      localStorage.removeItem('user')
      localStorage.removeItem('user_key')
      setUser(null)
      setIsAuthenticated(false)
    }
  }

  // --- Toaster ---
  const addToast = (title, message) => {
    const id = Math.random().toString(36).slice(2)
    setToasts((t) => [...t, { id, title, message }])
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3500)
  }
  const handleSend = async (query) => {
    if (!query) return;
    const time = new Date().toLocaleTimeString();

    setMessages((prev) => [
      ...prev,
      { role: 'user', content: query, time },
      { role: 'assistant', content: '', time },
    ]);

    setStreamingLoading(true);
    const controller = new AbortController();
    abortRef.current = controller;
    let full = '';

    try {
      // 你的调用代码保持原样，完全不用动！
      await streamChat({
        endpoint: 'chatbot/chat_multiround/',
        query,
        history: [],
        userId,
        signal: controller.signal,
        onToken: (token) => {
          try {
            const obj = JSON.parse(token);
            if (obj.type === 'history') return;
          } catch { }
          full += token;
          setMessages((prev) => {
            const newMsgs = [...prev];
            for (let i = newMsgs.length - 1; i >= 0; i--) {
              if (newMsgs[i].role === 'assistant') {
                newMsgs[i] = { ...newMsgs[i], content: full };
                break;
              }
            }
            return newMsgs;
          });
        },
        onError: (err) => addToast('Error', String(err)),
      });
    } catch (err) {
      if (err.name !== 'AbortError') addToast('Error', err.message || String(err));
    } finally {
      setStreamingLoading(false);
      abortRef.current = null;
    }
  };


  const handleStop = () => {
    if (abortRef.current) {
      abortRef.current.abort()
      abortRef.current = null
      setStreamingLoading(false)
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

  // --- 初始 loading 指示 ---
  if (authLoading) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="animate-spin h-12 w-12 border-4 border-blue-500 border-t-transparent rounded-full" />
      </div>
    )
  }

  // --- 主渲染 ---
  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900">
      {/* 导航栏 */}
      <nav className="bg-gray-800/50 backdrop-blur-sm border-b border-gray-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
                <span className="text-white font-bold text-xl">C</span>
              </div>
              <span className="text-white text-xl font-bold">课程顾问系统</span>
            </div>

            <div className="flex items-center gap-4">
              {isAuthenticated ? (
                <>
                  <div className="text-gray-300 text-sm">
                    <span className="text-gray-400">欢迎, </span>
                    <span className="font-semibold">{user?.email}</span>
                  </div>

                  <button
                    onClick={() => setShowLicense(true)}
                    className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-medium transition-colors"
                  >
                    许可证管理
                  </button>

                  <button
                    onClick={handleLogout}
                    className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg font-medium transition-colors"
                  >
                    登出
                  </button>
                </>
              ) : (
                <button
                  onClick={() => setShowAuth(true)}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
                >
                  登录 / 注册
                </button>
              )}
            </div>
          </div>
        </div>
      </nav>

      {/* 主内容区布局：左侧会话栏 + 中间聊天区 */}
      <div className="h-[calc(100vh-64px)] flex">
        {/* 左侧栏 */}
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
                  className={`w-full text-left px-3 py-2 rounded-md text-sm mb-1 transition ${s.id === currentSession
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
          </div>
        )}

        {/* 聊天主区 */}
        <main className="flex-1 flex flex-col bg-[#0d1117] p-6 overflow-hidden">
          {isAuthenticated ? (
            <div className="space-y-6">
              {/* 欢迎卡片 */}

              {/* 许可证状态卡片 */}
              <div className="bg-gray-800/50 backdrop-blur-sm rounded-2xl p-6 border border-gray-700">
                <div className="flex justify-between items-center">
                  <div>
                    <h2 className="text-xl font-semibold text-white mb-2">许可证状态</h2>
                    <div className="flex items-center gap-2">
                      {user?.license?.license_active ? (
                        <>
                          <div className="w-3 h-3 rounded-full bg-green-500 animate-pulse" />
                          <span className="text-green-400 font-semibold">已激活</span>
                        </>
                      ) : (
                        <>
                          <div className="w-3 h-3 rounded-full bg-gray-500" />
                          <span className="text-gray-400">未激活</span>
                        </>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={() => setShowLicense(true)}
                    className="px-6 py-3 bg-gradient-to-r from-purple-600 to-purple-700 hover:from-purple-700 hover:to-purple-800 text-white rounded-lg font-semibold transition-all duration-200 shadow-lg hover:shadow-purple-500/50"
                  >
                    管理许可证
                  </button>
                </div>

                {user?.license?.license_active && (
                  <div className="mt-4 grid grid-cols-3 gap-4 text-sm">
                    <div className="bg-gray-900/50 rounded-lg p-3">
                      <p className="text-gray-400 mb-1">许可证密钥</p>
                      <code className="text-blue-400 font-mono text-xs">
                        {user.license.license_key}
                      </code>
                    </div>
                    <div className="bg-gray-900/50 rounded-lg p-3">
                      <p className="text-gray-400 mb-1">设备ID</p>
                      <p className="text-white">{user.license.device_id || '未绑定'}</p>
                    </div>
                    <div className="bg-gray-900/50 rounded-lg p-3">
                      <p className="text-gray-400 mb-1">剩余天数</p>
                      <p className="text-green-400 font-semibold">
                        {user.license.days_until_expiry || '永久'}
                      </p>
                    </div>
                  </div>
                )}
              </div>

              {/* 功能演示区（聊天窗口等） */}
              <div className="bg-gray-800/50 backdrop-blur-sm rounded-2xl p-6 border border-gray-700">
                <h3 className="text-lg font-semibold text-white mb-3">💬 智能对话</h3>
                <p className="text-gray-400 text-sm mb-4">
                  基于 LangGraph 的智能课程顾问系统
                </p>
                <div className="h-[480px] bg-[#071018] rounded-lg overflow-hidden">
                  <ChatWindow
                    messages={messages}
                    streaming={streamingLoading}
                    onSuggestionClick={handleSend}
                    onSend={handleSend}
                    loading={streamingLoading}
                    onStop={handleStop}
                  />
                </div>
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-20">
              <div className="text-center space-y-4">
                <div className="w-20 h-20 bg-gradient-to-br from-blue-500 to-purple-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
                  <span className="text-white font-bold text-4xl">C</span>
                </div>
                <h1 className="text-4xl font-bold text-white">欢迎使用课程顾问系统</h1>
                <p className="text-gray-400 text-lg">请先登录以使用完整功能</p>
                <button
                  onClick={() => setShowAuth(true)}
                  className="mt-6 px-8 py-3 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white rounded-lg font-semibold transition-all duration-200 shadow-lg hover:shadow-blue-500/50"
                >
                  立即登录
                </button>
              </div>
            </div>
          )}
        </main>
      </div>

      {/* Toaster */}
      <Toaster
        toasts={toasts}
        onRemove={(id) => setToasts((t) => t.filter((x) => x.id !== id))}
      />

      {/* 模态框 */}
      {showAuth && <AuthForm onSuccess={handleAuthSuccess} />}
      {showLicense && isAuthenticated && (
        <LicensePanel
          user={user}
          onClose={() => setShowLicense(false)}
        />
      )}
    </div>
  )
}
