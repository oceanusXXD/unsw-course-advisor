// src/services/api.js

const API_BASE = 'http://localhost:8000/api/';

// ==================== 内部通用请求函数 (不直接导出) ====================
/**
 * 这是一个底层的、统一的请求处理器，能处理常规JSON和SSE流。
 * @param {string} endpoint - API端点, e.g., 'accounts/login/'.
 * @param {object} options - 配置对象.
 */
async function _makeRequest(endpoint, options = {}) {
  const {
    method = 'GET',
    body = null,
    useAuth = false,
    stream = false,
    signal,
    onToken,
    onSources,
    onError,
  } = options;

  const headers = { 'Content-Type': 'application/json' };
  if (useAuth) {
    const token = localStorage.getItem('access');
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
  }

  const fetchOptions = { method, headers, signal };
  if (body) {
    const requestBody = stream ? { ...body, stream: true } : body;
    fetchOptions.body = JSON.stringify(requestBody);
  }

  try {
    const res = await fetch(`${API_BASE}${endpoint}`, fetchOptions);

    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}));
      throw new Error(
        errorData.detail || errorData.error || errorData.message || `请求失败: ${res.status}`
      );
    }

    if (stream) {
      if (!res.body) throw new Error('Response body is missing for stream.');
      const reader = res.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const messages = buffer.split('\n\n');
        buffer = messages.pop() || '';
        for (const msg of messages) {
          const lines = msg.split('\n');
          for (const line of lines) {
            if (line.trim().startsWith('data:')) {
              const payload = line.trim().slice(5).trim();
              if (payload === '[DONE]') continue;
              try {
                const data = JSON.parse(payload);
                if (data.type === 'token') onToken?.(data.data);
                else if (data.type === 'sources') onSources?.(data.data);
                else if (data.type === 'history') onToken?.(JSON.stringify({ type: 'history' }));
              } catch {
                onToken?.(payload);
              }
            }
          }
        }
      }
      return;
    }

    const contentType = res.headers.get("content-type");
    if (contentType && contentType.includes("application/json")) {
      return await res.json();
    }
    return;

  } catch (err) {
    if (err.name !== 'AbortError') {
      onError?.(err);
      throw err;
    }
  }
}

// ==================== SSE 流式聊天 ====================
export async function streamChat({
  endpoint,
  query,
  history = [],
  userId,
  signal,
  onToken,
  onSources,
  onError,
}) {
  return _makeRequest(endpoint, {
    method: 'POST',
    useAuth: true,
    stream: true,
    signal,
    body: { query, history, user_id: userId },
    onToken,
    onSources,
    onError,
  });
}

// ==================== 用户认证 ====================
export async function loginUser(email, password) {
  const data = await _makeRequest('accounts/login/', {
    method: 'POST',
    body: { email, password },
  });
  return {
    access: data.tokens?.access_token || data.access,
    refresh: data.tokens?.refresh_token || data.refresh,
    user: data.user,
    license_active: data.license_active,
  };
}

export async function registerUser(email, password, username = '') {
  const data = await _makeRequest('accounts/register/', {
    method: 'POST',
    body: { email, password, username },
  });
  return {
    access: data.tokens?.access_token || data.access,
    refresh: data.tokens?.refresh_token || data.refresh,
    user: data.user,
    license_status: data.license_status,
  };
}

export async function getCurrentUser() {
  return _makeRequest('accounts/me/', { useAuth: true });
}

export async function logoutUser(refreshToken) {
  return _makeRequest('accounts/logout/', {
    method: 'POST',
    body: { refresh: refreshToken },
    useAuth: true,
  });
}

export async function changePassword(oldPassword, newPassword) {
  return _makeRequest('accounts/change-password/', {
    method: 'POST',
    body: { old_password: oldPassword, new_password: newPassword },
    useAuth: true,
  });
}

// ==================== 许可证管理 ====================
export async function activateLicense(deviceId, expiresInDays = 365) {
  return _makeRequest('accounts/license/activate/', {
    method: 'POST',
    body: { device_id: deviceId, expires_in_days: expiresInDays },
    useAuth: true,
  });
}

export async function validateLicense(licenseKey) {
  try {
    return await _makeRequest('accounts/license/validate/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ license_key: licenseKey }),
      useAuth: true,
    });
  } catch (err) {
    // 如果是 HTTP 错误，可以尝试解析 JSON
    if (err.response) {
      const data = await err.response.json();
      throw new Error(data.error || '许可证验证失败');
    }
    throw err;
  }
}


