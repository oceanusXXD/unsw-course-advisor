import { create } from 'zustand';
import { createMessagesSlice } from './messages';
import { createFrontendStateSlice } from './frontendState';
import { createTimelineSlice } from './timeline';
import { createStreamingSlice } from './streaming';

/**
 * 主聊天 Store -  新增用户切换支持
 */
export const useChatStore = create((set, get) => ({
  ...createMessagesSlice(set, get),
  ...createFrontendStateSlice(set, get),
  ...createTimelineSlice(set, get),
  ...createStreamingSlice(set, get),

  //  新增：切换用户时重置聊天数据
  switchUser: (userId) => {
    console.log(`[ChatStore] Switching to user: ${userId}`);

    // 清空当前所有状态
    get().clearAllMessages?.();

    // 加载新用户的消息
    get().loadUserMessages?.(userId);
  },

  //  新增：清空所有聊天数据
  clearAllChatData: () => {
    console.log('[ChatStore] Clearing all chat data');
    get().clearAllMessages?.();
  },
}));

// 导出 selectors（用于性能优化）
export const chatSelectors = {
  // 消息相关
  selectMessages: (tabId) => (state) => state.getMessages(tabId),
  selectMessageById: (tabId, msgId) => (state) =>
    state.getMessages(tabId).find((m) => m.id === msgId),

  // Frontend State 相关
  selectFrontendState: (tabId) => (state) => state.getFrontendState(tabId),
  selectStudentInfo: (tabId) => (state) => state.getFrontendState(tabId).student_info,
  selectMemory: (tabId) => (state) => state.getFrontendState(tabId).memory,
  selectPendingFileGeneration: (tabId) => (state) =>
    state.getFrontendState(tabId).pending_file_generation,

  // Timeline 相关
  selectTimeline: (turnId) => (state) => state.getTimeline(turnId),
  selectTurnIdForMessage: (msgId) => (state) => state.getTurnIdForMessage(msgId),

  // 状态
  selectIsGenerating: (state) => state.isGenerating,
};
