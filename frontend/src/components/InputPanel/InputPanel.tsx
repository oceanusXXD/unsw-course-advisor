// [!! 助手更改] 1. 导入 useRef (保持不变)
import React, { useState, useEffect, useRef } from "react";

interface InputPanelProps {
  onSearch?: (q: string) => void;
  onSubmit?: () => void;
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
    if (!query.trim()) {
      setLocalError(true);
      setIsFocused(false);
      return;
    }
    onSearch?.(query.trim());
    onSubmit?.();
    setQuery("");
    setLocalError(false);
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

  // [!! 助手更改] 2. 为“上传”按钮创建点击处理程序
  const handleUploadClick = () => {
    console.log("点击成功");
    // 你可以在这里实现未来的文件上传逻辑
  };

  // === 样式逻辑 (保持不变) ===
  const containerBaseClass =
    "relative flex items-end self-stretch py-3 px-4 rounded-3xl transition-all duration-300";

  const darkBg = "#262626";
  const lightBg = "white";
  const darkBorder = "#404040";
  const lightBorder = "#E5E7EB";

  let containerStyle: React.CSSProperties = {};
  if (effectiveError) {
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
    (effectiveError ? "bg-white" : isFocused ? "bg-white" : "bg-gray-50") +
    " dark:bg-neutral-800";

  const defaultStroke = isDark ? "#a3a3a3" : "#9CA3AF";

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
        {/* [!! 助手更改] 3. 替换为 +号 上传按钮 */}
        <button
          type="button"
          onClick={handleUploadClick}
          onMouseDown={(e) => e.preventDefault()} // 
          disabled={isLoading}
          className="mr-3 flex-shrink-0 mb-1.5 p-1 rounded-full hover:bg-gray-100 dark:hover:bg-neutral-700 transition-colors duration-150"
          aria-label="Upload file"
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 18 18"
            fill="none"
          >
            <path
              d="M9 3.75V14.25"
              stroke={
                effectiveError ? "#EF4444" : isFocused ? "#F59E0B" : defaultStroke
              }
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <path
              d="M3.75 9H14.25"
              stroke={
                effectiveError ? "#EF4444" : isFocused ? "#F59E0B" : defaultStroke
              }
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>

        {/* ✏️ 多行输入框 (保持不变) */}
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
                      ${effectiveError
              ? "placeholder:text-red-300 dark:placeholder:text-red-500/70 text-red-700 dark:text-red-300"
              : "text-black dark:text-neutral-100"
            }`}
          style={{
            caretColor: effectiveError
              ? "#B91C1C"
              : isFocused
                ? "#F59E0B"
                : isDark
                  ? "#e5e5e5"
                  : undefined,
          }}
        />

        {/* 🚀 提交/停止按钮 (保持不变) */}
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
      </div >
    </>
  );
};

export default InputPanel;