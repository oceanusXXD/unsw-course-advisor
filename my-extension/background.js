// background.js
// 完整实现：后台进程（service_worker）
// - 负责注入 content_script、调度每学期执行、刷新并继续、与 popup 通信

const API_BASE = "http://localhost:8000/api"; // 根据需要调整

let popupWindowId = null;
let enrollmentState = {
  isProcessing: false,
  currentStep: null,
  completedTerms: [],
  failedTerms: [],
};

// -----------------------------
// 窗口管理
// -----------------------------
chrome.action.onClicked.addListener((tab) => {
  if (popupWindowId !== null) {
    chrome.windows.get(popupWindowId, {}, (existingWindow) => {
      if (chrome.runtime.lastError) {
        createNewWindow();
      } else {
        chrome.windows.update(popupWindowId, { focused: true });
      }
    });
  } else {
    createNewWindow();
  }
});

function createNewWindow() {
  chrome.windows.create(
    {
      url: "popup.html",
      type: "popup",
      width: 380,
      height: 580,
      focused: true,
    },
    (window) => {
      popupWindowId = window.id;
    }
  );
}

chrome.windows.onRemoved.addListener((windowId) => {
  if (windowId === popupWindowId) {
    popupWindowId = null;
  }
});

// -----------------------------
// 辅助：将回调型 API 包装成 Promise
// -----------------------------
function queryTabs(queryInfo) {
  return new Promise((resolve) => {
    chrome.tabs.query(queryInfo, (tabs) => resolve(tabs || []));
  });
}

function sendMessageToTab(tabId, message, timeout = 20000) {
  return new Promise((resolve, reject) => {
    let done = false;
    const timer = setTimeout(() => {
      if (!done) {
        done = true;
        reject(new Error("sendMessageToTab timeout"));
      }
    }, timeout);

    chrome.tabs.sendMessage(tabId, message, (resp) => {
      if (done) return;
      clearTimeout(timer);
      done = true;
      if (chrome.runtime.lastError) {
        return reject(new Error(chrome.runtime.lastError.message));
      }
      resolve(resp);
    });
  });
}

// -----------------------------
// 查找已打开的 UNSW 选课页标签（优先在所有标签中匹配）
// -----------------------------
async function findUnswTab() {
  try {
    // 尝试按 url 模式查询（有些 Chromium 版本支持）
    const candidateTabs = await new Promise((resolve) => {
      chrome.tabs.query(
        { url: ["*://*.my.unsw.edu.au/*", "*://my.unsw.edu.au/*"] },
        (tabs) => resolve(tabs || [])
      );
    });
    if (candidateTabs && candidateTabs.length) {
      return candidateTabs[0];
    }
  } catch (e) {
    // 某些环境可能不支持带 url 的 query，回退到全表扫描
    console.warn("[BG] URL 模式查询失败，回退全标签扫描:", e);
  }

  // 回退：遍历所有标签，找第一个匹配的
  const allTabs = await queryTabs({});
  const matched = allTabs.find(
    (t) => t.url && t.url.includes("my.unsw.edu.au")
  );
  return matched || null;
}

// -----------------------------
// 等待标签页加载到 status === 'complete'
// -----------------------------
function waitForTabComplete(tabId, timeout = 20000) {
  return new Promise((resolve, reject) => {
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      chrome.tabs.onUpdated.removeListener(onUpdated);
      reject(new Error("等待标签页加载超时"));
    }, timeout);

    function onUpdated(updatedTabId, changeInfo, tab) {
      if (updatedTabId !== tabId) return;
      if (changeInfo.status === "complete") {
        clearTimeout(timer);
        chrome.tabs.onUpdated.removeListener(onUpdated);
        if (!timedOut) resolve(tab);
      }
    }

    chrome.tabs.onUpdated.addListener(onUpdated);
  });
}

