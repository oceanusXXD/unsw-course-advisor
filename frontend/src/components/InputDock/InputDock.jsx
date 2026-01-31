import React, { useEffect, useRef, useState, useCallback } from 'react';
import * as Tooltip from '@radix-ui/react-tooltip';
import styles from './InputDock.module.scss';
import '../../styles/glass.css';

import { Paperclip, Send, Square, FileText, X, Loader, Globe } from 'lucide-react';

function FilePreview({ file, onRemove, uploading = false }) {
  const isImage = file.type?.startsWith('image/');
  const isPDF = file.type === 'application/pdf';
  const isDoc = file.type?.includes('document') || file.type?.includes('word');

  const [preview, setPreview] = useState(null);

  useEffect(() => {
    if (isImage) {
      const reader = new FileReader();
      reader.onload = (e) => setPreview(e.target.result);
      reader.readAsDataURL(file);
    }
  }, [file, isImage]);

  return (
    <div className={`${styles.fileChip} ${uploading ? styles.uploading : ''}`}>
      {uploading && (
        <div className={styles.uploadProgress}>
          <Loader size={14} className={styles.spinner} />
        </div>
      )}

      <div className={styles.fileIcon}>
        {isImage && preview ? (
          <img src={preview} alt={file.name} className={styles.thumbnail} />
        ) : isPDF || isDoc ? (
          <FileText size={16} />
        ) : (
          <Paperclip size={16} />
        )}
      </div>

      <div className={styles.fileInfo}>
        <span className={styles.fileName}>{file.name}</span>
        <span className={styles.fileSize}>{formatFileSize(file.size)}</span>
      </div>

      <button className={styles.removeBtn} onClick={onRemove} aria-label="移除文件">
        <X size={14} />
      </button>
    </div>
  );
}

