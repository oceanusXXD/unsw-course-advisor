// src/components/ProfileModal/ProfileModal.jsx
import React, { useEffect } from 'react';
import { useUIStore } from '../../store/ui';
import { X, User } from 'lucide-react';
import ProfileForm from './ProfileForm';
import styles from './styles/ProfileModal.module.scss';
import '../../styles/glass.css';

export default function ProfileModal() {
  const { profileOpen, closeProfile } = useUIStore();

  // ESC 键关闭
  useEffect(() => {
    const handleEsc = (e) => {
      if (e.key === 'Escape' && profileOpen) {
        closeProfile();
      }
    };
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [profileOpen, closeProfile]);

  if (!profileOpen) return null;

  return (
    <div className={styles.modalOverlay} onClick={closeProfile}>
      <div className={`${styles.modalContainer} glass-liquid`} onClick={(e) => e.stopPropagation()}>
        {/* 头部 */}
        <header className={styles.modalHeader}>
          <div className={styles.headerLeft}>
            <div className={styles.iconWrapper}>
              <User size={24} />
            </div>
            <div>
              <h2 className={styles.modalTitle}>个人资料</h2>
              <p className={styles.modalSubtitle}>完善信息以获得更好的学习建议</p>
            </div>
          </div>
          <button className={styles.closeBtn} onClick={closeProfile} aria-label="关闭">
            <X size={20} />
          </button>
        </header>

        {/* 表单 */}
        <div className={styles.modalBody}>
          <ProfileForm onClose={closeProfile} />
        </div>
      </div>
    </div>
  );
}
