// content_script.js - v3
// 负责：注入 injector.js -> 在页面上下文运行需要 DOM 的选课逻辑 (startEnrollment) -> 与 background 通信
console.log("[CONTENT] 内容脚本已加载");

try {
  let pendingTokenRequest = null;
  let tokenRequestTimeout = null;
  let injectorInjected = false;
  let injectionPromiseResolved = false;
  let pageReadyAckReceived = false;

  console.log("[CONTENT] 开始注入 injector.js");

  const injectorUrl = chrome.runtime.getURL("injector.js");

  const injectionPromise = fetch(injectorUrl)
    .then((res) => {
      if (!res.ok)
        throw new Error("fetch injector.js failed, status=" + res.status);
      return res.text();
    })
    .then((code) => {
      const s = document.createElement("script");
      s.textContent = code + "\n//# sourceURL=injected/injector.js";
      (document.head || document.documentElement).appendChild(s);
      setTimeout(() => s.remove(), 5000);
      injectorInjected = true;
      injectionPromiseResolved = true;
      console.log("[CONTENT] injector.js 已注入到页面上下文");

      // 通知 background 注入成功
      chrome.runtime
        .sendMessage({
          from: "content-script",
          type: "injector-ready",
        })
        .catch((e) => {
          console.warn("[CONTENT] 无法通知 background:", e.message);
        });

      // 通知页面脚本页面已准备好
      window.postMessage(
        {
          source: "content-script",
          type: "PAGE_READY",
        },
        "*"
      );
    })
    .catch((err) => {
      console.error("[CONTENT] 注入 injector.js 失败:", err);
      injectorInjected = false;
      injectionPromiseResolved = true;
      chrome.runtime
        .sendMessage({
          from: "content-script",
          type: "injector-failed",
          error: String(err),
        })
        .catch((e) => {});
    });

  // --- 页面消息监听 ---
  window.addEventListener("message", (event) => {
    if (event.source !== window) return;

    const { source, type } = event.data;

    if (source !== "injector") return;

    console.log("[CONTENT] 从页面脚本收到消息:", type);

    // Token 结果处理
    if (type === "AUTH_TOKEN_RESULT") {
      if (pendingTokenRequest) {
        const timeout = tokenRequestTimeout;
        clearTimeout(timeout);

        if (event.data.token) {
          console.log("[CONTENT] 成功获取令牌");
          pendingTokenRequest.sendResponse({ token: event.data.token });
        } else {
          console.error("[CONTENT] 令牌获取失败:", event.data.error);
          pendingTokenRequest.sendResponse({
            error: event.data.error || "未能获取令牌",
          });
        }
        pendingTokenRequest = null;
      }
      return;
    }

    // 页面就绪确认
    if (type === "PAGE_READY_ACK") {
      pageReadyAckReceived = true;
      console.log("[CONTENT] 页面已就绪");
      return;
    }

    // 选课状态检查
    if (type === "ENROLLMENT_STATUS") {
      chrome.runtime
        .sendMessage({
          from: "content-script",
          type: "enrollment-status-update",
          success: event.data.success,
          hasError: event.data.hasError,
        })
        .catch((e) => {});
      return;
    }
  });

  // --- Background 消息监听 ---
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    const msgType = message.type || message.action;

    console.log("[CONTENT] 收到 Runtime 消息:", msgType);

    // 检查是否在正确的页面
    if (msgType === "checkPage") {
      const isCorrectPage = window.location.href.includes("studentClassEnrol");
      sendResponse({ isCorrectPage });
      return true;
    }

    // 获取认证令牌
    if (msgType === "GET_AUTH_TOKEN") {
      if (pendingTokenRequest) {
        console.warn("[CONTENT] 已有待处理的令牌请求，忽略新请求");
        sendResponse({ error: "已有待处理的令牌请求" });
        return false;
      }

      pendingTokenRequest = { sendResponse };

      const requestTokenFromInjector = () => {
        console.log("[CONTENT] 向页面发送 REQUEST_TOKEN");
        window.postMessage(
          { source: "content-script", type: "REQUEST_TOKEN" },
          "*"
        );

        clearTimeout(tokenRequestTimeout);
        tokenRequestTimeout = setTimeout(() => {
          console.error("[CONTENT] 等待令牌超时");
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
        console.error("[CONTENT] 页面脚本注入失败");
        sendResponse({ error: "页面脚本注入失败，无法获取令牌。" });
        pendingTokenRequest = null;
      } else {
        console.log("[CONTENT] 等待注入器准备就绪...");
        injectionPromise
          .then(() => {
            if (injectorInjected && pendingTokenRequest) {
              console.log("[CONTENT] 注入完成，现在发送 REQUEST_TOKEN");
              requestTokenFromInjector();
            } else if (!injectorInjected && pendingTokenRequest) {
              console.error("[CONTENT] 注入失败");
              pendingTokenRequest.sendResponse({
                error: "页面脚本注入失败，无法获取令牌。",
              });
              pendingTokenRequest = null;
            }
          })
          .catch((err) => {
            console.error("[CONTENT] 注入 Promise 出错:", err);
            if (pendingTokenRequest) {
              pendingTokenRequest.sendResponse({
                error: "页面脚本注入异常: " + err.message,
              });
              pendingTokenRequest = null;
            }
          });
      }

      return true; // 异步响应
    }

    // 检查页面是否准备好（用于后台选课）
    if (msgType === "checkPageReady") {
      sendResponse({
        isCorrectPage: window.location.href.includes("studentClassEnrol"),
        injectorReady: injectorInjected,
        pageReady: pageReadyAckReceived,
      });
      return false;
    }

    // 运行 API（由注入的页面脚本执行）
    if (msgType === "runApis" && Array.isArray(message.urls)) {
      console.log("[CONTENT] 运行 APIs");
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

    // 通知选课完成（用于后台流程检查）
    if (msgType === "checkEnrollmentStatus") {
      window.postMessage(
        { source: "content-script", type: "CHECK_ENROLLMENT_STATUS" },
        "*"
      );

      // 等待一段时间获取页面状态
      setTimeout(() => {
        const hasSuccess = document.body.innerHTML.includes("badge-success");
        const hasError = document.body.innerHTML.includes("badge-danger");
        sendResponse({
          success: hasSuccess && !hasError,
          hasError,
        });
      }, 500);

      return true; // 异步
    }

    // 如果 background 请求开始执行选课（传递 courseList）
    if (msgType === "startEnrollment" && Array.isArray(message.group)) {
      // 兼容：有些 background 传 groupedCourses[term] 为 message.group 或 message.courseList
    }

    if (
      msgType === "startEnrollment" &&
      (message.courseList || message.group)
    ) {
      const courseList =
        message.courseList || message.group || message.courseList;
      (async () => {
        try {
          const res = await startEnrollment(courseList);
          // 向 background 返回结果
          chrome.runtime.sendMessage({
            from: "content-script",
            type: "UNSW_TERM_COMPLETED",
            term: res && res.currentTerm ? res.currentTerm : null,
            success: res && res.success === true,
            result: res,
          });
          sendResponse({ ok: true, result: res });
        } catch (err) {
          console.error("[CONTENT] startEnrollment 运行出错:", err);
          chrome.runtime.sendMessage({
            from: "content-script",
            type: "UNSW_TERM_COMPLETED",
            term: null,
            success: false,
            error: String(err),
          });
          sendResponse({ ok: false, error: err.message || String(err) });
        }
      })();
      return true; // 异步
    }

    console.warn("[CONTENT] 未处理的消息:", msgType);
    return false;
  });

  // 辅助函数：睡眠
  function sleep(ms) {
    return new Promise((r) => setTimeout(r, ms));
  }

  // 切换到指定学期（使用页面 DOM 或页面函数）
  async function ensureTermActive(selector, timeout = 7000) {
    if (!selector) {
      console.log("未提供学期选择器，使用当前激活学期");
      return true;
    }

    console.log(`尝试切换到学期: ${selector}`);

    let linkId = selector;
    if (!/^term\d+Link$/.test(linkId) && /^\d+$/.test(selector)) {
      linkId = `term${selector}Link`;
    }

    const tryClickLink = () => {
      const el = document.getElementById(linkId);
      if (el) {
        console.log(`找到学期链接 id=${linkId}，点击切换`);
        el.click();
        return true;
      }
      const el2 = document.getElementById(selector);
      if (el2) {
        console.log(`找到学期链接 id=${selector}，点击切换`);
        el2.click();
        return true;
      }
      return false;
    };

    try {
      if (typeof window.selectTerm === "function") {
        const idNumMatch = selector.match(/\d+/);
        if (idNumMatch) {
          console.log(`调用 selectTerm(${idNumMatch[0]})`);
          try {
            window.selectTerm(idNumMatch[0]);
          } catch (e) {
            console.warn("调用 window.selectTerm 抛错:", e);
          }
        }
      }
    } catch (e) {
      console.warn("调用 selectTerm 失败:", e);
    }

    tryClickLink();

    const start = Date.now();
    while (Date.now() - start < timeout) {
      const activeForm = document.querySelector("div.tab-pane.active form");
      if (activeForm) {
        const termInput = activeForm.querySelector('input[name="term"]');
        if (!selector) return true;
        if (
          termInput &&
          (termInput.value === selector || termInput.value.includes(selector))
        ) {
          console.log("[OK] 已切换到目标学期");
          return true;
        }
        if (
          document.querySelector(`#${linkId}.active`) ||
          document.querySelector("div.tab-pane.active")
        ) {
          console.log("[OK] 检测到激活的学期标签");
          return true;
        }
      }
      await sleep(250);
    }

    console.warn("[WARN] 切换学期超时，将在当前学期继续");
    return false;
  }

  // 等待激活表单
  async function waitForActiveForm(timeout = 7000) {
    const start = Date.now();
    while (Date.now() - start < timeout) {
      const activeForm = document.querySelector("div.tab-pane.active form");
      if (activeForm) {
        const seq = activeForm.querySelector('input[name="bsdsSequence"]');
        const term = activeForm.querySelector('input[name="term"]');
        if (seq && term) {
          return { activeForm, sequenceInput: seq, termInput: term };
        }
        return {
          activeForm,
          sequenceInput: seq || null,
          termInput: term || null,
        };
      }
      await sleep(200);
    }
    return null;
  }

  // 步骤 0：搜索课程
  async function runStep0_SearchCourse(courseCode, activeFormInfo, forcedTerm) {
    console.log("=== 步骤 0：搜索课程 ===");
    if (!activeFormInfo || !activeFormInfo.activeForm) {
      console.error("找不到激活的表单");
      return null;
    }

    const { activeForm, sequenceInput, termInput } = activeFormInfo;

    if (!sequenceInput) {
      console.error("找不到必要的表单字段 (bsdsSequence)");
      return null;
    }

    const termValue = forcedTerm || (termInput ? termInput.value : "");

    const searchPayload = {
      bsdsSequence: sequenceInput.value,
      term: termValue,
      search: courseCode,
      "bsdsSubmit-search-courses": "Search",
    };

    console.log("发送搜索请求:", searchPayload);

    try {
      const response = await fetch(
        "https://my.unsw.edu.au/active/studentClassEnrol/courses.xml",
        {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: new URLSearchParams(searchPayload),
          credentials: "same-origin",
        }
      );

      if (!response.ok) {
        console.error(`搜索失败: ${response.status} ${response.statusText}`);
        return null;
      }

      const searchResultHtml = await response.text();
      console.log("[OK] 搜索成功");

      const sequenceMatch = searchResultHtml.match(
        /<input type="hidden" name="bsdsSequence" value="(\d+)"/
      );

      if (!sequenceMatch) {
        console.error("无法从搜索结果中提取 bsdsSequence");
        return null;
      }

      const newSequence = sequenceMatch[1];
      console.log(`[OK] 获取到新令牌: ${newSequence}`);

      return { sequence: newSequence, termValue: termValue };
    } catch (error) {
      console.error("搜索请求网络错误:", error);
      return null;
    }
  }

  // 步骤 1：提交课程选择（支持多个课程一起提交）
  async function runStep1_SubmitCourses(courseCodes, searchData, forcedTerm) {
    console.log("=== 步骤 1：提交课程选择（批量）===");

    // 验证所有课程都有对应的 ID（这里假设 caller 已提供 COURSE_ID_MAP）
    const courseIds = [];
    for (const courseCode of courseCodes) {
      if (!window.__COURSE_ID_MAP || !window.__COURSE_ID_MAP[courseCode]) {
        console.error(`课程代码 ${courseCode} 没有对应的课程ID`);
        return null;
      }
      courseIds.push(window.__COURSE_ID_MAP[courseCode]);
    }

    const termValue = forcedTerm || (searchData && searchData.termValue) || "";

    // 构建表单数据 - 关键：使用数组方式添加多个 selectCourses[]
    const formData = new URLSearchParams();
    formData.append("bsdsSequence", searchData.sequence);
    formData.append("term", termValue);
    formData.append("course", "");
    formData.append("class", "");

    for (const courseId of courseIds) {
      formData.append("selectCourses[]", courseId);
    }

    formData.append("search", courseCodes.join(" "));
    formData.append("bsdsSubmit-submit-courses", "Confirm Enrolment Request");

    console.log("发送批量课程提交请求:", Object.fromEntries(formData));

    try {
      const response = await fetch(
        "https://my.unsw.edu.au/active/studentClassEnrol/courses.xml",
        {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: formData,
          credentials: "same-origin",
        }
      );

      if (!response.ok) {
        console.error(`提交失败: ${response.status} ${response.statusText}`);
        return null;
      }

      const confirmPageHtml = await response.text();
      console.log("[OK] 成功进入确认页面");

      const sequenceMatch = confirmPageHtml.match(
        /<input type="hidden" name="bsdsSequence" value="(\d+)"/
      );

      if (!sequenceMatch) {
        console.error("无法从确认页面提取 bsdsSequence");
        return null;
      }

      const confirmSequence = sequenceMatch[1];
      console.log(`[OK] 获取到确认令牌: ${confirmSequence}`);

      return { confirmSequence, termValue };
    } catch (error) {
      console.error("提交请求网络错误:", error);
      return null;
    }
  }

  // 步骤 2：最终确认注册
  async function runStep2_ConfirmEnrolment(confirmSequence, forcedTerm) {
    console.log("=== 步骤 2：最终确认注册 ===");
    const confirmPayload = {
      bsdsSequence: confirmSequence,
      term: forcedTerm || "",
      "bsdsSubmit-confirm": "Submit Enrolment Request",
    };

    console.log("发送最终确认请求:", confirmPayload);

    const maxAttempts = 2;
    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
      try {
        const response = await fetch(
          "https://my.unsw.edu.au/active/studentClassEnrol/confirm.xml",
          {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams(confirmPayload),
            credentials: "same-origin",
          }
        );

        if (!response.ok) {
          console.warn(`确认请求返回 ${response.status} (尝试 ${attempt})`);
          if (response.status === 403 && attempt < maxAttempts) {
            await sleep(300);
            continue;
          }
          console.error(`确认失败: ${response.status}`);
          return { success: false, status: response.status };
        }

        const resultHtml = await response.text();
        console.log("[OK] 已收到最终结果页面");

        if (
          resultHtml.includes("badge-success") &&
          (resultHtml.includes("Success") ||
            resultHtml.includes("Enrolment Results"))
        ) {
          console.log("[DONE] 注册成功！");
          return { success: true, resultHtml };
        } else if (
          resultHtml.includes("badge-danger") ||
          resultHtml.includes("Error")
        ) {
          console.error("[ERR] 注册失败");
          return { success: false, status: "enrol_failed", resultHtml };
        } else {
          console.warn("[WARN] 结果未知");
          return { success: false, status: "unknown", resultHtml };
        }
      } catch (error) {
        console.error("确认请求网络错误:", error);
        return {
          success: false,
          status: "network_error",
          error: error.message,
        };
      }
    }

    return { success: false, status: "max_attempts" };
  }

  // 同学期批量选课的完整流程
  async function batchEnrollSameTerm(courseCodes, termAlias) {
    console.log("=".repeat(60));
    console.log(`[START] 开始 ${termAlias} 学期批量选课: ${courseCodes.join(", ")}`);
    console.log("=".repeat(60));

    const TERM_MAP = {
      "2026_SUMMER": "5262",
      "2026_T1": "5263",
      "2026_T2": "5266",
      "2026_T3": "5269",
      SUMMER: "5262",
      T1: "5263",
      T2: "5266",
      T3: "5269",
    };

    const termSelector = TERM_MAP[termAlias];
    if (!termSelector) {
      console.error(`未知的学期别名: ${termAlias}`);
      return { success: false, error: "unknown_term" };
    }
    console.log(`学期 ID: ${termSelector}`);

    // 切换到目标学期
    await ensureTermActive(termSelector);

    let activeFormInfo = await waitForActiveForm();
    if (!activeFormInfo) {
      console.error("流程终止：找不到激活表单");
      return { success: false, error: "no_form" };
    }

    // 确保表单的 term 字段已更新
    if (activeFormInfo.termInput) {
      const start = Date.now();
      while (Date.now() - start < 5000) {
        if (
          activeFormInfo.termInput.value &&
          activeFormInfo.termInput.value.includes(termSelector)
        ) {
          console.log("[OK] active form 的 term 字段已更新");
          break;
        }
        await sleep(250);
        activeFormInfo = (await waitForActiveForm(2000)) || activeFormInfo;
      }
    }

    async function runFullBatch() {
      const firstCourse = courseCodes[0];
      const searchData = await runStep0_SearchCourse(
        firstCourse,
        activeFormInfo,
        termSelector
      );
      if (!searchData) {
        console.error("流程终止：搜索失败");
        return { success: false, stage: "search" };
      }

      await sleep(300);

      const submitResult = await runStep1_SubmitCourses(
        courseCodes,
        searchData,
        termSelector
      );
      if (!submitResult || !submitResult.confirmSequence) {
        console.error("流程终止：提交课程失败");
        return { success: false, stage: "submit" };
      }

      await sleep(300);

      const confirmResult = await runStep2_ConfirmEnrolment(
        submitResult.confirmSequence,
        termSelector
      );
      return confirmResult;
    }

    let attemptResult = await runFullBatch();

    if (
      !attemptResult.success &&
      (attemptResult.status === 403 ||
        attemptResult.status === "max_attempts" ||
        attemptResult.stage === "submit")
    ) {
      console.warn("[WARN] 首次尝试失败，正在重试...");
      await sleep(300);
      activeFormInfo = (await waitForActiveForm()) || activeFormInfo;
      attemptResult = await runFullBatch();
    }

    if (attemptResult.success) {
      console.log(`[OK] ${termAlias} 学期选课完成：成功`);
    } else {
      console.log(`[ERR] ${termAlias} 学期选课完成：失败`, attemptResult);
    }

    console.log("=".repeat(60));
    return attemptResult;
  }

  // 页面级的 startEnrollment：接收 courseList 格式 [["COMP9101","courseId","T2"], ...]
  async function startEnrollment(courseList) {
    // courseList -> 提取 course code 列表与映射
    const COURSE_ID_MAP = {};
    const COURSE_LIST = [];
    let currentTerm = null;

    for (const [courseCode, courseId, termAlias] of courseList) {
      COURSE_ID_MAP[courseCode] = courseId;
      COURSE_LIST.push(courseCode);
      if (!currentTerm) currentTerm = termAlias;
    }

    // 暴露到 window 供 runStep1 使用
    window.__COURSE_ID_MAP = COURSE_ID_MAP;

    console.log("开始同学期批量选课, currentTerm=", currentTerm);

    // 执行
    const result = await batchEnrollSameTerm(COURSE_LIST, currentTerm);

    // 当成功时，将 completedTerms 放入 sessionStorage
    if (result && result.success) {
      const completedTerms = JSON.parse(
        sessionStorage.getItem("completedTerms") || "[]"
      );
      if (!completedTerms.includes(currentTerm)) {
        completedTerms.push(currentTerm);
        sessionStorage.setItem(
          "completedTerms",
          JSON.stringify(completedTerms)
        );
      }
    }

    // 返回结果对象（包含 currentTerm，success 等）
    return { currentTerm, ...result };
  }

  // End of try block
} catch (e) {
  console.error("[CONTENT] 脚本顶层出现意外错误:", e);
  try {
    chrome.runtime.sendMessage({
      from: "content-script",
      type: "content-script-error",
      error: String(e),
    });
  } catch (err) {}
}
