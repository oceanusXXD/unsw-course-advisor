import React, { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";
import { oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";

// [!! 助手更改] 1. 导入 useAuth 和图标
import { useAuth } from "../../context/AuthContext";
import { IoSchoolOutline } from "react-icons/io5";

type MsgFrom = "user" | "bot" | "system";

const MessageItem: React.FC<{ from: MsgFrom; text: string }> = ({
  from = "bot",
  text,
}) => {
  const isUser = from === "user";

  // [!! 助手更改] 2. 获取 authState 来显示用户首字母
  const { authState } = useAuth();
  const userInitial = authState.user?.name
    ? authState.user.name[0].toUpperCase()
    : "U"; // 'U' 作为后备

  const [isDark, setIsDark] = useState<boolean>(
    document.documentElement.classList.contains("dark")
  );

  // 监听主题变化 (保持不变)
  useEffect(() => {
    const observer = new MutationObserver(() => {
      setIsDark(document.documentElement.classList.contains("dark"));
    });
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class"],
    });
    return () => observer.disconnect();
  }, []);

  // System 消息 (保持不变)
  if (from === "system") {
    return (
      <div className="text-center text-xs text-gray-400 dark:text-neutral-500 italic py-2">
        System: {text}
      </div>
    );
  }

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      {/* [!! 助手更改] 3. Bot 头像 (品牌化) */}
      {!isUser && (
        <div className="mr-3 w-8 h-8 rounded-full bg-gradient-to-r from-yellow-400 to-red-500 flex items-center justify-center text-white self-start flex-shrink-0">
          <IoSchoolOutline size={18} />
        </div>
      )}
      <div
        className={`max-w-[80%] px-4 py-3 rounded-2xl shadow-sm
     ${isUser
            ? "bg-yellow-400 text-black dark:bg-yellow-600 dark:text-white" // User 气泡
            : "bg-white border border-gray-200 text-gray-900 dark:bg-neutral-800 dark:border-neutral-700 dark:text-neutral-100" // Bot 气泡
          }`}
      >
        <div className="prose prose-sm max-w-none dark:prose-invert prose-pre:p-0 prose-pre:my-0 prose-pre:bg-transparent">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              code({ inline, className, children, ...props }) {
                const match = /language-(\w+)/.exec(className || "");
                return !inline && match ? (
                  // 代码块 (保持不变)
                  <SyntaxHighlighter
                    style={isDark ? vscDarkPlus : oneLight}
                    language={match[1]}
                    PreTag="div"
                    {...props}
                  >
                    {String(children).replace(/\n$/, "")}
                  </SyntaxHighlighter>
                ) : (
                  <code
                    className="bg-yellow-100 text-red-800 dark:bg-yellow-900/50 dark:text-yellow-200 px-1 py-0.5 rounded text-sm font-semibold"
                    {...props}
                  >
                    {children}
                  </code>
                );
              },
            }}
          >
            {text}
          </ReactMarkdown>
        </div>
      </div>
      {isUser && (
        <div className="ml-3 w-8 h-8 rounded-full bg-neutral-200 dark:bg-neutral-700 
        flex items-center justify-center text-sm font-semibold text-neutral-600 dark:text-neutral-300 self-start flex-shrink-0">
          {userInitial}
        </div>
      )}
    </div>
  );
};
export default MessageItem;