// 状态节点映射
export const STATUS_NODE_MAP = {
  ANALYZE: 'analyze_context',
  PLAN: 'router_llm_planner',
  RETRIEVE: 'retrieve_rag',
  GENERATE: 'generate',
};

// 重试配置
export const RETRY_CONFIG = {
  MAX_RETRIES: 2,
  INITIAL_BACKOFF: 300,
};

// 轮询配置
export const TIMELINE_POLL_INTERVAL = 1000;
