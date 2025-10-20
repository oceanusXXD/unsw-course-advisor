// LeftPanel.tsx
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
const COLLAPSED_PANEL_WIDTH = 56;
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

  // 拖拽：按下
  const handleMouseDown = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsResizing(true);
  }, []);

  // 拖拽：移动（基于面板左边界计算宽度）
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

  // 拖拽：释放
  const handleMouseUp = useCallback(() => {
    setIsResizing(false);
  }, []);

  // 全局事件监听（拖拽）
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

  // 把宽度通知父组件（展开/收起时发送当前有效宽度）
  useEffect(() => {
    const currentWidth = isOpen ? width : COLLAPSED_PANEL_WIDTH;
    onWidthChange(currentWidth);
  }, [isOpen, width, onWidthChange]);

  // 切换收起/展开（展开时恢复上次宽度）
  const togglePanel = useCallback(() => {
    setIsOpen((prev) => {
      const next = !prev;
      if (next) {
        // 展开，恢复上次宽度（保证在范围内）
        setWidth(Math.max(PANEL_MIN_WIDTH, Math.min(lastOpenWidth.current || PANEL_DEFAULT_WIDTH, PANEL_MAX_WIDTH)));
      } else {
        // 收起时保存当前宽度
        lastOpenWidth.current = width;
      }
      return next;
    });
  }, [width]);

  // 新建聊天（需要登录）
  const handleNewChat = useCallback(() => {
    if (!authState?.isLoggedIn) {
      setIsAuthModalOpen(true);
      return;
    }
    createNewChat();
  }, [authState, createNewChat]);

  // 删除聊天
  const handleDeleteChat = useCallback(
    (e: React.MouseEvent, chatId: string) => {
      e.stopPropagation();
      if (window.confirm("确定要删除这个聊天吗?")) {
        deleteChat(chatId);
      }
    },
    [deleteChat]
  );

  // 选择聊天
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

  // 打开认证模态
  const handleOpenAuth = useCallback(() => {
    setIsAuthModalOpen(true);
  }, []);

  return (
    <>
      <div
        ref={panelRef}
        className="fixed top-0 left-0 h-screen bg-white border-r border-gray-200 shadow-lg flex flex-col transition-[width] duration-300 ease-in-out z-40"
        style={{
          width: isOpen ? `${width}px` : `${COLLAPSED_PANEL_WIDTH}px`,
        }}
        onClick={!isOpen ? togglePanel : undefined}
      >
        {/* 顶部：标题 + 折叠按钮（TopPanel 只负责标题和按钮） */}
        <TopPanel isOpen={isOpen} togglePanel={togglePanel} />

        {/* 中间 + 底部 区域：始终渲染，使用 transform/opacity 做平滑显示/隐藏 */}
        <div className="flex-1 relative overflow-hidden flex flex-col">
          {/* 内容容器：使用平滑的 opacity + translate 动画来避免布局抖动 */}
          <div
            // 用 will-change 提示浏览器优化动画；用 aria-hidden 控制可访问性
            aria-hidden={!isOpen}
            className={`flex-1 flex flex-col w-full transition-all duration-280 ease-in-out`}
            style={{
              // 平滑控制可见性：当折叠时只做位移与透明度变化，避免重新布局
              opacity: isOpen ? 1 : 0,
              transform: isOpen ? "translateX(0)" : "translateX(-6px)",
              pointerEvents: isOpen ? "auto" : "none",
              willChange: "opacity, transform",
            }}
          >
            {/* 中间：搜索 / 新建 / 用户简略信息 & 聊天列表 */}
            <MiddlePanel
              searchTerm={searchTerm}
              setSearchTerm={setSearchTerm}
              onNewChat={handleNewChat}
              onSelectChat={handleSelectChat}
              onDeleteChat={handleDeleteChat}
            />

            {/* 底部：用户信息 / 登录 / 设置 / 登出 */}
            <BottomPanel onOpenAuth={handleOpenAuth} />
          </div>

          {/* 拖拽条（始终显示在右侧） */}
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
      </div>

      {/* 认证模态 */}
      <AuthModal isOpen={isAuthModalOpen} onClose={() => setIsAuthModalOpen(false)} />
    </>
  );
};

export default LeftPanel;
