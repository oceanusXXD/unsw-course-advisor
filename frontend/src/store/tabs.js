// src/store/tabs.js
import { create } from 'zustand';
import { nanoid } from 'nanoid';

export const useTabsStore = create((set, get) => ({
  tabs: [],
  activeTabId: null,
  currentUserId: null, //  新增：当前用户 ID

  /**
   *  新增：设置当前用户（由 auth store 调用）
   */
  setCurrentUser: (userId) => {
    set({ currentUserId: userId });
  },

  /**
   *  修改：按用户加载数据
   */
  init: (userId = 'anonymous') => {
    const storageKey = `app_tabs_${userId}`; //  用户隔离的 key
    const saved = localStorage.getItem(storageKey);
    let messagesToRestore = null;

    if (saved) {
      try {
        const data = JSON.parse(saved);
        set({
          tabs: data.tabs || [],
          activeTabId: data.activeTabId,
          currentUserId: userId, //  记录当前用户
        });
        messagesToRestore = data.messages || null;
      } catch (e) {
        console.error('[Tabs] Failed to load from localStorage:', e);
      }
    } else {
      set({ currentUserId: userId });
    }

    // 如果没有任何 tab，创建一个默认的
    if (get().tabs.length === 0) {
      get().create('新对话');
    }

    return messagesToRestore;
  },

  /**
   *  修改：按用户持久化
   */
  persist: (messages = null) => {
    const { tabs, activeTabId, currentUserId } = get();
    const userId = currentUserId || 'anonymous';
    const storageKey = `app_tabs_${userId}`; //  用户隔离的 key

    const data = { tabs, activeTabId };

    if (messages !== null) {
      data.messages = messages;
    } else {
      const saved = localStorage.getItem(storageKey);
      if (saved) {
        try {
          const oldData = JSON.parse(saved);
          if (oldData.messages) {
            data.messages = oldData.messages;
          }
        } catch (e) {
          console.warn('[Tabs] Failed to preserve old messages:', e);
        }
      }
    }

    localStorage.setItem(storageKey, JSON.stringify(data));
  },

  /**
   *  新增：清空当前用户的所有数据
   */
  clearUserData: () => {
    const { currentUserId } = get();
    const userId = currentUserId || 'anonymous';
    const storageKey = `app_tabs_${userId}`;

    localStorage.removeItem(storageKey);
    set({
      tabs: [],
      activeTabId: null,
    });

    console.log(`[Tabs] Cleared data for user: ${userId}`);
  },

  /**
   *  新增：切换用户时重新加载数据
   */
  switchUser: (userId) => {
    const oldUserId = get().currentUserId;
    if (oldUserId === userId) return; // 同一用户，无需切换

    console.log(`[Tabs] Switching from ${oldUserId} to ${userId}`);

    // 清空当前状态
    set({
      tabs: [],
      activeTabId: null,
      currentUserId: userId,
    });

    // 加载新用户数据
    return get().init(userId);
  },

  setActive: (id) => {
    set({ activeTabId: id });
    get().persist();
  },

  create: (title = '新对话') => {
    const newTab = {
      id: nanoid(),
      tabId: null,
      title,
      messageCount: 0,
      updatedAt: Date.now(),
      createdAt: Date.now(),
      pinned: false,
      citations: [],
    };

    set((state) => ({
      tabs: [newTab, ...state.tabs],
      activeTabId: newTab.id,
    }));

    get().persist();
    return newTab.id;
  },

  update: (id, updates) => {
    set((state) => ({
      tabs: state.tabs.map((tab) => (tab.id === id ? { ...tab, ...updates } : tab)),
    }));
    get().persist();
  },

  setBackendTabId: (id, backendTabId) => {
    console.log('[Tabs] Setting backend tabId:', { id, backendTabId });
    set((state) => ({
      tabs: state.tabs.map((tab) => (tab.id === id ? { ...tab, tabId: backendTabId } : tab)),
    }));
    get().persist();
  },

  getTabById: (id) => {
    return get().tabs.find((tab) => tab.id === id);
  },

  getActiveTab: () => {
    const { tabs, activeTabId } = get();
    return tabs.find((tab) => tab.id === activeTabId);
  },

  getTabByBackendId: (backendTabId) => {
    return get().tabs.find((tab) => tab.tabId === backendTabId);
  },

  remove: (id) => {
    set((state) => {
      const newTabs = state.tabs.filter((tab) => tab.id !== id);
      const newActiveTabId = state.activeTabId === id ? newTabs[0]?.id || null : state.activeTabId;

      return {
        tabs: newTabs,
        activeTabId: newActiveTabId,
      };
    });
    get().persist();
  },

  togglePin: (id) => {
    const tab = get().tabs.find((t) => t.id === id);
    if (tab) {
      get().update(id, { pinned: !tab.pinned });
    }
  },

  updateTitle: (id, title) => {
    get().update(id, {
      title,
      updatedAt: Date.now(),
    });
  },

  touch: (id) => {
    get().update(id, { updatedAt: Date.now() });
  },

  updateCitations: (id, citations) => {
    set((state) => ({
      tabs: state.tabs.map((tab) => (tab.id === id ? { ...tab, citations } : tab)),
    }));
    get().persist();
  },
}));
