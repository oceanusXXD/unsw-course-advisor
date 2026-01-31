// src/store/chat/frontendState.js

import { normalizeHistory } from './utils';
import { useTabsStore } from '../tabs';
import { useAuthStore } from '../auth';
import { getStudentProfile } from '../../services/api';

/**
 * Frontend State 管理模块
 * 处理 student_info, memory, pending_file_generation 等状态
 */
export const createFrontendStateSlice = (set, get) => ({
  // 状态
  tabFrontendState: {}, // { [tabId]: { memory, student_info, pending_file_generation, etc. } }

  // Getters
  getFrontendState: (tabId) => {
    if (!tabId) return {};
    return get().tabFrontendState[tabId] || {};
  },

  /**
   *  异步获取 student_info（如果本地没有）
   */
  ensureStudentInfo: async (tabId) => {
    const existingState = get().getFrontendState(tabId);

    // 如果已经有 student_info，直接返回
    if (existingState.student_info) {
      return existingState.student_info;
    }

    // 1. 检查 localStorage 临时数据
    const tempProfileKey = `temp_student_profile_${tabId}`;
    const tempProfile = localStorage.getItem(tempProfileKey);

    if (tempProfile) {
      try {
        const studentInfo = JSON.parse(tempProfile);
        console.log('[FrontendState] Using temp profile from localStorage');

        // 更新到 store
        get().setStudentInfo(tabId, studentInfo);

        // 使用后清除
        localStorage.removeItem(tempProfileKey);

        return studentInfo;
      } catch (e) {
        console.warn('[FrontendState] Failed to parse temp profile:', e);
      }
    }

    // 2. 从服务器获取
    try {
      const tabsStore = useTabsStore.getState();
      const authStore = useAuthStore.getState();
      const currentTab = tabsStore.tabs.find((t) => t.id === tabId);

      if (currentTab?.tabId) {
        const response = await getStudentProfile({
          tabId: currentTab.tabId,
          userId: authStore.user?.id,
          useAuth: true,
        });

        if (response?.status === 'ok' && response?.student_info) {
          console.log('[FrontendState] Loaded student profile from server');

          // 更新到 store
          get().setStudentInfo(tabId, response.student_info);

          return response.student_info;
        }
      }
    } catch (error) {
      console.warn('[FrontendState] Failed to load student profile:', error);
    }

    return null;
  },

  /**
   * 构建完整的 frontend_state（用于发送给后端）
   * 注意：这是同步方法，调用前应该先调用 ensureStudentInfo
   */
  buildFrontendStateForBackend: (tabId) => {
    const messages = get().getMessages(tabId);
    const existingState = get().getFrontendState(tabId);

    return {
      // 必需字段：规范化的消息历史
      messages: normalizeHistory(messages),

      // 可选字段：从现有状态继承或使用默认值
      pending_file_generation: existingState.pending_file_generation || null,
      pending_plugin_install: existingState.pending_plugin_install || null,
      last_proposal_ts: existingState.last_proposal_ts || 0.0,
      file_generation_declined: Boolean(existingState.file_generation_declined || false),

      // 记忆结构（如果有）
      ...(existingState.memory ? { memory: existingState.memory } : {}),

      //  学生信息（如果有）
      ...(existingState.student_info ? { student_info: existingState.student_info } : {}),
    };
  },

  // Actions
  updateFrontendState: (tabId, updates) => {
    set((state) => ({
      tabFrontendState: {
        ...state.tabFrontendState,
        [tabId]: {
          ...(state.tabFrontendState[tabId] || {}),
          ...updates,
        },
      },
    }));
    persistFrontendState();
  },

  setStudentInfo: (tabId, studentInfo) => {
    get().updateFrontendState(tabId, { student_info: studentInfo });
  },

  setMemory: (tabId, memory) => {
    get().updateFrontendState(tabId, { memory });
  },

  setPendingFileGeneration: (tabId, pendingFileGen) => {
    get().updateFrontendState(tabId, {
      pending_file_generation: pendingFileGen,
      last_proposal_ts: Date.now() / 1000,
    });
  },

  declineFileGeneration: (tabId) => {
    get().updateFrontendState(tabId, {
      file_generation_declined: true,
      pending_file_generation: null,
    });
  },

  clearFileGenerationState: (tabId) => {
    get().updateFrontendState(tabId, {
      pending_file_generation: null,
      file_generation_declined: false,
    });
  },
});

// 辅助函数
function persistFrontendState() {
  try {
    useTabsStore.getState().persist();
  } catch (e) {
    console.warn('[FrontendState] persist failed', e);
  }
}
