// src/components/RightPanel/RightPanel.tsx
import React, { useState } from "react";
import { ResultCardsList, CourseData } from "./ResultCard";

// 重新导出类型供 App.tsx 使用
export { type CourseData as ResultItem };

interface RightPanelProps {
  results: CourseData[];
}

const RightPanel: React.FC<RightPanelProps> = ({ results }) => {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const handleCardClick = (id: string) => {
    setExpandedId((prev) => (prev === id ? null : id));
  };

  return (
    // 侧边栏面板容器
    <div className="flex flex-col h-full bg-white w-full">
      <div className="flex-1 overflow-y-auto p-3">
        {results.length === 0 ? (
          // 空状态
          <div className="text-center text-gray-500 mt-10">暂无结果。</div>
        ) : (
          // 结果列表
          <ResultCardsList
            courses={results}
            expandedId={expandedId}
            onCardClick={handleCardClick}
          />
        )}
      </div>
    </div>
  );
};

export default RightPanel;