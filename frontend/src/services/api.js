// src/services/api.js
const API_BASE = 'https://dancing-inquire-brother-aurora.trycloudflare.com/api/';
//const API_BASE = import.meta.env.VITE_API_BASE;
console.log('[API_BASE]', API_BASE);

//  集中管理 API endpoints
export const API_ENDPOINTS = {
  // Chat - 修正字段名
  CHAT_MULTIROUND: 'chatbot/chat_multiround/',
  TURN_TIMELINE: 'chatbot/turn/{turnId}/timeline/',
  CHATBOT_PROFILE: 'chatbot/chatbot_profile/',

  // Auth
  LOGIN: 'accounts/login/',
  REGISTER: 'accounts/register/',
  LOGOUT: 'accounts/logout/',
  ME: 'accounts/me/',
  CHANGE_PASSWORD: 'accounts/change-password/',
  DELETE_ACCOUNT: 'accounts/delete/',

  // OAuth
  GOOGLE_AUTH: 'accounts/google/',
  GITHUB_AUTH: 'accounts/github/',
  OUTLOOK_AUTH: 'accounts/outlook/',

  // License
  LICENSE_VALIDATE: 'accounts/license/validate/',
  LICENSE_FILE_KEY: 'accounts/license/file-key/',
  LICENSE_ACTIVATE: 'accounts/license/activate/',
  LICENSE_MY: 'accounts/license/my/',
  LICENSE_COURSE_MAP: 'accounts/license/course-map/', // 新增
  // Feedback
  FEEDBACK_SUBMIT: 'accounts/feedback/',
  FEEDBACK_LIST: 'accounts/feedback/list/',
  FEEDBACK_MY: 'accounts/feedback/my/',
  FEEDBACK_DETAIL: 'accounts/feedback/{feedbackId}/',
  FEEDBACK_REPLY: 'accounts/feedback/{feedbackId}/reply/',
  FEEDBACK_UPDATE_STATUS: 'accounts/feedback/{feedbackId}/status/',
};

/**
 * 统一请求处理器，支持 JSON 与 SSE/chunked 流
 */
export async function _makeRequest(endpoint, options = {}) {
  const {
    method = 'GET',
    body = null,
    useAuth = false,
    stream = false,
    signal = null,
    onToken,
    onSources,
    onStatus,
    onCitation,
    onError,
    onSessionInit,
    onPartialResponse,
    onToolInvocation,
    onToolResult,
    onFinalResponse,
    headers: customHeaders,
    token: directToken,
  } = options;

  const headers = {
    'Content-Type': 'application/json',
    ...(customHeaders ?? {}),
  };

  headers['Accept'] = stream ? 'text/event-stream' : 'application/json';

  // 认证
  let authToken = directToken;
  if (!authToken && useAuth) {
    const savedAuth =
      typeof window !== 'undefined' ? window.localStorage.getItem('authState') : null;
    if (savedAuth) {
      try {
        const authState = JSON.parse(savedAuth);
        authToken = authState?.accessToken;
      } catch (e) {
        console.error('Failed to parse auth state from localStorage', e);
      }
    }
  }
  if (authToken) {
    headers['Authorization'] = `Bearer ${authToken}`;
  }

  const fetchOptions = {
    method,
    headers,
    signal: signal ?? undefined,
  };

  if (body) {
    const requestBody = stream ? { ...body, stream: true } : body;
    fetchOptions.body = typeof requestBody === 'string' ? requestBody : JSON.stringify(requestBody);
  }

  try {
    console.log(`[API] Fetching ${endpoint}`, { headers: fetchOptions.headers });
    const res = await fetch(`${API_BASE}${endpoint}`, fetchOptions);

    if (!res.ok) {
      let errorData = null;
      try {
        errorData = await res.json();
      } catch {
        try {
          const text = await res.text();
          errorData = JSON.parse(text);
        } catch {
          // ignore
        }
      }
      const msg =
        errorData?.detail || errorData?.error || errorData?.message || `请求失败: ${res.status}`;
      const error = new Error(msg);
      error.status = res.status;
      error.responseData = errorData;
      throw error;
    }

    if (stream) {
      if (!res.body) throw new Error('Response body is missing for stream.');
      await parseSSEStream(res.body, {
        onToken,
        onSources,
        onStatus,
        onCitation,
        onError,
        onSessionInit,
        onPartialResponse,
        onToolInvocation,
        onToolResult,
        onFinalResponse,
      });
      return;
    }

    const contentType = res.headers.get('content-type') ?? '';
    if (contentType.includes('application/json')) {
      return await res.json();
    }
    return;
  } catch (err) {
    if (err?.name === 'AbortError') return;
    options.onError?.(err);
    throw err;
  }
}

