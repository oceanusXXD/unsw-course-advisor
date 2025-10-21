// content_script.js - v3: Added more logging and timeout

(function () {
  try {
    console.log("[EXT CONTENT] content-script executing on", location.href);

    // --- Injector Script Injection (Keep this part) ---
    const injectorUrl = chrome.runtime.getURL("injector.js");
    let injectorInjected = false;
    let injectionPromiseResolved = false; // Track if the promise below completed

    const injectionPromise = fetch(injectorUrl) // Store promise
      .then((res) => {
        /* ... (fetch code remains same) ... */
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
        injectionPromiseResolved = true; // Mark as resolved
        console.log("[EXT CONTENT] injector.js injected to page context");
        chrome.runtime
          .sendMessage({ from: "ext-debug", msg: "injector injected" })
          .catch((e) => {});
      })
      .catch((err) => {
        console.error("[EXT CONTENT] error injecting injector.js", err);
        injectorInjected = false; // Ensure flag is false on error
        injectionPromiseResolved = true; // Mark as resolved (with error)
        chrome.runtime
          .sendMessage({
            from: "ext-debug",
            msg: "inject-failed",
            err: String(err),
          })
          .catch((e) => {});
      });

    // --- Message Handling ---
    let pendingTokenRequest = null;
    let tokenRequestTimeout = null; // Timeout handle

    // 1. Listen for messages FROM Page/Injector
    window.addEventListener("message", (event) => {
      if (event.source !== window) return;

      console.log("[EXT CONTENT] 从页面脚本收到消息:", event.data.type);

      if (event.data.type === "AUTH_TOKEN_RESULT") {
        clearTimeout(tokenRequestTimeout);

        if (pendingTokenRequest) {
          if (event.data.token) {
            console.log("[EXT CONTENT] 成功获取令牌");
            pendingTokenRequest.sendResponse({ token: event.data.token });
          } else {
            console.error("[EXT CONTENT] 令牌获取失败:", event.data.error);
            pendingTokenRequest.sendResponse({
              error: event.data.error || "未能获取令牌",
            });
          }
          pendingTokenRequest = null;
        }
      }
    });

    // 2. Listen for messages FROM Popup/Background
    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
      console.log(
        "[EXT CONTENT] Received message from runtime:",
        message.type || message.action
      );

      // Request FROM popup.js to get the Auth Token
      if (message.type === "GET_AUTH_TOKEN") {
        if (pendingTokenRequest) {
          console.warn("[EXT CONTENT] 已有待处理的令牌请求，忽略新请求。");
          sendResponse({ error: "已有待处理的令牌请求" });
          return false; // ✅ 同步响应错误
        }

        pendingTokenRequest = { sendResponse };

        const requestTokenFromInjector = () => {
          console.log("[EXT CONTENT] >>> 向页面发送 REQUEST_TOKEN");
          window.postMessage(
            { source: "content-script", type: "REQUEST_TOKEN" },
            "*"
          );

          clearTimeout(tokenRequestTimeout);
          tokenRequestTimeout = setTimeout(() => {
            console.error("[EXT CONTENT] 等待令牌超时");
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
          console.error("[EXT CONTENT] 页面脚本注入失败");
          sendResponse({ error: "页面脚本注入失败，无法获取令牌。" });
          pendingTokenRequest = null;
        } else {
          console.log("[EXT CONTENT] 等待注入器准备就绪...");
          injectionPromise
            .then(() => {
              if (injectorInjected && pendingTokenRequest) {
                console.log("[EXT CONTENT] 注入完成，现在发送 REQUEST_TOKEN");
                requestTokenFromInjector();
              } else if (!injectorInjected && pendingTokenRequest) {
                console.error("[EXT CONTENT] 注入失败");
                pendingTokenRequest.sendResponse({
                  error: "页面脚本注入失败，无法获取令牌。",
                });
                pendingTokenRequest = null;
              }
            })
            .catch((err) => {
              console.error("[EXT CONTENT] 注入 Promise 出错:", err);
              if (pendingTokenRequest) {
                pendingTokenRequest.sendResponse({
                  error: "页面脚本注入异常: " + err.message,
                });
                pendingTokenRequest = null;
              }
            });
        }

        return true; // ✅ 异步响应
      }

      // Keep your original api runner logic
      if (message.action === "runApis" && Array.isArray(message.urls)) {
        // ... (api runner logic remains same)
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
        return false;
      }

      return false; // Default: no async response
    });
  } catch (e) {
    console.error("[EXT CONTENT] unexpected error in content script:", e);
    try {
      chrome.runtime.sendMessage({
        from: "ext-debug",
        msg: "content-script-error",
        err: String(e),
      });
    } catch (err) {}
  }
})();
