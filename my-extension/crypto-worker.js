// crypto-worker.js - 可被 popup 作为 Worker 使用（示例，未被 popup 自动使用）
self.addEventListener('message', async (ev) => {
    const { action, data } = ev.data || {};
    if (action === 'decrypt') {
        try {
            // 这里示例采用页面端 crypto 实现，实际可重复 crypto.js 的逻辑
            const { ciphertextJsonText, passphrase } = data;
            // 直接 post 回（示例）
            self.postMessage({ ok: true, result: 'worker not implemented fully' });
        } catch (e) {
            self.postMessage({ ok: false, err: e.message });
        }
    }
});
