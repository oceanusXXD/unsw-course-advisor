import React, { useState } from "react";
import { ResultCardsList, CourseData } from "./ResultCard";

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
    <div className="flex flex-col h-full bg-white dark:bg-neutral-900 w-full">
      <div className="flex-1 overflow-y-auto p-3">
        {results.length === 0 ? (
          <div className="text-center text-gray-500 dark:text-neutral-500 mt-10">暂无结果。</div>
        ) : (
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