// -----------------------------
// 确保 content_script 注入并且页面脚本（injector）准备好
// -----------------------------
// 替换 background.js 中的 ensureContentScriptReady
async function ensureContentScriptReady(tabId, timeout = 12000) {
  // 先快速询问是否已有注入并就绪
  try {
    const quick = await new Promise((resolve) => {
      chrome.tabs.sendMessage(tabId, { type: "checkPageReady" }, (r) => {
        if (chrome.runtime.lastError) return resolve(null);
        resolve(r);
      });
    });
    if (quick && (quick.injectorReady || quick.pageReady)) {
      return true;
    }
  } catch (e) {
    // ignore
  }

  // 1) 动态注入 content_script.js
  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      files: ["content_script.js"],
    });
  } catch (e) {
    console.warn("[BG] 注入 content_script 失败（可能已注入或权限问题）:", e);
    // 继续尝试注入 injector.js 以增加兼容性
  }

  // 2) 直接用 scripting.executeScript 注入 injector.js 到页面上下文
  //    这一步替代 content_script 中的 fetch+eval 注入，能绕过 CSP/fetch 问题
  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      files: ["injector.js"],
    });
    console.log("[BG] 已通过 scripting 注入 injector.js");
  } catch (e) {
    console.warn("[BG] 注入 injector.js 失败:", e);
    // 如果这里失败，通常是 manifest/web_accessible_resources 或 host_permissions 配置问题
    // 抛出错误以便上层流程处理
    throw new Error("注入 injector.js 失败: " + e.message);
  }

  // 3) 等待 content_script 的 checkPageReady 返回就绪（轮询）
  const start = Date.now();
  while (Date.now() - start < timeout) {
    try {
      const status = await new Promise((resolve) => {
        chrome.tabs.sendMessage(tabId, { type: "checkPageReady" }, (r) => {
          if (chrome.runtime.lastError) return resolve(null);
          resolve(r);
        });
      });
      if (status && (status.injectorReady || status.pageReady)) {
        return true;
      }
    } catch (e) {
      // 忽略单次错误，继续轮询
    }
    await new Promise((r) => setTimeout(r, 300));
  }

  throw new Error("content_script / injector 未在超时内就绪");
}

// -----------------------------
// 通知 popup（如果 popup 已打开或可接收）
// -----------------------------
function notifyPopup(data) {
  try {
    chrome.runtime.sendMessage(data);
  } catch (e) {
    console.warn("[BG] notifyPopup 失败:", e);
  }
}

// -----------------------------
// 网络请求处理函数（validateLicense / getFileKey / fetchCourseIds）
// -----------------------------
async function handleValidateLicense(payload) {
  try {
    const { license_key } = payload;
    const response = await fetch(`${API_BASE}/accounts/license/validate/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ license_key }),
    });
    const data = await response.json().catch(() => ({}));
    return { ok: response.ok, data };
  } catch (error) {
    console.error("[BG] 验证 License 失败:", error);
    return { ok: false, error: error.message };
  }
}

async function handleGetFileKey(payload) {
  try {
    const { encrypted_file, license_key } = payload;
    const response = await fetch(`${API_BASE}/accounts/license/file-key/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ encrypted_file, license_key }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      return {
        ok: false,
        error: data.error || `服务器错误 (${response.status})`,
      };
    }
    return { ok: true, data };
  } catch (error) {
    console.error("[BG] 获取文件密钥失败:", error);
    return { ok: false, error: error.message };
  }
}

async function handleFetchCourseIds(payload) {
  try {
    const { coursePairs } = payload;
    const uniqueCourses = [...new Set(coursePairs.map((p) => p[1]))];
    const keys = uniqueCourses.join(",");

    const storage = await new Promise((resolve) =>
      chrome.storage.local.get(["userKey", "licenseKey", "authToken"], (res) =>
        resolve(res || {})
      )
    );
    const headers = { "Content-Type": "application/json" };
    if (storage.authToken)
      headers["Authorization"] = "Bearer " + storage.authToken;

    const url = `${API_BASE}/accounts/get_course/?keys=${encodeURIComponent(
      keys
    )}`;
    const response = await fetch(url, { method: "GET", headers });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.error || `服务器返回 ${response.status}`);
    }
    const respJson = await response.json();
    if (!respJson.success) {
      throw new Error(respJson.error || "后端返回失败");
    }
    return { ok: true, data: respJson.data || {} };
  } catch (error) {
    console.error("[BG] 获取课程信息失败:", error);
    return { ok: false, error: error.message };
  }
}

