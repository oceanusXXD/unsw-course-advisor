// src/components/CitationPanel/CitationPanel.jsx
import React, { useMemo, useState, useCallback } from 'react';
import PropTypes from 'prop-types';
import { useTabsStore } from '../../store/tabs.js';
import { BookOpen, ExternalLink, ChevronRight, ChevronLeft, Copy } from 'lucide-react';
import styles from './CitationPanel.module.scss';
import '../../styles/glass.css';

/**
 * CitationPanel
 * props:
 *  - collapsed: boolean
 *  - onToggle: () => void
 */
export default function CitationPanel({ collapsed, onToggle }) {
  //  对齐 tabs.js：tabs, activeTabId
  const { tabs = [], activeTabId } = useTabsStore() || {};
  const activeTab = tabs.find((s) => s.id === activeTabId) || {};
  const rawCitations = activeTab?.citations || [];

  // memoize citations list
  const citations = useMemo(() => rawCitations, [rawCitations]);

  // 控制每条描述的展开状态（默认收起）
  const [expandedSet, setExpandedSet] = useState(() => new Set());
  const toggleExpand = useCallback((key) => {
    setExpandedSet((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  // 复制链接到剪贴板并给出短暂反馈（简单实现）
  const [copiedKey, setCopiedKey] = useState(null);
  const copyToClipboard = useCallback(async (text, key) => {
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      setCopiedKey(key);
      setTimeout(() => setCopiedKey(null), 1800);
    } catch (e) {
      // 若失败则无需抛错，仅静默失败
      console.warn('复制失败', e);
    }
  }, []);

  // 生成稳定 key
  const makeKey = (citation, idx) => citation.id ?? citation.url ?? `idx-${idx}`;

  // 键盘可激活的折叠/展开处理
  const onToggleKeyDown = (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onToggle?.();
    }
  };

  // --- 收起窄条视图 ---
  if (collapsed) {
    return (
      <aside
        className={`${styles.citationPanelCollapsed} glass-liquid`}
        aria-hidden={false}
        aria-label="引用侧边栏 — 已收起"
      >
        <button
          className={styles.expandBtn}
          onClick={onToggle}
          onKeyDown={onToggleKeyDown}
          title="展开引用"
          aria-label="展开引用"
        >
          <ChevronLeft size={20} />
        </button>

        <div className={styles.collapsedIcon} aria-hidden>
          <BookOpen size={20} />
        </div>

        {citations.length > 0 && (
          <div className={styles.collapsedBadge} aria-live="polite">
            {citations.length}
          </div>
        )}
      </aside>
    );
  }

  // --- 完整视图（无引用）
  if (citations.length === 0) {
    return (
      <aside className={`${styles.citationPanel} glass-liquid`} aria-label="引用来源">
        <div className={styles.header}>
          <BookOpen size={16} aria-hidden />
          <span className={styles.titleText}>引用来源</span>
          <button
            className={styles.collapseBtn}
            onClick={onToggle}
            title="收起"
            aria-label="收起引用面板"
          >
            <ChevronRight size={16} />
          </button>
        </div>

        <div className={styles.emptyState}>
          <BookOpen size={48} className={styles.emptyIcon} aria-hidden />
          <p>暂无引用</p>
        </div>
      </aside>
    );
  }

  // --- 有引用时的完整渲染 ---
  return (
    <aside className={`${styles.citationPanel} glass-liquid`} aria-label="引用来源">
      <div className={styles.header}>
        <BookOpen size={16} aria-hidden />
        <span className={styles.titleText}>引用来源</span>

        <div className={styles.badge} aria-hidden>
          {citations.length}
        </div>

        <button
          className={styles.collapseBtn}
          onClick={onToggle}
          title="收起"
          aria-label="收起引用面板"
        >
          <ChevronRight size={16} />
        </button>
      </div>

      <div className={styles.citationList} role="list">
        {citations.map((citation, index) => {
          const key = makeKey(citation, index);
          const isExpanded = expandedSet.has(key);
          const description = citation.description ?? '';
          const shouldTruncate = description.length > 220; // 超长收起
          const visibleDesc =
            isExpanded || !shouldTruncate ? description : `${description.slice(0, 220)}…`;

          return (
            <article
              key={key}
              className={styles.citationCard}
              role="listitem"
              aria-label={`引用 ${index + 1}`}
            >
              <div className={styles.citationHeader}>
                <span className={styles.citationIndex}>[{index + 1}]</span>
              </div>

              <div className={styles.citationContent}>
                <h4 className={styles.citationTitle} title={citation.title || citation.name || ''}>
                  {citation.title || citation.name || `来源 ${index + 1}`}
                </h4>

                {description ? (
                  <p className={styles.citationDesc}>
                    {visibleDesc}
                    {shouldTruncate && (
                      <button
                        className={styles.expandDescBtn}
                        onClick={() => toggleExpand(key)}
                        aria-expanded={isExpanded}
                        aria-controls={`desc-${key}`}
                        title={isExpanded ? '折叠描述' : '展开完整描述'}
                      >
                        {isExpanded ? '收起' : '展开'}
                      </button>
                    )}
                  </p>
                ) : null}

                <div className={styles.linkRow}>
                  {citation.url ? (
                    <a
                      href={citation.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={styles.citationLink}
                      title="在新标签页中打开链接"
                    >
                      <ExternalLink size={12} />
                      查看详情
                    </a>
                  ) : null}

                  {citation.url ? (
                    <button
                      className={styles.copyBtn}
                      onClick={() => copyToClipboard(citation.url, key)}
                      title="复制链接"
                      aria-label="复制链接"
                    >
                      <Copy size={12} />
                      {copiedKey === key ? '已复制' : '复制链接'}
                    </button>
                  ) : null}
                </div>
              </div>
            </article>
          );
        })}
      </div>
    </aside>
  );
}

CitationPanel.propTypes = {
  collapsed: PropTypes.bool,
  onToggle: PropTypes.func.isRequired,
};
