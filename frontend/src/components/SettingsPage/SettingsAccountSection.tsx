// src/components/SettingsPage/SettingsAccountSection.tsx

import React from "react";
import { FiLogOut, FiTrash2 } from "react-icons/fi";

interface Props {
    onLogout: () => void;
}

const SettingsAccountSection: React.FC<Props> = ({ onLogout }) => {
    return (
        <section className="space-y-4">
            <h2 className="text-xl font-semibold border-b border-neutral-200 dark:border-neutral-700 pb-2 text-neutral-900 dark:text-neutral-100">
                Account
            </h2>
            <div className="p-6 rounded-xl bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 shadow-sm space-y-4">
                {/* Logout (Colors are red, which is correct for this action) */}
                <div className="flex justify-between items-center">
                    <div>
                        <p className="font-medium text-neutral-800 dark:text-neutral-200">Log Out</p>
                        <p className="text-sm text-neutral-500 dark:text-neutral-400">Log out of your current session.</p>

                    </div>
                    <button
                        onClick={onLogout} // [!!] Use prop
                        className="px-4 py-2 text-sm font-semibold text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/30 hover:bg-red-100 dark:hover:bg-red-900/50 rounded-lg transition flex items-center gap-2"
                    >
                        <FiLogOut size={14} /> Log Out
                    </button>
                </div>
                {/* Delete Account (Colors are red, which is correct) */}
                <div className="flex justify-between items-center pt-4 border-t border-neutral-200 dark:border-neutral-700">
                    <div>
                        <p className="font-medium text-red-600 dark:text-red-400">Delete Account</p>
                        <p className="text-sm text-neutral-500 dark:text-neutral-400">Permanently delete your account and data.</p>

                    </div>
                    <button
                        onClick={() => alert("Delete account placeholder")}

                        className="px-4 py-2 text-sm font-semibold text-red-600 dark:text-red-400 border border-red-200 dark:border-red-900/50 hover:bg-red-50 dark:hover:bg-red-900/30 rounded-lg transition flex items-center gap-2"
                    >
                        <FiTrash2 size={14} /> Delete
                    </button>
                </div>
            </div>
        </section>
    );
};

export default SettingsAccountSection;