// src/components/LeftPanel/BottomPanelTypes.ts

/**
 * 共享的用户类型定义
 */
export interface AuthUser {
  avatarUrl?: string | null;
  name?: string | null;
  email: string;
  subscription?: string | null;
}
