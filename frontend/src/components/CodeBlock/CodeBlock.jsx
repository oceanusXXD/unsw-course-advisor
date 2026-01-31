// src/components/CodeBlock/CodeBlock.jsx
import React, { useState, useMemo, useEffect } from 'react';
import styles from './CodeBlock.module.scss';
import { Copy, Check, ChevronDown, ChevronUp } from 'lucide-react';

export default function CodeBlock({
  inline,
  className,
  children,
  node,
  longThreshold = 15,
  copiedTimeout = 2000,
  ...props
}) {
  const [copied, setCopied] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const code = useMemo(() => String(children || ''), [children]);
  const isLong = useMemo(() => code.split('\n').length > longThreshold, [code, longThreshold]);

  useEffect(() => {
    let timer;
    if (copied) timer = setTimeout(() => setCopied(false), copiedTimeout);
    return () => clearTimeout(timer);
  }, [copied, copiedTimeout]);

  if (inline) {
    return (
      <code className={styles.inlineCode} {...props}>
        {children}
      </code>
    );
  }

  // 语言 + 元信息（支持 ```ts title="app.ts"）
  const lang = (className || '').replace('language-', '') || 'text';
  const meta = node?.meta || '';
  const titleMatch = meta?.match(/title="([^"]+)"|title=([^\s]+)/);
  const title = titleMatch ? titleMatch[1] || titleMatch[2] : '';

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
    } catch (err) {
      console.error('Copy failed:', err);
    }
  };

  return (
    <div className={`${styles.codeBlock} ${expanded ? styles.expanded : ''}`}>
      <div className={styles.header}>
        <div className={styles.titleWrap}>
          {title && <span className={styles.fileTitle}>{title}</span>}
          <span className={styles.lang}>{lang}</span>
        </div>
        <div className={styles.actions}>
          {isLong && (
            <button
              className={styles.actionBtn}
              onClick={() => setExpanded(!expanded)}
              aria-label={expanded ? '折叠代码' : '展开代码'}
            >
              {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
              {expanded ? '折叠' : '展开'}
            </button>
          )}
          <button className={styles.actionBtn} onClick={handleCopy} aria-label="复制代码">
            {copied ? <Check size={16} /> : <Copy size={16} />}
            {copied ? '已复制' : '复制'}
          </button>
        </div>
      </div>
      <pre className={styles.pre}>
        <code className={className} {...props}>
          {children}
        </code>
      </pre>
    </div>
  );
}
