// src/services/api.ts
/* eslint-disable @typescript-eslint/no-explicit-any */
const API_BASE = "http://localhost:8000/api/";
console.log(API_BASE);
export interface MakeRequestOptions {
  method?: string;
  body?: any;
  useAuth?: boolean;
  stream?: boolean;
  signal?: AbortSignal | null;
  onToken?: (data: any) => void;
  onSources?: (data: any) => void;
  onError?: (err: any) => void;
  headers?: Record<string, string>;
}

/**
 * 统一请求处理器，支持 JSON 与 SSE/chunked 流
 */
export async function _makeRequest(
  endpoint: string,
  options: MakeRequestOptions & { token?: string } = {},
): Promise<any> {
  const {
    method = "GET",
    body = null,
    useAuth = false,
    stream = false,
    signal = null,
    onToken,
    onSources,
    onError,
    headers: customHeaders,
    token: directToken, // 将传入的 token 解构出来
  } = options;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(customHeaders ?? {}),
  };
  //认证逻辑重构
  let authToken = directToken; // 1. 优先使用直接传入的 token

  // 2. 如果没有直接传入的 token，并且需要认证，才从 localStorage 查找
  if (!authToken && useAuth) {
    const savedAuth =
      typeof window !== "undefined"
        ? window.localStorage.getItem("authState")
        : null;
    if (savedAuth) {
      try {
        const authState = JSON.parse(savedAuth);
        authToken = authState?.accessToken;
      } catch (e) {
        console.error("Failed to parse auth state from localStorage", e);
      }
    }
  }

  // 3. 如果最终找到了 token，则设置请求头
  if (authToken) {
    headers["Authorization"] = `Bearer ${authToken}`;
  }

  const fetchOptions: RequestInit = {
    method,
    headers,
    signal: signal ?? undefined,
  };
  if (body) {
    const requestBody = stream ? { ...body, stream: true } : body;
    fetchOptions.body =
      typeof requestBody === "string"
        ? requestBody
        : JSON.stringify(requestBody);
  }

  try {
    console.log(`[API] Fetching ${endpoint}`, {
      headers: fetchOptions.headers,
    });
    const res = await fetch(`${API_BASE}${endpoint}`, fetchOptions);

    if (!res.ok) {
      let errorData: any = null;
      try {
        errorData = await res.json();
      } catch {
        // ignore
      }
      const msg =
        errorData?.detail ||
        errorData?.error ||
        errorData?.message ||
        `请求失败: ${res.status}`;
      const error = new Error(msg);
      (error as any).status = res.status;
      (error as any).responseData = errorData;
      throw error;
    }

    if (stream) {
      if (!res.body) throw new Error("Response body is missing for stream.");
      const reader = res.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const messages = buffer.split("\n\n");
        buffer = messages.pop() || "";
        for (const msg of messages) {
          const lines = msg.split("\n");
          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed) continue;
            if (trimmed.startsWith("data:")) {
              const payload = trimmed.slice(5).trim();
              if (payload === "[DONE]") continue;
              try {
                const data = JSON.parse(payload);

                // [!! 修正] 调整此处的逻辑
                if (data?.type === "token") {
                  onToken?.(data.data); // 假设 data.data 是字符串
                } else if (data?.type === "sources") {
                  onSources?.(data.data);
                } else if (data?.type === "history") {
                  // [!! 修正] (修复问题 1)
                  // 不将 "history" 元数据作为 Token 发送到 UI
                  console.log("[API Stream] History event received.");
                } else {
                  // [!! 修正] (修复问题 2: [object Object])
                  // 不将未知对象作为 Token 发送
                  console.warn(
                    "[API Stream] Received unknown data structure:",
                    data,
                  );
                }
              } catch {
                // 回退：如果 JSON 解析失败，则发送原始负载（字符串）
                onToken?.(payload);
              }
            } else {
              // [!! 修正] 同样处理非 "data:" 开头的行
              try {
                const data = JSON.parse(trimmed);
                if (data?.type === "token") {
                  onToken?.(data.data);
                } else if (data?.type === "sources") {
                  onSources?.(data.data);
                } else {
                  // [!! 修正] (修复问题 2: [object Object])
                  console.warn(
                    "[API Stream] Received unknown non-data structure:",
                    data,
                  );
                }
              } catch {
                // 回退：如果 JSON 解析失败，则发送原始文本（字符串）
                onToken?.(trimmed);
              }
            }
          }
        }
      }
      return;
    }

    const contentType = res.headers.get("content-type") ?? "";
    if (contentType.includes("application/json")) {
      return await res.json();
    }
    return;
  } catch (err: any) {
    if (err?.name === "AbortError") {
      return;
    }
    options.onError?.(err);
    throw err;
  }
}

/* ========== 导出 API ========== */

// 流式聊天
export async function streamChat(params: {
  endpoint: string;
  query: string;
  history?: any[];
  userId?: string;
  signal?: AbortSignal | null;
  onToken?: (t: any) => void;
  onSources?: (s: any) => void;
  onError?: (e: any) => void;
}) {
  const {
    endpoint,
    query,
    history = [],
    userId,
    signal = null,
    onToken,
    onSources,
    onError,
  } = params;
  return _makeRequest(endpoint, {
    method: "POST",
    useAuth: true,
    stream: true,
    signal,
    body: { query, history, user_id: userId },
    onToken,
    onSources,
    onError,
  });
}

// Auth
export async function loginUser(email: string, password: string) {
  const data = await _makeRequest("accounts/login/", {
    method: "POST",
    body: { email, password },
  });
  return {
    access: data?.tokens?.access_token || data?.access,
    refresh: data?.tokens?.refresh_token || data?.refresh,
    user: data?.user,
    license_active: data?.license_active,
  };
}

