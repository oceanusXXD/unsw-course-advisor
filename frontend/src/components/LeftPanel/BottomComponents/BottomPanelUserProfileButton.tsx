// src/components/LeftPanel/BottomPanelUserProfileButton.tsx

import React from "react";
import { AuthUser } from "./BottomPanelTypes";

interface Props {
    user: AuthUser;
    onClick: () => void;
}

// 获取用户姓名首字母
const getInitials = (name?: string | null, email?: string) => {
    if (name) {
        const parts = name.trim().split(" ");
        if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
        return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    }
    if (email) return email.slice(0, 2).toUpperCase();
    return "U";
};

const BottomPanelUserProfileButton: React.FC<Props> = ({ user, onClick }) => {
    return (
        <button
            onClick={onClick}
            // 亮色悬停改为 yellow
            className="flex items-center gap-3 w-full hover:bg-yellow-100 dark:hover:bg-neutral-800 p-2 rounded-xl transition"
            aria-label="打开用户菜单"
        >
            {user.avatarUrl ? (
                <img
                    src={user.avatarUrl}
                    alt={user.name ?? user.email}
                    className="w-11 h-11 rounded-full object-cover"
                />
            ) : (
                <div className="w-11 h-11 rounded-full bg-gradient-to-br from-yellow-400 to-yellow-500 flex items-center justify-center text-black font-bold text-base">
                    {getInitials(user.name, user.email)}
                </div>
            )}

            <div className="flex flex-col items-start text-left overflow-hidden">
                <div className="text-sm font-semibold text-gray-800 dark:text-gray-100 truncate">
                    {user.name ?? "User"}
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-400 truncate">
                    {(user.subscription ?? "FREE").toString().toUpperCase()} PLAN
                </div>
            </div>
        </button>
    );
};

export default BottomPanelUserProfileButton;