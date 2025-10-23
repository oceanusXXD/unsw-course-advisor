// src/components/LeftPanel/BottomPanelLoggedOut.tsx

import React from "react";
import { FiUser } from "react-icons/fi";

interface Props {
    onOpenAuth: () => void;
}

const BottomPanelLoggedOut: React.FC<Props> = ({ onOpenAuth }) => {
    return (
        <div className="flex flex-col gap-2">
            <button
                onClick={onOpenAuth}
                className="w-full py-2.5 px-3 bg-yellow-400 text-black font-semibold rounded-xl hover:bg-yellow-500 transition text-sm"
                aria-label="登录或注册"
            >
                登录 / 注册
            </button>
            <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
                <FiUser /> <span>或继续匿名使用，功能受限</span>
            </div>
        </div>
    );
};

export default BottomPanelLoggedOut;