// popup.js
// 保留 License / UserKey / 选课 UI 与逻辑。
// 仅修改上传/解密流程：上传后自动解析并填充到选课文本框，禁用原来的“解密文件”显示。

document.addEventListener("DOMContentLoaded", () => {
  // --- 元素引用 ---
  const appContainer = document.getElementById("app-container");
  const loginView = document.getElementById("login-view");
  const licenseForm = document.getElementById("license-form");
  const licenseKeyInput = document.getElementById("license-key");
  const verifyLicenseBtn = document.getElementById("verify-license-btn");
  const licenseError = document.getElementById("license-error");
  const createLicenseLink = document.getElementById("create-license-link");

  const userkeyView = document.getElementById("userkey-view");
  const userkeyForm = document.getElementById("userkey-form");
  const userKeyInput = document.getElementById("user-key");
  const activateBtn = document.getElementById("activate-btn");
  const userkeyError = document.getElementById("userkey-error");
  const backToLicenseBtn = document.getElementById("back-to-license-btn");
  const verifiedLicenseStatus = document.getElementById(
    "verified-license-status"
  );
  const verifiedLicenseExpiry = document.getElementById(
    "verified-license-expiry"
  );

  const mainView = document.getElementById("main-view");
  const logoutBtn = document.getElementById("logout-btn");
  const licenseInfoDiv = document.getElementById("license-info");
  const licenseStatusSpan = licenseInfoDiv.querySelector(".license-status");
  const licenseExpirySpan = licenseInfoDiv.querySelector(".license-expiry");
  const licenseSpinner = licenseInfoDiv.querySelector(".license-spinner");

  // 上传 / 解密 / 选课元素
  const dropzone = document.getElementById("dropzone");
  const dropzoneText = document.getElementById("dropzone-text");
  const fileSelectBtn = document.getElementById("file-select-btn");
  const fileInput = document.getElementById("file-input");
  // const submitCourseBtn = document.getElementById("submit-course-btn");
  const statusMessage = document.getElementById("status-message"); // 用于文件上传的状态

  // 选课相关
  const unswEnrollBtn = document.getElementById("unsw-enrollBtn");
  const unswStatusEl = document.getElementById("unsw-status"); // 用于选课的状态
  const unswPageWarning = document.getElementById("unsw-pageWarning");
  const unswCoursePairsInput = document.getElementById("unsw-course-pairs");

  // --- 状态变量 ---
  let selectedFile = null;
  let verifiedLicenseData = null;

  // 初始化 tab
  initializeTabs();
  // 初始禁用选课按钮
  if (unswEnrollBtn) unswEnrollBtn.disabled = true;

  function navigateTo(viewName) {
    if (appContainer) {
      appContainer.setAttribute("data-view", viewName);
    }
    // 确保在导航时隐藏所有顶层错误消息
    if (licenseError) licenseError.style.display = "none";
    if (userkeyError) userkeyError.style.display = "none";
  }

  // ============================================
  // --- 与 background 通信辅助函数 ---
  // ============================================
  function sendMessageToBackground(action, payload) {
    return new Promise((resolve, reject) => {
      chrome.runtime.sendMessage({ action, payload }, (response) => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
        } else if (response && response.ok === false) {
          const errorMsg =
            response.error ||
            (response.data && response.data.error) || // 备用
            response.message || // 备用
            "未知错误"; // 最后的备用

          reject(new Error(errorMsg));
        } else {
          resolve(response);
        }
      });
    });
  }

  // 接收 background 的通知（进度、刷新、完成、错误）
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === "enrollmentProgress") {
      unswShowStatus(
        `正在处理 ${message.term} 学期的 ${message.courses.length} 门课程...`,
        "info"
      );
    } else if (message.type === "enrollmentRefresh") {
      unswShowStatus(
        `[OK] ${message.term} 学期处理完成！准备处理 ${message.nextTerm}...`,
        "success"
      );
    } else if (message.type === "enrollmentComplete") {
      unswShowStatus(
        `[OK] 所有 ${message.completedTerms.length} 个学期的选课请求已完成！`,
        "success"
      );
    } else if (message.type === "enrollmentError") {
      const errorMsg = message.term
        ? `${message.term} 学期处理失败: ${message.error}`
        : `选课失败: ${message.error}`;
      unswShowStatus(errorMsg, "error");
    }
    sendResponse({ received: true });
    return true; // 保持异步响应通道
  });

  // ============================================
  // --- 初始检查（license/userKey）---
  // ============================================
  async function checkInitialState() {
    try {
      const result = await chrome.storage.local.get(["licenseKey", "userKey"]);
      if (result.licenseKey && result.userKey) {
        navigateTo("main");
        await validateAndDisplayLicense(result.licenseKey); // 检查许可证状态
        checkAutoResume(); // 检查是否有中断的任务
      } else {
        navigateTo("login");
      }
    } catch (error) {
      console.error("初始状态检查失败:", error);
      navigateTo("login");
    }
  }

  async function checkAutoResume() {
    try {
      const storage = await chrome.storage.local.get([
        "autoResumeEnrollment",
        "nextTerm",
        "remainingTerms",
        "groupedCourses",
      ]);
      if (
        storage.autoResumeEnrollment &&
        storage.remainingTerms &&
        storage.groupedCourses
      ) {
        unswShowStatus(
          `检测到中断的选课流程，将自动继续处理 ${storage.remainingTerms.join(
            ", "
          )} 学期...`,
          "info"
        );
        await new Promise((r) => setTimeout(r, 1200));
        await sendMessageToBackground("startEnrollment", {
          coursePairs: storage.groupedCourses,
          groupedCourses: storage.groupedCourses,
          termOrder: storage.remainingTerms,
        });
      }
    } catch (error) {
      unswShowStatus("恢复选课流程失败: " + error.message, "error");
    }
  }

  checkInitialState();

  // ============================================
  // --- 许可证验证（委托 background）---
  // ============================================
  async function validateAndDisplayLicense(licenseKey) {
    showLicenseLoading(
      true,
      licenseInfoDiv,
      licenseStatusSpan,
      licenseExpirySpan,
      licenseSpinner
    );
    try {
      const response = await sendMessageToBackground("validateLicense", {
        license_key: licenseKey,
      });

      // API 成功响应，我们现在检查 data
      if (response.ok && response.data) {
        displayLicenseInfo(
          response.data,
          licenseInfoDiv,
          licenseStatusSpan,
          licenseExpirySpan
          // (spinner 已在 displayLicenseInfo 中处理)
        );

        if (!response.data.valid || response.data.expired) {
          unswShowStatus(
            `许可证状态: ${response.data.error || "已过期/无效"}`,
            "error"
          );
        }
      } else {
        displayLicenseInfo(
          {
            license_active: false,
            expired: true,
            error: "服务器返回数据格式错误",
          },
          licenseInfoDiv,
          licenseStatusSpan,
          licenseExpirySpan
        );
      }
    } catch (error) {
      console.error("验证许可证失败:", error);
      displayLicenseInfo(
        {
          license_active: false,
          expired: true,
          error: error.message || "无法连接到服务器",
        },
        licenseInfoDiv,
        licenseStatusSpan,
        licenseExpirySpan
      );
    }
  }

  licenseForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    showLoading(verifyLicenseBtn, true);
    licenseError.style.display = "none";
    const licenseKey = licenseKeyInput.value.trim();

    if (!licenseKey) {
      showLicenseError("License Key 不能为空");
      showLoading(verifyLicenseBtn, false);
      return;
    }

    try {
      // sendMessageToBackground 在 ok:false 时会 reject
      // (即 HTTP 4xx 或 5xx 会进入 catch 块)
      const response = await sendMessageToBackground("validateLicense", {
        license_key: licenseKey,
      });

      // 验证成功 (200 OK)
      verifiedLicenseData = { ...response.data, license_key: licenseKey };
      displayVerifiedLicenseInfo(
        response.data,
        verifiedLicenseStatus,
        verifiedLicenseExpiry
      );
      navigateTo("userkey");
    } catch (error) {
      console.error("验证失败:", error);
      showLicenseError(error.message || "无法连接到服务器，请检查网络连接");
    } finally {
      showLoading(verifyLicenseBtn, false);
    }
  });

  // ============================================
  // --- User Key 提交 ---
  // ============================================
  userkeyForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    showLoading(activateBtn, true);
    userkeyError.style.display = "none";
    const userKey = userKeyInput.value.trim();
    if (!userKey) {
      showUserkeyError("User Key 不能为空");
      showLoading(activateBtn, false);
      return;
    }
    try {
      await chrome.storage.local.set({
        licenseKey: verifiedLicenseData.license_key,
        userKey,
      });
      navigateTo("main");
      displayLicenseInfo(
        verifiedLicenseData,
        licenseInfoDiv,
        licenseStatusSpan,
        licenseExpirySpan
        // (spinner 在 displayLicenseInfo 中处理)
      );
      licenseKeyInput.value = "";
      userKeyInput.value = "";
    } catch (error) {
      console.error("保存密钥失败:", error);
      showUserkeyError("无法保存密钥，请稍后再试");
    } finally {
      showLoading(activateBtn, false);
    }
  });

  backToLicenseBtn.addEventListener("click", () => {
    navigateTo("login");
    userkeyError.style.display = "none";
    userKeyInput.value = "";
    verifiedLicenseData = null;
  });

  createLicenseLink.addEventListener("click", (e) => {
    e.preventDefault();
    chrome.tabs.create({ url: "https://your-website.com/create-license" });
  });

  // ============================================
  // --- 登出处理 ---
  // ============================================
  function logoutAndGoToLogin() {
    chrome.storage.local.remove(["licenseKey", "userKey"], async () => {
      try {
        await sendMessageToBackground("resetEnrollmentState", {});
      } catch (e) {}

      navigateTo("login");
      licenseKeyInput.value = "";
      userKeyInput.value = "";
      handleFile(null); // 清空文件选择
      hideStatus();
      unswShowStatus("", "info", true); // 隐藏 unsw 状态
      licenseError.style.display = "none";
      userkeyError.style.display = "none";
      licenseInfoDiv.style.display = "none";
      verifiedLicenseData = null;
      if (unswCoursePairsInput) unswCoursePairsInput.value = ""; // 清空文本框
    });
  }
  logoutBtn.addEventListener("click", logoutAndGoToLogin);

  // ============================================
  // --- 文件上传 / 解密 / 自动填充选课列表 ---
  // ============================================

  // 隐藏原来的解密输出和提交按钮
  try {
    const decryptedOutput = document.getElementById("decrypted-output");
    if (decryptedOutput) decryptedOutput.style.display = "none";
  } catch (e) {}

  try {
    const submitCourseBtn = document.getElementById("submit-course-btn");
    if (submitCourseBtn) {
      submitCourseBtn.style.display = "none";
      submitCourseBtn.disabled = true;
    }
  } catch (e) {}

  // 绑定文件选择按钮
  fileSelectBtn.addEventListener("click", () => fileInput.click());

  fileInput.addEventListener("change", (e) => {
    const f = e.target?.files?.[0] || null;
    handleFileAutoProcess(f);
  });

  // 拖拽上传
  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });
  dropzone.addEventListener("dragleave", () =>
    dropzone.classList.remove("dragover")
  );
  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    const f = e.dataTransfer?.files?.[0] || null;
    handleFileAutoProcess(f);
  });

  // 更新选择文件 UI
  function handleFile(f) {
    if (f) {
      selectedFile = f;
      dropzoneText.textContent = `已选择: ${f.name}`;
      hideStatus();
    } else {
      selectedFile = null;
      dropzoneText.textContent = "拖拽加密文件到这里, 或";
      hideStatus();
    }
    if (fileInput) fileInput.value = ""; // 清空 input 以便选择同名文件
  }

  // 上传后自动处理文件
  async function handleFileAutoProcess(file) {
    handleFile(file);

    if (!unswCoursePairsInput || !unswEnrollBtn) {
      console.error(
        "UI 元素未正确加载 (unswCoursePairsInput or unswEnrollBtn)"
      );
      return;
    }

    if (!file) {
      unswCoursePairsInput.value = "";
      unswEnrollBtn.disabled = true;
      return;
    }

    showStatus("正在读取文件...", "info");
    try {
      const fileContent = await readFileAsText(file);
      let parsedJson;
      try {
        parsedJson = JSON.parse(fileContent);
      } catch (e) {
        throw new Error("文件不是有效的 JSON");
      }

      // 如果 JSON 已包含 selected 字段，直接填充
      if (parsedJson && Array.isArray(parsedJson.selected)) {
        const pairs = parsedJson.selected
          .map((it) => {
            const code = (it.course_code || it.courseCode || it.code || "")
              .toString()
              .trim()
              .toUpperCase();
            const term = (it.term || "").toString().trim().toUpperCase();
            return `${term} ${code}`.trim();
          })
          .filter((l) => l && l.split(/\s+/).length >= 2);

        if (pairs.length === 0) throw new Error("解密数据中未包含有效课程对");
        unswCoursePairsInput.value = pairs.join("\n");
        unswEnrollBtn.disabled = false;
        showStatus("文件解析完成，已填充选课列表", "success");
        return;
      }

      // 否则请求后台解密
      showStatus("向服务器请求文件密钥...", "info");
      const storageResult = await chrome.storage.local.get([
        "licenseKey",
        "userKey",
      ]);
      const licenseKey = storageResult.licenseKey;
      const userKeyB64 = storageResult.userKey;
      if (!licenseKey || !userKeyB64)
        throw new Error("缺少 licenseKey 或 userKey，请先登录插件");

      const resp = await sendMessageToBackground("getFileKey", {
        encrypted_file: parsedJson,
        license_key: licenseKey,
      });
      if (!resp || !resp.data) throw new Error("服务器返回数据格式错误");

      const wrappedFileKey = resp.data.wrapped_file_key;
      if (!wrappedFileKey)
        throw new Error("服务器返回数据中缺少 wrapped_file_key");

      showStatus("正在解密文件密钥...", "info");
      const fileKeyBytes = await unwrapFileKey(wrappedFileKey, userKeyB64);

      showStatus("正在解密文件内容...", "info");
      const decryptedData = await decryptFileContent(parsedJson, fileKeyBytes);

      if (!decryptedData || !Array.isArray(decryptedData.selected))
        throw new Error("解密后数据格式不正确，缺少 selected");

      const finalPairs = decryptedData.selected
        .map((it) => {
          const code = (it.course_code || it.courseCode || it.code || "")
            .toString()
            .trim()
            .toUpperCase();
          const term = (it.term || "").toString().trim().toUpperCase();
          return `${term} ${code}`.trim();
        })
        .filter((l) => l && l.split(/\s+/).length >= 2);

      if (finalPairs.length === 0)
        throw new Error("解密结果中未解析到有效课程对");

      unswCoursePairsInput.value = finalPairs.join("\n");
      unswEnrollBtn.disabled = false;
      showStatus("解密并解析成功，已填充选课列表", "success");
    } catch (error) {
      console.error("处理文件失败:", error);
      unswCoursePairsInput.value = "";
      unswEnrollBtn.disabled = true;
      showStatus("解析失败: " + (error.message || error), "error");
    }
  }

  // ============================================
  // --- UNSW 批量选课（popup 解析并发给 background） ---
  // ============================================
  function parseCoursePairs(inputText) {
    const lines = inputText.split("\n").filter((line) => line.trim());
    const pairs = [];
    for (const line of lines) {
      const trimmed = line.trim().toUpperCase();
      if (!trimmed) continue;
      const parts = trimmed.split(/\s+/);
      if (parts.length >= 2) {
        const term = parts[0];
        const courseCode = parts[1];
        pairs.push([term, courseCode]);
      }
    }
    return pairs;
  }

  unswEnrollBtn.addEventListener("click", async () => {
    if (!unswCoursePairsInput) {
      unswShowStatus("错误: 课程输入框未找到", "error");
      return;
    }

    const inputText = (unswCoursePairsInput.value || "").trim();
    if (!inputText) {
      unswShowStatus("请输入至少一对课程和学期", "error");
      return;
    }
    const coursePairs = parseCoursePairs(inputText);
    if (coursePairs.length === 0) {
      unswShowStatus("未识别到有效的课程-学期对，请检查输入格式", "error");
      return;
    }
    unswShowStatus(`已识别 ${coursePairs.length} 对课程，正在处理...`, "info");
    showLoading(unswEnrollBtn, true);

    try {
      // 从 background 获取课程数据
      const courseResponse = await sendMessageToBackground("fetchCourseIds", {
        coursePairs,
      });

      if (!courseResponse || !courseResponse.data)
        throw new Error("未能从服务器获取课程数据");

      const courseData = courseResponse.data;

      // 构建选课列表
      const { enrollmentList, errors } = buildEnrollmentList(
        coursePairs,
        courseData
      );

      if (errors.length > 0) {
        const errorMsg = "部分课程处理失败:\n" + errors.join("\n");
        unswShowStatus(errorMsg, "error");
        if (enrollmentList.length === 0) {
          return; // 没有可执行的课程，停止
        }
      }

      // 按学期分组
      const groupedByTerm = {};
      for (const [courseCode, courseId, term] of enrollmentList) {
        if (!groupedByTerm[term]) groupedByTerm[term] = [];
        groupedByTerm[term].push([courseCode, courseId, term]);
      }

      const termOrder = Object.keys(groupedByTerm);
      if (termOrder.length === 0) {
        throw new Error("未能构建任何有效的选课组合");
      }

      // 启动选课流程（由 background 管理）
      await sendMessageToBackground("startEnrollment", {
        coursePairs, // (原始数据，用于可能的重试)
        groupedCourses: groupedByTerm,
        termOrder: termOrder,
      });

      unswShowStatus("[OK] 选课流程已启动，后台将继续处理", "success");
    } catch (error) {
      console.error("批量选课流程失败:", error);
      unswShowStatus("执行失败: " + (error.message || error), "error");
    } finally {
      showLoading(unswEnrollBtn, false);
    }
  });

  function buildEnrollmentList(coursePairs, courseData) {
    const enrollmentList = [];
    const errors = [];
    for (const [term, courseCode] of coursePairs) {
      const upperTerm = term.toUpperCase();
      const entries = courseData[courseCode];
      if (!entries || entries.length === 0) {
        errors.push(`未找到课程: ${courseCode}`);
        continue;
      }
      const matchedEntries = entries.filter(
        (item) => item.term && item.term.toUpperCase() === upperTerm
      );
      if (matchedEntries.length === 0) {
        errors.push(`未找到 ${courseCode} 在学期 ${term} 的数据`);
        continue;
      }
      const entry = matchedEntries[0];
      const courseId = entry.course_id || entry.courseId || entry.id;
      if (!courseId) {
        errors.push(`${courseCode} (${term}) 缺少 course_id`);
        continue;
      }
      enrollmentList.push([courseCode, courseId, term]);
    }
    return { enrollmentList, errors };
  }

  // ============================================
  // --- 工具 / UI 函数 ---
  // ============================================

  function initializeTabs() {
    const tabBtns = Array.from(document.querySelectorAll(".tab-btn"));
    const tabContents = Array.from(document.querySelectorAll(".tab-content"));
    if (!tabBtns.length || !tabContents.length) return;

    function activateTab(tabId, save = true) {
      tabBtns.forEach((btn) =>
        btn.dataset.tab === tabId
          ? btn.classList.add("active")
          : btn.classList.remove("active")
      );
      tabContents.forEach((el) => {
        if (el.id === tabId) {
          el.classList.add("active");
        } else {
          el.classList.remove("active");
        }
      });
      if (save) {
        try {
          chrome.storage.local.set({ popupActiveTab: tabId });
        } catch (e) {}
      }
    }

    tabBtns.forEach((btn) =>
      btn.addEventListener("click", () => {
        const t = btn.dataset.tab;
        if (t) activateTab(t);
      })
    );
    try {
      chrome.storage.local.get("popupActiveTab", (res) => {
        const tabToOpen = res && res.popupActiveTab ? res.popupActiveTab : null;
        const validTab =
          tabToOpen && tabContents.some((c) => c.id === tabToOpen);
        if (validTab) {
          activateTab(tabToOpen, false);
        } else {
          // 默认激活第一个
          activateTab(tabContents[0].id, false);
        }
      });
    } catch (e) {
      activateTab(tabContents[0].id, false);
    }
  }

  function showLoading(btn, isLoading) {
    if (!btn) return;
    btn.disabled = isLoading;
    const btnText = btn.querySelector(".btn-text");
    const spinner = btn.querySelector(".spinner");
    if (!btnText || !spinner) return; // 确保元素存在

    if (isLoading) {
      btnText.style.display = "none";
      spinner.style.display = "inline-block";
    } else {
      btnText.style.display = "inline-block";
      spinner.style.display = "none";
    }
  }

  function showLicenseLoading(
    isLoading,
    container,
    statusEl,
    expiryEl,
    spinnerEl
  ) {
    if (!container) return;
    if (isLoading) {
      container.style.display = "flex"; // 确保容器可见
      if (statusEl) statusEl.textContent = "验证中...";
      if (expiryEl) expiryEl.textContent = "";
      if (spinnerEl) spinnerEl.style.display = "inline-block";
    } else {
      // 加载结束时，只隐藏 spinner，让 displayLicenseInfo 决定内容
      if (spinnerEl) spinnerEl.style.display = "none";
    }
  }

  //  Header 许可证信息显示 (并在失败时触发登出)
  function displayLicenseInfo(
    data, // { license_active, expired, license_expires_at, error }
    container,
    statusEl,
    expiryEl
  ) {
    if (!container) return;
    container.style.display = "flex"; // 确保可见
    // 确保 spinner 隐藏 (showLicenseLoading(false,...) 也许没调用)
    const spinnerEl = container.querySelector(".license-spinner");
    if (spinnerEl) spinnerEl.style.display = "none";

    if (!data || !data.license_active || data.expired) {
      statusEl.textContent = data.expired ? "已过期" : "无效";
      expiryEl.textContent = "请重新登录";
      setTimeout(logoutAndGoToLogin, 1500); // 延迟登出，让用户看到提示
      return;
    }

    statusEl.textContent = "已激活";
    expiryEl.textContent = data.license_expires_at
      ? `到期: ${new Date(data.license_expires_at).toLocaleDateString()}`
      : "";
  }

  function displayVerifiedLicenseInfo(
    data, // { license_active, expired, license_expires_at }
    statusEl,
    expiryEl
  ) {
    if (statusEl) {
      statusEl.textContent = data.license_active ? "有效" : "未激活";
      if (data.expired) statusEl.textContent = "已过期";
    }
    if (expiryEl) {
      expiryEl.textContent = data.license_expires_at
        ? new Date(data.license_expires_at).toLocaleDateString()
        : "N/A";
    }
  }

  function showStatus(msg, type) {
    if (!statusMessage) return;
    statusMessage.textContent = msg;
    statusMessage.style.display = "block";
    statusMessage.className = "status-message " + (type || "");
  }
  function hideStatus() {
    if (!statusMessage) return;
    statusMessage.style.display = "none";
  }
  function showLicenseError(msg) {
    if (licenseError) {
      licenseError.style.display = "block";
      licenseError.textContent = msg;
    }
  }
  function showUserkeyError(msg) {
    if (userkeyError) {
      userkeyError.style.display = "block";
      userkeyError.textContent = msg;
    }
  }
  function readFileAsText(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = (e) => reject(e);
      reader.readAsText(file);
    });
  }

  function unswShowStatus(msg, type, hide = false) {
    if (!unswStatusEl) return;
    if (hide) {
      unswStatusEl.style.display = "none";
      return;
    }
    unswStatusEl.style.display = "block";
    unswStatusEl.textContent = msg;
    unswStatusEl.className = "status-message " + (type || "");
  }

  // 页面加载完毕默认隐藏状态
  hideStatus();
});
