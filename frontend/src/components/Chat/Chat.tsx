import React, { useState, useRef, useEffect, useMemo } from "react";
import MessageItem from "./MessageItem";
import EmptyState from "./EmptyState";
import InputPanel from "../InputPanel/InputPanel";
import { Toaster, useToaster } from "../Toaster/Toaster";
import { streamChat } from "../../services/api";
import { useChat } from "../../context/ChatContext";
import { useAuth } from "../../context/AuthContext";
import { Message } from "../../types";
import { FiArrowRight } from "react-icons/fi";

interface ChatProps {
  onSources?: (sources: any[]) => void;
}

const PRESET_QUERIES = [
  "What are the prerequisites for COMP1511?",
  "Show me level 3 courses in the Business School",
  "Compare COMP9021 and COMP9024",
];

const Chat: React.FC<ChatProps> = ({ onSources }) => {
  const { currentChat, addMessage, createNewChat, updateLastMessageContent } =
    useChat();
  const { authState } = useAuth();
  const [streamingLoading, setStreamingLoading] = useState(false);
  const { toasts, removeToast, showError } = useToaster();
  const abortRef = useRef<AbortController | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const messages = useMemo(() => currentChat?.messages || [], [currentChat]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async (query: string) => {
    if (!query || streamingLoading) return;

    let activeChat = currentChat;
    if (!activeChat) {
      activeChat = createNewChat(`Chat about "${query}"`);
    }
    const chatId = activeChat.id;

    const userMsg: Message = {
      id: `user-${Date.now()}`,
      role: "user",
      content: query,
      timestamp: new Date(),
    };
    addMessage(chatId, userMsg);

    const botMsg: Message = {
      id: `bot-${Date.now()}`,
      role: "assistant",
      content: "",
      timestamp: new Date(),
    };
    addMessage(chatId, botMsg);

    const historyPayload = [...(activeChat?.messages ?? []), userMsg]
      .map((m) => ({
        role: m.role,
        content: m.content,
      }))
      .filter((m) => m.role && m.role !== "system");

    setStreamingLoading(true);
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await streamChat({
        endpoint: "chatbot/chat_multiround/",
        query,
        history: historyPayload,
        userId: authState.user?.id,
        signal: controller.signal,
        onToken: (token) => {
          if (chatId) {
            updateLastMessageContent(chatId, token);
          }
        },
        onSources: (sourcesData) => {
          onSources?.(sourcesData);
        },
        onError: (err) => {
          showError(String(err));
        },
      });
    } catch (err: any) {
      if (err.name !== "AbortError") {
        showError(err.message || String(err));
      }
    } finally {
      setStreamingLoading(false);
      abortRef.current = null;
    }
  };

  const handleStop = () => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
      setStreamingLoading(false);
    }
  };

  return (
    <div className="flex flex-col w-full min-h-[calc(100vh-80px)]">
      <Toaster toasts={toasts} onRemove={removeToast} />

      <div className="flex-grow w-full">
        {messages.length === 0 ? (
          <div className="flex flex-col flex-grow justify-center items-center px-4">
            <EmptyState />
            <div className="w-full max-w-5xl mt-8">
              <div
                className="mt-8 space-y-4"
                role="list"
                aria-label="Preset queries list"
              >
                {PRESET_QUERIES.map((preset, index) => (
                  <button
                    key={preset + index}
                    type="button"
                    role="listitem"
                    onClick={() => handleSend(preset)}
                    disabled={streamingLoading}
                    aria-disabled={streamingLoading}
                    aria-label={`发送预设: ${preset}`}
                    style={{ animationDelay: `${index * 0.12}s` }}
                    className={`
       relative w-full flex items-center justify-between gap-4 px-6 py-4 rounded-2xl
       overflow-hidden
       bg-white dark:bg-neutral-900
       shadow-sm hover:shadow-md
       transform motion-safe:transition motion-safe:duration-200 motion-safe:ease-out
       disabled:opacity-50 disabled:cursor-not-allowed
       focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:focus-visible:ring-offset-neutral-900
       focus-visible:ring-yellow-400 dark:focus-visible:ring-yellow-300
       group
       `}
                  >
                    <span
                      aria-hidden="true"
                      className={`
        pointer-events-none absolute inset-0 rounded-2xl
        before:absolute before:inset-0 before:rounded-2xl
        before:bg-gradient-to-r before:from-yellow-50 before:to-red-50
        dark:before:from-yellow-600 dark:before:to-red-600
        before:opacity-0 group-hover:before:opacity-100 before:transition-opacity before:duration-300
        after:absolute after:inset-[1px] after:rounded-2xl after:bg-white dark:after:bg-neutral-900
        `}
                    />

                    <span className="relative z-10 flex-1 text-left">
                      <span
                        className={`
         text-lg font-medium
         text-black dark:text-white
         block
         line-clamp-2
         `}
                      >
                        {preset}
                      </span>
                    </span>

                    <FiArrowRight
                      className={`
        relative z-10 w-5 h-5
        text-gray-400 dark:text-neutral-500
        transform transition-all duration-200
        opacity-0 -translate-x-2
        group-hover:opacity-100 group-hover:translate-x-0
        motion-reduce:transition-none motion-reduce:translate-x-0 motion-reduce:opacity-100
        `}
                      aria-hidden="true"
                    />
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="mb-6 px-4 w-full max-w-5xl mx-auto">
            {messages.map((msg) => (
              <MessageItem
                key={msg.id}
                from={msg.role === "assistant" ? "bot" : msg.role}
                text={msg.content}
              />
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      <div className="w-full mt-auto pt-4 border-t border-gray-100 dark:border-neutral-800 px-4 pb-4">
        <div className="max-w-5xl mx-auto">
          <InputPanel
            onSearch={handleSend}
            isLoading={streamingLoading}
            onStop={handleStop}
          />
        </div>
      </div>

    </div>
  );
};

export default Chat;