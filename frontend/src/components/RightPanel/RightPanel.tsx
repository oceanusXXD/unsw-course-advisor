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
    // [!!] Updated dark mode background
    <div className="flex flex-col h-full bg-white dark:bg-neutral-900 w-full">
      <div className="flex-1 overflow-y-auto p-3">
        {results.length === 0 ? (
          // [!!] Updated dark mode empty state text color
          <div className="text-center text-gray-500 dark:text-neutral-500 mt-10">暂无结果。</div>
        ) : (
          // 结果列表 (styles are handled within ResultCard)
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