// 解析 SSE 流（支持 API 文档中定义的所有事件类型）
async function parseSSEStream(body, callbacks) {
  const reader = body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  const onSessionInitOnce = callbacks.onSessionInit
    ? (() => {
        let called = false;
        return (data) => {
          if (called) return;
          called = true;
          callbacks.onSessionInit?.(data);
        };
      })()
    : undefined;

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    const messages = buffer.split('\n\n');
    buffer = messages.pop() || '';

    for (const message of messages) {
      if (!message.trim()) continue;

      const lines = message.split('\n');
      let eventType = null;
      const dataLines = [];

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        if (trimmed.startsWith(':')) continue; // keep-alive
        if (trimmed.startsWith('event:')) {
          eventType = trimmed.slice(6).trim();
        } else if (trimmed.startsWith('data:')) {
          dataLines.push(trimmed.slice(5));
        }
      }

      const eventData = dataLines.join('\n').trim();
      if (eventType && eventData) {
        handleSSEEvent(eventType, eventData, {
          ...callbacks,
          onSessionInit: onSessionInitOnce,
        });
      }
    }
  }
}

function handleSSEEvent(eventType, eventData, callbacks) {
  try {
    switch (eventType) {
      case 'session_init': {
        try {
          const data = JSON.parse(eventData);
          const tabId = data?.tab_id || data?.tabId;
          const turnId = data?.turn_id || data?.turnId;
          if (tabId || turnId) {
            callbacks.onSessionInit?.({
              tabId: tabId || data.tabId,
              turnId: turnId || data.turnId,
            });
          }
        } catch (e) {
          console.error('[SSE] Failed to parse session_init data:', eventData, e);
        }
        break;
      }
      case 'partial_response': {
        try {
          const data = JSON.parse(eventData);
          callbacks.onPartialResponse?.(data);
        } catch (e) {
          console.error('[SSE] Failed to parse partial_response data:', eventData, e);
        }
        break;
      }
      case 'tool_invocation': {
        try {
          const data = JSON.parse(eventData);
          callbacks.onToolInvocation?.(data);
        } catch (e) {
          console.error('[SSE] Failed to parse tool_invocation data:', eventData, e);
        }
        break;
      }
      case 'tool_result': {
        try {
          const data = JSON.parse(eventData);
          callbacks.onToolResult?.(data);
        } catch (e) {
          console.error('[SSE] Failed to parse tool_result data:', eventData, e);
        }
        break;
      }
      case 'final_response': {
        try {
          const data = JSON.parse(eventData);
          callbacks.onFinalResponse?.(data);
        } catch (e) {
          console.error('[SSE] Failed to parse final_response data:', eventData, e);
        }
        break;
      }
      case 'token': {
        try {
          const parsed = JSON.parse(eventData);
          if (typeof parsed === 'string') callbacks.onToken?.(parsed);
          else callbacks.onToken?.(String(parsed?.text ?? ''));
        } catch {
          callbacks.onToken?.(eventData);
        }
        break;
      }
      case 'source': {
        try {
          const sourceData = JSON.parse(eventData);
          callbacks.onSources?.([sourceData]);
        } catch (e) {
          console.error('[SSE] Failed to parse source data:', eventData, e);
        }
        break;
      }
      case 'status': {
        try {
          const statusData = JSON.parse(eventData);
          console.log(`[SSE Status] ${statusData.node}: ${statusData.message}`);
          const tabId = statusData?.tab_id || statusData?.tabId;
          if (tabId) callbacks.onSessionInit?.({ tabId });
          callbacks.onStatus?.({
            node: statusData.node || '',
            message: statusData.message || '',
            turn_id: statusData.turn_id,
            ...statusData,
          });
        } catch (e) {
          console.error('[SSE] Failed to parse status data:', eventData, e);
        }
        break;
      }
      case 'citation': {
        try {
          const citationData = JSON.parse(eventData);
          callbacks.onCitation?.(citationData);
        } catch (e) {
          console.error('[SSE] Failed to parse citation data:', eventData, e);
        }
        break;
      }
      case 'decision': {
        try {
          const decisionData = JSON.parse(eventData);
          console.log('[SSE Decision]', decisionData);
          callbacks.onStatus?.({
            node: 'decision',
            message: `Decision: ${decisionData.route || 'unknown'}`,
            ...decisionData,
          });
        } catch (e) {
          console.error('[SSE] Failed to parse decision data:', eventData, e);
        }
        break;
      }
      case 'final_state':
        console.log('[SSE] Final state received');
        break;
      case 'end_of_stream':
        console.log('[SSE] Stream finished (end_of_stream)');
        break;
      case 'end':
        console.log('[SSE] Stream finished (end)');
        break;
      case 'error': {
        try {
          const errorData = JSON.parse(eventData);
          console.error('[SSE Error]', errorData);
          callbacks.onError?.(new Error(errorData.message || 'Unknown error'));
        } catch (e) {
          console.error('[SSE] Failed to parse error data:', eventData, e);
        }
        break;
      }
      default:
        console.warn(`[SSE] Unknown event type: ${eventType}`);
    }
  } catch (error) {
    console.error(`[SSE] Error handling event ${eventType}:`, error);
  }
}

