import React, { useState, useEffect, useRef } from "react";
import { useFileUpload } from '../hooks/useFileUpload';
import { UploadButton } from './UploadButton';
import { FilePreviewList } from './FilePreviewList';

interface InputPanelProps {
  onSearch?: (q: string) => void;
  onSubmit?: (files?: File[]) => void;
  isLoading?: boolean;
  onStop?: () => void;
  hasError?: boolean;
}

const InputPanel: React.FC<InputPanelProps> = ({
  onSearch,
  onSubmit,
  isLoading = false,
  onStop,
  hasError = false,
}) => {
  const [query, setQuery] = useState("");
  const [isFocused, setIsFocused] = useState(false);
  const [localError, setLocalError] = useState(false);
  const effectiveError = hasError || localError;

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [isDark, setIsDark] = useState(false);

  // 使用文件上传 hook
  const {
    uploadedFiles,
    errors: uploadErrors,
    fileInputRef,
    handleFiles,
    removeFile,
    clearFiles,
    openFilePicker,
  } = useFileUpload({
    maxFiles: 5,
    maxSize: 10 * 1024 * 1024,
    acceptedTypes: ['image/*', 'application/pdf', '.txt', '.doc', '.docx'],
  });

  useEffect(() => {
    const checkDarkMode = () =>
      setIsDark(document.documentElement.classList.contains("dark"));
    checkDarkMode();
    const observer = new MutationObserver(checkDarkMode);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class"],
    });
    return () => observer.disconnect();
  }, []);

  const adjustTextareaHeight = () => {
    if (textareaRef.current) {
      const el = textareaRef.current;
      el.style.height = "auto";
      const maxHeight = 120;

      if (el.scrollHeight <= maxHeight) {
        el.style.height = `${el.scrollHeight}px`;
        el.style.overflowY = "hidden";
      } else {
        el.style.height = `${maxHeight}px`;
        el.style.overflowY = "auto";
      }
    }
  };

  useEffect(() => {
    adjustTextareaHeight();
  }, [query]);

  const handleSubmit = () => {
    if (isLoading) {
      onStop?.();
      return;
    }
    if (!query.trim() && uploadedFiles.length === 0) {
      setLocalError(true);
      setIsFocused(false);
      return;
    }

    onSearch?.(query.trim());
    onSubmit?.(uploadedFiles.map(f => f.file));

    setQuery("");
    setLocalError(false);
    clearFiles();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !isLoading) {
      if (e.shiftKey) {
        e.preventDefault();
        const target = e.target as HTMLTextAreaElement;
        const { selectionStart, selectionEnd } = target;
        const newValue =
          query.substring(0, selectionStart) +
          "\n" +
          query.substring(selectionEnd);

        setQuery(newValue);

        setTimeout(() => {
          target.selectionStart = target.selectionEnd = selectionStart + 1;
        }, 0);
      } else {
        e.preventDefault();
        handleSubmit();
      }
    }
  };

  const containerBaseClass =
    "relative flex flex-col self-stretch py-3 px-4 rounded-3xl transition-all duration-300";

  const darkBg = "#262626";
  const lightBg = "white";
  const darkBorder = "#404040";
  const lightBorder = "#E5E7EB";

  let containerStyle: React.CSSProperties = {};
  if (effectiveError || uploadErrors.length > 0) {
    containerStyle = {
      border: "2px solid rgba(239,68,68,0.5)",
      boxShadow: isDark
        ? "0 6px 18px rgba(239,68,68,0.08), 0 0 0 5px rgba(153, 27, 27, 0.4)"
        : "0 6px 18px rgba(239,68,68,0.08), 0 0 0 5px rgba(254,226,226,0.4)",
      animation: "shake 600ms ease",
    };
  } else if (isFocused) {
    containerStyle = {
      backgroundImage: isDark
        ? `linear-gradient(${darkBg}, ${darkBg}), linear-gradient(135deg, #FCD34D, #DA291C)`
        : `linear-gradient(${lightBg}, ${lightBg}), linear-gradient(135deg, #FCD34D, #DA291C)`,
      backgroundOrigin: "border-box",
      backgroundClip: "padding-box, border-box",
      border: "2px solid transparent",
      boxShadow: isDark
        ? "0 0 0 3px rgba(252, 211, 77, 0.3)"
        : "0 0 0 3px rgba(252, 211, 77, 0.3)",
    };
  } else {
    containerStyle = {
      border: `2px solid ${isDark ? darkBorder : lightBorder}`,
    };
  }

  const containerFocusClass =
    (effectiveError || uploadErrors.length > 0 ? "bg-white" : isFocused ? "bg-white" : "bg-gray-50") +
    " dark:bg-neutral-800";

  const shakeKeyframes = `
@keyframes shake {
0% { transform: translateX(0); }
10% { transform: translateX(-8px); }
30% { transform: translateX(8px); }
50% { transform: translateX(-6px); }
70% { transform: translateX(6px); }
90% { transform: translateX(-2px); }
100% { transform: translateX(0); }
}
`;

  return (
    <>
      <style>{shakeKeyframes}</style>

      <div
        className={`${containerBaseClass} ${containerFocusClass}`}
        style={containerStyle}
      >
        {/* 文件预览列表 */}
        <FilePreviewList
          files={uploadedFiles}
          onRemove={removeFile}
          isDark={isDark}
        />

        {/* 错误提示 */}
        {uploadErrors.length > 0 && (
          <div className="mb-2 text-sm text-red-600 dark:text-red-400">
            {uploadErrors.map((err, i) => (
              <div key={i}>{err.file}: {err.message}</div>
            ))}
          </div>
        )}

        {/* 输入区域 */}
        <div className="flex items-end">
          <UploadButton
            onClick={openFilePicker}
            disabled={isLoading}
            isError={effectiveError || uploadErrors.length > 0}
            isFocused={isFocused}
            isDark={isDark}
          />

          {/* 隐藏的文件输入 */}
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept="image/*,.pdf,.txt,.doc,.docx"
            onChange={(e) => handleFiles(e.target.files)}
            className="hidden"
          />

          <textarea
            ref={textareaRef}
            placeholder="Ask about courses (Shift + Enter for new line)"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              if (localError && e.target.value.trim()) setLocalError(false);
            }}
            onKeyDown={handleKeyDown}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            disabled={isLoading}
            rows={1}
            className={`flex-1 resize-none text-base bg-transparent border-0 outline-none 
                        placeholder:text-gray-400 dark:placeholder:text-neutral-500
                        disabled:text-gray-500 disabled:placeholder:text-gray-300
                        dark:disabled:text-neutral-600 dark:disabled:placeholder:text-neutral-700
                        py-1.5 
                        ${effectiveError || uploadErrors.length > 0
                ? "placeholder:text-red-300 dark:placeholder:text-red-500/70 text-red-700 dark:text-red-300"
                : "text-black dark:text-neutral-100"
              }`}
            style={{
              caretColor: effectiveError || uploadErrors.length > 0
                ? "#B91C1C"
                : isFocused
                  ? "#F59E0B"
                  : isDark
                    ? "#e5e5e5"
                    : undefined,
            }}
          />

          <button
            onMouseDown={(e) => e.preventDefault()}
            onClick={handleSubmit}
            className={`flex items-center justify-center w-9 h-9 ml-2 rounded-2xl flex-shrink-0 transition-all duration-200 ${isLoading
              ? "bg-red-100 hover:bg-red-200 dark:bg-red-900/50 dark:hover:bg-red-900/70"
              : "bg-gradient-to-r from-yellow-400 to-red-600 hover:from-yellow-500 hover:to-red-700 hover:shadow-md dark:from-yellow-400 dark:to-red-500 dark:hover:from-yellow-500 dark:hover:to-red-600"
              }`}
          >
            {isLoading ? (
              <span className="text-sm font-bold text-red-600 dark:text-red-300">
                ■
              </span>
            ) : (
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="currentColor"
                className="text-white"
              >
                <path d="M3.478 2.405a.75.75 0 00-.926.94l2.432 7.905H13.5a.75.75 0 010 1.5H4.984l-2.432 7.905a.75.75 0 00.926.94 60.519 60.519 0 0018.445-8.986.75.75 0 000-1.218A60.517 60.517 0 003.478 2.405z" />
              </svg>
            )}
          </button>
        </div>
      </div>
    </>
  );
};

export default InputPanel;