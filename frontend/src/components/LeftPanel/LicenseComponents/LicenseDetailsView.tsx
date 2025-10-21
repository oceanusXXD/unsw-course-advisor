// src/components/LeftPanel/LicenseDetailsView.tsx

import React, { useState } from "react";
import {
    FiEye,
    FiShield,
    FiMonitor,
    FiCalendar,
    FiCopy,
} from "react-icons/fi";
// [!! 修正] 导入路径
import { AuthUser } from "../BottomComponents/BottomPanelTypes";
import { getMyLicense } from "../../../services/api";
import { Spinner, Alert, KeyDisplay, InfoDisplay, CheckCircleIcon } from '../../common/CommonUI'; // Import helpers

// Matches /license/my/ response
interface LicenseDetails {
    license_key: string;
    device_id: string;
    license_active: boolean;
    license_expires_at: string;
}

interface Props {
    user: AuthUser;
}

type DetailsViewState = "idle" | "showing_keys";

const LicenseDetailsView: React.FC<Props> = ({ user }) => {
    const [viewState, setViewState] = useState<DetailsViewState>("idle");
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [licenseDetails, setLicenseDetails] = useState<LicenseDetails | null>(null);

    /** Get current user's license details */
    const handleViewLicense = async () => {
        setIsLoading(true);
        setError(null);
        try {
            const data: LicenseDetails = await getMyLicense();
            if (data && data.license_key) {
                setLicenseDetails(data);
                setViewState("showing_keys");
            } else {
                // This case might happen if license exists but API returns unexpected data
                throw new Error("Could not retrieve license information.");
            }
        } catch (err: any) {
            setError(err.message || "Failed to fetch license details.");
            // Don't change viewState on error, stay in idle
        }
        setIsLoading(false);
    };

    // Helper date formatter
    const formatExpiresAt = (dateString: string) => {
        if (!dateString) return "N/A";
        try {
            return new Date(dateString).toLocaleDateString("default", {
                year: 'numeric', month: 'long', day: 'numeric'
            });
        } catch { return dateString; }
    };

    // --- Render Functions ---

    // Initial view when license is active
    const renderActivatedIdle = () => (
        <div className="p-4 space-y-4">
            {isLoading && <div className="absolute inset-0 bg-white/50 dark:bg-neutral-800/50 flex items-center justify-center z-10"><Spinner /></div>}
            {error && <Alert message={error} onClose={() => setError(null)} />}
            {/* [!! 修正] 颜色改为 yellow */}
            <div className="p-4 bg-yellow-50 dark:bg-yellow-900/30 rounded-lg text-center border border-yellow-200 dark:border-yellow-800/50">
                <CheckCircleIcon className="mx-auto h-10 w-10 text-yellow-500" />
                <h5 className="mt-2 text-lg font-semibold text-yellow-700 dark:text-yellow-300">
                    {user.subscription?.toUpperCase() ?? 'Pro'} License Active
                </h5>
                <p className="text-sm text-neutral-600 dark:text-neutral-300">
                    Thank you! You have access to all Pro features.
                </p>
            </div>
            <button
                onClick={handleViewLicense}
                className="w-full flex items-center justify-center gap-2 py-2.5 px-3 bg-neutral-100 dark:bg-neutral-800 text-neutral-700 dark:text-neutral-200 font-medium rounded-lg hover:bg-neutral-200 dark:hover:bg-neutral-700 transition text-sm"
                disabled={isLoading}
            >
                <FiEye size={16} />
                {isLoading ? "Fetching..." : "View My License Details"}
            </button>
        </div>
    );

    // View to show license details (保持绿色，表示安全/激活状态)
    const renderShowingKeys = () => (
        <div className="p-4 space-y-4">
            {error && <Alert message={error} onClose={() => setError(null)} />} {/* Show potential errors */}
            <div className="text-center">
                <FiShield className="mx-auto text-4xl text-green-500" />
                <h5 className="mt-2 font-semibold text-neutral-800 dark:text-neutral-100">
                    Your License Information
                </h5>
            </div>
            <div className="space-y-1">
                <label className="text-xs font-medium text-neutral-600 dark:text-neutral-300">License Key</label>
                <KeyDisplay value={licenseDetails?.license_key || "Loading..."} />
            </div>
            <div className="space-y-1">
                <label className="text-xs font-medium text-neutral-600 dark:text-neutral-300">Activated Device ID</label>
                <InfoDisplay value={licenseDetails?.device_id || "Loading..."} icon={<FiMonitor />} />
            </div>
            <div className="space-y-1">
                <label className="text-xs font-medium text-neutral-600 dark:text-neutral-300">Expires At</label>
                <InfoDisplay value={licenseDetails ? formatExpiresAt(licenseDetails.license_expires_at) : "Loading..."} icon={<FiCalendar />} />
            </div>
            <button
                onClick={() => setViewState("idle")} // Go back to idle view
                className="w-full py-2.5 px-3 bg-neutral-100 dark:bg-neutral-800 text-neutral-700 dark:text-neutral-200 font-medium rounded-lg hover:bg-neutral-200 dark:hover:bg-neutral-700 transition text-sm"
            >
                Hide Details
            </button>
        </div>
    );

    // Main render logic
    const renderContent = () => {
        switch (viewState) {
            case "idle": return renderActivatedIdle();
            case "showing_keys": return renderShowingKeys();
            default: return renderActivatedIdle();
        }
    };

    return (
        <div className="relative overflow-y-auto max-h-96"> {/* Ensure scrollable */}
            {renderContent()}
        </div>
    );
};

export default LicenseDetailsView;