/* ========== 导出 API ========== */

// 流式聊天 - 修正请求体字段名
export async function streamChat(params) {
  const {
    query,
    onDecision,
    frontendState,
    frontend_state, // 支持 snake_case
    history = [],
    userId = 'anonymous',
    user_id, // 支持 snake_case
    tabId,
    tab_id, // 支持 snake_case
    tools,
    memory_context,
    knowledge_context,
    temperature,
    signal = null,
    onToken,
    onSources,
    onStatus,
    onCitation,
    onSessionInit,
    onPartialResponse,
    onToolInvocation,
    onToolResult,
    onFinalResponse,
    onError,
    headers,
    token,
  } = params;

  // 构建请求体 - 使用 API 文档中的字段名
  const body = {
    query: query, // API 文档使用
    user_id: user_id || userId || 'anonymous',
  };

  // 优先使用 frontend_state
  if (frontend_state !== undefined || frontendState !== undefined) {
    body.frontend_state = frontend_state || frontendState;
  } else if (history && history.length > 0) {
    body.history = history;
  }

  // tab_id 是可选的
  const finalTabId = tab_id || tabId;
  if (finalTabId) {
    body.tabId = finalTabId; // 使用 camelCase，后端会处理
  }

  // 可选字段
  if (tools) body.tools = tools;
  if (memory_context) body.memory_context = memory_context;
  if (knowledge_context) body.knowledge_context = knowledge_context;
  if (temperature !== undefined) body.temperature = temperature;

  return _makeRequest(API_ENDPOINTS.CHAT_MULTIROUND, {
    method: 'POST',
    useAuth: true,
    stream: true,
    signal,
    body,
    onDecision,
    onToken,
    onSources,
    onStatus,
    onCitation,
    onSessionInit,
    onPartialResponse,
    onToolInvocation,
    onToolResult,
    onFinalResponse,
    onError,
    headers,
    token,
  });
}

// 获取 Turn Timeline
export async function getTurnTimeline(params) {
  const { turnId, turn_id, signal = null, headers, token, useAuth = true } = params;

  const finalTurnId = turn_id || turnId;
  if (!finalTurnId) {
    throw new Error('turnId or turn_id is required');
  }

  const endpoint = API_ENDPOINTS.TURN_TIMELINE.replace('{turnId}', encodeURIComponent(finalTurnId));

  return _makeRequest(endpoint, {
    method: 'GET',
    useAuth,
    signal,
    headers,
    token,
  });
}
// ==========================================================
//                    [NEW] Feedback API
// ==========================================================

/**
 * 提交用户反馈
 * @param {Object} params - 反馈参数
 * @param {string} params.type - 反馈类型 (bug | feature | suggestion | other)
 * @param {string} params.content - 反馈内容
 * @param {number} [params.rating] - 评分 (1-5)
 * @param {string} [params.contactEmail] - 联系邮箱
 * @returns {Promise<Object>} 反馈提交结果
 *
 * @example
 * const result = await submitFeedback({
 *   type: 'bug',
 *   content: '发现了一个问题...',
 *   rating: 4,
 *   contactEmail: 'user@example.com'
 * });
 */
