// src/components/SettingsModal/SettingsModal.jsx
import React, { useState, useEffect } from 'react';
import { useUIStore } from '../../store/ui';
import { X } from 'lucide-react';
import AppearanceTab from './tabs/AppearanceTab';
import SecurityTab from './tabs/SecurityTab';
import LicenseTab from './tabs/LicenseTab';
import CryptoTab from './tabs/CryptoTab';
import AccountTab from './tabs/AccountTab';
import TabNav from './TabNav';
import styles from './styles/SettingsModal.module.scss';
import '../../styles/glass.css';

export default function SettingsModal() {
  const { settingsOpen, closeSettings } = useUIStore();
  const [activeTab, setActiveTab] = useState('appearance');
  const [message, setMessage] = useState({ type: '', text: '' });

  const showMessage = (type, text) => {
    setMessage({ type, text });
    setTimeout(() => setMessage({ type: '', text: '' }), 3000);
  };

  // 关闭弹窗时重置状态
  useEffect(() => {
    if (!settingsOpen) {
      setActiveTab('appearance');
      setMessage({ type: '', text: '' });
    }
  }, [settingsOpen]);

  // ESC 键关闭
  useEffect(() => {
    const handleEsc = (e) => {
      if (e.key === 'Escape' && settingsOpen) {
        closeSettings();
      }
    };
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [settingsOpen, closeSettings]);

  if (!settingsOpen) return null;

  return (
    <div className={styles.modalOverlay} onClick={closeSettings}>
      <div className={`${styles.modalContainer} glass-liquid`} onClick={(e) => e.stopPropagation()}>
        {/* 头部 */}
        <header className={styles.modalHeader}>
          <h2 className={styles.modalTitle}>设置</h2>
          <button className={styles.closeBtn} onClick={closeSettings} aria-label="关闭">
            <X size={20} />
          </button>
        </header>

        {/* 主体 */}
        <div className={styles.modalBody}>
          {/* 左侧导航 */}
          <TabNav activeTab={activeTab} onChange={setActiveTab} />

          {/* 右侧内容 */}
          <main className={styles.tabContent}>
            {/* 消息提示 */}
            {message.text && (
              <div className={`${styles.message} ${styles[message.type]}`}>{message.text}</div>
            )}

            {/* 标签页内容 */}
            {activeTab === 'appearance' && <AppearanceTab />}
            {activeTab === 'security' && <SecurityTab showMessage={showMessage} />}
            {activeTab === 'license' && <LicenseTab showMessage={showMessage} />}
            {activeTab === 'crypto' && <CryptoTab showMessage={showMessage} />}
            {activeTab === 'account' && <AccountTab showMessage={showMessage} />}
          </main>
        </div>
      </div>
    </div>
  );
}
