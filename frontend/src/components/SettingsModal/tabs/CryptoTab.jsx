// src/components/SettingsModal/tabs/CryptoTab.jsx
import React, { useState } from 'react';
import { Lock, Loader, Download, Check } from 'lucide-react';
import { decryptLicensedFile } from '../../../services/api';
import styles from '../styles/SettingsModal.module.scss';

export default function CryptoTab({ showMessage }) {
  const [loading, setLoading] = useState(false);
  const [encryptedJson, setEncryptedJson] = useState('');
  const [licenseKey, setLicenseKey] = useState('');
  const [userKeyB64, setUserKeyB64] = useState('');
  const [decryptResult, setDecryptResult] = useState('');

  const handleDecrypt = async () => {
    if (!encryptedJson.trim() || !licenseKey.trim() || !userKeyB64.trim()) {
      showMessage('error', '请填写完整信息');
      return;
    }
    setLoading(true);
    try {
      const payload = JSON.parse(encryptedJson);
      const data = await decryptLicensedFile(payload, licenseKey, userKeyB64);
      setDecryptResult(JSON.stringify(data, null, 2));
      showMessage('success', '解密成功');
    } catch (e) {
      showMessage('error', e?.message || '解密失败，请检查格式');
      setDecryptResult('');
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className={styles.section}>
      <h3 className={styles.sectionTitle}>
        <Lock size={20} />
        文件加解密工具
      </h3>

      <div className={styles.inputGroup}>
        <label>加密文件 JSON</label>
        <textarea
          rows={6}
          placeholder='粘贴加密文件 JSON，例如 {"nonce":"...","tag":"...","ciphertext":"..."}'
          value={encryptedJson}
          onChange={(e) => setEncryptedJson(e.target.value)}
          className={styles.textarea}
        />
      </div>

      <div className={styles.inputGroup}>
        <label>许可证密钥</label>
        <input
          type="text"
          placeholder="输入许可证密钥..."
          value={licenseKey}
          onChange={(e) => setLicenseKey(e.target.value)}
          className={styles.input}
        />
      </div>

      <div className={styles.inputGroup}>
        <label>User Key (Base64)</label>
        <input
          type="text"
          placeholder="输入用户密钥..."
          value={userKeyB64}
          onChange={(e) => setUserKeyB64(e.target.value)}
          className={styles.input}
        />
      </div>

      <button className="btn primary" onClick={handleDecrypt} disabled={loading}>
        {loading ? <Loader size={16} className="spin" /> : <Download size={16} />}
        {loading ? '解密中...' : '解密'}
      </button>

      {decryptResult && (
        <div className={styles.codeBlock}>
          <div className={styles.codeHeader}>
            <Check size={14} />
            <span>解密结果</span>
          </div>
          <pre>{decryptResult}</pre>
        </div>
      )}
    </section>
  );
}
