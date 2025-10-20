// MiddlePanel.tsx
import React, { useState } from "react";
import {
    FiSearch,
    FiEdit,
    FiClock,
    FiChevronUp,
    FiChevronDown,
    FiTrash2,
    FiFileText,
    FiBookmark,
} from "react-icons/fi";
import { useChat } from "../../context/ChatContext";
import { useAuth } from "../../context/AuthContext";

interface Props {
    searchTerm: string;
    setSearchTerm: (s: string) => void;
    onNewChat: () => void;
    onSelectChat: (id: string) => void;
    onDeleteChat: (e: React.MouseEvent, id: string) => void;
}

const MiddlePanel: React.FC<Props> = ({ searchTerm, setSearchTerm, onNewChat, onSelectChat, onDeleteChat }) => {
    const { chats, currentChat } = useChat();

    const [isHistoryOpen, setHistoryOpen] = useState<boolean>(true);
    const [hoveredChatId, setHoveredChatId] = useState<string | null>(null);

    const filteredChats = (chats ?? []).filter((chat: any) =>
        (chat.title ?? "").toLowerCase().includes((searchTerm ?? "").toLowerCase())
    );

    return (
        <div className="flex-1 flex flex-col w-full px-3 pb-3 overflow-hidden">
            {/* 搜索框 */}
            <div className="pt-4 pb-5">
                <div className="relative">
                    <FiSearch className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400" />
                    <input
                        type="text"
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        placeholder="Search"
                        aria-label="搜索聊天"
                        className="w-full pl-11 pr-9 py-3 rounded-2xl bg-gray-100 focus:outline-none focus:ring-2 focus:ring-gray-300 text-base text-gray-700 placeholder-gray-400 transition"
                    />
                    {searchTerm && (
                        <button
                            onClick={() => setSearchTerm("")}
                            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition"
                            aria-label="清除搜索"
                        >
                            ×
                        </button>
                    )}
                </div>
            </div>

            {/* 新建聊天按钮 */}
            <div className="pb-5">
                <button
                    onClick={onNewChat}
                    className="w-full flex items-center gap-3 px-4 py-3 rounded-2xl  hover:bg-gray-200 transition text-base text-gray-700 font-medium"
                    aria-label="新建聊天"
                >
                    <FiEdit className="text-gray-600" />
                    <span>New Chat</span>
                </button>
            </div>

            {/* 历史记录部分 */}
            <nav className="flex-grow space-y-3 text-gray-700 overflow-y-auto" aria-label="Sidebar navigation">
                <div>
                    <button
                        onClick={() => setHistoryOpen((s) => !s)}
                        className="w-full text-left py-3 px-4 rounded-2xl flex items-center justify-between bg-gray-100 hover:bg-gray-200 transition text-base text-gray-800 font-semibold"
                        aria-expanded={isHistoryOpen}
                        aria-controls="chat-history-list"
                    >
                        <div className="flex items-center gap-3">
                            <FiClock className="text-gray-600" />
                            <span>Projects</span>
                        </div>
                        {isHistoryOpen ? <FiChevronUp /> : <FiChevronDown />}
                    </button>

                    {isHistoryOpen && (
                        <>
                            {filteredChats.length > 0 ? (
                                <div id="chat-history-list" className="mt-2 pl-5 space-y-1">
                                    {filteredChats.map((chat: any) => (
                                        <div
                                            key={chat.id}
                                            className="relative group"
                                            onMouseEnter={() => setHoveredChatId(chat.id)}
                                            onMouseLeave={() => setHoveredChatId(null)}
                                        >
                                            <button
                                                onClick={() => onSelectChat(chat.id)}
                                                className={`w-full text-left py-2 px-3 rounded-xl flex items-center gap-2 transition truncate text-sm ${currentChat?.id === chat.id
                                                    ? "bg-gray-200 text-gray-900 font-semibold"
                                                    : "text-gray-600 hover:bg-gray-100"
                                                    }`}
                                                title={chat.title ?? "Chat"}
                                            >
                                                <span className="w-1.5 h-1.5 bg-gray-300 rounded-full flex-shrink-0" />
                                                <span className="truncate flex-1">
                                                    {(chat.title ?? "").length > 24
                                                        ? `${(chat.title ?? "").substring(0, 24)}...`
                                                        : chat.title ?? "Untitled"}
                                                </span>
                                            </button>

                                            {hoveredChatId === chat.id && (
                                                <button
                                                    onClick={(e) => onDeleteChat(e, chat.id)}
                                                    className="absolute right-1 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-red-500 transition"
                                                    title="删除聊天"
                                                >
                                                    <FiTrash2 size={14} />
                                                </button>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <div className="mt-2 pl-5 text-sm text-gray-400 py-2">
                                    {searchTerm ? "No results" : "No conversations yet"}
                                </div>
                            )}
                        </>
                    )}
                </div>

                {/* 底部导航项 */}
                <div className="pt-5 space-y-3">
                    <a
                        href="#"
                        className="w-full flex items-center gap-3 py-3 px-4 rounded-2xl hover:bg-gray-100 transition text-base text-gray-700 font-medium"
                    >
                        <FiFileText className="text-gray-600" /> <span>Documents</span>
                    </a>
                    <a
                        href="#"
                        className="w-full flex items-center gap-3 py-3 px-4 rounded-2xl hover:bg-gray-100 transition text-base text-gray-700 font-medium"
                    >
                        <FiBookmark className="text-gray-600" /> <span>Saved</span>
                    </a>
                </div>
            </nav>
        </div>
    );
};

export default MiddlePanel;
