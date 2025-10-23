import React, { useState, useEffect } from "react";

// --- Toaster ---
type ToastType = "success" | "error" | "info" | "warning";
interface Toast {
  id: string;
  message: string;
  type: ToastType;
  duration?: number;
}

export const useToaster = () => {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const addToast = (message: string, type: ToastType = "info", duration = 3000) => {
    const id = `toast-${Date.now()}-${Math.random()}`;
    setToasts((prev) => [...prev, { id, message, type, duration }]);
  };
  const removeToast = (id: string) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  };
  return {
    toasts,
    removeToast,
    showSuccess: (msg: string, dur?: number) => addToast(msg, "success", dur),
    showError: (msg: string, dur?: number) => addToast(msg, "error", dur),
    showInfo: (msg: string, dur?: number) => addToast(msg, "info", dur),
  };
};

const ToastItem: React.FC<{ toast: Toast; onRemove: (id: string) => void }> = ({ toast, onRemove }) => {
  const [isVisible, setIsVisible] = useState(true);
  useEffect(() => {
    const timer = setTimeout(() => {
      setIsVisible(false);
      setTimeout(() => onRemove(toast.id), 300);
    }, toast.duration || 3000);
    return () => clearTimeout(timer);
  }, [toast, onRemove]);


  const colors = {
    success: "bg-green-500 dark:bg-green-600",
    error: "bg-red-500 dark:bg-red-600",
    warning: "bg-yellow-500 dark:bg-yellow-600",
    info: "bg-blue-500 dark:bg-blue-600",
  };
  const icons = { success: "✓", error: "✕", warning: "⚠", info: "ℹ" };

  return (
    <div
      className={`${isVisible ? "opacity-100 translate-x-0" : "opacity-0 translate-x-full"
        } transition-all duration-300 ${colors[toast.type]}
     text-white px-4 py-3 rounded-lg shadow-lg dark:shadow-neutral-900/50 // [!!] Added dark shadow
     min-w-[300px] max-w-[400px] flex items-start gap-3`}
    >
      <span className="text-xl font-bold">{icons[toast.type]}</span>
      <span className="flex-1 text-sm">{toast.message}</span>
      <button
        onClick={() => {
          setIsVisible(false);
          setTimeout(() => onRemove(toast.id), 300);
        }}
        className="text-white opacity-70 hover:opacity-100 dark:hover:text-neutral-200 font-bold text-lg leading-none transition-opacity"
      >
        ×
      </button>
    </div>
  );
};

export const Toaster: React.FC<{ toasts: Toast[]; onRemove: (id: string) => void }> = ({ toasts, onRemove }) => (
  <div className="fixed top-4 right-4 z-50 flex flex-col gap-2">
    {toasts.map((toast) => (
      <ToastItem key={toast.id} toast={toast} onRemove={onRemove} />
    ))}
  </div>
);