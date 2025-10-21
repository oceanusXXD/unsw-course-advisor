// AuthContext.tsx (已修正)
import React, { createContext, useContext, useState, useCallback, useEffect } from "react";
import { User, AuthState, LoginResponse } from "../types"; // [重要] 确保你的 AuthState 类型包含 accessToken 和 refreshToken
import { loginUser, registerUser, getCurrentUser, logoutUser } from "../services/api";

// 确保你的 types.ts 中的 AuthState 接口看起来像这样：
// export interface AuthState {
//   isLoggedIn: boolean;
//   user: User | null;
//   accessToken: string | null;
//   refreshToken: string | null;
//   userInitial: string; // [!!] 确保 AuthState 接口包含此字段
// }

interface AuthContextType {
    authState: AuthState;
    login: (email: string, password: string) => Promise<void>;
    signup: (email: string, password: string, name: string) => Promise<void>;
    logout: () => void;
    isLoading: boolean;
    error: string | null;
    refreshUser: () => Promise<void>; // 保留 refreshUser
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    //统一并初始化正确的状态结构
    const [authState, setAuthState] = useState<AuthState>({
        isLoggedIn: false,
        user: null,
        accessToken: null,
        refreshToken: null,
        // [!! 修正] 'username' 在此上下文中未定义。使用默认值 'U'。
        userInitial: "U",
    });
    //初始加载状态应为 true，因为我们需要验证本地 token
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // 统一的状态保存和清理函数，这是唯一的 localStorage 交互点
    const saveAuthState = (newState: AuthState) => {
        setAuthState(newState);
        localStorage.setItem("authState", JSON.stringify(newState));
    };

    const clearAuthState = () => {
        localStorage.removeItem("authState");
        setAuthState({
            isLoggedIn: false,
            user: null,
            accessToken: null,
            refreshToken: null,
            // [!! 修正] 必须提供 userInitial 字段以匹配 AuthState
            userInitial: "U",
        });
    };

    // 应用加载时的认证状态初始化
    useEffect(() => {
        const initAuth = async () => {
            const savedAuth = localStorage.getItem("authState");
            if (savedAuth) {
                try {
                    const parsedAuth: AuthState = JSON.parse(savedAuth);
                    //检查 accessToken 是否存在
                    if (parsedAuth.accessToken) {
                        // [!! 修正] 假设 getCurrentUser 返回 LoginResponse 结构
                        const userResponse = await getCurrentUser(parsedAuth.accessToken);
                        const { user } = userResponse;
                        if (!user) throw new Error("User not found during init.");

                        // [!! 修正] 在恢复会话时也需要重建完整的状态
                        const userName = user.username || user.name;
                        const userInitial = userName ? userName[0].toUpperCase() : "U";
                        const finalUser: User = {
                            id: user.id,
                            email: user.email,
                            name: userName,
                            avatar: user.avatar,
                            subscription: userResponse.license_active ? "plus" : "free",
                        };

                        // 验证成功，恢复完整的登录状态
                        saveAuthState({
                            ...parsedAuth,
                            isLoggedIn: true,
                            user: finalUser,
                            userInitial: userInitial
                        });
                    }
                } catch (err) {
                    // 如果 token 无效或解析失败，则清理状态
                    console.error("Failed to restore session, token might be expired.", err);
                    clearAuthState();
                }
            }
            setIsLoading(false);
        };
        initAuth();
    }, []);

