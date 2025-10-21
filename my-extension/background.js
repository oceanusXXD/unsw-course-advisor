// background.js

// 监听扩展图标的点击事件
chrome.action.onClicked.addListener((tab) => {
  chrome.windows.getAll(
    { populate: false, windowTypes: ["popup"] },
    (windows) => {
      const existingWindow = windows.find((win) => win.title === "课程助手");
      if (existingWindow) {
        // 如果窗口已存在，则聚焦它
        chrome.windows.update(existingWindow.id, { focused: true });
      } else {
        chrome.windows.create({
          url: "popup.html", // HTML 文件
          type: "popup", // 窗口类型
          width: 380, // 宽度
          height: 580, // 高度
          focused: true,
        });
      }
    }
  );
});
