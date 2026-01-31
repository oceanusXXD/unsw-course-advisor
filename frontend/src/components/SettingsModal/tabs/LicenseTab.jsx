// src/components/SettingsModal/tabs/LicenseTab.jsx
import React, { useState } from 'react';
import { Key, Loader, FileText } from 'lucide-react';
import { activateLicense, validateLicense, getMyLicense } from '../../../services/api';
import styles from '../styles/SettingsModal.module.scss';

export default function LicenseTab({ showMessage }) {
  const [loading, setLoading] = useState(false);
  const [licenseKey, setLicenseKey] = useState('');
  const [licenseInfo, setLicenseInfo] = useState(null);

  const handleActivate = async () => {
    setLoading(true);
    try {
      const data = await activateLicense();
      setLicenseInfo(data);
      showMessage('success', '许可证激活成功！');
    } catch (e) {
      showMessage('error', e?.message || '激活失败');
    } finally {
      setLoading(false);
    }
  };

  const handleValidate = async () => {
    if (!licenseKey.trim()) {
      showMessage('error', '请输入许可证密钥');
      return;
    }
    setLoading(true);
    try {
      const data = await validateLicense(licenseKey);
      setLicenseInfo(data);
      showMessage('success', '许可证校验成功！');
    } catch (e) {
      showMessage('error', e?.message || '校验失败');
    } finally {
      setLoading(false);
    }
  };

  const handleGetMy = async () => {
    setLoading(true);
    try {
      const data = await getMyLicense();
      setLicenseInfo(data);
      showMessage('success', '获取成功');
    } catch (e) {
      showMessage('error', e?.message || '获取失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className={styles.section}>
      <h3 className={styles.sectionTitle}>
        <Key size={20} />
        许可证管理
      </h3>

      <div className={styles.licenseActions}>
        <button className="btn primary" onClick={handleActivate} disabled={loading}>
          {loading ? <Loader size={16} className="spin" /> : '激活新许可证'}
        </button>
        <button className="btn ghost" onClick={handleGetMy} disabled={loading}>
          查询我的许可证
        </button>
      </div>

      <div className={styles.inputGroup}>
        <label>许可证密钥</label>
        <div className={styles.inputWithBtn}>
          <input
            type="text"
            placeholder="输入许可证密钥..."
            value={licenseKey}
            onChange={(e) => setLicenseKey(e.target.value)}
            className={styles.input}
          />
          <button className="btn primary" onClick={handleValidate} disabled={loading}>
            {loading ? <Loader size={16} className="spin" /> : '校验'}
          </button>
        </div>
      </div>

      {licenseInfo && (
        <div className={styles.codeBlock}>
          <div className={styles.codeHeader}>
            <FileText size={14} />
            <span>许可证信息</span>
          </div>
          <pre>{JSON.stringify(licenseInfo, null, 2)}</pre>
        </div>
      )}
    </section>
  );
}
