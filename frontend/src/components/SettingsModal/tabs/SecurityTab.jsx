// src/components/SettingsModal/tabs/SecurityTab.jsx
import React, { useState } from 'react';
import { Shield, Loader } from 'lucide-react';
import { changePassword } from '../../../services/api';
import styles from '../styles/SettingsModal.module.scss';

export default function SecurityTab({ showMessage }) {
  const [loading, setLoading] = useState(false);

  const handleChangePassword = async () => {
    const oldPassword = prompt('请输入旧密码：');
    if (!oldPassword) return;
    const newPassword = prompt('请输入新密码（至少 6 位）：');
    if (!newPassword || newPassword.length < 6) {
      showMessage('error', '新密码至少 6 位');
      return;
    }
    setLoading(true);
    try {
      await changePassword(oldPassword, newPassword);
      showMessage('success', '密码修改成功');
    } catch (e) {
      showMessage('error', e?.message || '修改失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className={styles.section}>
      <h3 className={styles.sectionTitle}>
        <Shield size={20} />
        安全设置
      </h3>
      <div className={styles.actionCard}>
        <div className={styles.cardContent}>
          <strong>修改密码</strong>
          <p>定期更换密码可提高账户安全性</p>
        </div>
        <button className="btn primary" onClick={handleChangePassword} disabled={loading}>
          {loading ? <Loader size={16} className="spin" /> : '修改密码'}
        </button>
      </div>
      <div className={styles.infoBox}>
        <Shield size={16} />
        <span>建议使用至少 8 位字符，包含字母、数字和符号</span>
      </div>
    </section>
  );
}
