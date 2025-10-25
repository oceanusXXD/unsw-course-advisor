import React, { createContext, useContext, useState, useCallback, useEffect, useRef } from "react";
import { ChatItem, Message } from "../types";

interface ChatContextType {
    chats: ChatItem[];
    currentChat: ChatItem | null;
    createNewChat: (title?: string) => ChatItem;
    deleteChat: (chatId: string) => void;
    selectChat: (chatId: string) => void;
    addMessage: (chatId: string, message: Message) => void;
    updateChatTitle: (chatId: string, title: string) => void;
    updateLastMessageContent: (chatId: string, chunk: string) => void;
}

const ChatContext = createContext<ChatContextType | undefined>(undefined);

const STORAGE_KEY = "chats";
const DEBOUNCE_DELAY = 500; // 500ms 防抖延迟
const MAX_CHATS = 100; // 最多保存 100 个对话
const MAX_MESSAGES_PER_CHAT = 500; // 每个对话最多 500 条消息

export const ChatProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [chats, setChats] = useState<ChatItem[]>([]);
    const [currentChat, setCurrentChat] = useState<ChatItem | null>(null);

    // 防抖保存的定时器引用
    const saveTimerRef = useRef<number | null>(null);
    // 用于跟踪是否正在流式更新（避免频繁保存）
    const isStreamingRef = useRef(false);

    // 初始化：从 localStorage 加载数据
    useEffect(() => {
        const loadChats = () => {
            try {
                const savedChats = localStorage.getItem(STORAGE_KEY);
                if (!savedChats) return;

                const parsedChats = JSON.parse(savedChats) as ChatItem[];

                // 数据验证和转换
                const validChats = parsedChats
                    .filter(chat => chat.id && chat.messages) // 过滤无效数据
                    .slice(0, MAX_CHATS) // 限制数量
                    .map(chat => ({
                        ...chat,
                        createdAt: new Date(chat.createdAt),
                        updatedAt: new Date(chat.updatedAt),
                        messages: chat.messages
                            .slice(-MAX_MESSAGES_PER_CHAT) // 只保留最近的消息
                            .map(msg => ({
                                ...msg,
                                timestamp: new Date(msg.timestamp),
                            }))
                    }));

                setChats(validChats);
            } catch (e) {
                console.error("Failed to load chats from localStorage:", e);
                // 损坏的数据清理
                try {
                    localStorage.removeItem(STORAGE_KEY);
                } catch (clearError) {
                    console.error("Failed to clear corrupted data:", clearError);
                }
            }
        };

        loadChats();
    }, []);

    // 优化的保存函数：带防抖、错误处理和配额检测
    const saveChatsToStorage = useCallback((newChats: ChatItem[], immediate = false) => {
        const performSave = () => {
            try {
                // 数据清理和优化
                const chatsToSave = newChats
                    .slice(0, MAX_CHATS)
                    .map(chat => ({
                        ...chat,
                        messages: chat.messages.slice(-MAX_MESSAGES_PER_CHAT)
                    }));

                const serialized = JSON.stringify(chatsToSave);

                // 检查数据大小（localStorage 通常限制 5-10MB）
                const sizeInMB = new Blob([serialized]).size / (1024 * 1024);
                if (sizeInMB > 4.5) {
                    console.warn(`Storage size approaching limit: ${sizeInMB.toFixed(2)}MB`);
                    // 可以在这里触发数据清理策略
                }

                localStorage.setItem(STORAGE_KEY, serialized);
            } catch (e) {
                // 处理配额超出错误
                if (e instanceof DOMException && e.name === 'QuotaExceededError') {
                    console.error("Storage quota exceeded. Attempting cleanup...");
                    try {
                        // 紧急清理：只保留最近的对话
                        const reducedChats = newChats.slice(0, Math.floor(MAX_CHATS / 2));
                        localStorage.setItem(STORAGE_KEY, JSON.stringify(reducedChats));
                    } catch (retryError) {
                        console.error("Failed to save even after cleanup:", retryError);
                    }
                } else {
                    console.error("Failed to save chats:", e);
                }
            }
        };

        // 清除之前的定时器
        if (saveTimerRef.current) {
            clearTimeout(saveTimerRef.current);
        }

        if (immediate || isStreamingRef.current === false) {
            // 立即保存（用于删除、创建等关键操作）
            performSave();
        } else {
            // 防抖保存（用于流式更新）
            saveTimerRef.current = setTimeout(performSave, DEBOUNCE_DELAY);
        }
    }, []);

    // 清理定时器
    useEffect(() => {
        return () => {
            if (saveTimerRef.current) {
                clearTimeout(saveTimerRef.current);
            }
        };
    }, []);

    const createNewChat = useCallback((title?: string): ChatItem => {
        const newChat: ChatItem = {
            id: "chat_" + Date.now() + "_" + Math.random().toString(36).substr(2, 9),
            title: title || `New Chat - ${new Date().toLocaleString()}`,
            createdAt: new Date(),
            updatedAt: new Date(),
            messages: [],
        };

        setChats(prevChats => {
            const updatedChats = [newChat, ...prevChats];
            saveChatsToStorage(updatedChats, true); // 立即保存
            return updatedChats;
        });
        setCurrentChat(newChat);
        return newChat;
    }, [saveChatsToStorage]);

    const deleteChat = useCallback((chatId: string) => {
        setChats(prevChats => {
            const updatedChats = prevChats.filter((chat) => chat.id !== chatId);
            saveChatsToStorage(updatedChats, true); // 立即保存

            if (currentChat?.id === chatId) {
                setCurrentChat(updatedChats[0] || null);
            }
            return updatedChats;
        });
    }, [currentChat, saveChatsToStorage]);

    const selectChat = useCallback((chatId: string) => {
        const chatToSelect = chats.find((c) => c.id === chatId);
        if (chatToSelect) {
            setCurrentChat(chatToSelect);
        }
    }, [chats]);

    const addMessage = useCallback((chatId: string, message: Message) => {
        setChats(prevChats => {
            const updatedChats = prevChats.map((chat) => {
                if (chat.id === chatId) {
                    return {
                        ...chat,
                        messages: [...chat.messages, message],
                        updatedAt: new Date(),
                    };
                }
                return chat;
            });

            // 添加新消息时立即保存
            saveChatsToStorage(updatedChats, true);

            const updatedCurrentChat = updatedChats.find(c => c.id === chatId);
            if (updatedCurrentChat) {
                setCurrentChat(updatedCurrentChat);
            }
            return updatedChats;
        });
    }, [saveChatsToStorage]);

    const updateLastMessageContent = useCallback((chatId: string, chunk: string) => {
        // 标记正在流式更新
        isStreamingRef.current = true;

        setChats(prevChats => {
            const updatedChats = prevChats.map(chat => {
                if (chat.id === chatId) {
                    if (chat.messages.length === 0) {
                        return chat;
                    }

                    const lastMessage = chat.messages[chat.messages.length - 1];

                    if (lastMessage && lastMessage.role === 'assistant') {
                        const updatedLastMessage = {
                            ...lastMessage,
                            content: lastMessage.content + chunk,
                            timestamp: new Date(),
                        };

                        const newMessages = [
                            ...chat.messages.slice(0, -1),
                            updatedLastMessage
                        ];

                        return { ...chat, messages: newMessages, updatedAt: new Date() };
                    }
                }
                return chat;
            });

            // 更新 currentChat state
            const updatedCurrentChat = updatedChats.find(c => c.id === chatId);
            if (updatedCurrentChat) {
                setCurrentChat(updatedCurrentChat);
            }

            // 防抖保存（流式更新时）
            saveChatsToStorage(updatedChats, false);
            return updatedChats;
        });

        // 在流式更新结束后一段时间，重置标记
        if (saveTimerRef.current) {
            clearTimeout(saveTimerRef.current);
        }
        saveTimerRef.current = setTimeout(() => {
            isStreamingRef.current = false;
        }, DEBOUNCE_DELAY + 100);
    }, [saveChatsToStorage]);

    const updateChatTitle = useCallback((chatId: string, title: string) => {
        setChats(prevChats => {
            const updatedChats = prevChats.map((chat) => {
                if (chat.id === chatId) {
                    return { ...chat, title };
                }
                return chat;
            });
            saveChatsToStorage(updatedChats, true); // 立即保存
            return updatedChats;
        });

        if (currentChat?.id === chatId) {
            setCurrentChat(prev => prev ? { ...prev, title } : null);
        }
    }, [currentChat, saveChatsToStorage]);

    return (
        <ChatContext.Provider
            value={{
                chats,
                currentChat,
                createNewChat,
                deleteChat,
                selectChat,
                addMessage,
                updateChatTitle,
                updateLastMessageContent,
            }}
        >
            {children}
        </ChatContext.Provider>
    );
};

export const useChat = () => {
    const context = useContext(ChatContext);
    if (!context) {
        throw new Error("useChat must be used within ChatProvider");
    }
    return context;
};