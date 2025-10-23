// App.tsx

import React, { useState, useCallback, useRef, useEffect } from "react";
import Chat from "./components/Chat/Chat";
import LeftPanel from "./components/LeftPanel/LeftPanel";
import RightPanel, { ResultItem } from "./components/RightPanel/RightPanel";
import ResizeHandle from "./components/ResizeHandle/ResizeHandle";
import { AuthProvider } from "./context/AuthContext";
import { ChatProvider } from "./context/ChatContext";
import { imageUrls } from "./assets/assets";
import "./index.css";

// Import AppProvider and AppContext
import { AppProvider, useAppContext } from "./context/AppContext";
// Import the new settings page
import SettingsPage from "./components/SettingsPage/SettingsPage";

// --- Constants (unchanged) ---
const RIGHT_PANEL_DEFAULT_WIDTH = 288;
const RIGHT_PANEL_MIN_WIDTH = 240;
const RIGHT_PANEL_MAX_WIDTH = 600;
const RESIZE_HANDLE_WIDTH = 12;
const COLLAPSED_PANEL_WIDTH_PX = 56;

const AppContent: React.FC = () => {
  // Get current view from Context
  const { activeView } = useAppContext();

  // --- State management (unchanged) ---
  const [leftPanelWidth, setLeftPanelWidth] = useState(280);
  const [results, setResults] = useState<ResultItem[]>([]);
  const [isRightPanelOpen, setIsRightPanelOpen] = useState(false);
  const [rightPanelWidth, setRightPanelWidth] = useState(
    RIGHT_PANEL_DEFAULT_WIDTH,
  );
  const [isResizing, setIsResizing] = useState(false);

  const chatRef = useRef<HTMLDivElement | null>(null);

  const mockCourses = [
    {
      id: "1",
      code: "CS101 - Intro to Programming",
      score: "A",
      description: "学习基础编程概念，包括变量、循环、函数与数据结构。",
      icon: "https://cdn-icons-png.flaticon.com/512/2721/2721292.png",
    },
    {
      id: "2",
      code: "CS204 - Data Structures",
      score: "B+",
      description: "介绍算法复杂度分析、链表、栈、队列、树与图等常用数据结构。",
      icon: "https://cdn-icons-png.flaticon.com/512/1975/1975643.png",
    },
  ];

  const handleLeftPanelWidthChange = useCallback((newWidth: number) => {
    setLeftPanelWidth(newWidth);
  }, []);

  const toggleRightPanel = () => setIsRightPanelOpen((prev) => !prev);
  //TODO
  const handleSources = (sourcesData: any[]) => {
  };

  const handleResizeMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsResizing(true);
  };

  const handleResizeMouseMove = useCallback(
    (e: MouseEvent) => {
      if (!isResizing) return;
      const newWidth = window.innerWidth - e.clientX;
      const clampedWidth = Math.max(
        RIGHT_PANEL_MIN_WIDTH,
        Math.min(newWidth, RIGHT_PANEL_MAX_WIDTH),
      );
      setRightPanelWidth(clampedWidth);
    },
    [isResizing],
  );

  const handleResizeMouseUp = useCallback(() => {
    setIsResizing(false);
  }, []);

  useEffect(() => {
    if (isResizing) {
      document.body.style.cursor = "col-resize";
      document.addEventListener("mousemove", handleResizeMouseMove);
      document.addEventListener("mouseup", handleResizeMouseUp);
    } else {
      document.body.style.cursor = "default";
      document.removeEventListener("mousemove", handleResizeMouseMove);
      document.removeEventListener("mouseup", handleResizeMouseUp);
    }
    return () => {
      document.body.style.cursor = "default";
      document.removeEventListener("mousemove", handleResizeMouseMove);
      document.removeEventListener("mouseup", handleResizeMouseUp);
    };
  }, [isResizing, handleResizeMouseMove, handleResizeMouseUp]);

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-neutral-800 w-full">
      <LeftPanel onWidthChange={handleLeftPanelWidthChange} />

      <div
        className="flex justify-center transition-all duration-300 ease-in-out"
        style={{
          paddingLeft: `${leftPanelWidth}px`,
          paddingRight: isRightPanelOpen
            ? `${rightPanelWidth}px`
            : `${COLLAPSED_PANEL_WIDTH_PX}px`,
        }}
      >
        <div
          ref={chatRef}
          className="w-full h-screen overflow-y-auto py-4 px-2"
        >
          {activeView === "chat" && <Chat onSources={handleSources} />}
          {activeView === "settings" && <SettingsPage />}
        </div>
      </div>

      <div
        className="fixed top-0 right-0 h-screen bg-white dark:bg-neutral-900 shadow-lg flex flex-col transition-[width] duration-300 ease-in-out z-40"
        style={{
          width: isRightPanelOpen
            ? `${rightPanelWidth}px`
            : `${COLLAPSED_PANEL_WIDTH_PX}px`,
        }}
        onClick={!isRightPanelOpen ? toggleRightPanel : undefined}
      >
        <div
          className="h-full w-full flex flex-col"
          onClick={(e) => e.stopPropagation()}
        >
          <div
            className={`flex-shrink-0 w-full h-16 flex items-center transition-all duration-300 ease-in-out ${isRightPanelOpen ? "justify-start px-4" : "justify-center px-0"
              }`}
          >
            <button
              onClick={toggleRightPanel}
              className="p-2 rounded-full hover:bg-gray-100 dark:hover:bg-neutral-700"
              title={isRightPanelOpen ? "Collapse" : "Expand"}
            >
              {isRightPanelOpen ? (
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={1.5}
                  stroke="currentColor"
                  className="w-6 h-6"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="m8.25 4.5 7.5 7.5-7.5 7.5"
                  />
                </svg>
              ) : (
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={1.5}
                  stroke="currentColor"

                  className="w-6 h-6"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M15.75 19.5 8.25 12l7.5-7.5"
                  />
                </svg>
              )}
            </button>
          </div>
          <div className="flex-1 relative overflow-hidden">
            {isRightPanelOpen && (
              <>
                <RightPanel results={mockCourses} />
                <div
                  className="absolute top-0 left-0 h-full z-50"
                  style={{
                    width: `${RESIZE_HANDLE_WIDTH}px`,
                    transform: `translateX(-${RESIZE_HANDLE_WIDTH / 2}px)`,
                  }}
                >
                  <ResizeHandle onMouseDown={handleResizeMouseDown} />
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

const App: React.FC = () => {
  return (
    <AuthProvider>
      <ChatProvider>
        <AppProvider>
          <AppContent />
        </AppProvider>
      </ChatProvider>
    </AuthProvider>
  );
};

export default App;