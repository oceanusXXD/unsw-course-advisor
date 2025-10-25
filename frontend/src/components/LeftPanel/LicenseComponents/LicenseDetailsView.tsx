import React, { useState } from "react";
import { FiEye, FiShield, FiMonitor, FiCalendar } from "react-icons/fi";
import { AuthUser } from "../BottomComponents/BottomPanelTypes";
import { getMyLicense } from "../../../services/api";
import { Toaster, useToaster } from "../../Toaster/Toaster";
import {
    Spinner,
    KeyDisplay,
    InfoDisplay,
    CheckCircleIcon,
} from "../../common/CommonUI";

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
    const [licenseDetails, setLicenseDetails] = useState<LicenseDetails | null>(null);
    const { toasts, removeToast, showSuccess, showError } = useToaster();

    const handleViewLicense = async () => {
        setIsLoading(true);
        try {
            const data: LicenseDetails = await getMyLicense();
            if (data && data.license_key) {
                setLicenseDetails(data);
                setViewState("showing_keys");
                showSuccess("许可证详情获取成功。");
            } else {
                throw new Error("Could not retrieve license information.");
            }
        } catch (err: any) {
            showError(err.message || "Failed to fetch license details.");
        }
        setIsLoading(false);
    };

    const formatExpiresAt = (dateString: string) => {
        if (!dateString) return "N/A";
        try {
            return new Date(dateString).toLocaleDateString("default", {
                year: "numeric",
                month: "long",
                day: "numeric",
            });
        } catch {
            return dateString;
        }
    };

    const renderActivatedIdle = () => (
        <div className="p-4 space-y-4">
            {isLoading && (
                <div className="absolute inset-0 bg-white/50 dark:bg-neutral-800/50 flex items-center justify-center z-10">
                    <Spinner />
                </div>
            )}
            <div className="p-4 bg-yellow-50 dark:bg-yellow-900/30 rounded-lg text-center border border-yellow-200 dark:border-yellow-800/50">
                <CheckCircleIcon className="mx-auto h-10 w-10 text-yellow-500" />
                <h5 className="mt-2 text-lg font-semibold text-yellow-700 dark:text-yellow-300">
                    {user.subscription?.toUpperCase() ?? "Pro"} License Active
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

    const renderShowingKeys = () => (
        <div className="p-4 space-y-4">
            <div className="text-center">
                <FiShield className="mx-auto text-4xl text-green-500" />
                <h5 className="mt-2 font-semibold text-neutral-800 dark:text-neutral-100">
                    Your License Information
                </h5>
            </div>
            <div className="space-y-1">
                <label className="text-xs font-medium text-neutral-600 dark:text-neutral-300">
                    License Key
                </label>
                <KeyDisplay value={licenseDetails?.license_key || "Loading..."} />
            </div>
            <div className="space-y-1">
                <label className="text-xs font-medium text-neutral-600 dark:text-neutral-300">
                    Activated Device ID
                </label>
                <InfoDisplay
                    value={licenseDetails?.device_id || "Loading..."}
                    key-value
                    icon={<FiMonitor />}
                />
            </div>
            <div className="space-y-1">
                <label className="text-xs font-medium text-neutral-600 dark:text-neutral-300">
                    Expires At
                </label>
                <InfoDisplay
                    value={
                        licenseDetails
                            ? formatExpiresAt(licenseDetails.license_expires_at)
                            : "Loading..."
                    }
                    icon={<FiCalendar />}
                />
            </div>
            <button
                onClick={() => setViewState("idle")}
                className="w-full py-2.5 px-3 bg-neutral-100 dark:bg-neutral-800 text-neutral-700 dark:text-neutral-200 font-medium rounded-lg hover:bg-neutral-200 dark:hover:bg-neutral-700 transition text-sm"
            >
                Hide Details
            </button>
        </div>
    );

    const renderContent = () => {
        switch (viewState) {
            case "idle":
                return renderActivatedIdle();
            case "showing_keys":
                return renderShowingKeys();
            default:
                return renderActivatedIdle();
        }
    };

    return (
        <div className="relative overflow-y-auto max-h-96">
            <Toaster toasts={toasts} onRemove={removeToast} />
            {renderContent()}
        </div>
    );
};

export default LicenseDetailsView;