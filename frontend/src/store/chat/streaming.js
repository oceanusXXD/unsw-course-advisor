import { nanoid } from 'nanoid';
import { streamChat } from '../../services/api';
import { useAuthStore } from '../auth';
import { useTabsStore } from '../tabs';
import { mapStatusNodeToStep, sourceToCourseCard } from './utils';
import { RETRY_CONFIG } from './constants';

/**
 * 流式响应处理模块
 */
export const createStreamingSlice = (set, get) => ({
  // 状态
  isGenerating: false,
  aborter: null,

  // Actions

  sendMessage: async (tabId, text, files = [], meta = {}) => {
    if (!tabId) {
      console.error('[Chat] No active tab');
      return;
    }

    console.log('[Chat] Sending message for tab:', tabId);

    const token = useAuthStore.getState().accessToken;
    const userId = useAuthStore.getState().user?.id || 'anonymous';
    const tabsStore = useTabsStore.getState();
    const currentTab = tabsStore.getTabById(tabId);

    if (!currentTab) {
      console.error('[Chat] Tab not found:', tabId);
      return;
    }

    // 获取后端 tabId
    let backendTabId = currentTab.tabId;
    console.log('[Chat] Current backend tabId:', backendTabId || 'will be generated');

    //  在构建 frontend_state 之前，确保有 student_info
    try {
      await get().ensureStudentInfo(tabId);
    } catch (error) {
      console.warn('[Chat] Failed to ensure student info:', error);
    }

    //  构建 frontend_state（现在包含 student_info）
    const frontendState = get().buildFrontendStateForBackend(tabId);

    //  添加 webSearch 等选项
    if (meta.webSearch) {
      frontendState.webSearch = true;
    }

    console.log('[Chat] Built frontend_state:', frontendState);

    // 创建消息
    const { userMsg, asstId } = createMessages(tabId, text, files, meta, backendTabId, get);

    // 流式响应状态
    const streamState = {
      ragMsgId: null,
      ragCards: [],
      started: false,
      allCitations: [],
      currentTurnId: null,
      backendTabIdReceived: false,
    };

    // 创建 abort controller
    const controller = new AbortController();
    set({ isGenerating: true, aborter: controller });

    // 创建流式处理器
    const handlers = createStreamHandlers(tabId, asstId, backendTabId, streamState, get, set);

    // 执行流式请求
    await executeStreamWithRetry({
      text,
      frontendState, //  现在包含了 student_info 和 webSearch
      userId,
      backendTabId,
      controller,
      token,
      handlers,
      streamState,
      tabId,
      asstId,
      get,
      set,
    });

    // 清理
    await finalizeStream(tabId, asstId, streamState, get, set);
  },

  stopGeneration: () => {
    const a = get().aborter;
    if (a) a.abort();
    get().stopTimelinePolling();
    set({ isGenerating: false, aborter: null });
  },
});

// === 辅助函数 ===

function createMessages(tabId, text, files, meta, backendTabId, get) {
  // 创建用户消息
  const userMsg = {
    id: nanoid(),
    role: 'user',
    content: text,
    files,
    createdAt: Date.now(),
  };
  get().addMessage(tabId, userMsg);

  // 创建助手消息占位
  const asstId = nanoid();
  get().addMessage(tabId, {
    id: asstId,
    role: 'assistant',
    content: '',
    createdAt: Date.now(),
    meta: {
      step: 'analyze_context',
      turnId: undefined,
      citations: [],
      backendTabId: backendTabId,
      ...meta,
    },
  });

  return { userMsg, asstId };
}

