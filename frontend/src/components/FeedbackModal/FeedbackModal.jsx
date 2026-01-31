// src/components/FeedbackModal/FeedbackModal.jsx
import React, { useState } from 'react';
import { useUIStore } from '../../store/ui';
import { useAuthStore } from '../../store/auth';
import { submitFeedback } from '../../services/api';
import { X, MessageSquare, Check, Loader, AlertCircle, Star } from 'lucide-react';
import styles from './FeedbackModal.module.scss';
import '../../styles/glass.css';

const FEEDBACK_TYPES = [
  { value: 'bug', label: '[Bug] Bug 报告', desc: '发现了系统错误或异常' },
  { value: 'feature', label: '[Tip] 功能建议', desc: '希望添加新功能' },
  { value: 'improvement', label: '[Result] 改进建议', desc: '现有功能可以做得更好' },
  { value: 'other', label: ' 其他反馈', desc: '其他意见或建议' },
];

export default function FeedbackModal() {
  const { feedbackOpen, closeFeedback } = useUIStore();
  const user = useAuthStore((state) => state.user);

  const [type, setType] = useState('');
  const [rating, setRating] = useState(0);
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [email, setEmail] = useState(user?.email || '');
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!type) {
      setError('请选择反馈类型');
      return;
    }
    if (!title.trim()) {
      setError('请填写标题');
      return;
    }
    if (!content.trim()) {
      setError('请填写详细内容');
      return;
    }

    setSubmitting(true);
    setError('');

    try {
      const feedbackData = {
        type,
        rating,
        title: title.trim(),
        content: content.trim(),
        email: email.trim(),
        user_id: user?.id,
        user_agent: navigator.userAgent,
        screen_resolution: `${window.screen.width}x${window.screen.height}`,
        timestamp: new Date().toISOString(),
      };

      await submitFeedback(feedbackData);

      setSubmitted(true);
      setTimeout(() => {
        closeFeedback();
        // 重置表单
        setTimeout(() => {
          setType('');
          setRating(0);
          setTitle('');
          setContent('');
          setSubmitted(false);
        }, 300);
      }, 2000);
    } catch (err) {
      console.error('[Feedback] Submit error:', err);
      setError(err?.message || '提交失败，请重试');
    } finally {
      setSubmitting(false);
    }
  };

  if (!feedbackOpen) return null;

  return (
    <div className={styles.modalOverlay} onClick={closeFeedback}>
      <div className={`${styles.modalContainer} glass-liquid`} onClick={(e) => e.stopPropagation()}>
        <header className={styles.modalHeader}>
          <div className={styles.headerLeft}>
            <div className={styles.iconWrapper}>
              <MessageSquare size={24} />
            </div>
            <div>
              <h2 className={styles.modalTitle}>用户反馈</h2>
              <p className={styles.modalSubtitle}>您的意见对我们很重要</p>
            </div>
          </div>
          <button className={styles.closeBtn} onClick={closeFeedback} aria-label="关闭">
            <X size={20} />
          </button>
        </header>

        <div className={styles.modalBody}>
          {submitted ? (
            <div className={styles.successState}>
              <div className={styles.successIcon}>
                <Check size={48} />
              </div>
              <h3>感谢您的反馈！</h3>
              <p>我们已收到您的意见，会尽快处理</p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className={styles.feedbackForm}>
              {error && (
                <div className={styles.errorMessage}>
                  <AlertCircle size={16} />
                  {error}
                </div>
              )}

              {/* 反馈类型 */}
              <div className={styles.formGroup}>
                <label className={styles.label}>
                  反馈类型 <span className={styles.required}>*</span>
                </label>
                <div className={styles.typeGrid}>
                  {FEEDBACK_TYPES.map((t) => (
                    <button
                      key={t.value}
                      type="button"
                      className={`${styles.typeCard} ${type === t.value ? styles.active : ''}`}
                      onClick={() => setType(t.value)}
                    >
                      <span className={styles.typeLabel}>{t.label}</span>
                      <span className={styles.typeDesc}>{t.desc}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* 评分 */}
              <div className={styles.formGroup}>
                <label className={styles.label}>整体评分（可选）</label>
                <div className={styles.ratingStars}>
                  {[1, 2, 3, 4, 5].map((star) => (
                    <button
                      key={star}
                      type="button"
                      className={`${styles.star} ${star <= rating ? styles.filled : ''}`}
                      onClick={() => setRating(star)}
                    >
                      <Star size={24} />
                    </button>
                  ))}
                </div>
              </div>

              {/* 标题 */}
              <div className={styles.formGroup}>
                <label className={styles.label}>
                  标题 <span className={styles.required}>*</span>
                </label>
                <input
                  type="text"
                  className={styles.input}
                  placeholder="简要描述问题或建议"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  maxLength={100}
                />
                <span className={styles.charCount}>{title.length}/100</span>
              </div>

              {/* 详细内容 */}
              <div className={styles.formGroup}>
                <label className={styles.label}>
                  详细描述 <span className={styles.required}>*</span>
                </label>
                <textarea
                  className={styles.textarea}
                  rows={6}
                  placeholder="请详细描述您的问题或建议..."
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  maxLength={1000}
                />
                <span className={styles.charCount}>{content.length}/1000</span>
              </div>

              {/* 联系邮箱 */}
              <div className={styles.formGroup}>
                <label className={styles.label}>联系邮箱（可选）</label>
                <input
                  type="email"
                  className={styles.input}
                  placeholder="如需回复，请留下邮箱"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>

              {/* 提交按钮 */}
              <div className={styles.formFooter}>
                <button
                  type="button"
                  className="btn secondary"
                  onClick={closeFeedback}
                  disabled={submitting}
                >
                  取消
                </button>
                <button
                  type="submit"
                  className="btn primary"
                  disabled={submitting || !type || !title.trim() || !content.trim()}
                >
                  {submitting ? (
                    <>
                      <Loader size={16} className="spin" />
                      提交中...
                    </>
                  ) : (
                    <>
                      <MessageSquare size={16} />
                      提交反馈
                    </>
                  )}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
