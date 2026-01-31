// src/store/chat/timeline.js
import { getTurnTimeline } from '../../services/api';
import { useAuthStore } from '../auth';

/**
 * Timeline 管理模块（移除轮询，改为流式累积）
 */
export const createTimelineSlice = (set, get) => ({
  // 状态
  turnIdByMsgId: {},
  timelines: {}, // { turnId: { events: [...] } }

  // Getters
  getTimeline: (turnId) => {
    return get().timelines[turnId] || null;
  },

  getTurnIdForMessage: (messageId) => {
    return get().turnIdByMsgId[messageId] || null;
  },

  // Actions
  setTurnIdForMessage: (messageId, turnId) => {
    set((state) => ({
      turnIdByMsgId: {
        ...state.turnIdByMsgId,
        [messageId]: turnId,
      },
    }));
  },

  /**
   *  新增：添加 timeline 事件（替代轮询）
   */
  addTimelineEvent: (turnId, event) => {
    set((state) => {
      const existing = state.timelines[turnId] || { events: [] };
      return {
        timelines: {
          ...state.timelines,
          [turnId]: {
            ...existing,
            events: [...existing.events, event],
          },
        },
      };
    });
  },

  /**
   *  可选：获取最终完整的 timeline（流结束后调用一次）
   */
  fetchFinalTimeline: async (turnId) => {
    try {
      const token = useAuthStore.getState().accessToken;
      const finalData = await getTurnTimeline({ turnId, token });
      console.log('[Timeline] Final data from API:', finalData);

      set((state) => ({
        timelines: {
          ...state.timelines,
          [turnId]: finalData,
        },
      }));

      return finalData;
    } catch (e) {
      console.error('[Timeline] Failed to fetch final:', e);
      return null;
    }
  },
});
