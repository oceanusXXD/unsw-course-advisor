// src/components/LeftPanel/HelpPopover.tsx

import React, { useState } from "react";
import {
    FiArrowLeft,
    FiExternalLink,
    FiChevronDown,
    FiMail,
    FiMessageSquare
} from "react-icons/fi";
import { ActiveMenu } from "./BottomComponents/BottomPanelUserProfileMenu";

interface Props {
    setActiveMenu: (menu: ActiveMenu) => void;
}

type HelpView = "main" | "faq";

const HelpPopover: React.FC<Props> = ({ setActiveMenu }) => {

    const [view, setView] = useState<HelpView>("main");

    const renderFaqView = () => (
        <>
            {/* 1. FAQ 视图头部*/}
            <div className="flex items-center gap-2 p-3 border-b border-gray-100 dark:border-gray-700 flex-shrink-0">
                <button
                    onClick={() => setView("main")}
                    className="p-1 rounded-full hover:bg-yellow-100 dark:hover:bg-neutral-800"
                    aria-label="返回帮助菜单"
                >
                    <FiArrowLeft className="text-gray-600 dark:text-gray-400" />
                </button>
                <h4 className="text-sm font-semibold text-gray-800 dark:text-gray-100">
                    常见问题 (FAQ)
                </h4>
            </div>

            {/* 2. FAQ 内容*/}
            <div className="flex-1 overflow-y-auto p-4 space-y-3 text-sm text-gray-700 dark:text-gray-300">

                <details className="group border-b border-gray-200 dark:border-gray-700 pb-2">
                    <summary className="flex items-center justify-between cursor-pointer list-none hover:text-gray-900 dark:hover:text-gray-100">
                        <span className="font-medium">如何激活我的许可证？</span>
                        <FiChevronDown className="text-gray-500 group-open:rotate-180 transition-transform" />
                    </summary>
                    <p className="mt-2 text-xs text-gray-600 dark:text-gray-400 leading-relaxed">
                        您可以在用户菜单中点击 "激活许可证"。如果您还没有许可证，可以选择 "创建新许可证" 来获取一个试用版。如果您已经购买了密钥，可以选择 "使用已有密钥" 来验证它。
                    </p>
                </details>

                <details className="group border-b border-gray-200 dark:border-gray-700 pb-2">
                    <summary className="flex items-center justify-between cursor-pointer list-none hover:text-gray-900 dark:hover:text-gray-100">
                        <span className="font-medium">如何修改我的密码？</span>
                        <FiChevronDown className="text-gray-500 group-open:rotate-180 transition-transform" />
                    </summary>
                    <p className="mt-2 text-xs text-gray-600 dark:text-gray-400 leading-relaxed">
                        请在用户菜单中点击 "设置"，在 "安全" 部分，您可以输入您的旧密码和新密码来完成修改。
                    </p>
                </details>

                <details className="group border-b border-gray-200 dark:border-gray-700 pb-2">
                    <summary className="flex items-center justify-between cursor-pointer list-none hover:text-gray-900 dark:hover:text-gray-100">
                        <span className="font-medium">User Key 是什么？</span>
                        <FiChevronDown className="text-gray-500 group-open:rotate-180 transition-transform" />

                    </summary>
                    <p className="mt-2 text-xs text-gray-600 dark:text-gray-400 leading-relaxed">
                        `User Key` 是一个只在您**创建**许可证时显示一次的高度敏感密钥。它用于解密您账户下的特定内容（如加密文件）。请务必将其保存在安全的地方，我们不会再次显示它。
                    </p>
                </details>

            </div>
        </>
    );

    const renderMainView = () => (
        <>
            {/* 1. 头部 */}
            <div className="flex items-center gap-2 p-3 border-b border-gray-100 dark:border-gray-700 flex-shrink-0">
                <button
                    onClick={() => setActiveMenu("main")}
                    className="p-1 rounded-full hover:bg-yellow-100 dark:hover:bg-neutral-800"
                    aria-label="返回主菜单"
                >
                    <FiArrowLeft className="text-gray-600 dark:text-gray-400" />
                </button>
                <h4 className="text-sm font-semibold text-gray-800 dark:text-gray-100">
                    帮助
                </h4>
            </div>

            {/* 2. 内容区域*/}
            <div className="flex-1 flex-col text-sm text-gray-700 dark:text-gray-300 p-4 space-y-4">

                {/* 选项 1: FAQ */}
                <button
                    onClick={() => setView("faq")}
                    // [!! 修正] 亮色悬停改为 yellow
                    className="flex items-center justify-between gap-3 px-3 py-2.5 hover:bg-yellow-100 dark:hover:bg-neutral-800 transition text-left rounded-lg border border-gray-200 dark:border-gray-700 w-full"
                >
                    <span className="flex items-center gap-3 font-medium">
                        <FiMessageSquare className="text-gray-500 dark:text-gray-400" />
                        常见问题 (FAQ)
                    </span>
                    <FiChevronDown className="text-gray-500 -rotate-90" />
                </button>

                {/* 选项 2: 联系支持 */}
                <div className="p-3 rounded-lg border border-gray-200 dark:border-gray-700 space-y-2">
                    <h5 className="font-medium flex items-center gap-3">
                        <FiMail className="text-gray-500 dark:text-gray-400" />
                        Route (GET)
                        联系支持
                    </h5>
                    <p className="text-xs text-gray-600 dark:text-gray-400">
                        如果遇到无法解决的问题，请联系我们：
                    </p>
                    <a
                        href="mailto:support@test.com"
                        className="flex items-center justify-between gap-3 px-3 py-2 bg-yellow-50 dark:bg-yellow-900/30 hover:bg-yellow-100 dark:hover:bg-yellow-900/50 transition rounded-md text-yellow-600 dark:text-yellow-400 text-xs font-medium"
                    >
                        support@test.com
                        <FiExternalLink size={14} />
                    </a>
                </div>

            </div>
        </>
    );

    return (
        <div
            className="absolute bottom-16 left-0 w-72 bg-white dark:bg-neutral-900 shadow-xl rounded-2xl border border-gray-100 dark:border-gray-700 overflow-hidden animate-fadeIn z-50 flex flex-col"
            role="menu"
            style={{ maxHeight: "70vh" }}
        >
            {view === "main" ? renderMainView() : renderFaqView()}

        </div>
    );
};

export default HelpPopover;