export async function submitFeedback({ type, content, rating, contactEmail }) {
  console.log('[API] Submitting feedback:', { type, content, rating, contactEmail });

  return _makeRequest(API_ENDPOINTS.FEEDBACK_SUBMIT, {
    method: 'POST',
    body: {
      feedback_type: type,
      content,
      rating: rating || null,
      contact_email: contactEmail || null,
    },
    useAuth: false, // 允许匿名提交
  });
}

/**
 * 获取当前用户的反馈列表
 * @returns {Promise<Object>} 包含用户反馈列表的对象
 *
 * @example
 * const { feedbacks } = await getMyFeedbacks();
 */
export async function getMyFeedbacks() {
  console.log('[API] Fetching my feedbacks');

  return _makeRequest(API_ENDPOINTS.FEEDBACK_MY, {
    method: 'GET',
    useAuth: true,
  });
}

/**
 * 获取反馈列表（管理员）
 * @param {Object} params - 查询参数
 * @param {number} [params.page] - 页码
 * @param {string} [params.status] - 状态过滤 (pending | reviewing | resolved | closed)
 * @param {string} [params.type] - 类型过滤 (bug | feature | suggestion | other)
 * @param {number} [params.pageSize] - 每页数量
 * @returns {Promise<Object>} 反馈列表和分页信息
 *
 * @example
 * const result = await getFeedbackList({
 *   page: 1,
 *   status: 'pending',
 *   pageSize: 20
 * });
 */
export async function getFeedbackList({ page = 1, status, type, pageSize = 20 } = {}) {
  console.log('[API] Fetching feedback list:', { page, status, type, pageSize });

  const params = new URLSearchParams();
  if (page) params.append('page', page);
  if (status) params.append('status', status);
  if (type) params.append('type', type);
  if (pageSize) params.append('page_size', pageSize);

  const endpoint = `${API_ENDPOINTS.FEEDBACK_LIST}?${params.toString()}`;

  return _makeRequest(endpoint, {
    method: 'GET',
    useAuth: true,
  });
}

/**
 * 获取反馈详情
 * @param {number} feedbackId - 反馈 ID
 * @returns {Promise<Object>} 反馈详情
 *
 * @example
 * const { feedback } = await getFeedbackDetail(123);
 */
export async function getFeedbackDetail(feedbackId) {
  console.log('[API] Fetching feedback detail:', feedbackId);

  const endpoint = API_ENDPOINTS.FEEDBACK_DETAIL.replace('{feedbackId}', feedbackId);

  return _makeRequest(endpoint, {
    method: 'GET',
    useAuth: true,
  });
}

/**
 * 管理员回复反馈
 * @param {number} feedbackId - 反馈 ID
 * @param {Object} params - 回复参数
 * @param {string} params.reply - 回复内容
 * @param {string} [params.status] - 更新状态 (pending | reviewing | resolved | closed)
 * @returns {Promise<Object>} 更新后的反馈信息
 *
 * @example
 * const result = await replyToFeedback(123, {
 *   reply: '感谢您的反馈，我们会尽快处理。',
 *   status: 'reviewing'
 * });
 */
export async function replyToFeedback(feedbackId, { reply, status }) {
  console.log('[API] Replying to feedback:', { feedbackId, reply, status });

  const endpoint = API_ENDPOINTS.FEEDBACK_REPLY.replace('{feedbackId}', feedbackId);

  return _makeRequest(endpoint, {
    method: 'POST',
    body: {
      reply,
      status: status || undefined,
    },
    useAuth: true,
  });
}

/**
 * 更新反馈状态（管理员）
 * @param {number} feedbackId - 反馈 ID
 * @param {string} status - 新状态 (pending | reviewing | resolved | closed)
 * @returns {Promise<Object>} 更新结果
 *
 * @example
 * const result = await updateFeedbackStatus(123, 'resolved');
 */
export async function updateFeedbackStatus(feedbackId, status) {
  console.log('[API] Updating feedback status:', { feedbackId, status });

  const endpoint = API_ENDPOINTS.FEEDBACK_UPDATE_STATUS.replace('{feedbackId}', feedbackId);

  return _makeRequest(endpoint, {
    method: 'PATCH',
    body: { status },
    useAuth: true,
  });
}

