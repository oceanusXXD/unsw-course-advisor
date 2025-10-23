// src/components/LeftPanel/BottomPanelUserProfileMenu.tsx

import React, { useState, useRef, useEffect } from "react";
import BottomPanelUserProfileButton from "./BottomPanelUserProfileButton";
import BottomPanelUserMenu from "./BottomPanelUserMenu";
import ActivateLicensePopover from "../ActivateLicensePopover";
import HelpPopover from "../HelpPopover";
import { AuthUser } from "./BottomPanelTypes";

export type ActiveMenu = "main" | "license" | "help" | null;

interface Props {
    user: AuthUser;
    logout: () => Promise<void>;
}

const BottomPanelUserProfileMenu: React.FC<Props> = ({ user, logout }) => {

    const [activeMenu, setActiveMenu] = useState<ActiveMenu>(null);
    const menuRef = useRef<HTMLDivElement | null>(null);

    // 点击外部关闭
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
                setActiveMenu(null);
            }
        };
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    const toggleMainMenu = () => {
        setActiveMenu((prev) => (prev === "main" ? null : "main"));
    };

    const renderActiveMenu = () => {
        switch (activeMenu) {
            case "main":
                return (
                    <BottomPanelUserMenu
                        user={user}
                        logout={logout}
                        setActiveMenu={setActiveMenu}
                    />
                );

            case "license":
                return (
                    <ActivateLicensePopover
                        setActiveMenu={setActiveMenu}
                        user={user}
                    />
                );

            case "help":
                return <HelpPopover setActiveMenu={setActiveMenu} />;
            default:
                return null;
        }
    };

    return (
        <div className="relative" ref={menuRef}>
            <BottomPanelUserProfileButton
                user={user}
                onClick={toggleMainMenu}
            />
            {renderActiveMenu()}
        </div>
    );
};

export default BottomPanelUserProfileMenu;