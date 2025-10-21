// src/components/LeftPanel/ActivateLicensePopover.tsx (Wrapper - Final Version)

import React, { useState, useEffect } from "react";
import { FiArrowLeft } from "react-icons/fi";
import { ActiveMenu } from "./BottomComponents/BottomPanelUserProfileMenu";
import { AuthUser } from "./BottomComponents/BottomPanelTypes";
import ActivationChoice from "./LicenseComponents/ActivationChoice"; // Import the choice component
import LicenseDetailsView from "./LicenseComponents/LicenseDetailsView";

interface Props {
    setActiveMenu: (menu: ActiveMenu) => void;
    user: AuthUser;
}

const ActivateLicensePopover: React.FC<Props> = ({ setActiveMenu, user }) => {
    // Determine initial activation state from user prop
    const [isActivated, setIsActivated] = useState(
        user.subscription?.toUpperCase() !== "FREE" && user.subscription != null
    );

    // Update isActivated if the user prop changes (e.g., after refreshUser)
    useEffect(() => {
        setIsActivated(
            user.subscription?.toUpperCase() !== "FREE" && user.subscription != null
        );
    }, [user.subscription]);

    // Callback for ActivationChoice/Flows to signal success
    const handleActivationSuccess = () => {
        setIsActivated(true);
        // Maybe force LicenseDetailsView to 'idle' state if needed?
        // It should fetch fresh data anyway.
    };

    return (
        <div
            className="absolute bottom-16 left-0 w-96 bg-white dark:bg-neutral-800 shadow-xl rounded-2xl border border-neutral-200 dark:border-neutral-700 overflow-hidden animate-fadeIn z-50 flex flex-col"
            role="menu"
            style={{ maxHeight: "calc(100vh - 100px)" }} // Prevent excessive height
        >
            {/* 1. Header with Back Button (Common to both flows) */}
            <div className="flex items-center gap-2 p-3 border-b border-neutral-200 dark:border-neutral-700 flex-shrink-0">
                <button
                    onClick={() => setActiveMenu("main")} // Always returns to the main user menu
                    className="p-1 rounded-full hover:bg-neutral-100 dark:hover:bg-neutral-700"
                    aria-label="Back to main menu"
                >
                    <FiArrowLeft className="text-neutral-600 dark:text-neutral-400" />
                </button>
                <h4 className="text-sm font-semibold text-neutral-800 dark:text-neutral-100">
                    {isActivated ? "License Details" : "Activate License"}
                </h4>
            </div>

            {/* 2. Content Area: Render correct flow based on activation status */}
            {isActivated ? (
                <LicenseDetailsView user={user} />
            ) : (
                <ActivationChoice onActivationSuccess={handleActivationSuccess} />
            )}
        </div>
    );
};

export default ActivateLicensePopover;