/**
 * 批量获取反馈统计信息（管理员）
 * @returns {Promise<Object>} 反馈统计数据
 *
 * @example
 * const stats = await getFeedbackStats();
 * // { total: 100, pending: 20, resolved: 70, ... }
 */
export async function getFeedbackStats() {
  console.log('[API] Fetching feedback statistics');

  // 注意：这个接口需要后端实现，这里先预留
  return _makeRequest('accounts/feedback/stats/', {
    method: 'GET',
    useAuth: true,
  });
}
// 获取聊天机器人档案
export async function getChatbotProfile(params = {}) {
  const { signal = null, headers, token, useAuth = true } = params;
  return _makeRequest(API_ENDPOINTS.CHATBOT_PROFILE, {
    method: 'GET',
    useAuth,
    signal,
    headers,
    token,
  });
}

// 保存/更新聊天机器人档案
export async function saveChatbotProfile(params) {
  const {
    name,
    personality,
    domain,
    temperature,
    max_tokens,
    tools_enabled,
    signal = null,
    headers,
    token,
    useAuth = true,
  } = params;

  const body = {};
  if (name !== undefined) body.name = name;
  if (personality !== undefined) body.personality = personality;
  if (domain !== undefined) body.domain = domain;
  if (temperature !== undefined) body.temperature = temperature;
  if (max_tokens !== undefined) body.max_tokens = max_tokens;
  if (tools_enabled !== undefined) body.tools_enabled = tools_enabled;

  return _makeRequest(API_ENDPOINTS.CHATBOT_PROFILE, {
    method: 'POST',
    useAuth,
    signal,
    body,
    headers,
    token,
  });
}
/**
 * 获取学生档案信息
 */
export async function getStudentProfile(params) {
  const { tabId, userId, signal = null, headers, token, useAuth = true } = params;

  // 构建 query string
  const queryParams = new URLSearchParams();
  if (tabId) queryParams.append('tab_id', tabId);
  if (userId) queryParams.append('user_id', userId);

  const query = queryParams.toString();
  const url = query ? `${API_ENDPOINTS.CHATBOT_PROFILE}?${query}` : API_ENDPOINTS.CHATBOT_PROFILE;

  return _makeRequest(url, {
    method: 'GET',
    useAuth,
    signal,
    headers,
    token,
  });
}

/**
 * 保存学生档案信息
 */
export async function saveStudentProfile(params) {
  const { studentInfo, userId, tabId, signal = null, headers, token, useAuth = true } = params;

  return _makeRequest(API_ENDPOINTS.CHATBOT_PROFILE, {
    method: 'POST',
    useAuth,
    signal,
    body: {
      student_info: studentInfo,
      ...(tabId ? { tab_id: tabId } : {}),
      ...(userId ? { user_id: String(userId) } : {}),
    },
    headers,
    token,
  });
}

// Auth - 修正响应处理
export async function loginUser(email, password) {
  const data = await _makeRequest(API_ENDPOINTS.LOGIN, {
    method: 'POST',
    body: { email, password },
  });
  return {
    access: data?.access || data?.tokens?.access,
    refresh: data?.refresh || data?.tokens?.refresh,
    user: data?.user,
    license_active: data?.license_active,
  };
}

export async function registerUser(email, password, password2, username = '') {
  const bodyData = { email, password };
  if (password2) bodyData.password2 = password2;
  if (username) bodyData.username = username;

  const data = await _makeRequest(API_ENDPOINTS.REGISTER, {
    method: 'POST',
    body: bodyData,
  });

  return {
    access: data?.access || data?.tokens?.access,
    refresh: data?.refresh || data?.tokens?.refresh,
    user: data?.user,
    license_status: data?.license_status,
  };
}

export async function loginWithGoogle(code, access_token) {
  const body = {};
  if (code) body.code = code;
  if (access_token) body.access_token = access_token;

  const data = await _makeRequest(API_ENDPOINTS.GOOGLE_AUTH, {
    method: 'POST',
    body,
    useAuth: false,
  });

  return {
    access: data?.access || data?.tokens?.access || data?.access_token,
    refresh: data?.refresh || data?.tokens?.refresh || data?.refresh_token,
    user: data?.user || data?.name || data?.email || null,
    license_status: data?.license_status,
  };
}

