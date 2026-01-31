import React from 'react';
import { Loader, AlertCircle, CheckCircle, Clock, Wrench, Zap } from 'lucide-react';
import styles from './TimelineInline.module.scss';

function getStepIcon(level, tool) {
  if (tool) return <Wrench size={12} />;
  switch (level) {
    case 'success':
    case 'done':
      return <CheckCircle size={12} />;
    case 'error':
    case 'warn':
      return <AlertCircle size={12} />;
    case 'running':
    case 'active':
      return <Loader size={12} className={styles.spinning} />;
    default:
      return <Clock size={12} />;
  }
}

//  辅助函数：规范化 level
function normalizeLevel(level) {
  const lower = level?.toLowerCase();
  if (['success', 'done', 'completed', 'ok'].includes(lower)) return 'success';
  if (['error', 'failed', 'failure'].includes(lower)) return 'error';
  if (['warn', 'warning'].includes(lower)) return 'warn';
  if (['running', 'active', 'pending'].includes(lower)) return 'running';
  return 'info';
}

export default function TimelineInline({ turnId, timelineData }) {
  if (!timelineData) {
    return (
      <div className={styles.empty}>
        <Clock size={16} />
        <span>暂无执行记录</span>
      </div>
    );
  }

  //  解析后端返回的数据格式
  const rawEvents = timelineData?.events || timelineData?.items || timelineData?.timeline || [];

  console.log('[TimelineInline] Raw events for', turnId, rawEvents);

  //  映射字段（重点提取 metadata.action 和 decision）
  const items = rawEvents.map((it) => ({
    title: it.metadata?.action || it.title || it.node || '步骤',
    route: it.decision?.route || it.route || it.node || null,
    tool: it.tool || it.tool_name || it.metadata?.tool || null,
    ms: it.ms || it.latency_ms || it.duration_ms || it.metadata?.duration_ms || 0,
    message: it.decision?.reason || it.message || it.metadata?.message || '',
    ts: it.ts || it.timestamp || null,
    level: normalizeLevel(it.level || it.status || it.metadata?.error ? 'error' : 'success'),
    error: it.error || it.error_message || it.metadata?.error || null,
    //  新增：保留原始数据
    decision: it.decision || null,
    metadata: it.metadata || null,
  }));

  console.log('[TimelineInline] Mapped items:', items);

  if (items.length === 0) {
    return (
      <div className={styles.empty}>
        <Clock size={16} />
        <span>暂无执行记录</span>
      </div>
    );
  }

  const totalMs = items.reduce((sum, it) => sum + (it.ms || 0), 0);

  return (
    <div className={styles.timelineInline}>
      <div className={styles.summary}>
        <span className={styles.summaryItem}>
          <Zap size={12} />共 {items.length} 步
        </span>
        <span className={styles.summaryItem}>
          <Clock size={12} />
          总耗时 {totalMs}ms
        </span>
      </div>

      <ul className={styles.timeline}>
        {items.map((item, idx) => (
          <li key={idx} className={`${styles.item} ${styles[item.level] || ''}`}>
            {idx < items.length - 1 && <div className={styles.connector} />}
            <div className={styles.dot}>{getStepIcon(item.level, item.tool)}</div>
            <div className={styles.content}>
              <div className={styles.header}>
                <span className={styles.title}>{item.title}</span>
                {item.ms > 0 && <span className={styles.time}>{item.ms}ms</span>}
              </div>
              {(item.route || item.tool) && (
                <div className={styles.meta}>
                  {item.route && item.route !== '-' && (
                    <span className={styles.badge}>{item.route}</span>
                  )}
                  {item.tool && (
                    <span className={`${styles.badge} ${styles.toolBadge}`}>
                      <Wrench size={10} />
                      {item.tool}
                    </span>
                  )}
                </div>
              )}
              {item.message && <p className={styles.message}>{item.message}</p>}
              {/*  显示 decision 的 confidence */}
              {item.decision?.confidence && (
                <p className={styles.confidence}>
                  置信度: {(item.decision.confidence * 100).toFixed(0)}%
                </p>
              )}
              {item.error && (
                <div className={styles.itemError}>
                  <AlertCircle size={12} />
                  <span>{item.error}</span>
                </div>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
