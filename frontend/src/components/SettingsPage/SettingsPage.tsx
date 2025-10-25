// src/components/SettingsPage/SettingsPage.tsx

import React from "react";
import { FiArrowLeft } from "react-icons/fi";
import { useAppContext } from "../../context/AppContext";
import { useAuth } from "../../context/AuthContext";

import { useToaster, Toaster } from "../Toaster/Toaster";

import SettingsProfileSection from "./SettingsProfileSection";
import SettingsAppearanceSection from "./SettingsAppearanceSection";
import SettingsSecuritySection from "./SettingsSecuritySection";
import SettingsAccountSection from "./SettingsAccountSection";

const SettingsPage: React.FC = () => {
    const { navigateTo } = useAppContext();
    const { authState, logout } = useAuth();

    const {
        toasts,
        removeToast,
        showSuccess,
        showError
    } = useToaster();

    // --- Logout Handler ---
    const handleLogout = async () => {
        if (window.confirm("Are you sure you want to log out?")) {
            try {
                await logout();
                showSuccess("已成功登出。");
            } catch (error: any) {
                showError(error?.message || "登出失败，请重试。");
            }
        }
    };

    return (
        // z-index 确保 Toaster 总在最上层
        <div className="w-full h-full max-w-5xl mx-auto p-6 lg:p-10 space-y-10 text-neutral-800 dark:text-neutral-200 relative">
            <Toaster toasts={toasts} onRemove={removeToast} />

            <div className="flex items-center gap-4">
                <button
                    onClick={() => navigateTo("chat")}
                    className="p-2 rounded-md hover:bg-yellow-100 dark:hover:bg-neutral-800 transition"
                    aria-label="Back to Chat"
                >
                    <FiArrowLeft
                        className="text-neutral-600 dark:text-neutral-400"
                        size={20}
                    />
                </button>
                <h1 className="text-3xl font-bold text-neutral-900 dark:text-neutral-100">
                    Settings
                </h1>
            </div>

            <SettingsProfileSection
                user={authState.user}
                showSuccess={showSuccess}
                showError={showError}
            />

            {/* 3. Appearance Section */}
            <SettingsAppearanceSection />

            {/* 4. Security Section */}
            <SettingsSecuritySection
                showSuccess={showSuccess}
                showError={showError}
            />

            {/* 5. Account Section */}
            <SettingsAccountSection
                onLogout={handleLogout}
                showSuccess={showSuccess}
                showError={showError}
            />
        </div>
    );
};

export default SettingsPage;