export async function loginWithGitHub(code, access_token) {
  const body = {};
  if (code) body.code = code;
  if (access_token) body.access_token = access_token;

  const data = await _makeRequest(API_ENDPOINTS.GITHUB_AUTH, {
    method: 'POST',
    body,
    useAuth: false,
  });
  console.log(data);

  // [OK] 统一返回格式（和 loginUser 一致）
  return {
    access: data?.access || data?.tokens?.access || data?.access_token,
    refresh: data?.refresh || data?.tokens?.refresh || data?.refresh_token,
    user: data?.user || data?.username || data?.email || null, //  关键：提取 user
    license_status: data?.license_status,
  };
}

export async function loginWithOutlook(code, access_token) {
  const body = {};
  if (code) body.code = code;
  if (access_token) body.access_token = access_token;

  const data = await _makeRequest(API_ENDPOINTS.OUTLOOK_AUTH, {
    method: 'POST',
    body,
    useAuth: false,
  });

  return {
    access: data?.access || data?.tokens?.access || data?.access_token,
    refresh: data?.refresh || data?.tokens?.refresh || data?.refresh_token,
    user: data?.user || null,
    license_status: data?.license_status,
  };
}

export async function getCurrentUser(token) {
  return _makeRequest(API_ENDPOINTS.ME, { useAuth: true, token });
}

export async function logoutUser(refreshToken, token) {
  return _makeRequest(API_ENDPOINTS.LOGOUT, {
    method: 'POST',
    body: refreshToken ? { refresh: refreshToken } : {},
    useAuth: true,
    token,
  });
}

export async function changePassword(oldPassword, newPassword, newPassword2, token) {
  const body = {
    old_password: oldPassword,
    password: newPassword,
  };
  if (newPassword2) body.password2 = newPassword2;

  return _makeRequest(API_ENDPOINTS.CHANGE_PASSWORD, {
    method: 'POST',
    body,
    useAuth: true,
    token,
  });
}

export async function deleteAccount(token) {
  return _makeRequest(API_ENDPOINTS.DELETE_ACCOUNT, {
    method: 'DELETE',
    useAuth: true,
    token,
  });
}

// License
export async function validateLicense(licenseKey, token) {
  return _makeRequest(API_ENDPOINTS.LICENSE_VALIDATE, {
    method: 'POST',
    body: { license_key: licenseKey },
    useAuth: false, // API 文档显示为 AllowAny
    token,
  });
}

export async function getFileDecryptKey(fileId, licenseKey, token) {
  return _makeRequest(API_ENDPOINTS.LICENSE_FILE_KEY, {
    method: 'POST',
    body: {
      file_id: fileId, // API 文档使用 file_id
      license_key: licenseKey,
    },
    useAuth: false, // API 文档显示为 AllowAny
    token,
  });
}

function getOrCreateDeviceId() {
  const KEY = 'app_device_id';
  let deviceId = localStorage.getItem(KEY);
  if (!deviceId) {
    deviceId = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
      const r = (Math.random() * 16) | 0;
      const v = c === 'x' ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
    localStorage.setItem(KEY, deviceId);
  }
  return deviceId;
}

export async function activateLicense(expiresInDays = 365, token) {
  const deviceId = getOrCreateDeviceId();
  return _makeRequest(API_ENDPOINTS.LICENSE_ACTIVATE, {
    method: 'POST',
    body: {
      device_id: deviceId,
      expires_in_days: expiresInDays,
    },
    useAuth: true,
    token,
  });
}

export async function getMyLicense(token) {
  return _makeRequest(API_ENDPOINTS.LICENSE_MY, {
    useAuth: true,
    token,
  });
}

// 新增：获取课程映射表
export async function getCourseMap() {
  return _makeRequest(API_ENDPOINTS.LICENSE_COURSE_MAP, {
    method: 'GET',
    useAuth: false, // API 文档显示为 AllowAny
  });
}

