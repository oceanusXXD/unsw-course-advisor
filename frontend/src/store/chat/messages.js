import { useTabsStore } from '../tabs';

/**
 * 消息管理模块 -  已支持按用户隔离
 */
export const createMessagesSlice = (set, get) => ({
  // 状态
  tabMessages: {},

  // Getters
  getMessages: (tabId) => {
    if (!tabId) return [];
    return get().tabMessages[tabId] || [];
  },

  // Actions
  addMessage: (tabId, msg) => {
    set((state) => ({
      tabMessages: {
        ...state.tabMessages,
        [tabId]: [...(state.tabMessages[tabId] || []), msg],
      },
    }));
    persistMessages(get().tabMessages);
  },

  updateMessage: (tabId, msgId, partial) => {
    set((state) => ({
      tabMessages: {
        ...state.tabMessages,
        [tabId]: (state.tabMessages[tabId] || []).map((m) =>
          m.id === msgId ? { ...m, ...partial } : m,
        ),
      },
    }));
    persistMessages(get().tabMessages);
  },

  removeMessage: (tabId, msgId) => {
    set((state) => ({
      tabMessages: {
        ...state.tabMessages,
        [tabId]: (state.tabMessages[tabId] || []).filter((m) => m.id !== msgId),
      },
    }));
    persistMessages(get().tabMessages);
  },

  clearMessages: (tabId) => {
    set((state) => ({
      tabMessages: {
        ...state.tabMessages,
        [tabId]: [],
      },
    }));
    persistMessages(get().tabMessages);
  },

  //  新增：清空所有消息
  clearAllMessages: () => {
    set({ tabMessages: {} });
    persistMessages({});
  },

  //  新增：加载用户消息
  loadUserMessages: (userId) => {
    const storageKey = `chatMessages_${userId}`;
    try {
      const saved = localStorage.getItem(storageKey);
      if (saved) {
        const messages = JSON.parse(saved);
        set({ tabMessages: messages });
        console.log(`[Messages] Loaded messages for user: ${userId}`);
      } else {
        set({ tabMessages: {} });
      }
    } catch (e) {
      console.error('[Messages] Failed to load user messages:', e);
      set({ tabMessages: {} });
    }
  },
});

//  修改：按用户持久化消息
function persistMessages(messages) {
  try {
    // 获取当前用户 ID
    const currentUserId = useTabsStore.getState().currentUserId || 'anonymous';
    const storageKey = `chatMessages_${currentUserId}`;

    localStorage.setItem(storageKey, JSON.stringify(messages));

    // 仍然调用 tabs 的 persist（为了保持兼容性）
    useTabsStore.getState().persist(messages);
  } catch (e) {
    console.warn('[Messages] persist failed', e);
  }
}
