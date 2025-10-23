// injector.js - v3: Added more specific logging

(function () {
  // --- API Runner Setup ---
  if (window.__apiRunner) {
    // ... (apiRunner setup remains the same)
    console.log("[EXT INJECTOR] __apiRunner already present");
    window.__apiRunner_ready = true;
    window.postMessage(
      { source: "api-runner-page-ready", msg: "injector already ready" },
      "*"
    );
  } else {
    console.log("[EXT INJECTOR] Setting up __apiRunner");
    window.__apiRunner = {
      run: async function (urls, params) {
        const results = [];
        console.log("[EXT INJECTOR] apiRunner running for URLs:", urls);
        for (const url of urls) {
          try {
            const resp = await fetch(url, {
              credentials: "include",
              method: "GET",
            });
            const text = await resp.text();
            results.push({
              url,
              status: resp.status,
              ok: resp.ok,
              len: text ? text.length : 0,
              snippet: text ? text.slice(0, 300) : "",
            });
          } catch (e) {
            console.error("[EXT INJECTOR] apiRunner fetch error for", url, e);
            results.push({ url, status: "error", ok: false, err: String(e) });
          }
        }
        window.postMessage({ source: "api-runner-page", results }, "*");
        console.log("[EXT INJECTOR] apiRunner finished, sent results.");
        return results;
      },
    };
    try {
      window.__apiRunner_ready = true;
      console.log("[EXT INJECTOR] __apiRunner initialized. 打开成功");
      window.postMessage(
        { source: "api-runner-page-ready", msg: "injector ready" },
        "*"
      );
    } catch (e) {
      console.error("[EXT INJECTOR] error marking apiRunner ready", e);
    }
  }

  // --- Message Listener ---
  console.log("[EXT INJECTOR] Adding message listener.");
  // 在injector 中
  window.addEventListener("message", (event) => {
    if (event.source !== window) return;

    if (
      event.data.source === "content-script" &&
      event.data.type === "REQUEST_TOKEN"
    ) {
      console.log("[INJECTOR] 收到 REQUEST_TOKEN 请求");

      try {
        // 从 localStorage/sessionStorage 获取 token
        const token =
          localStorage.getItem("auth_token") ||
          sessionStorage.getItem("token") ||
          window.__auth_token;

        if (token) {
          console.log("[INJECTOR] 发送令牌回 content-script");
          window.postMessage(
            { source: "injector", type: "AUTH_TOKEN_RESULT", token: token },
            "*"
          );
        } else {
          console.error("[INJECTOR] 找不到令牌");
          window.postMessage(
            {
              source: "injector",
              type: "AUTH_TOKEN_RESULT",
              error: "页面中找不到认证令牌，请确保已登录",
            },
            "*"
          );
        }
      } catch (error) {
        console.error("[INJECTOR] 获取令牌出错:", error);
        window.postMessage(
          {
            source: "injector",
            type: "AUTH_TOKEN_RESULT",
            error: error.message,
          },
          "*"
        );
      }
    }
  });

  console.log("[EXT INJECTOR] injector.js setup complete.");
})();
