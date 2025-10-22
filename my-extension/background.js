// ============================================
// 文件: background.js (合并版 - v2)
// 职责: 管理插件窗口的打开和聚焦
// ============================================

// 用于存储我们打开的 popup 窗口的 ID
let popupWindowId = null;

// 监听扩展图标的点击事件
// (这只会在 manifest.json 中没有 "default_popup" 时触发)
chrome.action.onClicked.addListener((tab) => {
  // 检查窗口是否还存在
  if (popupWindowId !== null) {
    chrome.windows.get(popupWindowId, {}, (existingWindow) => {
      if (chrome.runtime.lastError) {
        // 错误：窗口已被用户关闭
        console.log("窗口未找到，创建新窗口。");
        createNewWindow();
      } else {
        // 窗口存在，将其聚焦
        console.log("窗口已存在，正在聚焦。");
        chrome.windows.update(popupWindowId, { focused: true });
      }
    });
  } else {
    // 之前没有打开过窗口
    console.log("首次创建窗口。");
    createNewWindow();
  }
});

// 封装创建新窗口的函数
function createNewWindow() {
  chrome.windows.create(
    {
      url: "popup.html", // 你的 HTML 文件
      type: "popup", // 窗口类型
      width: 380, // 宽度
      height: 580, // 高度
      focused: true,
    },
    (window) => {
      // 存储新窗口的 ID
      popupWindowId = window.id;
    }
  );
}

// (可选) 监听窗口关闭事件，以便重置 ID
chrome.windows.onRemoved.addListener((windowId) => {
  if (windowId === popupWindowId) {
    console.log("窗口已关闭，重置 ID。");
    popupWindowId = null;
  }
});
