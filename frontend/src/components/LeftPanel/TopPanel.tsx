import React from "react";
import { VscLayoutSidebarLeft, VscLayoutSidebarLeftOff } from "react-icons/vsc";

interface Props {
    isOpen: boolean;
    togglePanel: () => void;
    title?: string;
    subtitle?: string;
}

const TopPanel: React.FC<Props> = ({
    isOpen,
    togglePanel,
    title = "Course Advisor",
    subtitle = "",
}) => {
    return (
        <div
            className={`flex-shrink-0 w-full h-16 flex items-center relative px-4`}
            role="banner"
        >
            {/* 左侧 Logo 和 标题 */}
            <div
                className={`flex items-center gap-3 transition-all duration-300 ease-in-out`}
                style={{
                    opacity: isOpen ? 1 : 0,
                    transform: isOpen ? "translateX(0)" : "translateX(-4px)",
                    pointerEvents: isOpen ? "auto" : "none",
                }}
            >
                <div
                    className="w-12 h-12 rounded-full bg-gradient-to-br from-yellow-400 to-yellow-500 
                    flex items-center justify-center text-black font-bold text-lg flex-shrink-0"
                    aria-hidden
                >
                    C
                </div>
                <div className="leading-tight overflow-hidden whitespace-nowrap">
                    <div className="text-sm font-bold text-gray-800 dark:text-neutral-100">
                        {title}
                    </div>
                    <div className="text-xs text-gray-500 dark:text-neutral-400">
                        {subtitle}
                    </div>
                </div>
            </div>

            {/* 折叠/展开按钮 */}
            <div
                className={`absolute top-1/2 -translate-y-1/2 transition-all duration-300 ease-in-out ${isOpen ? "right-4" : "left-1/2 -translate-x-1/2"
                    }`}
            >
                <button
                    onClick={(e) => {
                        e.stopPropagation();
                        togglePanel();
                    }}
                    className="p-2 rounded-full hover:bg-yellow-100 dark:hover:bg-neutral-800 transition text-gray-700 dark:text-neutral-300"
                    title={isOpen ? "Collapse" : "Expand"}
                    aria-label={isOpen ? "Collapse sidebar" : "Expand sidebar"}
                >
                    {isOpen ? (
                        <VscLayoutSidebarLeftOff size={20} />
                    ) : (
                        <VscLayoutSidebarLeft size={20} />
                    )}
                </button>
            </div>
        </div>
    );
};

export default TopPanel;
