// popup.js
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

  // 主视图
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

  let selectedFile = null;
  let verifiedLicenseData = null; // 存储已验证的许可证信息

  // --- 加密/解密辅助函数 ---

  /** Base64 字符串转 Uint8Array */
  function base64ToUint8Array(base64) {
    const cleaned = base64.replace(/-/g, "+").replace(/_/g, "/");
    const pad =
      cleaned.length % 4 === 0 ? "" : "=".repeat(4 - (cleaned.length % 4));
    const b64 = cleaned + pad;
    const binaryString = atob(b64);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }
    return bytes;
  }

  /** Uint8Array 转 UTF-8 字符串 */
  function uint8ArrayToString(bytes) {
    return new TextDecoder().decode(bytes);
  }

  /** 拼接两个 Uint8Array */
  function concat(a, b) {
    const out = new Uint8Array(a.length + b.length);
    out.set(a, 0);
    out.set(b, a.length);
    return out;
  }

  /**
   * AES-GCM 解密
   * @param {Uint8Array} keyBytes - 密钥字节
   * @param {Uint8Array} iv - 初始向量 (nonce)
   * @param {Uint8Array} data - 密文+标签
   */
  async function aesGcmDecrypt(keyBytes, iv, data) {
    const algo = { name: "AES-GCM", iv, tagLength: 128 };
    const cryptoKey = await crypto.subtle.importKey(
      "raw",
      keyBytes,
      { name: "AES-GCM" },
      false,
      ["decrypt"]
    );
    const decrypted = await crypto.subtle.decrypt(algo, cryptoKey, data);
    return new Uint8Array(decrypted);
  }

  /**
   * 解包 file_key：用 user_key 解密 wrapped_file_key
   */
  async function unwrapFileKey(wrappedFileKey, userKeyB64) {
    const userKeyBytes = base64ToUint8Array(userKeyB64);
    const nonce = base64ToUint8Array(wrappedFileKey.nonce);
    const tag = base64ToUint8Array(wrappedFileKey.tag);
    const ciphertext = base64ToUint8Array(wrappedFileKey.ciphertext);

    const fileKeyBytes = await aesGcmDecrypt(
      userKeyBytes,
      nonce,
      concat(ciphertext, tag)
    );
    return fileKeyBytes;
  }

  /**
   * 解密文件内容：用 file_key 解密
   */
  async function decryptFileContent(encryptedFileContent, fileKeyBytes) {
    const nonce = base64ToUint8Array(encryptedFileContent.nonce);
    const tag = base64ToUint8Array(encryptedFileContent.tag);
    const ciphertext = base64ToUint8Array(encryptedFileContent.ciphertext);

    const decryptedBytes = await aesGcmDecrypt(
      fileKeyBytes,
      nonce,
      concat(ciphertext, tag)
    );
    const decryptedText = uint8ArrayToString(decryptedBytes);
    return JSON.parse(decryptedText);
  }

  // --- UI 辅助函数 ---

  function navigateTo(viewName) {
    appContainer.setAttribute("data-view", viewName);
  }

  function showLoading(button, isLoading) {
    const btnText = button.querySelector(".btn-text");
    const spinner = button.querySelector(".spinner");
    if (isLoading) {
      btnText.style.display = "none";
      spinner.style.display = "block";
      button.disabled = true;
    } else {
      btnText.style.display = "block";
      spinner.style.display = "none";
      button.disabled = false;
    }
  }

  function showLicenseError(message) {
    licenseError.textContent = message;
    licenseError.style.display = "block";
  }

  function showUserkeyError(message) {
    userkeyError.textContent = message;
    userkeyError.style.display = "block";
  }

  function showStatus(message, type = "info") {
    statusMessage.textContent = message;
    statusMessage.className = `status-message ${type}`;
    statusMessage.style.display = "block";
  }

  function hideStatus() {
    statusMessage.style.display = "none";
  }

  function displayLicenseInfo(details) {
    if (details) {
      const isActive = details.license_active && !details.expired;
      licenseStatusSpan.textContent = isActive ? "许可证有效" : "许可证无效";

      const isDarkMode =
        window.matchMedia &&
        window.matchMedia("(prefers-color-scheme: dark)").matches;

      if (isActive) {
        licenseStatusSpan.style.color = isDarkMode ? "#86efac" : "#16a34a";
      } else {
        licenseStatusSpan.style.color = isDarkMode ? "#fca5a5" : "#dc2626";
      }

      let expiryText = "永久";
      if (details.license_expires_at) {
        try {
          expiryText = new Date(
            details.license_expires_at
          ).toLocaleDateString();
        } catch (e) {
          expiryText = "未知日期";
        }
      }
      licenseExpirySpan.textContent = expiryText;
      licenseInfoDiv.style.display = "flex";
      licenseSpinner.style.display = "none";
    } else {
      licenseInfoDiv.style.display = "none";
    }
  }

  function showLicenseLoading(isLoading) {
    if (isLoading) {
      licenseInfoDiv.style.display = "flex";
      licenseStatusSpan.textContent = "正在验证...";
      licenseExpirySpan.textContent = "...";
      licenseSpinner.style.display = "block";
    } else {
      licenseSpinner.style.display = "none";
    }
  }

  function displayVerifiedLicenseInfo(details) {
    const isActive = details.license_active && !details.expired;
    verifiedLicenseStatus.textContent = isActive ? "✓ 有效" : "✗ 无效";
    verifiedLicenseStatus.style.color = isActive ? "#16a34a" : "#dc2626";

    let expiryText = "永久";
    if (details.license_expires_at) {
      try {
        expiryText = new Date(details.license_expires_at).toLocaleDateString();
      } catch (e) {
        expiryText = "未知日期";
      }
    }
    verifiedLicenseExpiry.textContent = expiryText;
  }

  // --- 核心逻辑 ---

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

  /** 2. 验证并显示许可证信息 (主视图用) */
  async function validateAndDisplayLicense(licenseKey) {
    showLicenseLoading(true);
    try {
      const response = await fetch(`${API_BASE}/accounts/license/validate/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ license_key: licenseKey }),
      });

      const data = await response.json();

      if (response.ok && data.valid) {
        displayLicenseInfo(data);
      } else {
        displayLicenseInfo({
          license_active: false,
          expired: true,
          license_expires_at: null,
        });
        showStatus(`许可证验证失败: ${data.error || "未知错误"}`, "error");
      }
    } catch (error) {
      console.error("验证许可证失败:", error);
      showStatus("无法连接到服务器，请检查网络连接", "error");
      licenseInfoDiv.style.display = "none";
    } finally {
      showLicenseLoading(false);
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
      // 验证 license
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

      // 检查许可证是否激活
      if (!data.license_active) {
        showLicenseError("许可证未激活，请先激活您的许可证");
        showLoading(verifyLicenseBtn, false);
        return;
      }

      // 检查许可证是否过期
      if (data.expired) {
        showLicenseError("许可证已过期，请续费后再使用");
        showLoading(verifyLicenseBtn, false);
        return;
      }

      // 验证成功，保存数据并进入第二步
      verifiedLicenseData = { ...data, license_key: licenseKey };
      displayVerifiedLicenseInfo(data);
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
      // 保存密钥到本地
      await chrome.storage.local.set({
        licenseKey: verifiedLicenseData.license_key,
        userKey,
      });

      console.log("密钥已保存");

      // 进入主视图
      navigateTo("main");
      displayLicenseInfo(verifiedLicenseData);

      // 清空输入
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
      // Step 1: 获取存储的密钥
      showStatus("正在读取密钥信息...", "info");
      const { licenseKey, userKey: userKeyB64 } =
        await chrome.storage.local.get(["licenseKey", "userKey"]);

      if (!licenseKey || !userKeyB64) {
        throw new Error("无法获取密钥信息，请重新登录插件");
      }

      // Step 2: 读取加密文件
      showStatus("正在读取加密文件...", "info");
      const fileContent = await readFileAsText(selectedFile);
      let encryptedFileContent;
      try {
        encryptedFileContent = JSON.parse(fileContent);
      } catch (e) {
        throw new Error("加密文件格式无效 (非 JSON)");
      }

      if (!encryptedFileContent?.nonce || !encryptedFileContent?.ciphertext) {
        throw new Error("加密文件内容格式无效 (缺少必要字段)");
      }

      // Step 3: 调用后端获取 wrapped_file_key
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

      // Step 4: 用 user_key 解密得到 file_key
      showStatus("正在解密文件密钥...", "info");
      const fileKeyBytes = await unwrapFileKey(wrappedFileKey, userKeyB64);

      // Step 5: 用 file_key 解密文件内容
      showStatus("正在解密文件内容...", "info");
      const decryptedData = await decryptFileContent(
        encryptedFileContent,
        fileKeyBytes
      );

      // Step 6: 显示解密结果
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

  // --- 辅助函数 ---

  /** 读取文件为文本 */
  function readFileAsText(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (event) => resolve(event.target.result);
      reader.onerror = (error) => reject(error);
      reader.readAsText(file);
    });
  }
}); // End DOMContentLoaded
