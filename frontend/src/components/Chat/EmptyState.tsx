// src/components/Chat/EmptyState.tsx

import React from "react";
// [!! 助手更改] 1. 切换到一个更中性的“书本”图标
import { FiBookOpen } from "react-icons/fi";

const EmptyState: React.FC = () => {
  return (
    // [!! 助手更改] 2. 布局调整：
    // - 移除了 min-h-[50vh]
    // - 将 justify-center 改为 justify-start (顶部对齐)
    // - 添加 pt-24 (上内边距) 来定位，使其不会离输入框太远
    <div className="flex flex-col items-center justify-start text-center p-8 pt-24 animate-fadeIn">

      {/* [!! 助手更改] 3. 图标和颜色：
          - 使用新图标 FiBookOpen
          - 颜色改为 UNSW 的标志性黄色 (Tailwind 的 yellow-400/500 很接近)
      */}
      <FiBookOpen className="w-20 h-20 mb-6 text-yellow-500" />

      <h1 className="text-4xl font-bold mb-4">
        {/*
          [!! 助手更改] 4. 渐变色：
          - 将渐变从 (青色->蓝色) 改为 (UNSW 黄色 -> UNSW 红色)
          - 我们使用 'animate-gradient' 和 'bg-300%' (这些已在 index.css 中)
        */}
        <span className="
          bg-gradient-to-r from-yellow-400 to-red-600 
          dark:from-yellow-400 dark:to-red-500
          bg-clip-text text-transparent 
          animate-gradient bg-300%
        ">
          Welcome to UNSW Course Advisor
        </span>
      </h1>

      {/* 副标题保持不变 */}
      <p className="text-lg text-gray-500 dark:text-neutral-400">
        Ask me anything about courses, degrees, or prerequisites.
      </p>

    </div>
  );
};

export default EmptyState;