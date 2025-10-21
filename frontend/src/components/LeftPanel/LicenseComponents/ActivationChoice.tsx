// src/components/LeftPanel/ActivationChoice.tsx
import React, { useState } from "react";
import { FiKey, FiGift, FiLogIn } from "react-icons/fi";
import CreateLicenseFlow from "./CreateLicenseFlow"; // Import Path A component
import ValidateLicenseFlow from "./ValidateLicenseFlow"; // Import Path B component

interface Props {
    onActivationSuccess: () => void; // Pass this down
}

type ActivationSubFlow = "choice" | "create" | "validate";

const ActivationChoice: React.FC<Props> = ({ onActivationSuccess }) => {
    const [subFlow, setSubFlow] = useState<ActivationSubFlow>("choice");

    // Callback to return to the choice screen
    const handleBackToChoice = () => {
        setSubFlow("choice");
    };

    // Render the main choice view
    const renderChoiceView = () => (
        <div className="p-4 space-y-4">
            <div className="text-center">
                <FiKey className="mx-auto text-4xl text-neutral-400" />
                <h5 className="mt-2 font-semibold text-neutral-800 dark:text-neutral-100">
                    Activate License
                </h5>
                <p className="text-sm text-neutral-500 dark:text-neutral-400">
                    Choose an option to activate Pro features.
                </p>
            </div>
            <button
                onClick={() => setSubFlow("create")}
                // [!! 修正] 颜色改为 yellow/black
                className="w-full flex items-center justify-center gap-2 py-2.5 px-3 bg-yellow-400 text-black font-semibold rounded-lg hover:bg-yellow-500 transition text-sm"
            >
                <FiGift size={16} />
                Create New License (Trial)
            </button>
            <button
                onClick={() => setSubFlow("validate")}
                className="w-full flex items-center justify-center gap-2 py-2.5 px-3 bg-neutral-100 dark:bg-neutral-800 text-neutral-700 dark:text-neutral-200 font-medium rounded-lg hover:bg-neutral-200 dark:hover:bg-neutral-700 transition text-sm"
            >
                <FiLogIn size={16} />
                Use Existing License Key
            </button>
        </div>
    );

    // Render the correct sub-flow
    const renderContent = () => {
        switch (subFlow) {
            case "create":
                // Pass onActivationSuccess which signals completion *after* user confirms saving key
                return <CreateLicenseFlow onBack={handleBackToChoice} onFinish={onActivationSuccess} />;
            case "validate":
                // Pass onActivationSuccess which signals completion immediately on API success
                return <ValidateLicenseFlow onBack={handleBackToChoice} onSuccess={onActivationSuccess} />;
            case "choice":
            default:
                return renderChoiceView();
        }
    };

    return (
        // Wrapper div inheriting parent styles
        <div className="relative overflow-y-auto max-h-96"> {/* Ensure scrollable */}
            {renderContent()}
        </div>
    );
};

export default ActivationChoice;