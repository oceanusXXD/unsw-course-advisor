import React from 'react';

interface UploadButtonProps {
    onClick: () => void;
    disabled?: boolean;
    isError?: boolean;
    isFocused?: boolean;
    isDark?: boolean;
}

export const UploadButton: React.FC<UploadButtonProps> = ({
    onClick,
    disabled = false,
    isError = false,
    isFocused = false,
    isDark = false,
}) => {
    const defaultStroke = isDark ? "#a3a3a3" : "#9CA3AF";

    return (
        <button
            type="button"
            onClick={onClick}
            onMouseDown={(e) => e.preventDefault()}
            disabled={disabled}
            className="mr-3 flex-shrink-0 mb-1.5 p-1 rounded-full hover:bg-gray-100 dark:hover:bg-neutral-700 transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed"
            aria-label="Upload file"
        >
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                <path
                    d="M9 3.75V14.25"
                    stroke={isError ? "#EF4444" : isFocused ? "#F59E0B" : defaultStroke}
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                />
                <path
                    d="M3.75 9H14.25"
                    stroke={isError ? "#EF4444" : isFocused ? "#F59E0B" : defaultStroke}
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                />
            </svg>
        </button>
    );
};