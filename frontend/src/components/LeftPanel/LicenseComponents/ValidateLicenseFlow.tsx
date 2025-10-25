import React, { useState } from "react";
import { FiArrowLeft, FiLogIn } from "react-icons/fi";
import { useAuth } from "../../../context/AuthContext";
import { validateLicense } from "../../../services/api";
import { Toaster, useToaster } from "../../Toaster/Toaster";
import { Spinner } from '../../common/CommonUI';

interface Props {
    onBack: () => void;
    onSuccess: () => void;
}

const ValidateLicenseFlow: React.FC<Props> = ({ onBack, onSuccess }) => {
    const { refreshUser } = useAuth();
    const [isLoading, setIsLoading] = useState(false);
    const [activationKey, setActivationKey] = useState("");
    const { toasts, removeToast, showSuccess, showError } = useToaster();

    const handleValidateLicense = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsLoading(true);
        try {
            await validateLicense(activationKey);
            setActivationKey("");
            onSuccess();
            if (refreshUser) await refreshUser();
            showSuccess("许可证已成功激活！");
        } catch (err: any) {
            showError(err.message || "许可证密钥无效或已被使用。");
        }
        setIsLoading(false);
    };

    return (
        <form onSubmit={handleValidateLicense} className="p-4 space-y-4 relative">
            <Toaster toasts={toasts} onRemove={removeToast} />

            {isLoading && (
                <div className="absolute inset-0 bg-white/50 dark:bg-neutral-800/50 flex items-center justify-center z-10">
                    <Spinner />
                </div>
            )}

            <button
                type="button"
                onClick={onBack}
                className="flex items-center gap-1 text-xs text-neutral-500 dark:text-neutral-400 hover:underline mb-2"
                disabled={isLoading}
            >
                <FiArrowLeft size={12} /> Back to options
            </button>

            <div className="text-center">
                <FiLogIn className="mx-auto text-4xl text-neutral-400" />
                <h5 className="mt-2 font-semibold text-neutral-800 dark:text-neutral-100">
                    Validate Your License
                </h5>
            </div>

            <div className="space-y-2">
                <label htmlFor="license-key-validate" className="text-xs font-medium text-neutral-600 dark:text-neutral-300">
                    License Key
                </label>
                <input
                    id="license-key-validate"
                    type="text"
                    value={activationKey}
                    onChange={(e) => setActivationKey(e.target.value)}
                    placeholder="LIC-XXXX-XXXX-XXXX"
                    className="w-full p-2 border border-neutral-300 dark:border-neutral-600 rounded-lg bg-white dark:bg-neutral-700 focus:outline-none focus:ring-2 focus:ring-yellow-500 text-neutral-900 dark:text-neutral-100"
                    disabled={isLoading}
                />
            </div>

            <button
                type="submit"
                className="w-full py-2.5 px-3 bg-yellow-400 text-black font-semibold rounded-lg hover:bg-yellow-500 transition text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={isLoading || activationKey.length < 8}
            >
                {isLoading ? "Validating..." : "Validate & Activate"}
            </button>
        </form>
    );
};

export default ValidateLicenseFlow;