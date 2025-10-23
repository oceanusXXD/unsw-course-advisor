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
  userInitial: string;
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

// getCurrentUser() 的响应类型
export interface LoginResponse {
  user: {
    id: string;
    email: string;
    username?: string;
    name?: string;
    avatar?: string;
  };
  license_active?: boolean; // 在根级别，匹配 'userResponse.license_active'
}

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
