import React, { useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import styles from './AuthModal.module.scss';
import { useForm } from 'react-hook-form';
import { useUIStore } from '../../store/ui.js';
import { useAuthStore } from '../../store/auth.js';
import { loginUser, registerUser } from '../../services/api.js';
import { toast } from 'sonner';
import {
  X,
  Mail,
  Lock,
  User as UserIcon,
  Eye,
  EyeOff,
  Loader,
  Sparkles,
  Shield,
  Zap,
} from 'lucide-react';

const GOOGLE_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID;
const GITHUB_ID = import.meta.env.VITE_GITHUB_CLIENT_ID;
const OUTLOOK_ID = import.meta.env.VITE_OUTLOOK_CLIENT_ID;

function buildOAuthUrl(provider) {
  const origin = window.location.origin;
  if (provider === 'google' && GOOGLE_ID) {
    const redirect = `${origin}/auth/google/callback`;
    const scope = encodeURIComponent('openid email profile');
    return `https://accounts.google.com/o/oauth2/v2/auth?client_id=${encodeURIComponent(
      GOOGLE_ID,
    )}&redirect_uri=${encodeURIComponent(
      redirect,
    )}&response_type=code&scope=${scope}&access_type=offline&prompt=consent`;
  }
  if (provider === 'github' && GITHUB_ID) {
    const redirect = `${origin}/auth/github/callback`;
    const scope = encodeURIComponent('read:user user:email');
    return `https://github.com/login/oauth/authorize?client_id=${encodeURIComponent(
      GITHUB_ID,
    )}&redirect_uri=${encodeURIComponent(redirect)}&scope=${scope}`;
  }
  if (provider === 'outlook' && OUTLOOK_ID) {
    const redirect = `${origin}/auth/outlook/callback`;
    const scope = encodeURIComponent('openid email profile offline_access');
    return `https://login.microsoftonline.com/common/oauth2/v2.0/authorize?client_id=${encodeURIComponent(
      OUTLOOK_ID,
    )}&redirect_uri=${encodeURIComponent(redirect)}&response_type=code&scope=${scope}`;
  }
  return '';
}

export default function AuthModal() {
  const { authOpen, setAuthOpen } = useUIStore();
  const setAuth = useAuthStore((s) => s.setAuth);

  const [mode, setMode] = useState('login');
  const [showPassword, setShowPassword] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    reset,
    watch,
  } = useForm();

  const password = watch('password');

  const onSubmit = async (form) => {
    try {
      const data =
        mode === 'login'
          ? await loginUser(form.email, form.password)
          : await registerUser(form.email, form.password, form.confirm, form.name || '');

      const accessToken =
        data?.access ||
        data?.tokens?.access ||
        data?.tokens?.access_token ||
        data?.token ||
        data?.access_token;
      const refreshToken =
        data?.refresh || data?.tokens?.refresh || data?.tokens?.refresh_token || null;

      setAuth({ accessToken, refreshToken, user: data?.user || null });

      toast.success(mode === 'login' ? '欢迎回来！' : '注册成功！', {
        description: mode === 'login' ? '正在为您加载个性化内容...' : '开始探索您的AI助手吧',
      });

      setTimeout(() => {
        setAuthOpen(false);
        reset();
      }, 1000);
    } catch (e) {
      toast.error('操作失败', {
        description: e?.message || '请稍后重试',
      });
    }
  };

  const handleOAuth = (provider) => {
    const url = buildOAuthUrl(provider);
    if (!url) {
      toast.error(`${provider.toUpperCase()} 登录暂不可用`);
      return;
    }
    window.location.href = url;
  };

  const switchMode = () => {
    setMode((m) => (m === 'login' ? 'register' : 'login'));
    reset();
  };

  return (
    <Dialog.Root open={authOpen} onOpenChange={setAuthOpen}>
      <Dialog.Portal>
        <Dialog.Overlay className={styles.overlay} />
        <Dialog.Content className={styles.content} aria-describedby={undefined}>
          {/* 装饰性背景 */}
          <div className={styles.bgDecoration}>
            <div className={styles.gradientOrb} />
            <div className={styles.gradientOrb2} />
          </div>

          {/* 关闭按钮 */}
          <Dialog.Close className={styles.closeBtn} aria-label="关闭">
            <X size={18} />
          </Dialog.Close>

          {/* Logo区域 */}
          <div className={styles.logoArea}>
            <div className={styles.logoIcon}>
              {mode === 'login' ? <Shield size={32} /> : <Sparkles size={32} />}
            </div>
          </div>

          {/* 标题 */}
          <Dialog.Title className={styles.title}>
            {mode === 'login' ? '欢迎回来' : '创建账户'}
          </Dialog.Title>
          <p className={styles.subtitle}>
            {mode === 'login' ? '登录以继续您的AI对话之旅' : '加入我们，开启智能对话新体验'}
          </p>

          {/* 表单 */}
          <form className={styles.form} onSubmit={handleSubmit(onSubmit)}>
            {mode === 'register' && (
              <div className={styles.field}>
                <div className={styles.fieldInner}>
                  <UserIcon size={18} className={styles.fieldIcon} />
                  <input
                    type="text"
                    placeholder="用户名（可选）"
                    {...register('name')}
                    className={styles.input}
                  />
                </div>
              </div>
            )}

            <div className={styles.field}>
              <div className={styles.fieldInner}>
                <Mail size={18} className={styles.fieldIcon} />
                <input
                  type="email"
                  placeholder="邮箱地址"
                  {...register('email', {
                    required: '请输入邮箱',
                    pattern: {
                      value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
                      message: '邮箱格式不正确',
                    },
                  })}
                  className={styles.input}
                  aria-invalid={errors.email ? 'true' : 'false'}
                />
              </div>
              {errors.email && <span className={styles.error}>{errors.email.message}</span>}
            </div>

            <div className={styles.field}>
              <div className={styles.fieldInner}>
                <Lock size={18} className={styles.fieldIcon} />
                <input
                  type={showPassword ? 'text' : 'password'}
                  placeholder="密码"
                  {...register('password', {
                    required: '请输入密码',
                    minLength: { value: 6, message: '密码至少6位' },
                  })}
                  className={styles.input}
                  aria-invalid={errors.password ? 'true' : 'false'}
                />
                <button
                  type="button"
                  className={styles.eyeBtn}
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? '隐藏密码' : '显示密码'}
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
              {errors.password && <span className={styles.error}>{errors.password.message}</span>}
            </div>

            {mode === 'register' && (
              <div className={styles.field}>
                <div className={styles.fieldInner}>
                  <Lock size={18} className={styles.fieldIcon} />
                  <input
                    type={showPassword ? 'text' : 'password'}
                    placeholder="确认密码"
                    {...register('confirm', {
                      required: '请确认密码',
                      validate: (value) => value === password || '密码不匹配',
                    })}
                    className={styles.input}
                    aria-invalid={errors.confirm ? 'true' : 'false'}
                  />
                </div>
                {errors.confirm && <span className={styles.error}>{errors.confirm.message}</span>}
              </div>
            )}

            <button type="submit" className={styles.submitBtn} disabled={isSubmitting}>
              {isSubmitting ? (
                <>
                  <Loader size={18} className={styles.spin} />
                  处理中...
                </>
              ) : (
                <>
                  <Zap size={18} />
                  {mode === 'login' ? '立即登录' : '创建账户'}
                </>
              )}
            </button>
          </form>

          {/* 分隔线 */}
          <div className={styles.divider}>
            <span>OR</span>
          </div>

          {/* 社交登录 */}
          <div className={styles.socialBtns}>
            <button
              className={styles.socialBtn}
              onClick={() => handleOAuth('google')}
              disabled={!GOOGLE_ID}
            >
              <svg width="20" height="20" viewBox="0 0 24 24">
                <path
                  fill="#4285F4"
                  d="M23.745 12.27c0-.79-.07-1.54-.19-2.27h-11.3v4.28h6.47c-.29 1.48-1.14 2.73-2.4 3.58v3h3.86c2.26-2.09 3.56-5.17 3.56-8.59Z"
                />
                <path
                  fill="#34A853"
                  d="M12.255 24c3.24 0 5.95-1.08 7.93-2.91l-3.86-3c-1.08.72-2.45 1.16-4.07 1.16-3.13 0-5.78-2.11-6.73-4.96h-3.98v3.09C3.515 21.3 7.565 24 12.255 24Z"
                />
                <path
                  fill="#FBBC05"
                  d="M5.525 14.29c-.25-.72-.38-1.49-.38-2.29s.14-1.57.38-2.29V6.62h-3.98a11.86 11.86 0 0 0 0 10.76l3.98-3.09Z"
                />
                <path
                  fill="#EA4335"
                  d="M12.255 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C18.205 1.19 15.495 0 12.255 0c-4.69 0-8.74 2.7-10.71 6.62l3.98 3.09c.95-2.85 3.6-4.96 6.73-4.96Z"
                />
              </svg>
              使用 Google 登录
            </button>

            <button
              className={styles.socialBtn}
              onClick={() => handleOAuth('github')}
              disabled={!GITHUB_ID}
            >
              <svg width="20" height="20" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
              </svg>
              使用 GitHub 登录
            </button>
          </div>

          {/* 切换模式 */}
          <div className={styles.footer}>
            <span>{mode === 'login' ? '还没有账户？' : '已有账户？'}</span>
            <button className={styles.linkBtn} onClick={switchMode}>
              {mode === 'login' ? '立即注册' : '返回登录'}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
