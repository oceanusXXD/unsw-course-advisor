// src/components/Chat/MessageItem.tsx
import React from "react";
import MessageBubble from "./MessageBubble"; // 1. 导入新组件

type MsgFrom = "user" | "bot" | "system";

const MessageItem: React.FC<{ from: MsgFrom; text: string }> = ({ from = "bot", text }) => {
  const isUser = from === "user";

  // "system" 消息通常不显示，但这里我们以防万一
  if (from === "system") {
    return (
      <div className="text-center text-xs text-gray-400 italic py-2">
        System: {text}
      </div>
    );
  }

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      {/* 2. 保留头像逻辑 */}
      {!isUser && (
        <div className="mr-3 w-8 h-8 rounded-full bg-[#EEEFF1] flex items-center justify-center text-sm self-start">
          🤖
        </div>
      )}

      {/* 3. 使用 MessageBubble 渲染气泡 */}
      <MessageBubble from={from} text={text} />

      {/* 4. 保留头像逻辑 */}
      {isUser && (
        <div className="ml-3 w-8 h-8 rounded-full bg-[#EEEFF1] flex items-center justify-center text-sm self-start">
          👤
        </div>
      )}
    </div>
  );
};

export default MessageItem;