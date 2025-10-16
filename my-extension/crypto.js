// crypto.js - 插件端解密占位实现
// 支持三种占位格式：PLAIN（直接明文）、PLAINBASE64（ciphertext 为 base64(plaintext)）、
// 以及 AES-GCM + PBKDF2（示例实现，需后端严格配合参数）

function base64ToArrayBuffer(b64) {
    const binary = atob(b64);
    const len = binary.length;
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i++) bytes[i] = binary.charCodeAt(i);
    return bytes.buffer;
}
function arrayBufferToString(buf) {
    return new TextDecoder().decode(new Uint8Array(buf));
}

export async function decryptPackage(encryptedJsonText, options = {}) {
    // encryptedJsonText: string (the content of encrypted package file)
    // options: if using passphrase: { method: 'passphrase', passphrase: '...' }
    const pkg = JSON.parse(encryptedJsonText);

    if (!pkg.cipher) throw new Error('缺少 cipher 字段');
    const cipher = pkg.cipher;

    if (cipher === 'PLAIN') {
        // 测试占位：直接从 plaintext 字段读取（仅用于本地调试）
        if (!pkg.plaintext) throw new Error('PLAIN 模式需要 plaintext 字段');
        if (typeof pkg.plaintext === 'object') return pkg.plaintext;
        try { return JSON.parse(pkg.plaintext); } catch (e) { return pkg.plaintext; }
    }

    if (cipher === 'PLAINBASE64') {
        if (!pkg.ciphertext) throw new Error('PLAINBASE64 模式需要 ciphertext 字段（base64）');
        const txt = arrayBufferToString(base64ToArrayBuffer(pkg.ciphertext));
        try { return JSON.parse(txt); } catch (e) { return txt; }
    }

    if (cipher === 'AES-GCM' && pkg.kdf === 'PBKDF2') {
        if (!options || options.method !== 'passphrase' || !options.passphrase) {
            throw new Error('AES-GCM+PBKDF2 需要传入 passphrase（options.method="passphrase"）以派生 key');
        }
        if (!pkg.kdf_params || !pkg.kdf_params.salt) throw new Error('缺少 kdf_params.salt');
        const salt = base64ToArrayBuffer(pkg.kdf_params.salt);
        const iterations = pkg.kdf_params.iterations || 150000;
        const hash = pkg.kdf_params.hash || 'SHA-256';

        const enc = new TextEncoder();
        const passKey = await crypto.subtle.importKey('raw', enc.encode(options.passphrase), { name: 'PBKDF2' }, false, ['deriveKey']);
        const derivedKey = await crypto.subtle.deriveKey({
            name: 'PBKDF2',
            salt,
            iterations,
            hash
        }, passKey, { name: 'AES-GCM', length: 256 }, true, ['decrypt']);

        const iv = base64ToArrayBuffer(pkg.iv);
        const ct = base64ToArrayBuffer(pkg.ciphertext);

        const plainBuf = await crypto.subtle.decrypt({ name: 'AES-GCM', iv }, derivedKey, ct);
        const plainText = arrayBufferToString(plainBuf);
        return JSON.parse(plainText);
    }

    throw new Error('不支持的 cipher/kdf 类型（当前仅支持 PLAIN, PLAINBASE64, AES-GCM+PBKDF2 占位）');
}
