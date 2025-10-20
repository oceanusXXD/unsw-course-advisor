// src/components/InputPanel/InputPanel.tsx
import React, { useState } from "react";

interface InputPanelProps {
  onSearch?: (q: string) => void;
  onSubmit?: () => void;
  isLoading?: boolean;
  onStop?: () => void;
  /** 外部强制错误提示（一般无需传） */
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

  // 统一控制错误状态：外部 or 内部
  const effectiveError = hasError || localError;

  const handleSubmit = () => {
    if (isLoading) {
      onStop?.();
      return;
    }

    if (!query.trim()) {
      // 空输入 → 显示错误
      setLocalError(true);
      setIsFocused(false); // ✅ 强制失焦，立刻触发红框样式
      return;
    }

    // 正常提交逻辑
    onSearch?.(query.trim());
    onSubmit?.();
    setQuery("");
    setLocalError(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !isLoading) {
      handleSubmit();
    }
  };

  // --- 样式逻辑 ---
  const containerBaseClass = `relative flex items-center self-stretch py-3 px-4 rounded-3xl transition-all duration-300`;

  // 🔧 优先级调整：error > focus
  let containerStyle: React.CSSProperties = {};
  if (effectiveError) {
    containerStyle = {
      border: "2px solid rgba(239,68,68,0.5)",
      boxShadow:
        "0 6px 18px rgba(239,68,68,0.08), 0 0 0 5px rgba(254,226,226,0.4)",
      animation: "shake 600ms ease",
    };
  } else if (isFocused) {
    containerStyle = {
      backgroundImage:
        "linear-gradient(white, white), linear-gradient(135deg, #3B82F6, #8B5CF6, #EC4899)",
      backgroundOrigin: "border-box",
      backgroundClip: "padding-box, border-box",
      border: "2px solid transparent",
      boxShadow: "0 0 0 3px rgba(147,197,253,0.3)",
    };
  } else {
    containerStyle = {
      border: "2px solid #E5E7EB",
    };
  }

  const containerFocusClass =
    effectiveError ? "bg-white" : isFocused ? "bg-white" : "bg-gray-50";

  // --- 抖动动画 keyframes ---
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
        {/* 🔍 搜索图标 */}
        <svg
          width="18"
          height="18"
          viewBox="0 0 18 18"
          fill="none"
          className="mr-3 flex-shrink-0"
        >
          <path
            d="M8 14C11.3137 14 14 11.3137 14 8C14 4.68629 11.3137 2 8 2C4.68629 2 2 4.68629 2 8C2 11.3137 4.68629 14 8 14Z"
            stroke={
              effectiveError
                ? "#EF4444"
                : isFocused
                  ? "#8B5CF6"
                  : "#9CA3AF"
            }
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M16 16L13.85 13.85"
            stroke={
              effectiveError
                ? "#EF4444"
                : isFocused
                  ? "#8B5CF6"
                  : "#9CA3AF"
            }
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>

        {/* ✏️ 输入框 */}
        <input
          placeholder="Search by keyword, goal, or question..."
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            if (localError && e.target.value.trim()) setLocalError(false);
          }}
          onKeyDown={handleKeyDown}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          disabled={isLoading}
          className={`flex-1 text-base bg-transparent border-0 outline-none placeholder:text-gray-400 disabled:text-gray-500 disabled:placeholder:text-gray-300
            ${effectiveError
              ? "placeholder:text-red-300 text-red-700"
              : "text-black"
            }
          `}
          style={{
            caretColor: effectiveError ? "#B91C1C" : undefined,
          }}
        />

        {/* 🚀 提交/停止按钮 */}
        <button
          onMouseDown={(e) => e.preventDefault()} // ✅ 防止失焦
          onClick={handleSubmit}
          className={`flex items-center justify-center w-9 h-9 ml-2 rounded-2xl flex-shrink-0 transition-all duration-200 ${isLoading
              ? "bg-red-100 hover:bg-red-200"
              : "bg-gradient-to-r from-blue-500 to-purple-500 hover:shadow-md"
            }`}
          aria-label={isLoading ? "Stop generating" : "Submit search"}
        >
          {isLoading ? (
            <span className="text-sm font-bold text-red-600">■</span>
          ) : (
            <svg
              width="18"
              height="18"
              viewBox="0 0 18 18"
              fill="none"
              className="text-white"
            >
              <path d="M2 9L16 2V16L2 9Z" fill="currentColor" />
            </svg>
          )}
        </button>
      </div>
    </>
  );
};

export default InputPanel;