export async function getMyLicense() {
  return _makeRequest('accounts/license/my/', { useAuth: true });
}

export async function getFileDecryptKey(fileId, licenseKey) {
  return _makeRequest('accounts/license/file-key/', {
    method: 'POST',
    body: {
      file_id: fileId,
      license_key: licenseKey  // 添加license_key参数
    },
    useAuth: true,
  });
}

// ==================== 客户端解密辅助函数 (保持不变) ====================

// ==================== 客户端解密辅助函数 (已优化) ====================

// 工具函数 (保持不变)
export function base64ToUint8Array(base64) {
    const cleaned = base64.replace(/-/g, '+').replace(/_/g, '/');
    const pad = cleaned.length % 4 === 0 ? '' : '='.repeat(4 - (cleaned.length % 4));
    const b64 = cleaned + pad;
    const binary = atob(b64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    return bytes;
}

export function uint8ArrayToString(bytes) {
    return new TextDecoder().decode(bytes);
}

function toHexPreview(bytes, n = 16) {
    if (!bytes) return 'null';
    const len = Math.min(n, bytes.length);
    let out = [];
    for (let i = 0; i < len; i++) out.push(bytes[i].toString(16).padStart(2, '0'));
    return out.join(' ');
}

function concat(a, b) {
    const out = new Uint8Array(a.length + b.length);
    out.set(a, 0);
    out.set(b, a.length);
    return out;
}

/**
 * 核心 AES-GCM 解密函数
 * @param {object} params
 * @param {Uint8Array} params.keyBytes - 解密密钥 (32字节)
 * @param {Uint8Array} params.iv - Nonce (12字节)
 * @param {Uint8Array} params.data - 要解密的数据 (ciphertext + tag)
 * @returns {Promise<Uint8Array>} 解密后的明文字节数组
 */
async function aesGcmDecrypt({ keyBytes, iv, data }) {
    const algo = { name: 'AES-GCM', iv, tagLength: 128 };
    const cryptoKey = await crypto.subtle.importKey('raw', keyBytes, { name: 'AES-GCM' }, false, ['decrypt']);
    const decrypted = await crypto.subtle.decrypt(algo, cryptoKey, data);
    return new Uint8Array(decrypted);
}


// ==================== 解密主流程 ====================

/**
 * 步骤 1: 从服务器获取被 user_key 包裹的 file_key
 * @param {object} encryptedFileContent - 从服务器下载的加密文件JSON对象
 * @param {string} licenseKey - 用户的许可证密钥
 * @param {string} authToken - 用于API认证的Token (例如 JWT Bearer Token)
 * @returns {Promise<object>} 服务器返回的 wrapped_file_key 对象
 */
// 使用已有的 _makeRequest 来请求“包裹的文件密钥”
async function fetchWrappedFileKey(encryptedFileContent, licenseKey) {
  try {
    console.log('[API] 正在请求文件解密密钥...');

    // _makeRequest 会自动根据 useAuth 添加 Authorization（从 localStorage.getItem('access')）
    const data = await _makeRequest('accounts/license/file-key/', {
      method: 'POST',
      body: {
        encrypted_file: encryptedFileContent,
        license_key: licenseKey,
      },
      useAuth: true,
    });

    // 兼容返回结构：可能直接返回 wrapped_file_key，也可能在 data.wrapped_file_key
    // 如果后端直接返回某些字段，这里也能兼容
    const wrappedKey = data?.wrapped_file_key ?? data?.wrapped_file_key_base64 ?? data?.wrapped_file_key_b64 ?? data?.wrapped_key ?? data;

    if (!wrappedKey) {
      console.error('[API] 未能从响应中解析出 wrapped_file_key：', data);
      throw new Error('服务器返回的数据中缺少 wrapped_file_key');
    }

    console.log('[API] 成功获取到包裹的密钥:', wrappedKey);
    return wrappedKey;
  } catch (err) {
    console.error('[API] 获取密钥失败:', err);
    throw err;
  }
}


/**
 * 步骤 2: 使用 user_key 解开包裹，得到明文 file_key
 * @param {object} wrappedFileKey - 从服务器获取的密钥包 {nonce, tag, ciphertext}
 * @param {string} userKeyB64 - Base64 编码的用户密钥
 * @returns {Promise<Uint8Array>} 明文 file_key (字节数组)
 */
async function unwrapFileKey(wrappedFileKey, userKeyB64) {
    console.log('[UNWRAP] 准备用 user_key 解包 file_key...');
    
    const userKeyBytes = base64ToUint8Array(userKeyB64);
    const nonce = base64ToUint8Array(wrappedFileKey.nonce);
    const tag = base64ToUint8Array(wrappedFileKey.tag);
    const ciphertext = base64ToUint8Array(wrappedFileKey.ciphertext);

    console.log('[UNWRAP] userKey (len/hex):', userKeyBytes.length, toHexPreview(userKeyBytes));
    console.log('[UNWRAP] nonce (len/hex):', nonce.length, toHexPreview(nonce));
    
    try {
        const fileKeyBytes = await aesGcmDecrypt({
            keyBytes: userKeyBytes,
            iv: nonce,
            data: concat(ciphertext, tag) // PyCryptodome 将 tag 分离，WebCrypto需要拼接
        });
        console.log('[UNWRAP] 成功解出 file_key! (len/hex):', fileKeyBytes.length, toHexPreview(fileKeyBytes));
        return fileKeyBytes;
    } catch (e) {
        console.error('[UNWRAP] 解包 file_key 失败:', e);
        throw new Error('解包文件密钥失败，请检查 user_key 是否正确。');
    }
}

/**
 * 步骤 3: 使用明文 file_key 解密文件内容
 * @param {object} encryptedFileContent - 原始加密文件JSON对象
 * @param {Uint8Array} fileKeyBytes - 明文 file_key
 * @returns {Promise<object>} 解密后的文件内容 (JSON 对象)
 */
async function decryptFileContent(encryptedFileContent, fileKeyBytes) {
    console.log('[DECRYPT] 准备用 file_key 解密文件正文...');

    const nonce = base64ToUint8Array(encryptedFileContent.nonce);
    const tag = base64ToUint8Array(encryptedFileContent.tag);
    const ciphertext = base64ToUint8Array(encryptedFileContent.ciphertext);

    console.log('[DECRYPT] fileKey (len/hex):', fileKeyBytes.length, toHexPreview(fileKeyBytes));
    console.log('[DECRYPT] nonce (len/hex):', nonce.length, toHexPreview(nonce));

    try {
        const decryptedBytes = await aesGcmDecrypt({
            keyBytes: fileKeyBytes,
            iv: nonce,
            data: concat(ciphertext, tag)
        });
        const decryptedText = uint8ArrayToString(decryptedBytes);
        console.log('[DECRYPT] 成功解密文件内容!');
        return JSON.parse(decryptedText);
    } catch (e) {
        console.error('[DECRYPT] 解密文件正文失败:', e);
        throw new Error('解密文件内容失败，文件可能已损坏或密钥不匹配。');
    }
}

/**
 * 最终调用的主函数：完成整个解密流程
 * @param {object} encryptedFileContent - 从服务器下载的加密文件JSON对象
 * @param {string} licenseKey - 用户的许可证密钥
 * @param {string} userKeyB64 - Base64编码的用户密钥 (通常存储在localStorage或内存中)
 * @param {string} authToken - 用于API认证的Token
 * @returns {Promise<object>} 最终解密后的数据
 */
export async function decryptLicensedFile(encryptedFileContent, licenseKey, userKeyB64, authToken) {
    try {
        // 步骤 1: 从服务器获取加密的 file_key
        const wrappedFileKey = await fetchWrappedFileKey(encryptedFileContent, licenseKey, authToken);

        // 步骤 2: 用 user_key 解开包裹，得到明文 file_key
        const fileKeyBytes = await unwrapFileKey(wrappedFileKey, userKeyB64);

        // 步骤 3: 用明文 file_key 解密文件内容
        const decryptedData = await decryptFileContent(encryptedFileContent, fileKeyBytes);
        
        console.log('🎉 解密成功! 最终数据:', decryptedData);
        return decryptedData;

    } catch (error) {
        console.error('整个解密流程失败:', error.message);
        // 你可以在这里向用户显示错误信息
        throw error; // 将错误继续抛出，以便调用者可以处理
    }
}



// ==================== 默认导出 ====================
export default {
  streamChat,
  loginUser,
  registerUser,
  getCurrentUser,
  logoutUser,
  changePassword,
  activateLicense,
  validateLicense,
  getMyLicense,
  getFileDecryptKey,
  decryptLicensedFile
};