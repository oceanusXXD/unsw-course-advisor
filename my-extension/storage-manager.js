// storage-manager.js - 统一的入参/配置管理（Promise 封装）
export async function saveEncryptedPackage(text) {
    return new Promise((res) => chrome.storage.local.set({ encryptedPackage: text }, res));
}
export async function getEncryptedPackage() {
    return new Promise((res) => chrome.storage.local.get(['encryptedPackage'], r => res(r.encryptedPackage)));
}

export async function saveDecryptedParams(obj) {
    return new Promise((res) => chrome.storage.local.set({ decryptedParams: obj }, res));
}
export async function getDecryptedParams() {
    return new Promise((res) => chrome.storage.local.get(['decryptedParams'], r => res(r.decryptedParams)));
}
export async function clearDecryptedParams() {
    return new Promise((res) => chrome.storage.local.remove(['decryptedParams'], res));
}

export async function setInjectOnLoad(v) {
    return new Promise((res) => chrome.storage.local.set({ injectOnLoad: !!v }, res));
}
export async function getInjectOnLoad() {
    return new Promise((res) => chrome.storage.local.get(['injectOnLoad'], r => res(!!r.injectOnLoad)));
}

export async function saveLastSelectedUrls(urls) {
    return new Promise((res) => chrome.storage.local.set({ lastSelectedUrls: urls }, res));
}
export async function getLastSelectedUrls() {
    return new Promise((res) => chrome.storage.local.get(['lastSelectedUrls'], r => res(r.lastSelectedUrls || [])));
}

export async function appendLog(entry) {
    return new Promise((res) => {
        chrome.storage.local.get({ logs: [] }, (r) => {
            const logs = r.logs || [];
            logs.unshift(entry);
            chrome.storage.local.set({ logs }, res);
        });
    });
}
export async function getLogs() {
    return new Promise((res) => chrome.storage.local.get(['logs'], r => res(r.logs || [])));
}