/* ========== Crypto / 解密工具 ========== */
export function base64ToUint8Array(base64) {
  const cleaned = base64.replace(/-/g, '+').replace(/_/g, '/');
  const pad = cleaned.length % 4 === 0 ? '' : '='.repeat(4 - (cleaned.length % 4));
  const b64 = cleaned + pad;
  const binary =
    typeof window !== 'undefined'
      ? window.atob(b64)
      : Buffer.from(b64, 'base64').toString('binary');
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

export function uint8ArrayToString(bytes) {
  return new TextDecoder().decode(bytes);
}

function concat(a, b) {
  const out = new Uint8Array(a.length + b.length);
  out.set(a, 0);
  out.set(b, a.length);
  return out;
}

async function aesGcmDecrypt(params) {
  const { keyBytes, iv, data } = params;
  const algo = { name: 'AES-GCM', iv, tagLength: 128 };
  const cryptoKey = await crypto.subtle.importKey('raw', keyBytes, { name: 'AES-GCM' }, false, [
    'decrypt',
  ]);
  const decrypted = await crypto.subtle.decrypt(algo, cryptoKey, data);
  return new Uint8Array(decrypted);
}

export async function fetchWrappedFileKey(fileId, licenseKey) {
  const data = await _makeRequest(API_ENDPOINTS.LICENSE_FILE_KEY, {
    method: 'POST',
    body: {
      file_id: fileId,
      license_key: licenseKey,
    },
    useAuth: false,
  });
  const wrappedKey =
    data?.wrapped_file_key ??
    data?.wrapped_file_key_base64 ??
    data?.wrapped_file_key_b64 ??
    data?.wrapped_key ??
    data;
  if (!wrappedKey) throw new Error('服务器返回的数据中缺少 wrapped_file_key');
  return wrappedKey;
}

export async function unwrapFileKey(wrappedFileKey, userKeyB64) {
  const userKeyBytes = base64ToUint8Array(userKeyB64);
  const nonce = base64ToUint8Array(wrappedFileKey.nonce);
  const tag = base64ToUint8Array(wrappedFileKey.tag);
  const ciphertext = base64ToUint8Array(wrappedFileKey.ciphertext);
  const fileKeyBytes = await aesGcmDecrypt({
    keyBytes: userKeyBytes,
    iv: nonce,
    data: concat(ciphertext, tag),
  });
  return fileKeyBytes;
}

export async function decryptFileContent(encryptedFileContent, fileKeyBytes) {
  const nonce = base64ToUint8Array(encryptedFileContent.nonce);
  const tag = base64ToUint8Array(encryptedFileContent.tag);
  const ciphertext = base64ToUint8Array(encryptedFileContent.ciphertext);
  const decryptedBytes = await aesGcmDecrypt({
    keyBytes: fileKeyBytes,
    iv: nonce,
    data: concat(ciphertext, tag),
  });
  const decryptedText = uint8ArrayToString(decryptedBytes);
  return JSON.parse(decryptedText);
}

export async function decryptLicensedFile(fileId, licenseKey, userKeyB64) {
  const wrappedFileKey = await fetchWrappedFileKey(fileId, licenseKey);
  const fileKeyBytes = await unwrapFileKey(wrappedFileKey, userKeyB64);
  // 注意：这里可能需要调整，因为我们已经有了 fileKeyBytes
  // 实际的加密文件内容需要另外获取
  // 这个函数可能需要重新设计
  throw new Error('decryptLicensedFile needs redesign - file content should be fetched separately');
}

/* ========== 默认导出 ========== */
export default {
  _makeRequest,
  API_ENDPOINTS,
  // chat
  streamChat,
  getTurnTimeline,
  getChatbotProfile,
  saveChatbotProfile,
  saveStudentProfile,
  // auth
  loginUser,
  registerUser,
  loginWithGoogle,
  loginWithGitHub,
  loginWithOutlook,
  getCurrentUser,
  logoutUser,
  changePassword,
  deleteAccount,
  // license
  activateLicense,
  validateLicense,
  getMyLicense,
  getFileDecryptKey,
  getCourseMap,
  // crypto
  fetchWrappedFileKey,
  unwrapFileKey,
  decryptFileContent,
  decryptLicensedFile,
  base64ToUint8Array,
  uint8ArrayToString,
  //feedback
  submitFeedback,
  getMyFeedbacks,
  getFeedbackList,
  getFeedbackDetail,
  replyToFeedback,
  updateFeedbackStatus,
  getFeedbackStats,
};
