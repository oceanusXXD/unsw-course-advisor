// src/components/Chat/EmptyState.tsx

import React from "react";
import { FiBookOpen } from "react-icons/fi";

const EmptyState: React.FC = () => {
  return (
    <div className="flex flex-col items-center justify-start text-center p-8 pt-24 animate-fadeIn">
      <FiBookOpen className="w-20 h-20 mb-6 text-yellow-500" />

      <h1 className="text-4xl font-bold mb-4">
        <span className="
          bg-gradient-to-r from-yellow-400 to-red-600 
          dark:from-yellow-400 dark:to-red-500
          bg-clip-text text-transparent 
          animate-gradient bg-300%
        ">
          Welcome to UNSW Course Advisor
        </span>
      </h1>

      <p className="text-lg text-gray-500 dark:text-neutral-400">
        Ask me anything about courses, degrees, or prerequisites.
      </p>

    </div>
  );
};

export default EmptyState;