export async function registerUser(
  email: string,
  password: string,
  username = "",
) {
  const data = await _makeRequest("accounts/register/", {
    method: "POST",
    body: { email, password, username },
  });
  return {
    access: data?.tokens?.access_token || data?.access,
    refresh: data?.tokens?.refresh_token || data?.refresh,
    user: data?.user,
    license_status: data?.license_status,
  };
}

export async function getCurrentUser(token?: string) {
  return _makeRequest("accounts/me/", { useAuth: true, token: token });
}

export async function logoutUser(refreshToken?: string) {
  return _makeRequest("accounts/logout/", {
    method: "POST",
    body: refreshToken ? { refresh: refreshToken } : {},
    useAuth: true,
  });
}

export async function changePassword(oldPassword: string, newPassword: string) {
  return _makeRequest("accounts/change-password/", {
    method: "POST",
    body: { old_password: oldPassword, new_password: newPassword },
    useAuth: true,
  });
}

// License
/**
 * 辅助函数：获取或创建并存储一个唯一的设备 ID
 */
function getOrCreateDeviceId(): string {
  const KEY = "app_device_id";
  let deviceId = localStorage.getItem(KEY);

  if (!deviceId) {
    // 生成一个简单的唯一 ID (UUID v4)
    deviceId = "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(
      /[xy]/g,
      function (c) {
        var r = (Math.random() * 16) | 0,
          v = c == "x" ? r : (r & 0x3) | 0x8;
        return v.toString(16);
      },
    );
    localStorage.setItem(KEY, deviceId);
  }
  return deviceId;
}

/**
 * [API 1] 创建并激活一个新的许可证
 * (对应 "获取许可证" 步骤)
 */
export async function activateLicense(expiresInDays = 365) {
  const deviceId = getOrCreateDeviceId();

  return _makeRequest("accounts/license/activate/", {
    method: "POST",
    body: { device_id: deviceId, expires_in_days: expiresInDays },
    useAuth: true,
  });
}

/**
 * [API 2] 验证一个已有的许可证密钥
 * (对应 "输入许可证激活" 步骤)
 */
export async function validateLicense(licenseKey: string) {
  return _makeRequest("accounts/license/validate/", {
    method: "POST",
    body: { license_key: licenseKey },
    useAuth: true,
  });
}

/**
 * [API 3] 获取当前用户的许可证信息
 */
export async function getMyLicense() {
  return _makeRequest("accounts/license/my/", { useAuth: true });
}

export async function getFileDecryptKey(
  encryptedFile: any,
  licenseKey: string,
) {
  return _makeRequest("accounts/license/file-key/", {
    method: "POST",
    body: { encrypted_file: encryptedFile, license_key: licenseKey },
    useAuth: true,
  });
}

/* ========== Crypto / 解密工具 ========== */

export function base64ToUint8Array(base64: string): Uint8Array {
  const cleaned = base64.replace(/-/g, "+").replace(/_/g, "/");
  const pad =
    cleaned.length % 4 === 0 ? "" : "=".repeat(4 - (cleaned.length % 4));
  const b64 = cleaned + pad;
  const binary =
    typeof window !== "undefined"
      ? window.atob(b64)
      : Buffer.from(b64, "base64").toString("binary");
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

export function uint8ArrayToString(bytes: Uint8Array): string {
  return new TextDecoder().decode(bytes);
}

function concat(a: Uint8Array, b: Uint8Array) {
  const out = new Uint8Array(a.length + b.length);
  out.set(a, 0);
  out.set(b, a.length);
  return out;
}

async function aesGcmDecrypt(params: {
  keyBytes: Uint8Array;
  iv: Uint8Array;
  data: Uint8Array;
}) {
  const { keyBytes, iv, data } = params;
  const algo = { name: "AES-GCM", iv, tagLength: 128 } as AesGcmParams;
  const cryptoKey = await crypto.subtle.importKey(
    "raw",
    keyBytes,
    { name: "AES-GCM" },
    false,
    ["decrypt"],
  );
  const decrypted = await crypto.subtle.decrypt(algo, cryptoKey, data);
  return new Uint8Array(decrypted);
}

export async function fetchWrappedFileKey(
  encryptedFileContent: any,
  licenseKey: string,
) {
  const data = await _makeRequest("accounts/license/file-key/", {
    method: "POST",
    body: { encrypted_file: encryptedFileContent, license_key: licenseKey },
    useAuth: true,
  });

  const wrappedKey =
    data?.wrapped_file_key ??
    data?.wrapped_file_key_base64 ??
    data?.wrapped_file_key_b64 ??
    data?.wrapped_key ??
    data;

  if (!wrappedKey) throw new Error("服务器返回的数据中缺少 wrapped_file_key");
  return wrappedKey;
}

export async function unwrapFileKey(
  wrappedFileKey: any,
  userKeyB64: string,
): Promise<Uint8Array> {
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

export async function decryptFileContent(
  encryptedFileContent: any,
  fileKeyBytes: Uint8Array,
) {
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

export async function decryptLicensedFile(
  encryptedFileContent: any,
  licenseKey: string,
  userKeyB64: string,
) {
  const wrappedFileKey = await fetchWrappedFileKey(
    encryptedFileContent,
    licenseKey,
  );
  const fileKeyBytes = await unwrapFileKey(wrappedFileKey, userKeyB64);
  const decrypted = await decryptFileContent(
    encryptedFileContent,
    fileKeyBytes,
  );
  return decrypted;
}

/* ========== 默认导出 ========== */
export default {
  _makeRequest,
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
  fetchWrappedFileKey,
  unwrapFileKey,
  decryptFileContent,
  decryptLicensedFile,
  base64ToUint8Array,
  uint8ArrayToString,
};
