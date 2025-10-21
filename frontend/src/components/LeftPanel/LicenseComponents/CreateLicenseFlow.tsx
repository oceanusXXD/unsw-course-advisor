// src/components/LeftPanel/CreateLicenseFlow.tsx
import React, { useState } from "react";
import {
    FiArrowLeft,
    FiGift,
    FiAlertTriangle,
    FiCopy,
    FiXCircle,
    FiX,
} from "react-icons/fi";
import { useAuth } from "../../../context/AuthContext";
import { activateLicense } from "../../../services/api";
import { Spinner, Alert, KeyDisplay } from '../../common/CommonUI'; // Import helpers

// Matches /license/activate/ response
interface NewLicenseDetails {
    license_key: string;
    user_key: string;
    device_id: string;
    license_expires_at: string;
}

interface Props {
    onBack: () => void; // Go back to the choice screen
    onFinish: () => void; // Signal successful creation *after* user acknowledges
}

const CreateLicenseFlow: React.FC<Props> = ({ onBack, onFinish }) => {
    const { refreshUser } = useAuth();
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [newLicenseDetails, setNewLicenseDetails] = useState<NewLicenseDetails | null>(null);

    /** Handle Create License API Call */
    const handleCreateLicense = async () => {
        setIsLoading(true);
        setError(null);
        try {
            const data: NewLicenseDetails = await activateLicense(365); // Assuming 365 day trial
            setNewLicenseDetails(data); // Store keys to display
            if (refreshUser) await refreshUser(); // Refresh auth state in background
        } catch (err: any) {
            setError(err.message || "Failed to create license. You might already have one.");
        }
        setIsLoading(false);
    };

    // Initial button view
    const renderCreateButton = () => (
        <div className="p-4 space-y-4">
            {isLoading && <div className="absolute inset-0 bg-white/50 dark:bg-neutral-800/50 flex items-center justify-center z-10"><Spinner /></div>}
            {error && <Alert message={error} onClose={() => setError(null)} />}
            <button
                type="button"
                onClick={onBack}
                className="flex items-center gap-1 text-xs text-neutral-500 dark:text-neutral-400 hover:underline mb-2"
                disabled={isLoading}
            >
                <FiArrowLeft size={12} /> Back to options
            </button>
            <div className="text-center">
                {/* [!! 修正] 图标颜色改为 yellow */}
                <FiGift className="mx-auto text-4xl text-yellow-500" />
                <h5 className="mt-2 font-semibold text-neutral-800 dark:text-neutral-100">
                    Create New License
                </h5>
                <p className="text-sm text-neutral-500 dark:text-neutral-400">
                    Get started with a trial license.
                </p>
            </div>
            <button
                onClick={handleCreateLicense}
                // [!! 修正] 颜色改为 yellow/black
                className="w-full flex items-center justify-center gap-2 py-2.5 px-3 bg-yellow-400 text-black font-semibold rounded-lg hover:bg-yellow-500 transition text-sm disabled:opacity-50"
                disabled={isLoading}
            >
                <FiGift size={16} />
                {isLoading ? "Creating..." : "Create Trial License"}
            </button>
        </div>
    );

    // View after successful creation to show keys
    const renderShowingNewKeys = () => (
        <div className="p-4 space-y-4">
            {/* (这个警告框已经是黄色，保持不变) */}
            <div className="p-4 bg-yellow-50 dark:bg-yellow-900/30 rounded-lg text-center border border-yellow-200 dark:border-yellow-800/50">
                <FiAlertTriangle className="mx-auto h-10 w-10 text-yellow-500 dark:text-yellow-400" />
                <h5 className="mt-2 text-lg font-semibold text-yellow-700 dark:text-yellow-300">
                    Save Your User Key Now!
                </h5>
                <p className="text-sm text-yellow-600 dark:text-yellow-400">
                    This is the **only** time you will see the `User Key`. Copy and store it securely (e.g., password manager).
                </p>
            </div>
            <div className="space-y-1">
                <label className="text-xs font-medium text-neutral-600 dark:text-neutral-300">
                    License Key
                </label>
                <KeyDisplay value={newLicenseDetails?.license_key || "..."} />
            </div>
            <div className="space-y-1">
                <label className="text-xs font-medium text-red-600 dark:text-red-400">
                    User Key (Save Immediately!)
                </label>
                <KeyDisplay value={newLicenseDetails?.user_key || "..."} />
            </div>
            <button
                onClick={onFinish} // User confirms they saved the key
                // [!! 修正] 颜色改为 yellow/black
                className="w-full py-2.5 px-3 bg-yellow-400 text-black font-semibold rounded-lg hover:bg-yellow-500 transition text-sm"
            >
                I Have Saved My User Key, Finish
            </button>
        </div>
    );

    return (
        <div className="relative overflow-y-auto max-h-96"> {/* Ensure container is scrollable if content overflows */}
            {newLicenseDetails ? renderShowingNewKeys() : renderCreateButton()}
        </div>
    );
};

export default CreateLicenseFlow;