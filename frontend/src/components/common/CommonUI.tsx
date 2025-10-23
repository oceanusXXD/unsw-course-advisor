// src/components/common/CommonUI.tsx
import React from "react";
import { FiXCircle, FiX, FiCopy, FiMonitor, FiCalendar } from "react-icons/fi";

// --- Reusable UI Helper Components ---

/**
 * Loading Spinner Component
 */
export const Spinner: React.FC = () => (
    <svg
        className="animate-spin h-6 w-6 text-cyan-500"
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
    >
        <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
        ></circle>
        <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
        ></path>
    </svg>
);

/**
 * Error Alert Component
 */
export const Alert: React.FC<{ message: string; onClose: () => void }> = ({
    message,
    onClose,
}) => (
    <div className="rounded-lg bg-red-50 dark:bg-red-900/30 p-3 flex items-center justify-between space-x-2 animate-fadeIn border border-red-200 dark:border-red-800/50">
        <FiXCircle className="h-5 w-5 text-red-500 flex-shrink-0" />
        <p className="text-xs text-red-700 dark:text-red-300 flex-1">{message}</p>
        <button
            onClick={onClose}
            className="text-red-500 hover:text-red-700 dark:text-red-400 dark:hover:text-red-200"
            aria-label="Close error"
        >
            <FiX size={16} />
        </button>
    </div>
);

/**
 * Key Display Component (with Copy Button)
 */
export const KeyDisplay: React.FC<{ value: string }> = ({ value }) => (
    <div className="flex items-center gap-2 w-full p-2.5 border border-neutral-200 dark:border-neutral-700 rounded-lg bg-neutral-50 dark:bg-neutral-800/50">
        <span className="flex-1 font-mono text-sm text-neutral-700 dark:text-neutral-200 truncate">
            {value}
        </span>
        <button
            onClick={() => navigator.clipboard?.writeText(value)}
            className="p-1.5 text-neutral-500 dark:text-neutral-400 hover:bg-neutral-200 dark:hover:bg-neutral-700 rounded"
            aria-label="Copy"
        >
            <FiCopy size={14} />
        </button>
    </div>
);

/**
 * Informational Display Component (Read-only)
 */
export const InfoDisplay: React.FC<{
    value: string;
    icon: React.ReactElement;
}> = ({ value, icon }) => (
    <div className="flex items-center gap-2 w-full p-2.5 border border-neutral-200 dark:border-neutral-700 rounded-lg bg-neutral-50 dark:bg-neutral-800/50">
        {/* Ensure icon has size */}
        <span className="p-1.5 text-neutral-500 dark:text-neutral-400">
            {React.cloneElement(icon, { size: icon.props.size || 14 })}
        </span>
        <span className="flex-1 text-sm text-neutral-700 dark:text-neutral-200 truncate">
            {value}
        </span>
    </div>
);

/**
 * Gradient Check Circle Icon
 */
export const CheckCircleIcon: React.FC<{ className?: string }> = ({
    className,
}) => (
    <svg
        className={className}
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        xmlns="http://www.w3.org/2000/svg"
    >
        <defs>
            <linearGradient id="common-ui-grad1" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop
                    offset="0%"
                    style={{ stopColor: "rgb(6,182,212)", stopOpacity: 1 }}
                />{" "}
                <stop
                    offset="100%"
                    style={{ stopColor: "rgb(20,184,166)", stopOpacity: 1 }}
                />
            </linearGradient>
        </defs>
        <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            stroke="url(#common-ui-grad1)"
            d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
        />
    </svg>
);
