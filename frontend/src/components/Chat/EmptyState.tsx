// src/components/Chat/EmptyState.tsx
import React from "react";

const EmptyState: React.FC = () => {
  return (
    <div className="text-center">
      <span className="text-black text-[32px] font-bold">
        Welcome to UNSW Course Advisor
      </span>
    </div>
  );
};

export default EmptyState;