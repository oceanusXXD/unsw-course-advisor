// src/components/Auth/Auth.tsx
import React from 'react';
import { loginUser, logoutUser, registerUser, getCurrentUser } from '../../services/api';

async function handleLogin(email: string, password: string) {
  try {
    const { access, refresh, user } = await loginUser(email, password);
    if (access) localStorage.setItem('access', access);
    if (refresh) localStorage.setItem('refresh', refresh);
    // 更新 UI / 上层 context
  } catch (err) {
    console.error('登录失败', err);
  }
}
