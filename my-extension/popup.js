// popup.js (精简版)
document.addEventListener("DOMContentLoaded", () => {
  // --- 常量 ---
  const API_BASE = "http://localhost:8000/api";

  // --- 元素引用 ---
  const appContainer = document.getElementById("app-container");

  // 登录视图 (第一步：验证 License)
  const loginView = document.getElementById("login-view");
  const licenseForm = document.getElementById("license-form");
  const licenseKeyInput = document.getElementById("license-key");
  const verifyLicenseBtn = document.getElementById("verify-license-btn");
  const licenseError = document.getElementById("license-error");
  const createLicenseLink = document.getElementById("create-license-link");

  // User Key 视图 (第二步：输入 User Key)
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

  // 主视图（解密）
  const mainView = document.getElementById("main-view");
  const logoutBtn = document.getElementById("logout-btn");
  const licenseInfoDiv = document.getElementById("license-info");
  const licenseStatusSpan = licenseInfoDiv.querySelector(".license-status");
  const licenseExpirySpan = licenseInfoDiv.querySelector(".license-expiry");
  const licenseSpinner = licenseInfoDiv.querySelector(".license-spinner");
  const dropzone = document.getElementById("dropzone");
  const dropzoneText = document.getElementById("dropzone-text");
  const fileSelectBtn = document.getElementById("file-select-btn");
  const fileInput = document.getElementById("file-input");
  const submitCourseBtn = document.getElementById("submit-course-btn");
  const statusMessage = document.getElementById("status-message");
  const decryptedOutput = document.getElementById("decrypted-output");
  const decryptedContentArea = document.getElementById(
    "decrypted-content-area"
  );

  // UNSW 选课区域
  const unswCourseCodeInput = document.getElementById("unsw-courseCode");
  //const unswCourseIdInput = document.getElementById("unsw-courseId");
  const unswTermAliasInput = document.getElementById("unsw-termAlias");
  const unswEnrollBtn = document.getElementById("unsw-enrollBtn");
  //const unswAddCourseBtn = document.getElementById("unsw-addCourseBtn");
  const unswStatusEl = document.getElementById("unsw-status");
  const unswCourseListEl = document.getElementById("unsw-courseList");
  const unswPageWarning = document.getElementById("unsw-pageWarning");

  // --- 状态变量 ---
  let selectedFile = null;
  let verifiedLicenseData = null; // 存储已验证的许可证信息

  // ============================================
  // --- 核心逻辑 ---
  // ============================================

  // 在脚本加载时立即初始化标签页
  // (函数定义在 popup-utils.js)
  initializeTabs();

  /** 1. 检查初始状态 */
  async function checkInitialState() {
    try {
      const result = await chrome.storage.local.get(["licenseKey", "userKey"]);
      if (result.licenseKey && result.userKey) {
        navigateTo("main");
        await validateAndDisplayLicense(result.licenseKey);
      } else {
        navigateTo("login");
      }
    } catch (error) {
      console.error("初始状态检查失败:", error);
      navigateTo("login");
    }
  }

  checkInitialState();

  // 加载并显示 courseMap（UNSW）
  async function loadCourseMap() {
    try {
      const result = await chrome.storage.local.get(["courseMap"]);
      if (result.courseMap) {
        courseMap = result.courseMap;
      }
    } catch (e) {
      console.warn("读取 courseMap 失败，使用默认映射", e);
    } finally {
      //displayCourseList();
    }
  }
  loadCourseMap();

  // 定义在 window 上，以便 delBtn 的监听器可以调用
  window.removeCourse = function (code) {
    delete courseMap[code];
    chrome.storage.local.set({ courseMap });
    //displayCourseList();
    unswShowStatus(`已删除: ${code}`, "success");
  };

  /** 2. 验证并显示许可证信息 (主视图用) */
  async function validateAndDisplayLicense(licenseKey) {
    showLicenseLoading(
      true,
      licenseInfoDiv,
      licenseStatusSpan,
      licenseExpirySpan,
      licenseSpinner
    );
    try {
      const response = await fetch(`${API_BASE}/accounts/license/validate/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ license_key: licenseKey }),
      });

      const data = await response.json();

      if (response.ok && data.valid) {
        displayLicenseInfo(
          data,
          licenseInfoDiv,
          licenseStatusSpan,
          licenseExpirySpan,
          licenseSpinner
        );
      } else {
        displayLicenseInfo(
          {
            license_active: false,
            expired: true,
            license_expires_at: null,
          },
          licenseInfoDiv,
          licenseStatusSpan,
          licenseExpirySpan,
          licenseSpinner
        );
        showStatus(`许可证验证失败: ${data.error || "未知错误"}`, "error");
      }
    } catch (error) {
      console.error("验证许可证失败:", error);
      showStatus("无法连接到服务器，请检查网络连接", "error");
      licenseInfoDiv.style.display = "none";
    } finally {
      showLicenseLoading(
        false,
        licenseInfoDiv,
        licenseStatusSpan,
        licenseExpirySpan,
        licenseSpinner
      );
    }
  }

  /** 3. 第一步：验证 License Key */
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
      const response = await fetch(`${API_BASE}/accounts/license/validate/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ license_key: licenseKey }),
      });

      const data = await response.json();

      if (!response.ok || !data.valid) {
        showLicenseError(data.error || "许可证无效或已过期");
        showLoading(verifyLicenseBtn, false);
        return;
      }

      if (!data.license_active) {
        showLicenseError("许可证未激活，请先激活您的许可证");
        showLoading(verifyLicenseBtn, false);
        return;
      }

      if (data.expired) {
        showLicenseError("许可证已过期，请续费后再使用");
        showLoading(verifyLicenseBtn, false);
        return;
      }

      verifiedLicenseData = { ...data, license_key: licenseKey };
      displayVerifiedLicenseInfo(
        data,
        verifiedLicenseStatus,
        verifiedLicenseExpiry
      );
      navigateTo("userkey");
    } catch (error) {
      console.error("验证失败:", error);
      showLicenseError("无法连接到服务器，请检查网络连接");
    } finally {
      showLoading(verifyLicenseBtn, false);
    }
  });

  /** 4. 第二步：输入 User Key */
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

      console.log("密钥已保存");

      navigateTo("main");
      displayLicenseInfo(
        verifiedLicenseData,
        licenseInfoDiv,
        licenseStatusSpan,
        licenseExpirySpan,
        licenseSpinner
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

  /** 5. 返回重新输入许可证 */
  backToLicenseBtn.addEventListener("click", () => {
    navigateTo("login");
    userkeyError.style.display = "none";
    userKeyInput.value = "";
    verifiedLicenseData = null;
  });

  /** 6. 处理创建许可证链接 */
  createLicenseLink.addEventListener("click", (e) => {
    e.preventDefault();
    alert("创建新许可证的功能尚未实现");
  });

  /** 7. 处理登出 */
  function logoutAndGoToLogin() {
    chrome.storage.local.remove(["licenseKey", "userKey"], () => {
      navigateTo("login");
      licenseKeyInput.value = "";
      userKeyInput.value = "";
      handleFile(null);
      hideStatus();
      licenseError.style.display = "none";
      userkeyError.style.display = "none";
      licenseInfoDiv.style.display = "none";
      decryptedOutput.style.display = "none";
      verifiedLicenseData = null;
    });
  }
  logoutBtn.addEventListener("click", logoutAndGoToLogin);

  /** 8. 处理文件选择 */
  fileSelectBtn.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", (e) => {
    if (e.target?.files?.[0]) handleFile(e.target.files[0]);
  });
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
    if (e.dataTransfer?.files?.[0]) handleFile(e.dataTransfer.files[0]);
  });

  function handleFile(file) {
    if (file) {
      selectedFile = file;
      dropzoneText.textContent = `已选择: ${file.name}`;
      submitCourseBtn.disabled = false;
      hideStatus();
      decryptedOutput.style.display = "none";
    } else {
      selectedFile = null;
      dropzoneText.textContent = "拖拽加密文件到这里, 或";
      submitCourseBtn.disabled = true;
      fileInput.value = "";
      hideStatus();
      decryptedOutput.style.display = "none";
    }
  }

  /** 9. 处理文件解密提交 */
  submitCourseBtn.addEventListener("click", async () => {
    if (!selectedFile) return;

    showLoading(submitCourseBtn, true);
    hideStatus();
    decryptedOutput.style.display = "none";

    try {
      showStatus("正在读取密钥信息...", "info");
      const storageResult = await chrome.storage.local.get([
        "licenseKey",
        "userKey",
      ]);
      const licenseKey = storageResult.licenseKey;
      const userKeyB64 = storageResult.userKey;

      if (!licenseKey || !userKeyB64) {
        throw new Error("无法获取密钥信息，请重新登录插件");
      }

      showStatus("正在读取加密文件...", "info");
      const fileContent = await readFileAsText(selectedFile); // from popup-utils.js
      let encryptedFileContent;
      try {
        encryptedFileContent = JSON.parse(fileContent);
      } catch (e) {
        throw new Error("加密文件格式无效 (非 JSON)");
      }

      if (!encryptedFileContent?.nonce || !encryptedFileContent?.ciphertext) {
        throw new Error("加密文件内容格式无效 (缺少必要字段)");
      }

      showStatus("正在从服务器获取文件密钥...", "info");
      const response = await fetch(`${API_BASE}/accounts/license/file-key/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          encrypted_file: encryptedFileContent,
          license_key: licenseKey,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || `服务器错误 (${response.status})`);
      }

      const responseData = await response.json();
      const wrappedFileKey = responseData.wrapped_file_key;

      if (!wrappedFileKey) {
        throw new Error("服务器返回的数据中缺少 wrapped_file_key");
      }

      showStatus("正在解密文件密钥...", "info");
      const fileKeyBytes = await unwrapFileKey(wrappedFileKey, userKeyB64); // from popup-utils.js

      showStatus("正在解密文件内容...", "info");
      const decryptedData = await decryptFileContent(
        // from popup-utils.js
        encryptedFileContent,
        fileKeyBytes
      );

      showStatus("解密成功！", "success");
      console.log("解密后的数据:", decryptedData);

      decryptedContentArea.textContent = JSON.stringify(decryptedData, null, 2);
      decryptedOutput.style.display = "block";
    } catch (error) {
      console.error("解密流程失败:", error);
      showStatus(`错误: ${error.message}`, "error");
      decryptedOutput.style.display = "none";
    } finally {
      showLoading(submitCourseBtn, false);
    }
  });

  // --- UNSW: 添加课程映射 与 开始选课的逻辑 ---

  unswEnrollBtn.addEventListener("click", async () => {
    const courseCode = (unswCourseCodeInput.value || "").trim();
    const termAlias = (unswTermAliasInput.value || "").trim(); // 例如: T1, T2, T3

    if (!courseCode) {
      unswShowStatus("请输入课程代码", "error");
      return;
    }

    if (!termAlias) {
      unswShowStatus("请输入学期 (例如: T1, T2, T3)", "error");
      return;
    }

    unswShowStatus("正在从服务器获取课程 ID...", "info");
    unswEnrollBtn.disabled = true;

    try {
      // 获取已保存的 userKey 或 token（如果需要认证）
      const storage = await chrome.storage.local.get([
        "userKey",
        "licenseKey",
        "authToken",
      ]);
      const headers = { "Content-Type": "application/json" };
      if (storage.authToken)
        headers["Authorization"] = "Bearer " + storage.authToken;

      // 调用后端 API
      const url = `${API_BASE}/accounts/get_course/?keys=${encodeURIComponent(
        courseCode
      )}&term=${encodeURIComponent(termAlias)}`;
      const resp = await fetch(url, { method: "GET", headers });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.error || `服务器返回 ${resp.status}`);
      }

      const respJson = await resp.json();
      if (!respJson.success) {
        throw new Error(respJson.error || "后端返回失败");
      }

      const data = respJson.data || {};
      const entries = data[courseCode] || [];

      if (!entries || entries.length === 0) {
        unswShowStatus(
          `未找到课程 ${courseCode} 在 ${termAlias} 的对应 ID`,
          "error"
        );
        return;
      }

      // 解析成 [courseCode, courseId, termAlias] 的数组，允许多个条目
      const courseList = entries.map((item) => {
        const courseId = item.course_id || item.courseId || item.id;
        const term = item.term || termAlias; // 如果后端没有 term 字段，就用输入的 termAlias
        return [courseCode, courseId, term];
      });

      // 调试用
      console.log("解析后的课程列表:", courseList);

      // 检查当前活动 tab（UNSW 页面）
      const [tab] = await chrome.tabs.query({
        active: true,
        currentWindow: true,
      });
      if (!tab || !tab.url || !tab.url.includes("my.unsw.edu.au")) {
        unswShowStatus("请先打开 UNSW 选课页面", "error");
        if (unswPageWarning) unswPageWarning.style.display = "block";
        return;
      }
      if (unswPageWarning) unswPageWarning.style.display = "none";

      // 直接把整个课程列表传给 startEnrollment
      await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: startEnrollment,
        args: [courseList], // 注意这里是数组，里面包含多个 [courseCode, courseId, termAlias]
      });

      unswShowStatus("选课请求已发送，请查看页面结果", "success");
    } catch (error) {
      console.error("选课流程失败:", error);
      unswShowStatus("执行失败: " + (error.message || error), "error");
    } finally {
      unswEnrollBtn.disabled = false;
    }
  });

  // 避免 page 警告默认隐藏/显示逻辑初始化
  if (unswPageWarning) unswPageWarning.style.display = "none";
});
