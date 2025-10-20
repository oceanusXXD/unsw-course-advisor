// 聊天相关类型
export interface ChatItem {
  id: string;
  title: string;
  createdAt: Date;
  updatedAt: Date;
  messages: Message[];
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

// 用户相关类型
export interface User {
  id: string;
  email: string;
  name: string;
  avatar?: string;
  subscription: "free" | "plus" | "pro";
}

// [已修正 ✨]
export interface AuthState {
  isLoggedIn: boolean;
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
}

// 后端响应类型 (保持不变)
export interface LoginResponse {
  access: string;
  refresh?: string;
  user: {
    id?: string;
    email: string;
    username?: string;
    name?: string;
    avatar?: string;
  };
  license_active?: boolean;
}

export interface RegisterResponse {
  access: string;
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
