import React from 'react';
import { UploadedFile } from '../../types/upload';

interface FilePreviewListProps {
    files: UploadedFile[];
    onRemove: (fileId: string) => void;
    isDark?: boolean;
}

export const FilePreviewList: React.FC<FilePreviewListProps> = ({
    files,
    onRemove,
    isDark = false,
}) => {
    if (files.length === 0) return null;

    const formatFileSize = (bytes: number): string => {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    };

    const getFileIcon = (type: string) => {
        if (type.startsWith('image/')) return '🖼️';
        if (type === 'application/pdf') return '📄';
        if (type.includes('word')) return '📝';
        if (type.includes('text')) return '📃';
        return '📎';
    };

    return (
        <div className="flex flex-wrap gap-2 mb-2">
            {files.map((file) => (
                <div
                    key={file.id}
                    className="flex items-center gap-2 px-3 py-2 rounded-lg bg-gray-100 dark:bg-neutral-700 border border-gray-200 dark:border-neutral-600"
                >
                    {file.preview ? (
                        <img
                            src={file.preview}
                            alt={file.name}
                            className="w-8 h-8 rounded object-cover"
                        />
                    ) : (
                        <span className="text-2xl">{getFileIcon(file.type)}</span>
                    )}

                    <div className="flex flex-col min-w-0">
                        <span className="text-sm font-medium truncate max-w-[150px] text-gray-900 dark:text-neutral-100">
                            {file.name}
                        </span>
                        <span className="text-xs text-gray-500 dark:text-neutral-400">
                            {formatFileSize(file.size)}
                        </span>
                    </div>

                    <button
                        onClick={() => onRemove(file.id)}
                        className="ml-1 p-1 rounded-full hover:bg-gray-200 dark:hover:bg-neutral-600 transition-colors"
                        aria-label={`Remove ${file.name}`}
                    >
                        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                            <path
                                d="M10.5 3.5L3.5 10.5M3.5 3.5L10.5 10.5"
                                stroke="currentColor"
                                strokeWidth="1.5"
                                strokeLinecap="round"
                                className="text-gray-600 dark:text-neutral-300"
                            />
                        </svg>
                    </button>
                </div>
            ))}
        </div>
    );
};