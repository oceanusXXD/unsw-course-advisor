// src/components/Auth/AuthModal.tsx (已修正)

import React, { useState, useEffect } from "react";
import { FiX, FiEye, FiEyeOff } from "react-icons/fi";
import { useAuth } from "../../context/AuthContext";

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onClose }) => {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [username, setUsername] = useState("");
  // [!! 助手更改] 1. 为“确认密码”添加新状态
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const { login, signup, isLoading, error, authState } = useAuth();

  // [修正 ✨] 将 resetForm 的定义移到最前面
  const resetForm = () => {
    setEmail("");
    setPassword("");
    setUsername("");
    // [!! 助手更改] 2. 重置“确认密码”
    setConfirmPassword("");
    setLocalError(null);
  };

  // 监听认证状态变化
  useEffect(() => {
    if (authState.isLoggedIn) {
      onClose();
      resetForm(); // 现在调用时，它已经被定义了
    }
  }, [authState.isLoggedIn, onClose]);

  // 监听错误变化
  useEffect(() => {
    setLocalError(error);
  }, [error]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError(null);

    // 基本验证
    if (!email) {
      setLocalError("Please enter your email");
      return;
    }
    if (!password) {
      setLocalError("Please enter your password");
      return;
    }
    if (!isLogin && !username) {
      setLocalError("Please enter your name");
      return;
    }

    // [!! 助手更改] 3. 添加密码匹配验证
    if (!isLogin && !confirmPassword) {
      setLocalError("Please confirm your password");
      return;
    }
    if (!isLogin && password !== confirmPassword) {
      setLocalError("Passwords do not match");
      return;
    }
    // 密码长度验证（如果需要）
    if (!isLogin && password.length < 6) {
      setLocalError("Password must be at least 6 characters");
      return;
    }

    try {
      if (isLogin) {
        await login(email, password);
      } else {
        // signup 函数通常只需要 email, password, username
        await signup(email, password, username);
      }
    } catch (err) {
      console.error("Auth error:", err);
    }
  };

  const toggleMode = () => {
    setIsLogin(!isLogin);
    resetForm();
  };

  // ... 返回 JSX 的部分 ...
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-8 relative">
        {/* 关闭按钮 */}
        <button
          onClick={() => {
            onClose();
            resetForm();
          }}
          className="absolute top-4 right-4 p-2 hover:bg-gray-100 rounded-full transition"
          disabled={isLoading}
        >
          <FiX size={20} />
        </button>

        {/* 标题 */}
        <h2 className="text-2xl font-bold mb-2 text-gray-800">
          {isLogin ? "Sign In to Course advisor" : "Create Your Account"}
        </h2>
        <p className="text-gray-600 mb-6 text-sm">
          {isLogin
            ? "Welcome back! Sign in to continue your chat sessions."
            : "Join Course advisor Chat to start exploring and chatting."}
        </p>

        {/* 错误提示 */}
        {localError && (
          // [!! 助手更改] 样式微调，使其不那么刺眼
          <div className="mb-4 p-3 bg-red-50 border border-red-300 rounded-lg text-red-700 text-sm">
            {localError}
          </div>
        )}

        {/* 表单 */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* 名字字段 (仅注册) */}
          {!isLogin && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Full Name
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="John Doe"
                // [!! 助手更改] 4. 添加 text-gray-800
                className="w-full px-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-cyan-400 transition disabled:bg-gray-100 text-gray-800"
                disabled={isLoading}
              />
            </div>
          )}

          {/* 邮箱字段 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Email Address
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              // [!! 助手更改] 4. 添加 text-gray-800
              className="w-full px-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-cyan-400 transition disabled:bg-gray-100 text-gray-800"
              disabled={isLoading}
            />
          </div>

          {/* 密码字段 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Password
            </label>
            <div className="relative">
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                // [!! 助手更改] 4. 添加 text-gray-800
                className="w-full px-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-cyan-400 transition disabled:bg-gray-100 text-gray-800"
                disabled={isLoading}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 disabled:opacity-50"
                disabled={isLoading}
              >
                {showPassword ? <FiEyeOff size={18} /> : <FiEye size={18} />}
              </button>
            </div>
            {!isLogin && (
              <p className="text-xs text-gray-500 mt-1">
                Password must be at least 6 characters
              </p>
            )}
          </div>

          {/* [!! 助手更改] 5. 新增：确认密码字段 (仅注册) */}
          {!isLogin && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Confirm Password
              </label>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full px-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-cyan-400 transition disabled:bg-gray-100 text-gray-800"
                  disabled={isLoading}
                />
                {/* 这个按钮会同时控制两个密码框的可见性 */}
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 disabled:opacity-50"
                  disabled={isLoading}
                >
                  {showPassword ? <FiEyeOff size={18} /> : <FiEye size={18} />}
                </button>
              </div>
            </div>
          )}

          {/* 提交按钮 */}
          <button
            type="submit"
            disabled={isLoading}
            // [!! 助手更改] 调整了 mt-6，因为多了一个字段
            className={`w-full py-2 bg-cyan-400 text-white font-semibold rounded-lg hover:bg-cyan-500 transition disabled:bg-gray-400 disabled:cursor-not-allowed ${isLogin ? "mt-6" : "mt-4"}`}
          >
            {isLoading ? (
              <span className="flex items-center justify-center gap-2">
                <span className="inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
                Processing...
              </span>
            ) : isLogin ? (
              "Sign In"
            ) : (
              "Create Account"
            )}
          </button>
        </form>

        {/* 切换表单 */}
        <div className="mt-6 text-center">
          <p className="text-gray-600 text-sm">
            {isLogin ? "Don't have an account?" : "Already have an account?"}
            <button
              onClick={toggleMode}
              disabled={isLoading}
              className="ml-2 text-cyan-400 font-semibold hover:underline disabled:opacity-50"
            >
              {isLogin ? "Sign Up" : "Sign In"}_
            </button>
          </p>
        </div>

        {/* 开发者提示 */}
        <div className="mt-6 pt-6 border-t border-gray-200">
          <p className="text-xs text-gray-400 text-center">
            🔐 Secure authentication powered by Course advisor
          </p>
        </div>
      </div>
    </div>
  );
};

export default AuthModal;
