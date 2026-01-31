// src/components/ChatMessage/ChatMessage.jsx
import React, { useState, useEffect } from 'react';
import * as Tooltip from '@radix-ui/react-tooltip';
import styles from './styles/ChatMessage.module.scss';
import metaStyles from './styles/ChatMessageMeta.module.scss';
import { SafeMarkdown } from '../../util/markdown.jsx';
import TimelineInline from '../TimelineInline/TimelineInline.jsx';
import { Copy, Check, AlertCircle, ChevronDown, ChevronUp } from 'lucide-react';
import { useChatStore, chatSelectors } from '../../store/chat';

function formatTime(timestamp) {
  const date = new Date(timestamp);
  const now = new Date();
  const diff = now - date;
  const seconds = Math.floor(diff / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);

  if (seconds < 60) return '刚刚';
  if (minutes < 60) return `${minutes} 分钟前`;
  if (hours < 24) return `${hours} 小时前`;

  return date.toLocaleDateString('zh-CN', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text || '');
    return true;
  } catch (err) {
    console.error('Failed to copy:', err);
    return false;
  }
}

function TypingCursor() {
  return <span className={styles.typingIndicator}>...</span>;
}

export default function ChatMessage({
  message,
  isStreaming = false,
  historyState = 'expanded',
  profileState = 'expanded',
}) {
  const [copied, setCopied] = useState(false);
  const [timelineExpanded, setTimelineExpanded] = useState(false);

  const isUser = message.role === 'user';
  const isAssistant = message.role === 'assistant';
  const isError = message.role === 'error' || message.role === 'warn';

  const handleCopy = async () => {
    const success = await copyToClipboard(message.content);
    if (success) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  //  修复：直接从 message.meta.turnId 读取，而不是从 store
  const turnIdForMsg = message.meta?.turnId || null;

  // 获取 timeline 数据（如果有 turnId）
  const timelineData = useChatStore(chatSelectors.selectTimeline(turnIdForMsg));

  // 持久化展开状态
  const storageKey = turnIdForMsg ? `timeline_expanded_${turnIdForMsg}` : null;

  useEffect(() => {
    if (storageKey) {
      const saved = localStorage.getItem(storageKey);
      if (saved !== null) {
        setTimelineExpanded(saved === 'true');
      }
    }
  }, [storageKey]);

  const toggleTimeline = () => {
    const nextState = !timelineExpanded;
    setTimelineExpanded(nextState);
    if (storageKey) {
      localStorage.setItem(storageKey, String(nextState));
    }
  };

  //  修改：只要有 turnId 就显示按钮
  const hasTimeline = !!turnIdForMsg;

  // 用户消息
  if (isUser) {
    return (
      <article className={`${styles.message} ${styles.userMessage}`}>
        <div className={styles.userBubble}>
          <div className={styles.userContent}>{message.content}</div>
        </div>
        <div className={metaStyles.userMeta}>
          <span className={metaStyles.userTime}>{formatTime(message.createdAt || Date.now())}</span>
        </div>
      </article>
    );
  }

  // 助手消息
  if (isAssistant) {
    const shouldExpand =
      historyState === 'collapsed' && (profileState === 'compact' || profileState === 'collapsed');
    return (
      <article
        className={`${styles.message} ${styles.assistantMessage} ${
          shouldExpand ? styles.expanded : ''
        }`}
      >
        <div className={styles.assistantContent}>
          <div className={styles.assistantText}>
            <SafeMarkdown>{message.content || ''}</SafeMarkdown>
            {isStreaming && <TypingCursor />}
          </div>

          <div className={metaStyles.assistantMeta}>
            {/*  修改：按钮放在左侧 */}
            <div className={metaStyles.actions}>
              <Tooltip.Provider delayDuration={300}>
                <Tooltip.Root>
                  <Tooltip.Trigger asChild>
                    <button className={metaStyles.metaBtn} onClick={handleCopy} aria-label="复制">
                      {copied ? <Check size={14} /> : <Copy size={14} />}
                      <span className={metaStyles.btnLabel}>{copied ? '已复制' : '复制'}</span>
                    </button>
                  </Tooltip.Trigger>
                  <Tooltip.Content className={styles.tooltip} side="top">
                    {copied ? '已复制到剪贴板' : '复制内容'}
                  </Tooltip.Content>
                </Tooltip.Root>
              </Tooltip.Provider>

              {hasTimeline && (
                <Tooltip.Provider delayDuration={300}>
                  <Tooltip.Root>
                    <Tooltip.Trigger asChild>
                      <button
                        className={`${metaStyles.metaBtn} ${
                          timelineExpanded ? metaStyles.active : ''
                        }`}
                        onClick={toggleTimeline}
                        aria-label="执行详情"
                      >
                        {timelineExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                        <span className={metaStyles.btnLabel}>执行详情</span>
                      </button>
                    </Tooltip.Trigger>
                    <Tooltip.Content className={styles.tooltip} side="top">
                      {timelineExpanded ? '收起执行详情' : '查看执行详情'}
                    </Tooltip.Content>
                  </Tooltip.Root>
                </Tooltip.Provider>
              )}
            </div>

            {/*  修改：时间放在右侧 */}
            <span className={metaStyles.assistantTime}>
              {formatTime(message.createdAt || Date.now())}
            </span>
          </div>

          {hasTimeline && timelineExpanded && (
            <div className={styles.timelineWrapper}>
              <TimelineInline turnId={turnIdForMsg} timelineData={timelineData} />
            </div>
          )}
        </div>
      </article>
    );
  }

  // 错误消息
  if (isError) {
    return (
      <article className={`${styles.message} ${styles.assistantMessage}`}>
        <div className={styles.errorMessage}>
          <AlertCircle size={16} className={styles.errorIcon} />
          <span>{message.content}</span>
        </div>
      </article>
    );
  }

  return null;
}