function createStreamHandlers(tabId, asstId, backendTabId, streamState, get, set) {
  return {
    onSessionInit: ({ tabId: receivedTabId, turnId: receivedTurnId }) => {
      console.log('[Chat] Session init:', { receivedTabId, receivedTurnId });

      // 处理后端返回的 tabId
      if (receivedTabId && receivedTabId !== backendTabId) {
        console.log('[Chat] New backend tabId received:', receivedTabId);
        backendTabId = receivedTabId;
        streamState.backendTabIdReceived = true;

        const tabsStore = useTabsStore.getState();
        try {
          tabsStore.setBackendTabId(tabId, receivedTabId);
        } catch (e) {
          console.warn('[Chat] setBackendTabId failed', e);
        }

        const msg = get()
          .getMessages(tabId)
          .find((m) => m.id === asstId);
        get().updateMessage(tabId, asstId, {
          meta: { ...(msg?.meta || {}), backendTabId: receivedTabId },
        });
      }

      // 处理 turnId
      if (receivedTurnId && receivedTurnId !== streamState.currentTurnId) {
        streamState.currentTurnId = receivedTurnId;
        console.log('[Chat] Got turn_id from session_init:', receivedTurnId);
        get().setTurnIdForMessage(asstId, receivedTurnId);
        set((state) => ({
          timelines: {
            ...state.timelines,
            [receivedTurnId]: { events: [] },
          },
        }));
      }
    },

    onStatus: (status) => {
      console.log('[Chat] Status update:', status);

      const step = mapStatusNodeToStep(status.node);
      const cur = get()
        .getMessages(tabId)
        .find((m) => m.id === asstId);
      const turnId = status.turn_id || cur?.meta?.turnId;

      // 更新消息 meta
      const nextMeta = {
        ...(cur?.meta || {}),
        step,
        turnId,
        ...(backendTabId ? { backendTabId } : {}),
      };
      get().updateMessage(tabId, asstId, { meta: nextMeta });

      // 处理 turn_id
      if (turnId && turnId !== streamState.currentTurnId) {
        streamState.currentTurnId = turnId;
        console.log('[Chat] Got turn_id from status:', turnId);
        get().setTurnIdForMessage(asstId, turnId);
        if (turnId && status.node) {
          get().addTimelineEvent(turnId, {
            title: status.node,
            level: status.level || 'info',
            ts: Date.now(),
            metadata: status,
          });
        }
      }

      // 特殊处理检索状态
      if (step === 'retrieve_rag' && !cur?.content?.includes('正在检索课程')) {
        get().updateMessage(tabId, asstId, {
          content: (cur?.content || '') + '正在检索课程…\n\n',
        });
      }
    },
    onDecision: (decision) => {
      console.log('[Chat] Decision received:', decision);

      const cur = get()
        .getMessages(tabId)
        .find((m) => m.id === asstId);
      const turnId = cur?.meta?.turnId;

      if (turnId && decision) {
        get().addTimelineEvent(turnId, {
          title: decision.route || 'Decision',
          route: decision.route,
          level: 'success',
          message: decision.reason,
          ts: Date.now(),
          decision: decision,
          metadata: {
            confidence: decision.confidence,
            tool_info: decision.tool_info,
          },
        });
      }
    },
    onToken: (delta) => {
      if (!streamState.started) {
        console.log('[Chat] First token received');
        streamState.started = true;
      }
      const target = get()
        .getMessages(tabId)
        .find((m) => m.id === asstId);
      if (!target) return;
      get().updateMessage(tabId, asstId, {
        content: (target.content || '') + (delta || ''),
      });
    },

    onSources: (sources) => {
      console.log('[Chat] Sources received:', sources?.length);
      streamState.started = true;
      const newCards = (sources || []).map(sourceToCourseCard);
      streamState.ragCards = [...streamState.ragCards, ...newCards];

      if (!streamState.ragMsgId) {
        streamState.ragMsgId = nanoid();
        get().addMessage(tabId, {
          id: streamState.ragMsgId,
          role: 'rag_result',
          content: '',
          createdAt: Date.now(),
          meta: { cards: streamState.ragCards },
        });
      } else {
        get().updateMessage(tabId, streamState.ragMsgId, {
          meta: { cards: streamState.ragCards },
        });
      }
    },

    onCitation: (citation) => {
      console.log('[Chat] Citation received:', citation);
      streamState.allCitations.push(citation);
      const cur = get()
        .getMessages(tabId)
        .find((m) => m.id === asstId);
      get().updateMessage(tabId, asstId, {
        meta: { ...(cur?.meta || {}), citations: streamState.allCitations },
      });
    },

    onPartialResponse: (data) => {
      console.log('[Chat] Partial response:', data);
    },

    onToolInvocation: (data) => {
      console.log('[Chat] Tool invocation:', data);
    },

    onToolResult: (data) => {
      console.log('[Chat] Tool result:', data);
    },

    onFinalResponse: (data) => {
      console.log('[Chat] Final response:', data);
    },

    onError: (err) => {
      console.error('[Chat] Stream error:', err);
      throw err;
    },
  };
}

async function executeStreamWithRetry({
  text,
  frontendState,
  userId,
  backendTabId,
  controller,
  token,
  handlers,
  streamState,
  tabId,
  asstId,
  get,
  set,
}) {
  const runOnce = () =>
    streamChat({
      query: text,
      frontend_state: frontendState,
      user_id: userId,
      tabId: backendTabId || undefined,
      signal: controller.signal,
      token,
      ...handlers,
    });

  for (let attempt = 0; attempt <= RETRY_CONFIG.MAX_RETRIES; attempt++) {
    try {
      console.log('[Chat] Attempt', attempt + 1, 'of', RETRY_CONFIG.MAX_RETRIES + 1);
      await runOnce();
      console.log('[Chat] Stream completed successfully');
      break;
    } catch (e) {
      console.error('[Chat] Attempt', attempt + 1, 'failed:', e);

      if (controller.signal.aborted) {
        console.log('[Chat] Stream aborted by user');
        return;
      }

      const isLast = attempt === RETRY_CONFIG.MAX_RETRIES;

      if (streamState.started || isLast) {
        get().updateMessage(tabId, asstId, {
          role: 'error',
          content: e?.message || '发生错误，请重试。',
          meta: { error: String(e) },
        });
        set({ isGenerating: false, aborter: null });
        return;
      }

      const backoff = RETRY_CONFIG.INITIAL_BACKOFF * Math.pow(2, attempt);
      console.log('[Chat] Retrying in', backoff, 'ms');
      await new Promise((r) => setTimeout(r, backoff));
    }
  }
}

async function finalizeStream(tabId, asstId, streamState, get, set) {
  console.log('[Chat] Finalizing message');
  // 获取最终 timeline
  if (streamState.currentTurnId) {
    await get().fetchFinalTimeline(streamState.currentTurnId);
  }

  // 更新消息状态
  const cur = get()
    .getMessages(tabId)
    .find((m) => m.id === asstId);
  get().updateMessage(tabId, asstId, {
    meta: { ...(cur?.meta || {}), step: 'done' },
  });

  set({ isGenerating: false, aborter: null });

  // 更新 citations
  if (streamState.allCitations.length > 0) {
    const tabsStore = useTabsStore.getState();
    try {
      tabsStore.updateCitations(tabId, streamState.allCitations);
    } catch (e) {
      console.warn('[Chat] updateCitations failed', e);
    }
  }

  // 更新 tab 信息
  const messageCount = get()
    .getMessages(tabId)
    .filter((m) => m.role === 'user' || m.role === 'assistant').length;

  const tabsStore = useTabsStore.getState();
  try {
    tabsStore.update(tabId, {
      messageCount,
      updatedAt: Date.now(),
    });
  } catch (e) {
    console.warn('[Chat] tabs.update failed', e);
  }

  console.log('[Chat] Send message completed');
}
