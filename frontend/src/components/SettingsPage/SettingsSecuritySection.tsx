// src/components/SettingsPage/SettingsSecuritySection.tsx

import React, { useState } from "react";
import { FiLock, FiCheck, FiX } from "react-icons/fi";
import { changePassword } from "../../services/api"; // [!!] 确保路径正确

const SettingsSecuritySection: React.FC = () => {
    // --- Password Change State ---
    const [showPasswordForm, setShowPasswordForm] = useState(false);
    const [oldPassword, setOldPassword] = useState("");
    const [newPassword, setNewPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");
    const [isPasswordLoading, setIsPasswordLoading] = useState(false);
    const [passwordFeedback, setPasswordFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);

    // --- Password Handler ---
    const handleSubmitPasswordChange = async (e: React.FormEvent) => {
        e.preventDefault();
        setPasswordFeedback(null);

        if (newPassword !== confirmPassword) {
            setPasswordFeedback({ type: "error", message: "New passwords do not match." });
            return;
        }
        if (newPassword.length < 8) {
            setPasswordFeedback({ type: "error", message: "New password must be at least 8 characters." });
            return;
        }

        setIsPasswordLoading(true);
        try {
            await changePassword(oldPassword, newPassword);
            setPasswordFeedback({ type: "success", message: "Password updated successfully!" });
            setOldPassword("");
            setNewPassword("");
            setConfirmPassword("");
            setShowPasswordForm(false); // Hide form on success
        } catch (err: any) {
            setPasswordFeedback({ type: "error", message: err.message || "Failed to update password. Check your old password." });
        } finally {
            setIsPasswordLoading(false);
        }
    };

    return (
        <section className="space-y-4">
            <h2 className="text-xl font-semibold border-b border-neutral-200 dark:border-neutral-700 pb-2 text-neutral-900 dark:text-neutral-100">
                Security
            </h2>
            <div className="p-6 rounded-xl bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 shadow-sm space-y-4">
                {/* Password Feedback */}
                {passwordFeedback && !showPasswordForm && (
                    <div className={`flex items-start gap-2 text-sm p-3 rounded ${passwordFeedback.type === 'success'
                        ? 'bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-300'
                        : 'bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300'
                        }`}>
                        {passwordFeedback.type === 'success' ? <FiCheck /> : <FiX />}
                        <span className="flex-1">{passwordFeedback.message}</span>
                    </div>
                )}

                {/* Show Button OR Form */}
                {!showPasswordForm ? (
                    <div className="flex justify-between items-center">
                        <div>
                            <p className="font-medium text-neutral-800 dark:text-neutral-200">Password</p>
                            <p className="text-sm text-neutral-500 dark:text-neutral-400">Update your password.</p>
                        </div>
                        <button
                            onClick={() => { setShowPasswordForm(true); setPasswordFeedback(null); }}
                            // [!! 修正] 按钮颜色改为 yellow
                            className="px-4 py-2 text-sm font-semibold text-yellow-600 dark:text-yellow-400 bg-yellow-50 dark:bg-yellow-900/30 hover:bg-yellow-100 dark:hover:bg-yellow-900/50 rounded-lg transition"
                        >
                            Change
                        </button>
                    </div>
                ) : (
                    <form onSubmit={handleSubmitPasswordChange} className="space-y-4 pt-2">
                        {/* Form Feedback */}
                        {passwordFeedback && (
                            <div className={`flex items-start gap-2 text-sm p-3 rounded ${passwordFeedback.type === 'success'
                                ? 'bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-300'
                                : 'bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300'
                                }`}>
                                {passwordFeedback.type === 'success' ? <FiCheck /> : <FiX />}
                                <span className="flex-1">{passwordFeedback.message}</span>
                            </div>
                        )}
                        {/* Inputs */}
                        <div className="space-y-2">
                            <label htmlFor="old-pass" className="block text-sm font-medium text-neutral-700 dark:text-neutral-300">Current Password</label>
                            {/* [!! 修正] 焦点颜色改为 yellow */}
                            <input id="old-pass" type="password" value={oldPassword} onChange={(e) => setOldPassword(e.target.value)}
                                className="w-full p-3 border border-neutral-300 dark:border-neutral-600 rounded-md bg-neutral-50 dark:bg-neutral-700 focus:outline-none focus:ring-2 focus:ring-yellow-500 text-neutral-900 dark:text-neutral-100 transition" required />
                        </div>
                        <div className="space-y-2">
                            <label htmlFor="new-pass" className="block text-sm font-medium text-neutral-700 dark:text-neutral-300">New Password (min. 8 characters)</label>
                            {/* [!! 修正] 焦点颜色改为 yellow */}
                            <input id="new-pass" type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)}
                                className="w-full p-3 border border-neutral-300 dark:border-neutral-600 rounded-md bg-neutral-50 dark:bg-neutral-700 focus:outline-none focus:ring-2 focus:ring-yellow-500 text-neutral-900 dark:text-neutral-100 transition" required />
                        </div>
                        <div className="space-y-2">
                            <label htmlFor="confirm-pass" className="block text-sm font-medium text-neutral-700 dark:text-neutral-300">Confirm New Password</label>
                            {/* [!! 修正] 焦点颜色改为 yellow */}
                            <input id="confirm-pass" type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)}
                                className="w-full p-3 border border-neutral-300 dark:border-neutral-600 rounded-md bg-neutral-50 dark:bg-neutral-700 focus:outline-none focus:ring-2 focus:ring-yellow-500 text-neutral-900 dark:text-neutral-100 transition" required />
                        </div>
                        {/* Actions */}
                        <div className="flex gap-4 pt-2">
                            <button
                                type="submit"
                                disabled={isPasswordLoading}
                                // [!! 修正] 按钮颜色改为 yellow/black

                                className="flex items-center justify-center gap-2 py-2 px-4 bg-yellow-400 text-black font-semibold rounded-lg hover:bg-yellow-500 transition disabled:opacity-50 text-sm"
                            >
                                <FiLock size={16} />
                                {isPasswordLoading ? "Updating..." : "Update Password"}
                            </button>
                            <button
                                type="button"
                                onClick={() => { setShowPasswordForm(false); setPasswordFeedback(null); }}
                                className="py-2 px-4 text-sm text-neutral-600 dark:text-neutral-400 hover:bg-neutral-100 dark:hover:bg-neutral-700 rounded-lg transition"
                            >
                                Cancel
                            </button>
                        </div>
                    </form>
                )}
            </div>
        </section>

    );
};

export default SettingsSecuritySection;