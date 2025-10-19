import React, { useState } from 'react'
import { loginUser, registerUser } from '../../services/api'

export default function AuthForm({ onSuccess }) {
  const [isLogin, setIsLogin] = useState(true)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [username, setUsername] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // 调试信息对象（会展示在 UI）
  const [debugInfo, setDebugInfo] = useState(null)
  const [showDebug, setShowDebug] = useState(false)

  const collectDebug = (label, extra = {}) => {
    const info = {
      ts: new Date().toISOString(),
      label,
      url: window.location.href,
      userAgent: navigator.userAgent,
      localStorage: {
        access: localStorage.getItem('access'),
        refresh: localStorage.getItem('refresh'),
        user: localStorage.getItem('user'),
      },
      cookies: document.cookie,
      form: { isLogin, email, username },
      ...extra,
    }
    console.groupCollapsed(`[AuthForm][DEBUG] ${label}`)
    console.log(info)
    console.groupEnd()
    setDebugInfo(info)
    setShowDebug(true)
    return info
  }

  const formatAxiosLikeError = (err) => {
    try {
      const out = {
        message: err.message,
        name: err.name,
        stack: err.stack,
      }
      if (err.response) {
        out.response = {
          status: err.response.status,
          headers: err.response.headers,
          data: err.response.data,
        }
      }
      if (err.request) {
        out.request = err.request
      }
      return out
    } catch (e) {
      return { message: String(err) }
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    setDebugInfo(null)
    setShowDebug(false)

    collectDebug('submit-start')

    try {
      console.log('AuthForm: calling API with', { isLogin, email, username })

      const data = isLogin
        ? await loginUser(email, password)
        : await registerUser(email, password, username)

      // 打印后端原始返回（便于调试）
      console.log('AuthForm: api returned ->', data)
      collectDebug('api-success', { apiReturned: data })

      // 检查 token 格式
      if (!data || !data.access || !data.refresh) {
        const errMsg = '服务器返回了无效的 token 格式（缺少 access 或 refresh）'
        console.error(errMsg, data)
        collectDebug('invalid-token-format', { apiReturned: data })
        throw new Error(errMsg)
      }

      // 存储 token / user
      localStorage.setItem('access', data.access)
      localStorage.setItem('refresh', data.refresh)
      if (data.user) {
        localStorage.setItem('user', JSON.stringify(data.user))
      }

      onSuccess(data)
    } catch (err) {
      console.error('AuthForm: caught error ->', err)

      // 解析常见 axios-like 错误结构（方便观察 response.data / status）
      const parsed = formatAxiosLikeError(err)
      collectDebug('api-error', { parsed })

      // 对 401 或常见后端提示做友好提示并在 UI 高亮
      const status = parsed.response?.status
      const respData = parsed.response?.data
      const respTextShort = respData ? JSON.stringify(respData).slice(0, 1000) : ''

      if (status === 401 || (respData && /Authentication credentials were not provided/i.test(JSON.stringify(respData)))) {
        const msg = '认证失败：后端返回 "Authentication credentials were not provided."（401）。' +
                    '常见原因：后端需要身份验证但前端请求未带 token，或使用了不正确的认证方式 / CSRF / CORS 设置。' +
                    '请检查 Network 面板与后端日志。'
        setError(msg)
      } else {
        // 一般错误：显示后端返回的 message / data（如果有）
        const serverMsg = respData?.detail || respData?.message || respData || parsed.message || '未知错误'
        setError(String(serverMsg))
      }

      // 在 error UI 同时展示调试信息（状态码与响应片段）
      setDebugInfo((prev) => ({
        ...(prev || {}),
        errorParsed: parsed,
        status,
        respTextShort,
      }))
      setShowDebug(true)
    } finally {
      setLoading(false)
    }
  }

  const copyDebugToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(debugInfo, null, 2))
      alert('调试信息已复制到剪贴板')
    } catch (err) {
      alert('复制失败: ' + err.message)
    }
  }

  return (
    <div className="fixed inset-0 flex items-center justify-center bg-black/70 z-50 backdrop-blur-sm">
      <form
        onSubmit={handleSubmit}
        className="bg-gradient-to-br from-gray-900 to-gray-800 p-8 rounded-2xl w-96 shadow-2xl border border-gray-700 flex flex-col gap-4"
      >
        <div className="text-center mb-2">
          <h2 className="text-2xl font-bold text-white mb-1">
            {isLogin ? '欢迎回来' : '创建账户'}
          </h2>
          <p className="text-gray-400 text-sm">
            {isLogin ? '登录以继续使用服务' : '注册新账户开始使用'}
          </p>
        </div>

        {!isLogin && (
          <div className="flex flex-col gap-1">
            <label className="text-gray-300 text-sm font-medium">用户名</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="请输入用户名"
              className="p-3 rounded-lg bg-gray-800/50 text-white border border-gray-600 focus:outline-none focus:border-blue-500 transition-colors"
            />
          </div>
        )}

        <div className="flex flex-col gap-1">
          <label className="text-gray-300 text-sm font-medium">邮箱</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="your@email.com"
            required
            className="p-3 rounded-lg bg-gray-800/50 text-white border border-gray-600 focus:outline-none focus:border-blue-500 transition-colors"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-gray-300 text-sm font-medium">密码</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            required
            className="p-3 rounded-lg bg-gray-800/50 text-white border border-gray-600 focus:outline-none focus:border-blue-500 transition-colors"
          />
        </div>

        {error && (
          <div className="bg-red-500/10 border border-red-500/50 text-red-400 text-sm p-3 rounded-lg">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 disabled:from-gray-600 disabled:to-gray-700 text-white p-3 rounded-lg font-semibold transition-all duration-200 shadow-lg hover:shadow-blue-500/50 disabled:cursor-not-allowed"
        >
          {loading ? (
            <span className="flex items-center justify-center gap-2">
              <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              处理中...
            </span>
          ) : (
            isLogin ? '登录' : '注册'
          )}
        </button>

        <div className="text-center pt-2 border-t border-gray-700">
          <p className="text-gray-400 text-sm">
            {isLogin ? '还没有账号？' : '已有账号？'}
            <button
              type="button"
              onClick={() => {
                setIsLogin(!isLogin)
                setError('')
                setDebugInfo(null)
                setShowDebug(false)
              }}
              className="text-blue-400 hover:text-blue-300 font-medium ml-2 transition-colors"
            >
              {isLogin ? '立即注册' : '立即登录'}
            </button>
          </p>
        </div>

        {/* 调试面板（默认隐藏，出错时会显示） */}
        {showDebug && debugInfo && (
          <div className="mt-2 p-3 bg-gray-900/60 border border-gray-700 rounded-md text-xs text-gray-300">
            <div className="flex justify-between items-center mb-2">
              <div className="font-medium text-sm text-white">调试信息</div>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => { setShowDebug(false) }}
                  className="px-2 py-1 text-xs bg-gray-800/50 rounded"
                >
                  收起
                </button>
                <button
                  type="button"
                  onClick={copyDebugToClipboard}
                  className="px-2 py-1 text-xs bg-blue-600 rounded"
                >
                  复制
                </button>
              </div>
            </div>

            <div className="mb-1"><strong>时间:</strong> {debugInfo.ts}</div>
            <div className="mb-1"><strong>Label:</strong> {debugInfo.label}</div>
            <div className="mb-1"><strong>URL:</strong> {debugInfo.url}</div>
            <div className="mb-1"><strong>UserAgent:</strong> <span className="break-all">{debugInfo.userAgent}</span></div>
            <div className="mb-1"><strong>localStorage:</strong>
              <pre className="whitespace-pre-wrap text-xs bg-transparent mt-1">{JSON.stringify(debugInfo.localStorage, null, 2)}</pre>
            </div>
            {debugInfo.errorParsed && (
              <div className="mb-1">
                <strong>错误解析:</strong>
                <pre className="whitespace-pre-wrap text-xs bg-transparent mt-1">{JSON.stringify(debugInfo.errorParsed, null, 2)}</pre>
              </div>
            )}
            {debugInfo.status && (
              <div className="mb-1"><strong>HTTP 状态:</strong> {debugInfo.status}</div>
            )}
            {debugInfo.respTextShort && (
              <div className="mb-1">
                <strong>响应片段:</strong>
                <pre className="whitespace-pre-wrap text-xs bg-transparent mt-1">{debugInfo.respTextShort}</pre>
              </div>
            )}
          </div>
        )}
      </form>
    </div>
  )
}
