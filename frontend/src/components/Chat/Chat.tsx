import React, { useState, useRef, useEffect, useMemo } from "react";
import MessageItem from "./MessageItem";
import EmptyState from "./EmptyState";
import InputPanel from "../InputPanel/InputPanel";
import { Toaster, useToaster } from "../Toaster/Toaster";
import { streamChat } from "../../services/api";
import { useChat } from "../../context/ChatContext";
import { useAuth } from "../../context/AuthContext";
import { Message } from "../../types";

interface ChatProps {
  onSources?: (sources: any[]) => void;
}

const PRESET_QUERIES = [
  "How can I improve my productivity?",
  "What are the latest trends in AI?",
  "Tell me about sustainable living practices",
];

const Chat: React.FC<ChatProps> = ({ onSources }) => {
  const { currentChat, addMessage, createNewChat, updateLastMessageContent } = useChat();
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

    const userMsg: Message = { id: `user-${Date.now()}`, role: "user", content: query, timestamp: new Date() };
    addMessage(chatId, userMsg);

    const botMsg: Message = { id: `bot-${Date.now()}`, role: "assistant", content: "", timestamp: new Date() };
    addMessage(chatId, botMsg);

    const historyPayload = [...activeChat.messages, userMsg]
      .map((m) => ({
        role: m.role,
        content: m.content,
      }))
      .filter((m) => m.role);

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
          updateLastMessageContent(chatId, token);
        },
        onSources: (sourcesData) => { onSources?.(sourcesData); },
        onError: (err) => { showError(String(err)); },
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
    <div className="flex flex-col w-full h-[calc(100vh-100px)]">
      <Toaster toasts={toasts} onRemove={removeToast} />

      {messages.length === 0 ? (
        <div className="flex flex-col flex-grow justify-center items-center px-4">
          <EmptyState />
          <div className="w-full max-w-2xl mt-8">
            <InputPanel
              onSearch={handleSend}
              isLoading={streamingLoading}
              onStop={handleStop}
            />

            <div className="mt-8 space-y-3">
              {PRESET_QUERIES.map((preset, index) => (
                <button
                  key={index}
                  onClick={() => handleSend(preset)}
                  disabled={streamingLoading}
                  className="w-full text-left px-4 py-3 rounded-xl bg-gradient-to-r from-blue-50 to-purple-50 hover:from-blue-100 hover:to-purple-100 transition-all duration-200 border border-blue-100 hover:border-purple-300 disabled:opacity-50 disabled:cursor-not-allowed group"
                >
                  <p className="text-gray-600 text-sm group-hover:text-gray-800 transition-colors line-clamp-2">
                    {preset}
                  </p>
                </button>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <div className="flex flex-col flex-grow w-full overflow-hidden">
          <div className="flex-grow overflow-y-auto mb-6 px-4">
            {messages.map((msg) => (
              <MessageItem key={msg.id} from={msg.role === 'assistant' ? 'bot' : msg.role} text={msg.content} />
            ))}
            <div ref={messagesEndRef} />
          </div>

          <div className="w-full mt-auto pt-4 border-t border-gray-100 px-4 pb-4">
            <div className="max-w-2xl mx-auto">
              <InputPanel
                onSearch={handleSend}
                isLoading={streamingLoading}
                onStop={handleStop}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Chat;