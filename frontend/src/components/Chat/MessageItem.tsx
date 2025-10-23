import React, { useEffect, useState, CSSProperties } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";
import { oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";

type MsgFrom = "user" | "bot" | "system";

const MessageItem: React.FC<{ from: MsgFrom; text: string }> = ({
  from = "bot",
  text,
}) => {
  const isUser = from === "user";

  const [isDark, setIsDark] = useState<boolean>(
    document.documentElement.classList.contains("dark")
  );

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

  if (from === "system") {
    return (
      <div className="text-center text-xs text-gray-400 dark:text-neutral-500 italic py-2">
        System: {text}
      </div>
    );
  }

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      <div
        className={`
          max-w-2xl
         ${isUser
            ? "px-4 py-3 rounded-2xl shadow-sm bg-yellow-400 text-black dark:bg-yellow-600 dark:text-white"
            : "pt-3"
          }`}
      >
        <div className="prose prose-base max-w-none dark:prose-invert prose-pre:p-0 prose-pre:my-0 prose-pre:bg-transparent">

          {(!isUser && !text) ? (
            <div className="flex space-x-1 items-center h-5">
              <span className="w-2 h-2 bg-gray-400 dark:bg-neutral-500 rounded-full animate-pulse" style={{ animationDelay: '0s' }}></span>
              <span className="w-2 h-2 bg-gray-400 dark:bg-neutral-500 rounded-full animate-pulse" style={{ animationDelay: '0.2s' }}></span>
              <span className="w-2 h-2 bg-gray-400 dark:bg-neutral-500 rounded-full animate-pulse" style={{ animationDelay: '0.4s' }}></span>
            </div>
          ) : (
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                code({ node, inline, className, children, ...props }) {
                  const match = /language-(\w+)/.exec(className || "");
                  return !inline && match ? (
                    <SyntaxHighlighter
                      style={
                        (isDark ? vscDarkPlus : oneLight) as {
                          [key: string]: CSSProperties;
                        }
                      }
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
          )}

        </div>
      </div>
    </div>
  );
};
export default MessageItem;