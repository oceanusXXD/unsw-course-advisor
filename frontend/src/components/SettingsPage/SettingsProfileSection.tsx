// src/components/SettingsPage/SettingsProfileSection.tsx

import React, { useRef } from "react";
import { FiUser, FiCamera } from "react-icons/fi";
import { User } from "../../types"; // [!!] 确保你从 types.ts 导入了 User 类型

interface Props {
    user: User | null;
}

const SettingsProfileSection: React.FC<Props> = ({ user }) => {
    // --- Avatar Upload (Placeholder) ---
    const fileInputRef = useRef<HTMLInputElement>(null);
    const handleAvatarClick = () => {
        fileInputRef.current?.click();
    };
    const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (file) {
            // Placeholder: Replace with actual upload logic
            console.log("Selected file:", file.name);
            alert(`Avatar upload placeholder: ${file.name}`);
        }
    };

    return (
        <section className="space-y-4">
            <h2 className="text-xl font-semibold border-b border-neutral-200 dark:border-neutral-700 pb-2 text-neutral-900 dark:text-neutral-100">
                Profile
            </h2>
            <div className="flex flex-col sm:flex-row items-start gap-6 p-6 rounded-xl bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 shadow-sm">
                {/* Avatar */}
                <div className="relative group flex-shrink-0">
                    {/* [!! 修正] 颜色改为 yellow/black */}
                    <div className="w-24 h-24 rounded-full bg-gradient-to-br from-yellow-400 to-yellow-500 flex items-center justify-center text-black text-4xl font-bold overflow-hidden">
                        {/* Placeholder for actual image */}
                        <FiUser size={48} />
                    </div>
                    {/* Upload Overlay */}
                    <button
                        onClick={handleAvatarClick}
                        className="absolute inset-0 rounded-full bg-black/50 flex items-center justify-center text-white opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
                        aria-label="Change profile picture"
                    >
                        <FiCamera size={24} />
                    </button>
                    <input
                        type="file"
                        ref={fileInputRef}
                        onChange={handleFileChange}
                        accept="image/*"
                        className="hidden"
                    />
                </div>
                {/* User Info */}
                <div className="space-y-1">
                    <p className="font-semibold text-lg text-neutral-900 dark:text-neutral-100">{user?.name ?? "User"}</p>
                    <p className="text-sm text-neutral-500 dark:text-neutral-400">{user?.email}</p>
                    <p className="text-xs text-neutral-500 dark:text-neutral-500 pt-1">
                        {/* [!! 修正] 订阅颜色改为 yellow */}
                        Plan: <span className="font-medium text-yellow-600 dark:text-yellow-400">{user?.subscription?.toUpperCase() ?? "FREE"}</span>
                    </p>
                </div>
            </div>
        </section>
    );
};

export default SettingsProfileSection;