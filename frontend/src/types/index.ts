export interface ChatItem {
  id: string;
  title: string;
  createdAt: Date;
  updatedAt: Date;
  messages: Message[];
}

export interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: Date;
}

// 用户相关类型 (客户端状态)
export interface User {
  id: string;
  email: string;
  name: string;
  avatar?: string;
  subscription: "free" | "plus" | "pro";
}

// 完整的 AuthState (客户端状态)
export interface AuthState {
  isLoggedIn: boolean;
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  userInitial: string; // [!!] 字段已存在，实现已修正
}
export interface LoginTokenResponse {
  access: string;
  refresh: string;
}

// registerUser() 的响应类型 (仅包含令牌)
export interface RegisterTokenResponse {
  access: string;
  refresh: string;
}

// getCurrentUser() 的响应类型 (基于你的实现逻辑)
// [!!] 修正：这个类型现在匹配你的实现逻辑
export interface LoginResponse {
  // 你的代码中称之为 LoginResponse，但它似乎是 GetUserResponse
  user: {
    id: string;
    email: string;
    username?: string;
    name?: string;
    avatar?: string;
  };
  license_active?: boolean; // 在根级别，匹配 'userResponse.license_active'
}

// 你的原始 RegisterResponse 类型 (供参考)
// (你的实现没有使用这个，而是调用了 getCurrentUser)
export interface RegisterResponse {
  IAccess: string;
  refresh?: string;
  user: {
    id?: string;
    email: string;
    username?: string;
    name?: string;
    avatar?: string;
  };
  license_status?: string;
}
