// src/components/LeftPanel/BottomPanelUserMenu.tsx

import React from "react";
import {
    FiSettings,
    FiLogOut,
    FiKey,
    FiHelpCircle,
} from "react-icons/fi";
import { AuthUser } from "./BottomPanelTypes";
import { ActiveMenu } from "./BottomPanelUserProfileMenu";
import { useAppContext } from "../../../context/AppContext";

interface Props {
    user: AuthUser;
    logout: () => Promise<void>;
    setActiveMenu: (menu: ActiveMenu) => void;
}

const BottomPanelUserMenu: React.FC<Props> = ({ user, logout, setActiveMenu }) => {
    const { navigateTo } = useAppContext();

    const handleLogout = async () => {
        if (window.confirm("确定要登出吗?")) {
            try {
                await logout();
                setActiveMenu(null);
            } catch (err) {
                console.error("Logout failed:", err);
            }
        }
    };

    const handleSettingsClick = () => {
        setActiveMenu(null);
        navigateTo("settings");
    };

    return (
        <div
            // [!! 修正] 统一深色背景
            className="absolute bottom-16 left-0 w-64 bg-white dark:bg-neutral-900 shadow-xl rounded-2xl border border-gray-100 dark:border-neutral-700 overflow-hidden animate-fadeIn z-50"
            role="menu"
        >
            <div className="px-4 py-3 border-b border-gray-100 dark:border-neutral-700">
                <div className="text-sm font-medium text-gray-800 dark:text-gray-100 truncate">
                    {user.email}
                </div>
            </div>

            <div className="flex flex-col text-sm text-gray-700 dark:text-gray-300">
                {/* 1. 激活许可证 */}
                <button
                    onClick={() => setActiveMenu("license")}
                    // [!! 修正] 亮色悬停改为 yellow
                    className="flex items-center gap-3 px-4 py-2.5 hover:bg-yellow-100 dark:hover:bg-neutral-800 transition text-left"
                >
                    <FiKey className="text-gray-500 dark:text-gray-400" />
                    激活许可证
                </button>

                {/* 2. 设置按钮 */}
                <button
                    onClick={handleSettingsClick}
                    // [!! 修正] 亮色悬停改为 yellow
                    className="flex items-center gap-3 px-4 py-2.5 hover:bg-yellow-100 dark:hover:bg-neutral-800 transition text-left"
                >
                    <FiSettings className="text-gray-500 dark:text-gray-400" />
                    设置
                </button>

                <div className="border-t border-gray-100 dark:border-neutral-700 my-1"></div>

                {/* 3. 帮助按钮 */}
                <button
                    onClick={() => setActiveMenu("help")}
                    // [!! 修正] 亮色悬停改为 yellow
                    className="flex items-center gap-3 px-4 py-2.5 hover:bg-yellow-100 dark:hover:bg-neutral-800 transition text-left"
                >
                    <FiHelpCircle className="text-gray-500 dark:text-gray-400" />
                    帮助
                </button>

                {/* 4. 登出按钮 (保持红色 - UX 规范) */}
                <button
                    onClick={handleLogout}
                    className="flex items-center gap-3 px-4 py-2.5 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 transition text-left"
                >
                    <FiLogOut />
                    登出
                </button>
            </div>
        </div>
    );
};

export default BottomPanelUserMenu;