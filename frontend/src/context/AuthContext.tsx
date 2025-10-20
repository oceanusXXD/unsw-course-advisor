//AuthContext.tsx
import React, { createContext, useContext, useState, useCallback, useEffect } from "react";
import { User, AuthState } from "../types"; // [重要] 确保你的 AuthState 类型包含 accessToken 和 refreshToken
import { loginUser, registerUser, getCurrentUser, logoutUser } from "../services/api";

// 确保你的 types.ts 中的 AuthState 接口看起来像这样：
// export interface AuthState {
//   isLoggedIn: boolean;
//   user: User | null;
//   accessToken: string | null;
//   refreshToken: string | null;
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
                        // 使用已存储的 token 验证用户身份
                        const user = await getCurrentUser(parsedAuth.accessToken);
                        // 验证成功，恢复完整的登录状态
                        saveAuthState({ ...parsedAuth, isLoggedIn: true, user });
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
            const userResponse = await getCurrentUser(tokenResult.access);

            // [修正 ✨] 从响应中解构出 user 对象
            const { user } = userResponse;
            if (!user) {
                throw new Error("Failed to fetch user profile after login.");
            }

            // 3. 构建并保存最终的、完整的状态
            const finalAuthState: AuthState = {
                isLoggedIn: true,
                user: {
                    id: user.id,
                    email: user.email,
                    name: user.username || user.name,
                    avatar: user.avatar,
                    subscription: user.license?.license_active ? "plus" : "free",
                },
                accessToken: tokenResult.access,
                refreshToken: tokenResult.refresh,
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

            const finalAuthState: AuthState = {
                isLoggedIn: true,
                user: {
                    id: user.id,
                    email: user.email,
                    name: user.username || name,
                    avatar: user.avatar,
                    subscription: "free",
                },
                accessToken: result.access,
                refreshToken: result.refresh,
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

    // 登出
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
            const user = await getCurrentUser(authState.accessToken);
            setAuthState((prev) => ({ ...prev, user }));
        } catch (err) {
            console.error("Failed to refresh user:", err);
            // 如果刷新失败（例如 token 过期），则登出用户
            logout();
        }
    }, [authState.accessToken, logout]);

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