// -----------------------------
// 启动选课流程（入口）：寻找 UNSW 标签页、保存状态、并异步启动 processEnrollmentTerms
// -----------------------------
async function handleStartEnrollment(payload) {
  try {
    const { coursePairs, groupedCourses, termOrder } = payload;

    enrollmentState.isProcessing = true;
    enrollmentState.currentStep = "starting";

    // 尝试找到已打开的 UNSW 页签
    const unswTab = await findUnswTab();
    if (!unswTab) {
      return { ok: false, error: "请先打开 UNSW 选课页面 (my.unsw.edu.au)" };
    }

    const tabId = unswTab.id;

    // 保存状态到 storage（以便刷新/恢复）
    await new Promise((resolve) =>
      chrome.storage.local.set(
        {
          enrollmentTermOrder: termOrder,
          groupedCourses,
          currentEnrollmentTab: tabId,
        },
        () => resolve()
      )
    );

    // 异步启动主流程（不阻塞 caller）
    processEnrollmentTerms(tabId, termOrder, groupedCourses, coursePairs).catch(
      (error) => {
        console.error("[BG] 选课流程失败:", error);
        enrollmentState.isProcessing = false;
        enrollmentState.failedTerms.push(error.message);
        notifyPopup({ type: "enrollmentError", error: error.message });
      }
    );

    return { ok: true, message: "选课流程已启动", tabId };
  } catch (error) {
    console.error("[BG] 启动选课失败:", error);
    enrollmentState.isProcessing = false;
    return { ok: false, error: error.message };
  }
}

// -----------------------------
// 主流程：逐学期执行（确保 content_script 就绪、调用 startEnrollment、等待结果、刷新并继续）
// -----------------------------
async function processEnrollmentTerms(
  tabId,
  termOrder,
  groupedCourses,
  originalCoursePairs
) {
  console.log("[BG] 启动选课流程处理", { tabId, termOrder });

  for (const term of termOrder) {
    if (!groupedCourses[term] || groupedCourses[term].length === 0) {
      continue;
    }

    enrollmentState.currentStep = `processing_${term}`;

    try {
      notifyPopup({
        type: "enrollmentProgress",
        term,
        status: "processing",
        courses: groupedCourses[term],
      });

      // 1) 确保 content_script 注入并就绪（特别在刷新后）
      await ensureContentScriptReady(tabId);

      // 2) 调用 content_script 的 startEnrollment，并等待其返回（content_script 应在完成 confirm 后返回结果）
      let responseFromPage;
      try {
        responseFromPage = await sendMessageToTab(
          tabId,
          { type: "startEnrollment", courseList: groupedCourses[term] },
          60000
        );
      } catch (err) {
        // 若 sendMessage 失败（content_script 未注入或页面切换），尝试注入后重试一次
        console.warn("[BG] sendMessageToTab 失败，尝试重新注入并重试:", err);
        await ensureContentScriptReady(tabId, 8000);
        responseFromPage = await sendMessageToTab(
          tabId,
          { type: "startEnrollment", courseList: groupedCourses[term] },
          60000
        );
      }

      if (!responseFromPage || !responseFromPage.ok) {
        throw new Error(responseFromPage?.error || "页面脚本返回失败");
      }

      // content_script 返回的 result 应包含 success 字段
      const result = responseFromPage.result || {};
      const success = result.success === true;

      if (success) {
        if (!enrollmentState.completedTerms.includes(term))
          enrollmentState.completedTerms.push(term);
      } else {
        enrollmentState.failedTerms.push(term);
      }

      // 3) 处理完成后：如果还有下一个学期 -> 刷新并等待页面加载再继续；否则完成并清理
      const nextTermIndex = termOrder.indexOf(term) + 1;
      const hasNextTerm = nextTermIndex < termOrder.length;

      if (hasNextTerm) {
        notifyPopup({
          type: success ? "enrollmentRefresh" : "enrollmentError",
          term,
          nextTerm: termOrder[nextTermIndex],
          error: result.error,
        });

        // 保存恢复信息
        await new Promise((resolve) =>
          chrome.storage.local.set(
            {
              autoResumeEnrollment: true,
              nextTerm: termOrder[nextTermIndex],
              remainingTerms: termOrder.slice(nextTermIndex),
              groupedCourses,
              currentEnrollmentTab: tabId,
            },
            () => resolve()
          )
        );

        // 刷新页面并等待加载完成
        chrome.tabs.reload(tabId);
        await waitForTabComplete(tabId, 30000); // 增大超时以适应慢网页

        // 等待 content_script 再次就绪
        await ensureContentScriptReady(tabId, 15000);

        // （可选）再次调用 checkEnrollmentStatus 验证页面上是否呈现成功/失败
        try {
          const statusResp = await sendMessageToTab(
            tabId,
            { type: "checkEnrollmentStatus" },
            5000
          );
          if (statusResp) {
            // 如果页面上显示成功/失败可以更新 enrollmentState（这里仅日志）
            console.log("[BG] checkEnrollmentStatus after reload:", statusResp);
          }
        } catch (e) {
          console.warn("[BG] checkEnrollmentStatus 失败:", e);
        }

        // 继续循环处理下一个学期
      } else {
        // 最后一个学期完成：清理恢复标记
        await new Promise((resolve) =>
          chrome.storage.local.remove(
            [
              "autoResumeEnrollment",
              "nextTerm",
              "remainingTerms",
              "groupedCourses",
              "currentEnrollmentTab",
            ],
            () => resolve()
          )
        );

        notifyPopup({
          type: "enrollmentComplete",
          completedTerms: enrollmentState.completedTerms,
        });
      }
    } catch (error) {
      console.error(`[BG] ${term} 学期选课失败:`, error);
      enrollmentState.failedTerms.push(term);
      notifyPopup({ type: "enrollmentError", term, error: error.message });
      // 失败时决定是否继续：这里选择继续下一个学期
      // break;
    }
  }

  enrollmentState.isProcessing = false;
  console.log("[BG] 选课流程处理完毕");
}

