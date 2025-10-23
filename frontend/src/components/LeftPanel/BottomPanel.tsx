// src/components/LeftPanel/BottomPanel.tsx

import React from "react";
import { useAuth } from "../../context/AuthContext";
import BottomPanelLoading from "././BottomComponents//BottomPanelLoading";
import BottomPanelLoggedOut from "./BottomComponents/BottomPanelLoggedOut";
import BottomPanelUserProfileMenu from "./BottomComponents//BottomPanelUserProfileMenu";

interface Props {
    onOpenAuth: () => void;
}

const BottomPanel: React.FC<Props> = ({ onOpenAuth }) => {
    const { authState, logout, isLoading: authLoading } = useAuth();

    return (
        <div className="relative mt-4  border-gray-200 dark:border-gray-700 pt-4 px-3 pb-5 flex-shrink-0">
            {authLoading ? (
                // 1. 加载中
                <BottomPanelLoading />
            ) : authState?.isLoggedIn && authState.user ? (
                // 2. 已登录
                <BottomPanelUserProfileMenu
                    user={authState.user}
                    logout={logout}
                />
            ) : (
                // 3. 未登录
                <BottomPanelLoggedOut onOpenAuth={onOpenAuth} />
            )}
        </div>
    );
};

export default BottomPanel;