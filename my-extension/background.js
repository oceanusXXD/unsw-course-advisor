// background.js

// -------------------- 存储扩展 ID --------------------
chrome.runtime.onInstalled.addListener(() => {
    chrome.storage.local.set({ extensionId: chrome.runtime.id });
});

chrome.runtime.onStartup.addListener(() => {
    chrome.storage.local.set({ extensionId: chrome.runtime.id });
});

// -------------------- 处理来自 content 的消息 --------------------
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg === "get-extension-id") {
        sendResponse(chrome.runtime.id);
        return true; // 异步响应
    }

    // 原 api-runner-content 逻辑
    if (msg?.from === 'api-runner-content') {
        if (msg.ready) {
            console.log('[background] injector ready for', msg.pageUrl);
        } else if (msg.results) {
            console.log('[background] got api results', msg.results);
            chrome.runtime.sendMessage({ from: 'api-results', results: msg.results, page: msg.pageUrl });
            chrome.storage.local.get({ logs: [] }, (res) => {
                const logs = res.logs || [];
                logs.unshift({ time: Date.now(), page: msg.pageUrl, results: msg.results });
                chrome.storage.local.set({ logs });
            });
        }
    }
});


// -------------------- Tab 更新完成时自动注入 --------------------
chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
    if (changeInfo.status === 'complete') {
        const { injectOnLoad, lastSelectedUrls } = await new Promise(resolve =>
            chrome.storage.local.get(['injectOnLoad', 'lastSelectedUrls'], resolve)
        );
        if (injectOnLoad && Array.isArray(lastSelectedUrls) && lastSelectedUrls.length) {
            try {
                await chrome.scripting.executeScript({ target: { tabId }, files: ['content-script.js'] });
                chrome.tabs.sendMessage(tabId, { action: 'runApis', urls: lastSelectedUrls });
            } catch (e) {
                console.warn('[background] 自动注入或执行失败', e);
            }
        }
    }
});
