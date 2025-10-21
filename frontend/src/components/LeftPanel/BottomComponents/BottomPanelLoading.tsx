// src/components/LeftPanel/BottomPanelLoading.tsx

import React from "react";

const BottomPanelLoading: React.FC = () => {
    return (
        <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-full bg-gray-100 dark:bg-gray-800 animate-pulse" />
            <div className="flex-1">
                <div className="h-4 bg-gray-100 dark:bg-gray-800 rounded w-3/4 animate-pulse mb-2" />
                <div className="h-3 bg-gray-100 dark:bg-gray-800 rounded w-1/2 animate-pulse" />
            </div>
        </div>
    );
};

export default BottomPanelLoading;