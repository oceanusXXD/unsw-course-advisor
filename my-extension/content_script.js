// ============================================
// 文件: content_script.js (合并版)
// 在 https://my.unsw.edu.au/active/studentClassEnrol/* 上运行
// ============================================

console.log("[EXT CONTENT] 课程助手内容脚本已加载 (合并版)");

try {
  // --------------------------------------------
  // 变量定义 (来自 插件 A)
  // --------------------------------------------
  let pendingTokenRequest = null;
  let tokenRequestTimeout = null;
  let injectorInjected = false;
  let injectionPromiseResolved = false;

  // --------------------------------------------
  // 逻辑 (来自 插件 A: 注入 injector.js)
  // --------------------------------------------
  console.log("[EXT CONTENT] (A) 正在执行 injector.js 注入");
  const injectorUrl = chrome.runtime.getURL("injector.js");

  const injectionPromise = fetch(injectorUrl)
    .then((res) => {
      // 你在代码片段中遗漏了这部分，我假设它只是返回 res
      return res;
    })
    .then((res) => {
      if (!res.ok)
        throw new Error("fetch injector.js failed status=" + res.status);
      return res.text();
    })
    .then((code) => {
      const s = document.createElement("script");
      s.textContent = code + "\n//# sourceURL=injected/injector.js";
      (document.head || document.documentElement).appendChild(s);
      setTimeout(() => s.remove(), 5000);
      injectorInjected = true;
      injectionPromiseResolved = true;
      console.log("[EXT CONTENT] (A) injector.js injected to page context");
      chrome.runtime
        .sendMessage({ from: "ext-debug", msg: "injector injected" })
        .catch((e) => {});
    })
    .catch((err) => {
      console.error("[EXT CONTENT] (A) error injecting injector.js", err);
      injectorInjected = false;
      injectionPromiseResolved = true;
      chrome.runtime
        .sendMessage({
          from: "ext-debug",
          msg: "inject-failed",
          err: String(err),
        })
        .catch((e) => {});
    });

  // --------------------------------------------
  // 监听器 (来自 插件 A: 监听页面的 'message' 事件)
  // --------------------------------------------
  window.addEventListener("message", (event) => {
    if (event.source !== window) return;

    // console.log("[EXT CONTENT] (A) 从页面脚本收到消息:", event.data.type);

    if (event.data.type === "AUTH_TOKEN_RESULT") {
      clearTimeout(tokenRequestTimeout);

      if (pendingTokenRequest) {
        if (event.data.token) {
          console.log("[EXT CONTENT] (A) 成功获取令牌");
          pendingTokenRequest.sendResponse({ token: event.data.token });
        } else {
          console.error("[EXT CONTENT] (A) 令牌获取失败:", event.data.error);
          pendingTokenRequest.sendResponse({
            error: event.data.error || "未能获取令牌",
          });
        }
        pendingTokenRequest = null;
      }
    }
  });

  // --------------------------------------------
  // 合并的监听器 (监听 'chrome.runtime.onMessage')
  // --------------------------------------------
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    const msgType = message.type || message.action;
    console.log("[EXT CONTENT] (合并) 收到 Runtime 消息:", msgType);

    // ==================================
    // 逻辑 (来自 插件 B: content.js)
    // ==================================
    if (msgType === "checkPage") {
      console.log("[EXT CONTENT] (B) 正在处理 checkPage");
      const isCorrectPage = window.location.href.includes("studentClassEnrol");
      sendResponse({ isCorrectPage });
      return true; // 异步
    }

    // ==================================
    // 逻辑 (来自 插件 A: content_script.js)
    // ==================================

    // (A) 处理 GET_AUTH_TOKEN
    if (msgType === "GET_AUTH_TOKEN") {
      console.log("[EXT CONTENT] (A) 正在处理 GET_AUTH_TOKEN");
      if (pendingTokenRequest) {
        console.warn("[EXT CONTENT] (A) 已有待处理的令牌请求，忽略新请求。");
        sendResponse({ error: "已有待处理的令牌请求" });
        return false; // 同步响应错误
      }

      pendingTokenRequest = { sendResponse };

      const requestTokenFromInjector = () => {
        console.log("[EXT CONTENT] (A) >>> 向页面发送 REQUEST_TOKEN");
        window.postMessage(
          { source: "content-script", type: "REQUEST_TOKEN" },
          "*"
        );

        clearTimeout(tokenRequestTimeout);
        tokenRequestTimeout = setTimeout(() => {
          console.error("[EXT CONTENT] (A) 等待令牌超时");
          if (pendingTokenRequest) {
            pendingTokenRequest.sendResponse({
              error: "获取令牌超时：页面脚本无响应。",
            });
            pendingTokenRequest = null;
          }
          tokenRequestTimeout = null;
        }, 5000);
      };

      if (injectorInjected) {
        requestTokenFromInjector();
      } else if (injectionPromiseResolved && !injectorInjected) {
        console.error("[EXT CONTENT] (A) 页面脚本注入失败");
        sendResponse({ error: "页面脚本注入失败，无法获取令牌。" });
        pendingTokenRequest = null;
      } else {
        console.log("[EXT CONTENT] (A) 等待注入器准备就绪...");
        injectionPromise
          .then(() => {
            if (injectorInjected && pendingTokenRequest) {
              console.log("[EXT CONTENT] (A) 注入完成，现在发送 REQUEST_TOKEN");
              requestTokenFromInjector();
            } else if (!injectorInjected && pendingTokenRequest) {
              console.error("[EXT CONTENT] (A) 注入失败");
              pendingTokenRequest.sendResponse({
                error: "页面脚本注入失败，无法获取令牌。",
              });
              pendingTokenRequest = null;
            }
          })
          .catch((err) => {
            console.error("[EXT CONTENT] (A) 注入 Promise 出错:", err);
            if (pendingTokenRequest) {
              pendingTokenRequest.sendResponse({
                error: "页面脚本注入异常: " + err.message,
              });
              pendingTokenRequest = null;
            }
          });
      }

      return true; // 异步
    }

    // (A) 处理 runApis
    if (msgType === "runApis" && Array.isArray(message.urls)) {
      console.log("[EXT CONTENT] (A) 正在处理 runApis");
      const safeParams = message.params
        ? JSON.stringify(message.params)
        : "null";
      const runCode = `window.__apiRunner && window.__apiRunner.run(${JSON.stringify(
        message.urls
      )}, ${safeParams});`;
      const s2 = document.createElement("script");
      s2.textContent = runCode;
      (document.head || document.documentElement).appendChild(s2);
      setTimeout(() => s2.remove(), 2000);
      sendResponse({ ok: true });
      return false; // 同步
    }

    // 默认：没有匹配的消息
    console.warn("[EXT CONTENT] (合并) 未处理的消息:", message);
    return false; // 没有匹配的同步响应
  }); // --- 监听器结束 ---
} catch (e) {
  console.error("[EXT CONTENT] (合并) 脚本顶层出现意外错误:", e);
  try {
    chrome.runtime.sendMessage({
      from: "ext-debug",
      msg: "content-script-error",
      err: String(e),
    });
  } catch (err) {}
}
