// src/components/ContactModal/ContactModal.jsx
import React from 'react';
import { useUIStore } from '../../store/ui';
import { X, Mail, Github, ExternalLink } from 'lucide-react';
import styles from './ContactModal.module.scss';
import '../../styles/glass.css';

export default function ContactModal() {
  const { contactOpen, closeContact } = useUIStore();

  if (!contactOpen) return null;

  return (
    <div className={styles.modalOverlay} onClick={closeContact}>
      <div className={`${styles.modalContainer} glass-liquid`} onClick={(e) => e.stopPropagation()}>
        <header className={styles.modalHeader}>
          <div className={styles.headerLeft}>
            <div className={styles.iconWrapper}>
              <Mail size={24} />
            </div>
            <div>
              <h2 className={styles.modalTitle}>联系我们</h2>
              <p className={styles.modalSubtitle}>获取支持与帮助</p>
            </div>
          </div>
          <button className={styles.closeBtn} onClick={closeContact} aria-label="关闭">
            <X size={20} />
          </button>
        </header>

        <div className={styles.modalBody}>
          <div className={styles.contactList}>
            <a
              href="https://github.com/yourusername/your-repo"
              target="_blank"
              rel="noopener noreferrer"
              className={styles.contactCard}
            >
              <div className={styles.contactIcon}>
                <Github size={24} />
              </div>
              <div className={styles.contactInfo}>
                <h3 className={styles.contactTitle}>GitHub</h3>
                <p className={styles.contactDesc}>查看项目，提交 Issue</p>
                <span className={styles.contactLink}>
                  COMING SOON
                  <ExternalLink size={14} />
                </span>
              </div>
            </a>

            <a href="mailto:tao666918@gmail.com" className={styles.contactCard}>
              <div className={styles.contactIcon}>
                <Mail size={24} />
              </div>
              <div className={styles.contactInfo}>
                <h3 className={styles.contactTitle}>Email</h3>
                <p className={styles.contactDesc}>发送邮件获取技术支持</p>
                <span className={styles.contactLink}>
                  tao666918@gmail.com
                  <ExternalLink size={14} />
                </span>
              </div>
            </a>
          </div>

          <div className={styles.footer}>
            <p>工作时间：周一至周五 9:00-18:00 (AEST)</p>
            <p>我们会在 24 小时内回复您的邮件</p>
          </div>
        </div>
      </div>
    </div>
  );
}
