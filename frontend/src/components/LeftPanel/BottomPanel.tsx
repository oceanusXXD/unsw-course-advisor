// src/components/LeftPanel/BottomPanel.tsx

import React from "react";
import { useAuth } from "../../context/AuthContext";
import BottomPanelLoading from "././BottomComponents//BottomPanelLoading";
import BottomPanelLoggedOut from "./BottomComponents/BottomPanelLoggedOut";
import BottomPanelUserProfileMenu from "./BottomComponents//BottomPanelUserProfileMenu";
// 注意：图标导入不再需要，因为它们被移动到子组件中了

interface Props {
    onOpenAuth: () => void;
}

const BottomPanel: React.FC<Props> = ({ onOpenAuth }) => {
    const { authState, logout, isLoading: authLoading } = useAuth();

    // 注意：所有帮助函数 (getInitials, handleLogout, handleToggleTheme, useEffect)
    // 都已移至各自的子组件中。

    return (
        <div className="relative mt-4  border-gray-200 dark:border-gray-700 pt-4 px-3 pb-5 flex-shrink-0">
            {authLoading ? (
                // 1. 加载中
                <BottomPanelLoading />
            ) : authState?.isLoggedIn && authState.user ? (
                // 2. 已登录
                // 我们需要将 user 和 logout 传递下去
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