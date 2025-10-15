import React from 'react'
import { Sparkles } from 'lucide-react'


export default function Toaster({ toasts, onRemove }) {
    return (
        <div className="fixed bottom-6 right-6 space-y-3 z-50">
            {toasts.map((toast) => (
                <div
                    key={toast.id}
                    className="bg-bg-card border border-border-soft rounded-xl p-4 shadow-2xl min-w-[300px] animate-in slide-in-from-right"
                >
                    <div className="flex items-start gap-3">
                        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-red-500 to-orange-500 flex items-center justify-center flex-shrink-0">
                            <Sparkles className="w-4 h-4 text-white" />
                        </div>
                        <div className="flex-1">
                            <p className="text-sm font-semibold text-text-primary">{toast.title}</p>
                            <p className="text-xs text-text-muted mt-1">{toast.message}</p>
                        </div>
                        <button
                            onClick={() => onRemove(toast.id)}
                            className="text-text-muted hover:text-text-primary transition-colors"
                        >
                            ×
                        </button>
                    </div>
                </div>
            ))}
        </div>
    )
}