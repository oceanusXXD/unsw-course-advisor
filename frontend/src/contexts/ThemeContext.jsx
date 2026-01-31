import React, { useEffect } from 'react';
import { useUIStore } from '../store/ui.js';

export function ThemeProvider({ children }) {
  const theme = useUIStore((s) => s.theme);
  const setTheme = useUIStore((s) => s.setTheme);

  useEffect(() => {
    // 初始化系统主题监听（仅当 theme === 'system'）
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const listener = () => {
      if (theme === 'system') {
        applyTheme(mq.matches ? 'dark' : 'light');
      }
    };
    mq.addEventListener?.('change', listener);
    return () => mq.removeEventListener?.('change', listener);
  }, [theme]);

  useEffect(() => {
    // 首次刷新应用当前主题
    setTheme(theme);
  }, []);

  // [NEW] 应用主题时添加过渡效果
  const applyTheme = (targetTheme) => {
    const root = document.documentElement;

    // 添加过渡类
    root.classList.add('theme-transition');

    // 设置主题
    root.setAttribute('data-theme', targetTheme);

    // 300ms 后移除过渡类
    setTimeout(() => {
      root.classList.remove('theme-transition');
    }, 300);
  };

  return <>{children}</>;
}
