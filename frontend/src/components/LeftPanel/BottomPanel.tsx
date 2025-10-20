// BottomPanel.tsx
import React, { useState, useRef, useEffect } from "react";
import {
    FiUser,
    FiSettings,
    FiLogOut,
    FiStar,
    FiHelpCircle,
    FiSliders,
} from "react-icons/fi";
import { useAuth } from "../../context/AuthContext";

interface Props {
    onOpenAuth: () => void;
}

const BottomPanel: React.FC<Props> = ({ onOpenAuth }) => {
    const { authState, logout, isLoading: authLoading } = useAuth();
    const [isMenuOpen, setIsMenuOpen] = useState<boolean>(false);
    const menuRef = useRef<HTMLDivElement | null>(null);

    const getInitials = (name?: string, email?: string) => {
        if (name) {
            const parts = name.trim().split(" ");
            if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
            return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
        }
        if (email) return email.slice(0, 2).toUpperCase();
        return "U";
    };

    const handleLogout = async () => {
        if (window.confirm("确定要登出吗?")) {
            try {
                await logout();
            } catch (err) {
                // 错误可选处理
            }
        }
    };

    // 点击外部关闭菜单
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
                setIsMenuOpen(false);
            }
        };
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    return (
        <div className="relative mt-4 border-t border-gray-200 pt-4 px-3 pb-5 flex-shrink-0">
            {authLoading ? (
                <div className="flex items-center gap-3">
                    <div className="w-11 h-11 rounded-full bg-gray-100 animate-pulse" />
                    <div className="flex-1">
                        <div className="h-4 bg-gray-100 rounded w-3/4 animate-pulse mb-2" />
                        <div className="h-3 bg-gray-100 rounded w-1/2 animate-pulse" />
                    </div>
                </div>
            ) : authState?.isLoggedIn && authState.user ? (
                <div className="relative" ref={menuRef}>
                    {/* 头像部分 */}
                    <button
                        onClick={() => setIsMenuOpen((prev) => !prev)}
                        className="flex items-center gap-3 w-full hover:bg-gray-50 p-2 rounded-xl transition"
                        aria-label="打开用户菜单"
                    >
                        {authState.user.avatarUrl ? (
                            <img
                                src={authState.user.avatarUrl}
                                alt={authState.user.name ?? authState.user.email}
                                className="w-11 h-11 rounded-full object-cover"
                            />
                        ) : (
                            <div className="w-11 h-11 rounded-full bg-gradient-to-br from-teal-400 to-cyan-400 flex items-center justify-center text-white font-bold text-base">
                                {getInitials(authState.user.name, authState.user.email)}
                            </div>
                        )}

                        <div className="flex flex-col items-start text-left overflow-hidden">
                            <div className="text-sm font-semibold text-gray-800 truncate">
                                {authState.user.name ?? "User"}
                            </div>
                            <div className="text-xs text-gray-500 truncate">
                                {(authState.user.subscription ?? "FREE").toString().toUpperCase()} PLAN
                            </div>
                        </div>
                    </button>

                    {/* 弹出菜单 */}
                    {isMenuOpen && (
                        <div
                            className="absolute bottom-16 left-0 w-64 bg-white shadow-xl rounded-2xl border border-gray-100 overflow-hidden animate-fadeIn z-50"
                            role="menu"
                        >
                            <div className="px-4 py-3 border-b border-gray-100">
                                <div className="text-sm font-medium text-gray-800 truncate">
                                    {authState.user.email}
                                </div>
                            </div>

                            <div className="flex flex-col text-sm text-gray-700">
                                <button
                                    onClick={() => alert("Upgrade Package clicked")}
                                    className="flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50 transition text-left"
                                >
                                    <FiStar className="text-gray-500" />
                                    Upgrade Package
                                </button>
                                <button
                                    onClick={() => alert("Personalization clicked")}
                                    className="flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50 transition text-left"
                                >
                                    <FiSliders className="text-gray-500" />
                                    Personalization
                                </button>
                                <button
                                    onClick={() => alert("Set Up clicked")}
                                    className="flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50 transition text-left"
                                >
                                    <FiSettings className="text-gray-500" />
                                    Set Up
                                </button>
                                <div className="border-t border-gray-100 my-1"></div>
                                <button
                                    onClick={() => alert("Help clicked")}
                                    className="flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50 transition text-left"
                                >
                                    <FiHelpCircle className="text-gray-500" />
                                    Help
                                </button>
                                <button
                                    onClick={handleLogout}
                                    className="flex items-center gap-3 px-4 py-2.5 text-red-600 hover:bg-red-50 transition text-left"
                                >
                                    <FiLogOut />
                                    Logout
                                </button>
                            </div>
                        </div>
                    )}
                </div>
            ) : (
                <div className="flex flex-col gap-2">
                    <button
                        onClick={onOpenAuth}
                        className="w-full py-2.5 px-3 bg-cyan-400 text-white font-semibold rounded-xl hover:bg-cyan-500 transition text-sm"
                        aria-label="登录或注册"
                    >
                        登录 / 注册
                    </button>
                    <div className="flex items-center gap-2 text-xs text-gray-500">
                        <FiUser /> <span>或继续匿名使用，功能受限</span>
                    </div>
                </div>
            )}
        </div>
    );
};

export default BottomPanel;
