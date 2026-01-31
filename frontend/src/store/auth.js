import { create } from 'zustand';
import { getCurrentUser, logoutUser } from '../services/api.js';

export const useAuthStore = create((set, get) => ({
  accessToken: null,
  refreshToken: null,
  user: null,
  loaded: false,

  hydrateFromStorage: async () => {
    try {
      const saved = JSON.parse(localStorage.getItem('authState') || '{}');
      const accessToken = saved?.accessToken || null;
      const refreshToken = saved?.refreshToken || null;
      set({ accessToken, refreshToken });

      if (accessToken) {
        try {
          const user = await getCurrentUser(accessToken);
          set({ user });

          //  新增：加载用户的聊天数据
          if (user?.id) {
            const userId = String(user.id);
            await get().loadUserChatData(userId);
          }
        } catch (e) {
          console.error('[Auth] Token invalid, clearing:', e);
          localStorage.removeItem('authState');
          set({ accessToken: null, refreshToken: null, user: null });
        }
      }
    } finally {
      set({ loaded: true });
    }
  },

  setAuth: ({ accessToken, refreshToken, user }) => {
    localStorage.setItem(
      'authState',
      JSON.stringify({
        accessToken,
        refreshToken,
        user,
        savedAt: Date.now(),
      }),
    );
    set({ accessToken, refreshToken, user });

    //  新增：登录后加载用户数据
    if (user?.id) {
      const userId = String(user.id);
      get().loadUserChatData(userId);
    }
  },

  clearAuth: () => {
    localStorage.removeItem('authState');
    set({ accessToken: null, refreshToken: null, user: null });

    //  新增：清空聊天数据
    get().clearUserChatData();
  },

  logout: async () => {
    const { accessToken, refreshToken } = get();
    try {
      await logoutUser(refreshToken, accessToken);
    } catch (e) {
      console.error('[Auth] Logout failed:', e);
    }
    get().clearAuth();
  },

  //  新增：加载用户聊天数据
  loadUserChatData: async (userId) => {
    try {
      console.log(`[Auth] Loading chat data for user: ${userId}`);

      // 动态导入避免循环依赖
      const { useTabsStore } = await import('./tabs.js');
      const { useChatStore } = await import('./chat/index.js');

      // 切换 tabs 数据
      useTabsStore.getState().switchUser(userId);

      // 切换聊天消息
      useChatStore.getState().switchUser(userId);

      console.log(`[Auth] Chat data loaded for user: ${userId}`);
    } catch (e) {
      console.error('[Auth] Failed to load user chat data:', e);
    }
  },

  //  新增：清空用户聊天数据
  clearUserChatData: async () => {
    try {
      console.log('[Auth] Clearing user chat data');

      // 动态导入避免循环依赖
      const { useTabsStore } = await import('./tabs.js');
      const { useChatStore } = await import('./chat/index.js');

      // 清空 tabs
      useTabsStore.getState().clearUserData();

      // 清空消息
      useChatStore.getState().clearAllChatData();

      console.log('[Auth] User chat data cleared');
    } catch (e) {
      console.error('[Auth] Failed to clear user chat data:', e);
    }
  },
}));
