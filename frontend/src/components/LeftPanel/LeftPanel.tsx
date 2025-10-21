import React, { useState, useCallback, useEffect, useRef } from "react";
import ResizeHandle from "../ResizeHandle/ResizeHandle";
import AuthModal from "../Auth/AuthModal";
import TopPanel from "./TopPanel";
import MiddlePanel from "./MiddlePanel";
import BottomPanel from "./BottomPanel";
import { useChat } from "../../context/ChatContext";
import { useAuth } from "../../context/AuthContext";

/** 常量 */
const PANEL_DEFAULT_WIDTH = 280;
const COLLAPSED_PANEL_WIDTH = 80;
const PANEL_MIN_WIDTH = 200;
const PANEL_MAX_WIDTH = 700;
const RESIZE_HANDLE_WIDTH = 12;

interface Props {
  onWidthChange: (width: number) => void;
}

const LeftPanel: React.FC<Props> = ({ onWidthChange }) => {
  // 状态
  const [isOpen, setIsOpen] = useState<boolean>(true);
  const [width, setWidth] = useState<number>(PANEL_DEFAULT_WIDTH);
  const lastOpenWidth = useRef<number>(PANEL_DEFAULT_WIDTH);
  const [isResizing, setIsResizing] = useState<boolean>(false);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState<boolean>(false);
  const [searchTerm, setSearchTerm] = useState<string>("");
  const panelRef = useRef<HTMLDivElement | null>(null);

  // 上下文
  const { createNewChat, deleteChat, selectChat } = useChat();
  const { authState, logout, isLoading: authLoading } = useAuth();

  // 拖拽逻辑 (保持不变)
  const handleMouseDown = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsResizing(true);
  }, []);

  const handleMouseMove = useCallback(
    (e: MouseEvent) => {
      if (!isResizing) return;
      const panelLeft = panelRef.current ? panelRef.current.getBoundingClientRect().left : 0;
      const newWidth = e.clientX - panelLeft;
      const clamped = Math.max(PANEL_MIN_WIDTH, Math.min(newWidth, PANEL_MAX_WIDTH));
      setWidth(clamped);
      lastOpenWidth.current = clamped;
    },
    [isResizing]
  );

  const handleMouseUp = useCallback(() => {
    setIsResizing(false);
  }, []);

  // 全局事件监听 (保持不变)
  useEffect(() => {
    if (isResizing) {
      document.addEventListener("mousemove", handleMouseMove);
      document.addEventListener("mouseup", handleMouseUp);
      document.body.style.cursor = "col-resize";
    } else {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
      document.body.style.cursor = "default";
    }
    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
      document.body.style.cursor = "default";
    };
  }, [isResizing, handleMouseMove, handleMouseUp]);

  // 其他 Hooks (保持不变)
  useEffect(() => {
    const currentWidth = isOpen ? width : COLLAPSED_PANEL_WIDTH;
    onWidthChange(currentWidth);
  }, [isOpen, width, onWidthChange]);

  const togglePanel = useCallback(() => {
    setIsOpen((prev) => {
      const next = !prev;
      if (next) {
        setWidth(Math.max(PANEL_MIN_WIDTH, Math.min(lastOpenWidth.current || PANEL_DEFAULT_WIDTH, PANEL_MAX_WIDTH)));
      } else {
        lastOpenWidth.current = width;
      }
      return next;
    });
  }, [width]);

  const handleNewChat = useCallback(() => {
    if (!authState?.isLoggedIn) {
      setIsAuthModalOpen(true);
      return;
    }
    createNewChat();
  }, [authState, createNewChat]);

  const handleDeleteChat = useCallback(
    (e: React.MouseEvent, chatId: string) => {
      e.stopPropagation();
      if (window.confirm("确定要删除这个聊天吗?")) {
        deleteChat(chatId);
      }
    },
    [deleteChat]
  );

  const handleSelectChat = useCallback(
    (chatId: string) => {
      if (!authState?.isLoggedIn) {
        setIsAuthModalOpen(true);
        return;
      }
      selectChat(chatId);
    },
    [authState, selectChat]
  );

  const handleOpenAuth = useCallback(() => {
    setIsAuthModalOpen(true);
  }, []);

  // --- 渲染 ---
  return (
    <>
      <div
        ref={panelRef}
        // [!!] Updated dark mode background and border colors
        className={`fixed top-0 left-0 h-screen bg-white  border-gray-200 shadow-lg flex flex-col transition-width duration-300 ease-in-out z-40 dark:bg-neutral-900 dark:border-neutral-700`}
        style={{
          width: isOpen ? `${width}px` : `${COLLAPSED_PANEL_WIDTH}px`,
          minWidth: `${COLLAPSED_PANEL_WIDTH}px`,
        }}
        onClick={!isOpen ? togglePanel : undefined}
      >
        {/* 顶部：标题 + 折叠按钮 */}
        <TopPanel isOpen={isOpen} togglePanel={togglePanel} />

        {/* 中间区域（可滚动） */}
        <div className="flex-1 relative overflow-hidden flex flex-col">
          <div
            className={`flex-1 overflow-y-auto transition-all duration-300 ease-in-out px-2`}
            style={{
              opacity: isOpen ? 1 : 0,
              pointerEvents: isOpen ? "auto" : "none",
              transform: isOpen ? "translateX(0)" : "translateX(-4px)",
            }}
          >
            <MiddlePanel
              searchTerm={searchTerm}
              setSearchTerm={setSearchTerm}
              onNewChat={handleNewChat}
              onSelectChat={handleSelectChat}
              onDeleteChat={handleDeleteChat}
            />
          </div>

          {/* 拖拽条 (保持不变) */}
          <div
            className="absolute top-0 right-0 h-full z-50"
            style={{
              width: `${RESIZE_HANDLE_WIDTH}px`,
              transform: `translateX(${RESIZE_HANDLE_WIDTH / 2}px)`,
            }}
          >
            <ResizeHandle onMouseDown={handleMouseDown} />
          </div>
        </div>

        {/* 底部区域 */}
        <div
          className={`flex-shrink-0 w-full transition-all duration-300 ease-in-out`}
          style={{
            opacity: isOpen ? 1 : 0,
            pointerEvents: isOpen ? "auto" : "none",
            transform: isOpen ? "translateX(0)" : "translateX(-4px)",
          }}
        >
          <BottomPanel onOpenAuth={handleOpenAuth} />
        </div>
      </div>

      {/* 认证模态 (保持不变) */}
      <AuthModal isOpen={isAuthModalOpen} onClose={() => setIsAuthModalOpen(false)} />
    </>
  );
};

export default LeftPanel;