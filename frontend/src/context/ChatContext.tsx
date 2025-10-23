import React, { createContext, useContext, useState, useCallback, useEffect } from "react";
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

export const ChatProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [chats, setChats] = useState<ChatItem[]>([]);
    const [currentChat, setCurrentChat] = useState<ChatItem | null>(null);

    useEffect(() => {
        const savedChats = localStorage.getItem("chats");
        if (savedChats) {
            try {
                const parsedChats = JSON.parse(savedChats) as ChatItem[];
                const chatsWithDates = parsedChats.map(chat => ({
                    ...chat,
                    createdAt: new Date(chat.createdAt),
                    updatedAt: new Date(chat.updatedAt),
                    messages: chat.messages.map(msg => ({
                        ...msg,
                        timestamp: new Date(msg.timestamp),
                    }))
                }));
                setChats(chatsWithDates);
            } catch (e) {
                console.error("Failed to parse saved chats:", e);
            }
        }
    }, []);

    const saveChatsToStorage = (newChats: ChatItem[]) => {
        localStorage.setItem("chats", JSON.stringify(newChats));
    };

    const createNewChat = useCallback((title?: string): ChatItem => {
        const newChat: ChatItem = {
            id: "chat_" + Date.now(),
            title: title || `New Chat - ${new Date().toLocaleString()}`,
            createdAt: new Date(),
            updatedAt: new Date(),
            messages: [],
        };

        setChats(prevChats => {
            const updatedChats = [newChat, ...prevChats];
            saveChatsToStorage(updatedChats);
            return updatedChats;
        });
        setCurrentChat(newChat);
        return newChat;
    }, []);

    const deleteChat = useCallback((chatId: string) => {
        setChats(prevChats => {
            const updatedChats = prevChats.filter((chat) => chat.id !== chatId);
            saveChatsToStorage(updatedChats);

            if (currentChat?.id === chatId) {
                setCurrentChat(updatedChats[0] || null);
            }
            return updatedChats;
        });
    }, [currentChat]);

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
            saveChatsToStorage(updatedChats);

            const updatedCurrentChat = updatedChats.find(c => c.id === chatId);
            if (updatedCurrentChat) {
                setCurrentChat(updatedCurrentChat);
            }
            return updatedChats;
        });
    }, []);

    const updateLastMessageContent = useCallback((chatId: string, chunk: string) => {
        setChats(prevChats => {
            const updatedChats = prevChats.map(chat => {
                // 1. 找到需要更新的 chat
                if (chat.id === chatId) {
                    // 2. 确保至少有一条消息
                    if (chat.messages.length === 0) {
                        return chat;
                    }

                    const lastMessage = chat.messages[chat.messages.length - 1];

                    // 3. 检查最后一条消息是否是 assistant 发的
                    if (lastMessage && lastMessage.role === 'assistant') {
                        // 4. ✅ 正确：创建一个 *新的* 消息对象
                        const updatedLastMessage = {
                            ...lastMessage,
                            content: lastMessage.content + chunk, // 附加新的内容
                            timestamp: new Date(),
                        };

                        // 5. ✅ 正确：创建一个 *新的* 消息数组
                        const newMessages = [
                            ...chat.messages.slice(0, -1), // 包含除了最后一条之外的所有旧消息
                            updatedLastMessage       // 替换上更新后的最后一条消息
                        ];

                        // 6. 返回一个 *新的* chat 对象
                        return { ...chat, messages: newMessages, updatedAt: new Date() };
                    }
                }
                // 7. 对于其他 chat，返回原样
                return chat;
            });

            // 更新 currentChat state
            const updatedCurrentChat = updatedChats.find(c => c.id === chatId);
            if (updatedCurrentChat) {
                setCurrentChat(updatedCurrentChat);
            }

            saveChatsToStorage(updatedChats);
            return updatedChats;
        });
    }, []);

    const updateChatTitle = useCallback((chatId: string, title: string) => {
        setChats(prevChats => {
            const updatedChats = prevChats.map((chat) => {
                if (chat.id === chatId) {
                    return { ...chat, title };
                }
                return chat;
            });
            saveChatsToStorage(updatedChats);
            return updatedChats;
        });

        if (currentChat?.id === chatId) {
            setCurrentChat(prev => prev ? { ...prev, title } : null);
        }
    }, [currentChat]);

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