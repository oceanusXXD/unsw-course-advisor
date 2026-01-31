// src/components/ProfileModal/ProfileForm.jsx
import React, { useState, useEffect } from 'react';
import { useTabsStore } from '../../store/tabs';
import { useChatStore } from '../../store/chat';
import { useAuthStore } from '../../store/auth';
import { saveStudentProfile, getStudentProfile } from '../../services/api';
import {
  User,
  GraduationCap,
  BookOpen,
  Target,
  Clock,
  Award,
  Check,
  Loader,
  AlertCircle,
  Info,
} from 'lucide-react';
import styles from './styles/ProfileModal.module.scss';

export default function ProfileForm({ onClose }) {
  const activeTabId = useTabsStore((state) => state.activeTabId);
  const currentTab = useTabsStore((state) => state.getTabById(activeTabId));
  const setStudentInfo = useChatStore((state) => state.setStudentInfo);
  const getFrontendState = useChatStore((state) => state.getFrontendState);
  const user = useAuthStore((state) => state.user);

  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });

  //  匹配后端字段
  const [form, setForm] = useState({
    major_code: '',
    target_term: '',
    completed_courses: [],
    degree_level: '',
    current_uoc: '',
    wam: '',
    max_uoc_per_term: 20,
    goals: '',
    requirement_types: [],
  });

  const showMessage = (type, text) => {
    setMessage({ type, text });
    setTimeout(() => setMessage({ type: '', text: '' }), 3000);
  };

  const handleDegreeLevelChange = (e) => {
    const value = e.target.value.toUpperCase();
    // 允许空值、U、P、UG、PG
    if (value === '' || value === 'U' || value === 'P' || value === 'UG' || value === 'PG') {
      updateForm('degree_level', value);
    }
  };

  // 加载已有数据
  useEffect(() => {
    const loadProfile = async () => {
      setLoading(true);
      try {
        // 1. 优先从当前 tab 的 frontend_state 加载
        const frontendState = getFrontendState(activeTabId);
        if (frontendState?.student_info) {
          const si = frontendState.student_info;
          setForm({
            major_code: si.major_code || '',
            target_term: si.target_term || '',
            completed_courses: Array.isArray(si.completed_courses) ? si.completed_courses : [],
            degree_level: si.degree_level || '',
            current_uoc: si.current_uoc ?? '',
            wam: si.wam ?? '',
            max_uoc_per_term: si.max_uoc_per_term || 20,
            goals: si.goals || '',
            requirement_types: Array.isArray(si.requirement_types) ? si.requirement_types : [],
          });
          return;
        }

        // 2. 从服务器加载
        if (currentTab?.tabId) {
          const data = await getStudentProfile({
            tabId: currentTab.tabId,
            userId: user?.id,
            useAuth: true,
          });

          if (data?.status === 'ok' && data?.student_info) {
            const si = data.student_info;
            setForm({
              major_code: si.major_code || '',
              target_term: si.target_term || '',
              completed_courses: Array.isArray(si.completed_courses) ? si.completed_courses : [],
              degree_level: si.degree_level || '',
              current_uoc: si.current_uoc ?? '',
              wam: si.wam ?? '',
              max_uoc_per_term: si.max_uoc_per_term || 20,
              goals: si.goals || '',
              requirement_types: Array.isArray(si.requirement_types) ? si.requirement_types : [],
            });
            showMessage('info', '已加载档案信息');
          }
        }
      } catch (e) {
        console.warn('[ProfileForm] Failed to load profile:', e);
        // 静默失败，不影响用户填写
      } finally {
        setLoading(false);
      }
    };

    if (activeTabId) {
      loadProfile();
    }
  }, [activeTabId, getFrontendState, currentTab, user]);

  const handleSubmit = async (e) => {
    e.preventDefault();

    // 验证必填字段
    if (!form.major_code) {
      showMessage('error', '请填写专业代码');
      return;
    }
    if (!form.target_term) {
      showMessage('error', '请填写目标学期');
      return;
    }
    if (!form.degree_level) {
      showMessage('error', '请在 UG 和 PG 中选择输入');
      return;
    }
    if (!activeTabId) {
      showMessage('error', '请先选择一个对话');
      return;
    }

    setSaving(true);
    try {
      // 构建 student_info
      const studentInfo = {
        major_code: form.major_code,
        target_term: form.target_term,
        degree_level: form.degree_level,
        completed_courses: form.completed_courses,
        ...(form.current_uoc !== '' && { current_uoc: Number(form.current_uoc) }),
        ...(form.wam !== '' && { wam: Number(form.wam) }),
        ...(form.max_uoc_per_term && { max_uoc_per_term: Number(form.max_uoc_per_term) }),
        ...(form.goals && { goals: form.goals }),
        ...(form.requirement_types?.length > 0 && { requirement_types: form.requirement_types }),
      };

      console.log('[ProfileForm] Saving student_info:', studentInfo);

      const response = await saveStudentProfile({
        studentInfo,
        userId: user?.id,
        tabId: currentTab?.tabId,
        useAuth: true,
      });

      console.log('[ProfileForm] Save response:', response);

      if (response?.status === 'ok') {
        //  更新本地 store 的 frontendState
        setStudentInfo(activeTabId, studentInfo);

        //  同时保存到 localStorage 作为临时标记（供下次发送使用）
        const tempProfileKey = `temp_student_profile_${activeTabId}`;
        localStorage.setItem(tempProfileKey, JSON.stringify(studentInfo));

        showMessage('success', '档案保存成功！');
        setTimeout(() => onClose(), 1500);
      } else {
        showMessage('error', response?.error || '保存失败');
      }
    } catch (e) {
      console.error('[ProfileForm] Save error:', e);
      showMessage('error', e?.message || '保存失败，请重试');
    } finally {
      setSaving(false);
    }
  };

  const updateForm = (field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  // 处理课程列表输入（逗号分隔）
  const handleCoursesChange = (e) => {
    const text = e.target.value;
    const courses = text
      .split(',')
      .map((c) => c.trim().toUpperCase())
      .filter((c) => c.length > 0);
    updateForm('completed_courses', courses);
  };

  if (loading) {
    return (
      <div className={styles.loadingState}>
        <Loader size={32} className="spin" />
        <p>加载中...</p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className={styles.profileForm}>
      {/* 消息提示 */}
      {message.text && (
        <div className={`${styles.message} ${styles[message.type]}`}>
          {message.type === 'success' ? (
            <Check size={16} />
          ) : message.type === 'info' ? (
            <Info size={16} />
          ) : (
            <AlertCircle size={16} />
          )}
          {message.text}
        </div>
      )}

      {/* 基础信息 */}
      <section className={styles.formSection}>
        <h3 className={styles.sectionTitle}>
          <User size={18} />
          基础信息
        </h3>

        <div className={styles.inputRow}>
          <div className={styles.inputGroup}>
            <label>
              专业代码 <span className={styles.required}>*</span>
            </label>
            <input
              type="text"
              placeholder="例如：COMPA1"
              value={form.major_code}
              onChange={(e) => updateForm('major_code', e.target.value.toUpperCase())}
              className={styles.input}
              required
            />
          </div>

          <div className={styles.inputGroup}>
            <label>
              学位层次 <span className={styles.required}>*</span>
            </label>
            <input
              type="text"
              placeholder="UG 或 PG"
              value={form.degree_level}
              onChange={handleDegreeLevelChange}
              className={styles.input}
              maxLength={2}
              required
            />
            <p className={styles.hint}>输入 UG（本科）或 PG（研究生）</p>
          </div>
        </div>
      </section>

      {/* 学期与学分 */}
      <section className={styles.formSection}>
        <h3 className={styles.sectionTitle}>
          <GraduationCap size={18} />
          学期与学分
        </h3>

        <div className={styles.inputRow}>
          <div className={styles.inputGroup}>
            <label>
              目标学期 <span className={styles.required}>*</span>
            </label>
            <input
              type="text"
              placeholder="例如：25T1"
              value={form.target_term}
              onChange={(e) => updateForm('target_term', e.target.value)}
              className={styles.input}
              required
            />
            <p className={styles.hint}>格式：25T1 或 2025T1</p>
          </div>

          <div className={styles.inputGroup}>
            <label>当前已获得 UOC</label>
            <input
              type="number"
              placeholder="例如：72"
              value={form.current_uoc}
              onChange={(e) => updateForm('current_uoc', e.target.value)}
              className={styles.input}
            />
          </div>
        </div>

        <div className={styles.inputRow}>
          <div className={styles.inputGroup}>
            <label className={styles.labelWithIcon}>
              <Award size={16} />
              WAM 成绩
            </label>
            <input
              type="number"
              step="0.01"
              placeholder="例如：75.5"
              value={form.wam}
              onChange={(e) => updateForm('wam', e.target.value)}
              className={styles.input}
            />
          </div>

          <div className={styles.inputGroup}>
            <label className={styles.labelWithIcon}>
              <Clock size={16} />
              单学期最大 UOC
            </label>
            <input
              type="number"
              placeholder="默认 20"
              value={form.max_uoc_per_term}
              onChange={(e) => updateForm('max_uoc_per_term', e.target.value)}
              className={styles.input}
            />
          </div>
        </div>
      </section>

      {/* 已修课程 */}
      <section className={styles.formSection}>
        <h3 className={styles.sectionTitle}>
          <BookOpen size={18} />
          已修课程
        </h3>
        <div className={styles.inputGroup}>
          <label>课程代码列表</label>
          <textarea
            rows={4}
            placeholder="用逗号分隔，例如：COMP1511, COMP1521, MATH1081"
            value={form.completed_courses.join(', ')}
            onChange={handleCoursesChange}
            className={styles.textarea}
          />
          <p className={styles.hint}>已输入 {form.completed_courses.length} 门课程</p>
        </div>
      </section>

      {/* 学习目标 */}
      <section className={styles.formSection}>
        <h3 className={styles.sectionTitle}>
          <Target size={18} />
          学习目标与偏好
        </h3>

        <div className={styles.inputGroup}>
          <label>学习目标</label>
          <textarea
            rows={3}
            placeholder="描述你的学习目标和期望，例如：希望在人工智能方向深入发展"
            value={form.goals}
            onChange={(e) => updateForm('goals', e.target.value)}
            className={styles.textarea}
          />
        </div>

        <div className={styles.inputGroup}>
          <label>需求类型</label>
          <div className={styles.checkboxGroup}>
            {['Core', 'Elective', 'General Education', 'Free Elective'].map((type) => (
              <label key={type} className={styles.checkboxLabel}>
                <input
                  type="checkbox"
                  checked={form.requirement_types.includes(type)}
                  onChange={(e) => {
                    if (e.target.checked) {
                      updateForm('requirement_types', [...form.requirement_types, type]);
                    } else {
                      updateForm(
                        'requirement_types',
                        form.requirement_types.filter((t) => t !== type),
                      );
                    }
                  }}
                />
                <span>{type}</span>
              </label>
            ))}
          </div>
        </div>
      </section>

      {/* 底部按钮 */}
      <div className={styles.formFooter}>
        <button type="button" className="btn secondary" onClick={onClose} disabled={saving}>
          取消
        </button>
        <button type="submit" className="btn primary" disabled={saving}>
          {saving ? (
            <>
              <Loader size={16} className="spin" />
              保存中...
            </>
          ) : (
            <>
              <Check size={16} />
              保存档案
            </>
          )}
        </button>
      </div>
    </form>
  );
}