    // 登录
    const login = useCallback(async (email: string, password: string) => {
        setIsLoading(true);
        setError(null);
        try {
            // 1. 登录以获取令牌
            const tokenResult = await loginUser(email, password);
            if (!tokenResult.access || !tokenResult.refresh) {
                throw new Error("Login failed: Tokens not received from server.");
            }

            // 2. 使用新获取的 accessToken 获取用户信息
            // [!! 修正] 假设 getCurrentUser 返回 LoginResponse 结构
            const userResponse: LoginResponse = await getCurrentUser(tokenResult.access);

            // [修正 ✨] 从响应中解构出 user 对象
            const { user } = userResponse;
            if (!user) {
                throw new Error("Failed to fetch user profile after login.");
            }

            // [!! 修正] 提取 name 和 initial
            const userName = user.username || user.name;
            const userInitial = userName ? userName[0].toUpperCase() : "U";

            // 3. 构建并保存最终的、完整的状态
            const finalAuthState: AuthState = {
                isLoggedIn: true,
                user: {
                    id: user.id,
                    email: user.email,
                    name: userName || "user",
                    avatar: user.avatar,
                    // [!! 修正] 修正逻辑以匹配 LoginResponse 类型 (license_active 在根部)
                    subscription: userResponse.license_active ? "plus" : "free",
                },
                accessToken: tokenResult.access,
                refreshToken: tokenResult.refresh,
                // [!! 修正] 增加 userInitial 字段
                userInitial: userInitial,
            };
            saveAuthState(finalAuthState);
        } catch (err) {
            const message = err instanceof Error ? err.message : "An unknown login error occurred.";
            setError(message);
            throw err;
        } finally {
            setIsLoading(false);
        }
    }, []);

    // 注册
    const signup = useCallback(async (email: string, password: string, name: string) => {
        setIsLoading(true);
        setError(null);
        try {
            const result = await registerUser(email, password, name);
            if (!result.access || !result.refresh) {
                throw new Error("Signup failed: Tokens not received from server.");
            }

            // 注册成功后也立即获取用户信息
            const userResponse = await getCurrentUser(result.access);

            // [修正 ✨] 从响应中解构出 user 对象
            const { user } = userResponse;
            if (!user) {
                throw new Error("Failed to fetch user profile after signup.");
            }

            // [!! 修正] 提取 name 和 initial
            const userName = user.username || name; // 'name' 是从 signup 传入的
            const userInitial = userName ? userName[0].toUpperCase() : "U";

            const finalAuthState: AuthState = {
                isLoggedIn: true,
                user: {
                    id: user.id,
                    email: user.email,
                    name: userName,
                    avatar: user.avatar,
                    subscription: "free", // 注册后默认为 'free'
                },
                accessToken: result.access,
                refreshToken: result.refresh,
                // [!! 修正] 增加 userInitial 字段
                userInitial: userInitial,
            };
            saveAuthState(finalAuthState);
        } catch (err) {
            const message = err instanceof Error ? err.message : "Signup failed";
            setError(message);
            throw err;
        } finally {
            setIsLoading(false);
        }
    }, []);

    // 登出 (保持不变)
    const logout = useCallback(async () => {
        setIsLoading(true);
        const tokenToInvalidate = authState.refreshToken;
        try {
            if (tokenToInvalidate) {
                await logoutUser(tokenToInvalidate);
            }
        } catch (err) {
            console.error("Logout API call failed, proceeding to clear local state.", err);
        } finally {
            clearAuthState();
            setIsLoading(false);
        }
    }, [authState.refreshToken]);

    // 刷新用户信息
    const refreshUser = useCallback(async () => {
        if (!authState.accessToken) return; //依赖 accessToken

        try {
            // [!! 修正] 刷新逻辑需要像登录一样完整
            const userResponse = await getCurrentUser(authState.accessToken);
            const { user } = userResponse;
            if (!user) {
                throw new Error("Failed to refresh user data.");
            }

            const userName = user.username || user.name;
            const updatedUser: User = {
                id: user.id,
                email: user.email,
                name: userName,
                avatar: user.avatar,
                subscription: userResponse.license_active ? "plus" : "free",
            };
            const updatedInitial = userName ? userName[0].toUpperCase() : "U";

            setAuthState((prev) => ({
                ...prev,
                user: updatedUser,
                userInitial: updatedInitial
            }));
        } catch (err) {
            console.error("Failed to refresh user:", err);
            // 如果刷新失败（例如 token 过期），则登出用户
            logout();
        }
    }, [authState.accessToken, logout]); // [!! 修正] 确保 logout 在依赖项中

    return (
        <AuthContext.Provider
            value={{ authState, login, signup, logout, isLoading, error, refreshUser }}
        >
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error("useAuth must be used within AuthProvider");
    }
    return context;
};