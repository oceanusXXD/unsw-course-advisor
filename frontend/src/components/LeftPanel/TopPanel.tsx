// TopPanel.tsx
import React from "react";
import { VscLayoutSidebarLeft, VscLayoutSidebarLeftOff } from "react-icons/vsc";

interface Props {
    isOpen: boolean;
    togglePanel: () => void;
    /** 标题与副标题允许自定义，若不传使用默认文本 */
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
            className={`flex-shrink-0 w-full h-16 flex items-center transition-all duration-300 ease-in-out px-4 ${isOpen ? "justify-between" : "justify-center"
                }`}
            role="banner"
        >
            {/* 左侧：logo 与 标题（仅在展开时显示） */}
            {isOpen ? (
                <div className="flex items-center gap-3">
                    <div
                        className="w-12 h-12 rounded-full bg-gradient-to-br from-teal-400 to-cyan-400 flex items-center justify-center text-white font-bold text-lg"
                        aria-hidden
                    >
                        C
                    </div>

                    <div className="leading-tight">
                        <div className="text-sm font-bold text-gray-800">{title}</div>
                        <div className="text-xs text-gray-500">{subtitle}</div>
                    </div>
                </div>
            ) : (
                // 折叠时不渲染任何左侧内容，保证折叠下只有按钮（居中显示）
                <div />
            )}

            {/* 右侧：折叠/展开按钮（折叠时仍然可见） */}
            <div className="flex items-center">
                <button
                    onClick={(e) => {
                        e.stopPropagation();
                        togglePanel();
                    }}
                    className="p-2 rounded-full hover:bg-gray-100 transition"
                    title={isOpen ? "Collapse" : "Expand"}
                    aria-label={isOpen ? "Collapse sidebar" : "Expand sidebar"}
                >
                    {isOpen ? <VscLayoutSidebarLeftOff size={20} /> : <VscLayoutSidebarLeft size={20} />}
                </button>
            </div>
        </div>
    );
};

export default TopPanel;