export default function InputDock({ onSend, onStop, generating, profileState = 'expanded' }) {
  const [value, setValue] = useState('');
  const [files, setFiles] = useState([]);
  const [focused, setFocused] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [webSearch, setWebSearch] = useState(false);

  const textareaRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    autoGrow();
  }, [value, files, focused, dragging]);

  function getLineHeight(el) {
    const cs = window.getComputedStyle(el);
    let lh = cs.lineHeight;
    if (lh === 'normal' || !lh) {
      const fs = parseFloat(cs.fontSize) || 15;
      return fs * 1.6;
    }
    return parseFloat(lh);
  }

  function centerFirstCharIfEmpty() {
    const el = textareaRef.current;
    if (!el) return;
    if (el.value.length === 0) {
      const height = el.clientHeight;
      const lineHeight = getLineHeight(el) || 28;
      const paddingTop = Math.max((height - lineHeight) / 2, 6);
      el.style.paddingTop = `${paddingTop}px`;
      el.style.paddingBottom = '6px';
    } else {
      el.style.paddingTop = '';
      el.style.paddingBottom = '';
    }
  }

  function autoGrow() {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    const lineHeight = getLineHeight(el) || 28;
    const maxLines = 5;
    const maxHeight = lineHeight * maxLines;
    const newHeight = Math.min(el.scrollHeight, maxHeight);
    el.style.height = newHeight + 'px';
    requestAnimationFrame(centerFirstCharIfEmpty);
  }

  // 使用 useCallback 包裹 handleSend，确保在 useEffect 中引用的是最新版本
  const handleSend = useCallback(
    (e, overrideText, extraMeta) => {
      e?.preventDefault();
      const text = (overrideText ?? value).trim();
      if (!text && files.length === 0) return;

      onSend?.(text, files, { webSearch, ...(extraMeta || {}) });

      setValue('');
      setFiles([]);

      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
        requestAnimationFrame(centerFirstCharIfEmpty);
      }
    },
    [value, files, webSearch, onSend],
  ); // 添加必要的依赖

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      if (e.shiftKey) {
        return;
      } else {
        if (!generating) {
          e.preventDefault();
          handleSend(e);
        }
      }
    }
  };

  const handleFileChange = (e) => {
    const newFiles = Array.from(e.target.files || []);
    setFiles((prev) => [...prev, ...newFiles.slice(0, 5 - prev.length)]);
  };

  const handlePaste = (e) => {
    const items = e.clipboardData?.items;
    if (!items) return;

    for (let item of items) {
      if (item.type.startsWith('image/')) {
        e.preventDefault();
        const file = item.getAsFile();
        if (file) setFiles((prev) => [...prev, file]);
      }
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const droppedFiles = Array.from(e.dataTransfer.files || []);
    setFiles((prev) => [...prev, ...droppedFiles.slice(0, 5 - prev.length)]);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setDragging(true);
  };

  const handleDragLeave = () => {
    setDragging(false);
  };

  const onFocus = () => {
    setFocused(true);
    requestAnimationFrame(centerFirstCharIfEmpty);
  };
  const onBlur = () => {
    setFocused(false);
    requestAnimationFrame(centerFirstCharIfEmpty);
  };

  const charCount = value.length;
  const maxChars = 4000;
  const nearLimit = charCount > maxChars * 0.9;

  // 监听来自 EmptyState 的"预设输入并发送"事件
  useEffect(() => {
    const quickSendListener = (e) => {
      const text = e?.detail?.text || '';
      const meta = e?.detail?.meta || {};
      if (!text) return;
      if (generating) return; // 正在生成时忽略，避免串台

      // 直接调用 onSend，避免闭包问题
      setValue(text);
      setFiles([]);

      // 更新 textarea 高度
      requestAnimationFrame(() => {
        if (textareaRef.current) {
          autoGrow();
          textareaRef.current.style.height = 'auto';
          centerFirstCharIfEmpty();
        }
      });

      // 直接调用 onSend 而不是通过 handleSend
      onSend?.(text, [], { webSearch, source: 'quick-send', ...meta });
    };

    window.addEventListener('app:quickSend', quickSendListener);
    return () => window.removeEventListener('app:quickSend', quickSendListener);
  }, [generating, webSearch, onSend]); // 确保依赖项正确

  return (
    <div
      className={`${styles.inputDock} ${styles[profileState]} glass-pill`}
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
    >
      <div
        className={`${styles.dock} ${focused ? styles.focused : ''} ${
          dragging ? styles.dragging : ''
        }`}
      >
        {dragging && (
          <div className={styles.dragOverlay}>
            <Paperclip size={32} />
            <span>释放以上传文件</span>
          </div>
        )}

        <div className={styles.leftTools}>
          <Tooltip.Provider delayDuration={300}>
            <Tooltip.Root>
              <Tooltip.Trigger asChild>
                <button
                  className={`${styles.toolBtn} ${files.length > 0 ? styles.active : ''}`}
                  onClick={() => fileInputRef.current?.click()}
                  aria-label="上传文件"
                >
                  <Paperclip size={20} />
                  {files.length > 0 && <span className={styles.toolBadge}>{files.length}</span>}
                </button>
              </Tooltip.Trigger>
              <Tooltip.Content className={`${styles.tooltip} glass-liquid`} side="top">
                上传文件
              </Tooltip.Content>
            </Tooltip.Root>

            <input
              ref={fileInputRef}
              type="file"
              multiple
              hidden
              accept="image/*,.pdf,.doc,.docx,.txt"
              onChange={handleFileChange}
            />
          </Tooltip.Provider>

          <Tooltip.Provider delayDuration={300}>
            <Tooltip.Root>
              <Tooltip.Trigger asChild>
                <button
                  className={`${styles.toolBtn} ${webSearch ? styles.active : ''}`}
                  onClick={() => setWebSearch(!webSearch)}
                  aria-label="联网搜索"
                >
                  <Globe size={20} />
                </button>
              </Tooltip.Trigger>
              <Tooltip.Content className={`${styles.tooltip} glass-liquid`} side="top">
                {webSearch ? '关闭联网搜索' : '启用联网搜索'}
              </Tooltip.Content>
            </Tooltip.Root>
          </Tooltip.Provider>
        </div>

        <div className={styles.inputArea}>
          {files.length > 0 && (
            <div className={styles.filePreviewArea}>
              {files.map((file, i) => (
                <FilePreview
                  key={i}
                  file={file}
                  onRemove={() => setFiles(files.filter((_, j) => i !== j))}
                />
              ))}
            </div>
          )}

          <textarea
            ref={textareaRef}
            className={styles.textarea}
            placeholder="有什么可以帮助您的？ (Shift+Enter 换行)"
            value={value}
            onChange={(e) => {
              setValue(e.target.value);
              if (e.target.value.length > 0 && textareaRef.current) {
                textareaRef.current.style.paddingTop = '';
                textareaRef.current.style.paddingBottom = '';
              }
            }}
            onFocus={onFocus}
            onBlur={onBlur}
            onPaste={handlePaste}
            onKeyDown={handleKeyDown}
            rows={1}
            aria-label="消息输入框"
            aria-multiline="true"
          />

          {focused && charCount > 0 && (
            <div className={`${styles.charCount} ${nearLimit ? styles.warning : ''}`}>
              {charCount} / {maxChars}
            </div>
          )}
        </div>

        <div className={styles.rightTools}>
          {!generating ? (
            <Tooltip.Provider>
              <Tooltip.Root>
                <Tooltip.Trigger asChild>
                  <button
                    className={`${styles.sendBtn} ${
                      !value.trim() && files.length === 0 ? styles.disabled : ''
                    }`}
                    onClick={(e) => handleSend(e)}
                    disabled={!value.trim() && files.length === 0}
                    aria-label="发送消息"
                  >
                    <Send size={20} />
                  </button>
                </Tooltip.Trigger>
                <Tooltip.Content className={`${styles.tooltip} glass-liquid`} side="top">
                  发送
                  <kbd className="kbd" style={{ marginLeft: 8 }}>
                    Enter
                  </kbd>
                </Tooltip.Content>
              </Tooltip.Root>
            </Tooltip.Provider>
          ) : (
            <button className={styles.stopBtn} onClick={onStop} aria-label="停止生成">
              <Square size={20} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}
