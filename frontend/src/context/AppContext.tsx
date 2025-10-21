// src/context/AppContext.tsx

import React, { createContext, useContext, useState, useMemo } from "react";

// 定义应用可以处于的视图
export type AppView = "chat" | "settings";

interface AppContextType {
    activeView: AppView;
    navigateTo: (view: AppView) => void;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

export const AppProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [activeView, setActiveView] = useState<AppView>("chat");

    const navigateTo = (view: AppView) => {
        setActiveView(view);
    };

    const value = useMemo(() => ({
        activeView,
        navigateTo,
    }), [activeView]);

    return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
};

export const useAppContext = () => {
    const context = useContext(AppContext);
    if (!context) {
        throw new Error("useAppContext 必须在 AppProvider 内部使用");
    }
    return context;
};