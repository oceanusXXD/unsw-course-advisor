// src/main.jsx
import React, { useEffect } from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Toaster } from 'sonner';
import App from './app/App';
import AuthCallback from './pages/AuthCallback';
import { useAuthStore } from './store/auth';
import { useTabsStore } from './store/tabs';
import './styles/globals.css';
import axios from 'axios';
axios.interceptors.response.use(
  (response) => response,
  (error) => {
    if (
      error.config &&
      (error.config.url.endsWith('favicon.ico') || error.config.url.endsWith('/static/favicon.ico'))
    ) {
      return Promise.resolve({ data: null }); // 忽略 favicon 错误
    }
    return Promise.reject(error);
  },
);

function AppInit({ children }) {
  useEffect(() => {
    // 原有初始化逻辑
    const init = async () => {
      useAuthStore.getState().hydrateFromStorage();
      const messages = useTabsStore.getState().init();
      if (messages) {
        const { useChatStore } = await import('./store/chat/index.js');
        useChatStore.setState({ tabMessages: messages });
      }
    };
    init();

    // -------------------------------
    // 背景懒加载逻辑（最小改动）
    // -------------------------------
    const bgUrl = getComputedStyle(document.documentElement)
      .getPropertyValue('--bg-image')
      .trim()
      .slice(4, -1); // 去掉 url('...')

    const bg = new Image();
    bg.src = bgUrl; // 同 CSS 文件夹下
    bg.onload = () => {
      document.body.style.transition = 'background 0.5s ease-in-out';
      document.body.style.backgroundImage = `url('${bg.src}')`;
    };
  }, []);

  return children;
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <AppInit>
        <Routes>
          <Route path="/" element={<App />} />
          <Route path="/auth/:provider/callback" element={<AuthCallback />} />
        </Routes>
        <Toaster
          position="top-center"
          toastOptions={{
            style: {
              background: 'var(--glass-bg)',
              color: 'var(--fg)',
              border: '1px solid var(--glass-border)',
              borderRadius: '12px',
              backdropFilter: 'blur(20px)',
              boxShadow: '0 8px 32px rgba(0, 0, 0, 0.1)',
            },
          }}
        />
      </AppInit>
    </BrowserRouter>
  </React.StrictMode>,
);
