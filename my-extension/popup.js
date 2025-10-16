// popup.js (type=module)
import * as Storage from './storage-manager.js';
import { decryptPackage } from './crypto.js';

const apiListEl = document.getElementById('apiList');
const runBtn = document.getElementById('runBtn');
const logArea = document.getElementById('logArea');
const decryptBtn = document.getElementById('decryptBtn');
const encryptedInput = document.getElementById('encryptedInput');
const passphraseInput = document.getElementById('passphrase');
const importTemplateBtn = document.getElementById('importTemplateBtn');
const clearEncryptedBtn = document.getElementById('clearEncryptedBtn');
const wipeBtn = document.getElementById('wipeBtn');
const downloadParamsBtn = document.getElementById('downloadParamsBtn');
const clearLogsBtn = document.getElementById('clearLogsBtn');
const injectOnLoadEl = document.getElementById('injectOnLoad');

function log(msg) {
    const time = new Date().toLocaleTimeString();
    logArea.textContent = `${time} — ${msg}\n` + logArea.textContent;
}

async function loadApis() {
    const url = chrome.runtime.getURL('apis.json');
    const resp = await fetch(url);
    const apis = await resp.json();
    apiListEl.innerHTML = '';
    apis.forEach(api => {
        const el = document.createElement('label');
        el.innerHTML = `<input type="checkbox" data-id="${api.id}" data-url="${api.urlTemplate}" /> ${api.label} <small style="color:#666">(${api.urlTemplate})</small>`;
        apiListEl.appendChild(el);
    });
}

decryptBtn.addEventListener('click', async () => {
    const txt = encryptedInput.value.trim();
    if (!txt) { log('请先粘贴或导入加密包'); return; }
    const pass = passphraseInput.value || undefined;
    try {
        const decrypted = await decryptPackage(txt, pass ? { method: 'passphrase', passphrase: pass } : {});
        await Storage.saveDecryptedParams(decrypted);
        log('解密成功并已保存（仅本地）。显示部分： ' + JSON.stringify(decrypted).slice(0, 200));
    } catch (e) {
        console.error(e);
        log('解密失败：' + e.message);
    }
});

importTemplateBtn.addEventListener('click', async () => {
    try {
        const url = chrome.runtime.getURL('templates/encrypted_template.json');
        const r = await fetch(url);
        const js = await r.text();
        encryptedInput.value = js;
        log('已加载示例模板到输入区（用于本地调试）');
    } catch (e) {
        log('加载示例失败：' + e.message);
    }
});

clearEncryptedBtn.addEventListener('click', () => {
    encryptedInput.value = '';
    log('已清空加密包输入区');
});

runBtn.addEventListener('click', async () => {
    // collect selected urls
    const selected = Array.from(apiListEl.querySelectorAll('input[type=checkbox]')).filter(cb => cb.checked);
    if (selected.length === 0) { log('未选择任何 API'); return; }
    const urls = selected.map(cb => cb.dataset.url);

    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tabs || tabs.length === 0) { log('找不到活动标签页'); return; }
    const tab = tabs[0];

    // get decrypted params (optional)
    const params = await Storage.getDecryptedParams();
    // send to content script
    chrome.tabs.sendMessage(tab.id, { action: 'runApis', urls, params }, (resp) => {
        if (chrome.runtime.lastError) {
            log('向 content script 发送消息失败：' + chrome.runtime.lastError.message);
        } else {
            log('请求已发送到页面，等待回传...');
        }
    });
});

wipeBtn.addEventListener('click', async () => {
    await Storage.clearDecryptedParams();
    log('已清除已解密参数（本地）');
});

downloadParamsBtn.addEventListener('click', async () => {
    const params = await Storage.getDecryptedParams();
    if (!params) { log('无已解密参数可导出'); return; }
    const blob = new Blob([JSON.stringify(params, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'decrypted_params.json';
    a.click();
    URL.revokeObjectURL(url);
    log('已下载解密后的参数文件');
});

clearLogsBtn.addEventListener('click', () => { logArea.textContent = ''; });

injectOnLoadEl.addEventListener('change', () => {
    Storage.setInjectOnLoad(injectOnLoadEl.checked);
    log('injectOnLoad = ' + injectOnLoadEl.checked);
});

document.addEventListener('DOMContentLoaded', async () => {
    await loadApis();
    const s = await Storage.getInjectOnLoad();
    injectOnLoadEl.checked = s;
    // listen for results from background/content
    chrome.runtime.onMessage.addListener((msg, sender) => {
        if (msg?.from === 'api-results') {
            const r = msg.results || [];
            const out = `来自页面 ${msg.page || (sender.tab && sender.tab.url) || 'unknown'} 的结果:\n` +
                r.map(x => `${x.url} -> ${x.status} (${x.len || 0})`).join('\n');
            log(out);
        }
    });
});
