// src/apiClient.js
const API_BASE = 'http://localhost:8000/api/';

async function fetchWithTimeout(url, options = {}, timeout = 20000) {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeout);
  try {
    const res = await fetch(url, { ...options, signal: controller.signal });
    clearTimeout(id);
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`HTTP ${res.status}: ${text}`);
    }
    return await res.json();
  } catch (err) {
    clearTimeout(id);
    throw err;
  }
}

// 简单指数退避重试（用于不幂等的 POST 需慎用）
export async function apiGet(path, opts = {}) {
  const url = `${API_BASE}${path}`;
  const maxRetries = 2;
  let attempt = 0;
  let wait = 300;
  while (true) {
    try {
      return await fetchWithTimeout(url, { method: 'GET', headers: { 'Content-Type': 'application/json' }, ...opts }, 20000);
    } catch (err) {
      attempt += 1;
      if (attempt > maxRetries) throw err;
      await new Promise(r => setTimeout(r, wait));
      wait *= 2;
    }
  }
}

export async function apiPost(path, body, opts = {}) {
  const url = `${API_BASE}${path}`;
  return fetchWithTimeout(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
    body: JSON.stringify(body),
    ...opts,
  }, opts.timeout || 60000);
}
