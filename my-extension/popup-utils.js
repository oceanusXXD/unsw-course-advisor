// popup-utils.js (完整版 - 工具函数)

// ============================================
// --- 加密/解密辅助函数 ---
// ============================================

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

function uint8ArrayToString(bytes) {
  return new TextDecoder().decode(bytes);
}

function concat(a, b) {
  const out = new Uint8Array(a.length + b.length);
  out.set(a, 0);
  out.set(b, a.length);
  return out;
}

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

// ============================================
// --- UI 辅助函数 ---
// ============================================

function navigateTo(viewName) {
  const appContainer = document.getElementById("app-container");
  if (appContainer) appContainer.setAttribute("data-view", viewName);
}

function showLoading(button, isLoading) {
  const btnText = button.querySelector(".btn-text");
  const spinner = button.querySelector(".spinner");
  if (isLoading) {
    if (btnText) btnText.style.display = "none";
    if (spinner) spinner.style.display = "inline-block";
    button.disabled = true;
  } else {
    if (btnText) btnText.style.display = "inline-block";
    if (spinner) spinner.style.display = "none";
    button.disabled = false;
  }
}

function showLicenseError(message) {
  const licenseError = document.getElementById("license-error");
  if (licenseError) {
    licenseError.textContent = message;
    licenseError.style.display = "block";
  }
}

function showUserkeyError(message) {
  const userkeyError = document.getElementById("userkey-error");
  if (userkeyError) {
    userkeyError.textContent = message;
    userkeyError.style.display = "block";
  }
}

function showStatus(message, type = "info") {
  const statusMessage = document.getElementById("status-message");
  if (!statusMessage) return;
  statusMessage.textContent = message;
  statusMessage.className = `status-message ${type}`;
  statusMessage.style.display = "block";
}

function hideStatus() {
  const statusMessage = document.getElementById("status-message");
  if (statusMessage) statusMessage.style.display = "none";
}

function displayLicenseInfo(
  details,
  licenseInfoDiv,
  licenseStatusSpan,
  licenseExpirySpan,
  licenseSpinner
) {
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
        expiryText = new Date(details.license_expires_at).toLocaleDateString();
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

function showLicenseLoading(
  isLoading,
  licenseInfoDiv,
  licenseStatusSpan,
  licenseExpirySpan,
  licenseSpinner
) {
  if (isLoading) {
    licenseInfoDiv.style.display = "flex";
    licenseStatusSpan.textContent = "正在验证...";
    licenseExpirySpan.textContent = "...";
    licenseSpinner.style.display = "inline-block";
  } else {
    licenseSpinner.style.display = "none";
  }
}

function displayVerifiedLicenseInfo(
  details,
  verifiedLicenseStatus,
  verifiedLicenseExpiry
) {
  const isActive = details.license_active && !details.expired;
  verifiedLicenseStatus.textContent = isActive ? "[OK] 有效" : "[X] 无效";
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

// ============================================
// --- UNSW 辅助函数 ---
// ============================================

function unswShowStatus(message, type) {
  const unswStatusEl = document.getElementById("unsw-status");
  if (!unswStatusEl) return;
  unswStatusEl.textContent = message;
  unswStatusEl.className = `status-message ${type || ""}`;
  unswStatusEl.style.display = "block";
  if (type === "success") {
    setTimeout(() => {
      if (unswStatusEl) unswStatusEl.style.display = "none";
    }, 5000);
  }
}

// ============================================
// --- 标签页切换逻辑 ---
// ============================================

function initializeTabs() {
  const tabButtons = document.querySelectorAll(".tab-btn");
  const tabContents = document.querySelectorAll(".tab-content");

  if (!tabButtons.length || !tabContents.length) {
    return;
  }

  tabButtons.forEach((button) => {
    button.addEventListener("click", () => {
      // 移除所有激活状态
      tabButtons.forEach((btn) => btn.classList.remove("active"));
      tabContents.forEach((content) => content.classList.remove("active"));

      // 激活当前标签
      button.classList.add("active");
      const tabId = button.dataset.tab;
      const activeTabContent = document.getElementById(tabId);
      if (activeTabContent) {
        activeTabContent.classList.add("active");
      }
    });
  });
}

// ============================================
// --- 文件读取辅助 ---
// ============================================

function readFileAsText(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (event) => resolve(event.target.result);
    reader.onerror = (error) => reject(error);
    reader.readAsText(file);
  });
}
