// src/components/Chat/MessageItem.tsx
import React from "react";

// 消息类型，与 Chat.tsx 保持一致
type MsgFrom = "user" | "bot" | "system";

const MessageItem: React.FC<{ from: MsgFrom; text: string }> = ({ from = "bot", text }) => {
  const isUser = from === "user";

  if (from === "system") {
    return (
      <div className="text-center text-xs text-gray-400 italic py-2">
        System: {text}
      </div>
    );
  }

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      {!isUser && (
        <div className="mr-3 w-8 h-8 rounded-full bg-[#EEEFF1] flex items-center justify-center text-sm self-start">
          🤖
        </div>
      )}
      {/* 消息气泡的样式直接内联在这里 */}
      <div className={`max-w-[70%] px-4 py-3 rounded-2xl ${isUser ? "bg-[#EEEFF1]" : "bg-[#F9FAFC] border border-[#EEEFF1]"}`}>
        <div className="whitespace-pre-wrap text-sm text-black">{text}</div>
      </div>
      {isUser && (
        <div className="ml-3 w-8 h-8 rounded-full bg-[#EEEFF1] flex items-center justify-center text-sm self-start">
          👤
        </div>
      )}
    </div>
  );
};

export default MessageItem;