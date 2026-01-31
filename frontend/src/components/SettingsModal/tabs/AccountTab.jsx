// src/components/SettingsModal/tabs/AccountTab.jsx
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Trash2, Loader, AlertCircle } from 'lucide-react';
import { deleteAccount } from '../../../services/api';
import { useAuthStore } from '../../../store/auth';
import { useUIStore } from '../../../store/ui';
import styles from '../styles/SettingsModal.module.scss';

export default function AccountTab({ showMessage }) {
  const navigate = useNavigate();
  const { clearAuth } = useAuthStore();
  const { closeSettings } = useUIStore();
  const [loading, setLoading] = useState(false);

  const handleDelete = async () => {
    if (!confirm('[WARN] 此操作不可撤销！确定删除账户吗？')) return;
    if (!confirm('最后确认：删除后所有数据将永久丢失！')) return;
    setLoading(true);
    try {
      await deleteAccount();
      clearAuth();
      closeSettings();
      showMessage('success', '账户已删除');
      setTimeout(() => navigate('/'), 1500);
    } catch (e) {
      showMessage('error', e?.message || '删除失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className={styles.section}>
      <h3 className={styles.sectionTitle}>
        <Trash2 size={20} />
        账户管理
      </h3>

      <div className={styles.dangerZone}>
        <div className={styles.dangerCard}>
          <div className={styles.cardContent}>
            <strong>删除账户</strong>
            <p>永久删除您的账户和所有相关数据，此操作不可撤销</p>
          </div>
          <button className="btn danger" onClick={handleDelete} disabled={loading}>
            {loading ? <Loader size={16} className="spin" /> : <Trash2 size={16} />}
            删除账户
          </button>
        </div>
      </div>

      <div className={styles.warningBox}>
        <AlertCircle size={16} />
        <span>删除后将无法恢复对话记录、个人设置等所有数据</span>
      </div>
    </section>
  );
}