// -----------------------------
// 来自 popup/content 的消息统一处理
// -----------------------------

// Popup 通知函数
function notifyPopup(message) {
  chrome.runtime.sendMessage({ from: "background", ...message });
}

// 通用 fetch 错误处理
async function fetchWithJsonError(url, options = {}) {
  try {
    const response = await fetch(url, options);

    if (response.ok) {
      const data = await response.json();
      return { ok: true, data };
    } else {
      let errorData = null;
      try {
        errorData = await response.json();
      } catch (e) {
        console.error("无法解析错误 JSON:", e);
      }
      return {
        ok: false,
        error:
          (errorData && errorData.error) ||
          response.statusText ||
          `服务器返回 ${response.status}`,
      };
    }
  } catch (e) {
    return { ok: false, error: e.message };
  }
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  const { action, payload, type, from } = message;

  // 处理来自 content_script 的消息
  if (
    from === "content-script" ||
    type === "injector-ready" ||
    type === "UNSW_TERM_COMPLETED" ||
    type === "enrollment-status-update" ||
    type === "injector-failed"
  ) {
    if (type === "injector-ready") {
      console.log("[BG] 收到 content-script: injector-ready");
      sendResponse({ ok: true });
      return false;
    }

    if (type === "injector-failed") {
      console.warn("[BG] content-script 注入失败:", message.error);
      sendResponse({ ok: false, error: message.error });
      return false;
    }

    if (type === "enrollment-status-update") {
      console.log("[BG] content-script enrollment-status-update:", message);
      sendResponse({ ok: true });
      return false;
    }

    if (type === "UNSW_TERM_COMPLETED") {
      const { term, success, error: err } = message;
      console.log(
        "[BG] content-script 通知 UNSW_TERM_COMPLETED",
        term,
        success,
        err
      );
      if (success && term) {
        if (!enrollmentState.completedTerms.includes(term))
          enrollmentState.completedTerms.push(term);
      } else {
        enrollmentState.failedTerms.push(term || err || "unknown");
      }
      notifyPopup({
        type: success ? "enrollmentRefresh" : "enrollmentError",
        term,
        error: err,
      });
      sendResponse({ ok: true });
      return false;
    }
  }

  // 处理来自 popup 的 action
  (async () => {
    try {
      if (action === "validateLicense") {
        const resp = await handleValidateLicense(payload);
        sendResponse(resp);
        return;
      }

      if (action === "getFileKey") {
        const resp = await handleGetFileKey(payload);
        sendResponse(resp);
        return;
      }

      if (action === "fetchCourseIds") {
        const resp = await handleFetchCourseIds(payload);
        sendResponse(resp);
        return;
      }

      if (action === "startEnrollment") {
        const resp = await handleStartEnrollment(payload);
        sendResponse(resp);
        return;
      }

      if (action === "getEnrollmentStatus") {
        sendResponse({ ok: true, state: enrollmentState });
        return;
      }

      if (action === "resetEnrollmentState") {
        enrollmentState = {
          isProcessing: false,
          currentStep: null,
          completedTerms: [],
          failedTerms: [],
        };
        chrome.storage.local.remove(
          [
            "autoResumeEnrollment",
            "nextTerm",
            "remainingTerms",
            "groupedCourses",
            "currentEnrollmentTab",
          ],
          () => {
            sendResponse({ ok: true });
          }
        );
        return;
      }

      // 未知 action
      console.warn("[BG] 未知 action:", action);
      sendResponse({ ok: false, error: "未知 action" });
    } catch (e) {
      console.error("[BG] 处理 action 出错:", e);
      sendResponse({ ok: false, error: e.message });
    }
  })();

  // 必须返回 true 才能在异步 sendResponse 中生效
  return true;
});
