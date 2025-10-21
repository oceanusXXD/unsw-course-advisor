// src/components/SettingsPage/SettingsAppearanceSection.tsx

import React, { useState } from "react";
import { FiSun, FiMoon } from "react-icons/fi";

const SettingsAppearanceSection: React.FC = () => {
    // --- Theme State ---
    const [isDark, setIsDark] = useState<boolean>(
        document.documentElement.classList.contains("dark")
    );

    // --- Theme Handler ---
    const handleToggleTheme = () => {
        const html = document.documentElement;
        html.classList.toggle("dark");
        const newTheme = html.classList.contains("dark");
        setIsDark(newTheme);
        localStorage.setItem("theme", newTheme ? "dark" : "light");
    };

    return (
        <section className="space-y-4">
            <h2 className="text-xl font-semibold border-b border-neutral-200 dark:border-neutral-700 pb-2 text-neutral-900 dark:text-neutral-100">
                Appearance
            </h2>
            <div className="p-4 rounded-xl bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 shadow-sm">
                <button
                    onClick={handleToggleTheme}
                    className="w-full flex items-center justify-between transition"
                    aria-label={`Toggle theme, current theme is ${isDark ? "Dark" : "Light"}`}
                >
                    <span className="flex items-center gap-3 font-medium text-neutral-800 dark:text-neutral-200">
                        {isDark ? (
                            <FiSun className="text-yellow-500" size={20} />
                        ) : (
                            <FiMoon className="text-neutral-500" size={20} />
                        )}
                        <span>
                            Theme:{" "}
                            <span className="font-semibold">{isDark ? "Dark" : "Light"}</span>
                        </span>
                    </span>
                    <div
                        aria-hidden="true"
                        // [!! 修正] 切换开关颜色改为 yellow
                        className={`relative inline-flex items-center h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out 
        ${isDark ? 'bg-yellow-400' : 'bg-gray-200 dark:bg-neutral-600'}`}
                    >
                        <span
                            className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out 
          ${isDark ? 'translate-x-5' : 'translate-x-0'}`}
                        />
                    </div>
                </button>
            </div>
        </section>
    );
};

export default SettingsAppearanceSection;