// src/pages/AuthCallback.jsx
import React, { useEffect, useState, useRef } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import {
  loginWithGoogle,
  loginWithGitHub,
  loginWithOutlook,
  getCurrentUser, //  新增导入
} from '../services/api.js';
import { useAuthStore } from '../store/auth.js';
import {
  Loader,
  CheckCircle,
  XCircle,
  ArrowLeft,
  RefreshCw,
  Chrome,
  Github,
  Mail,
} from 'lucide-react';
import styles from './AuthCallback.module.scss';

const PROVIDER_INFO = {
  google: {
    name: 'Google',
    icon: Chrome,
    color: '#4285F4',
  },
  github: {
    name: 'GitHub',
    icon: Github,
    color: '#181717',
  },
  outlook: {
    name: 'Microsoft',
    icon: Mail,
    color: '#0078D4',
  },
};

export default function AuthCallback() {
  const { provider } = useParams();
  const [sp] = useSearchParams();
  const code = sp.get('code');
  const navigate = useNavigate();
  const setAuth = useAuthStore((s) => s.setAuth);

  const [status, setStatus] = useState('loading');
  const [message, setMessage] = useState('正在验证授权信息...');
  const [step, setStep] = useState(0);

  //  使用 ref 防止重复请求
  const hasInitiated = useRef(false);

  useEffect(() => {
    //  防止重复执行
    if (hasInitiated.current) {
      console.log('[AuthCallback] Already initiated, skipping...');
      return;
    }

    async function handleAuth() {
      // 参数验证
      if (!provider || !code) {
        setStatus('error');
        setMessage('缺少必要的授权参数');
        return;
      }

      // 标记已开始
      hasInitiated.current = true;

      try {
        console.log(
          `[AuthCallback] Starting auth with provider: ${provider}, code: ${code.substring(
            0,
            8,
          )}...`,
        );

        // Step 1: 验证授权码
        setMessage('正在验证授权信息...');
        setStep(0);
        await new Promise((resolve) => setTimeout(resolve, 500));

        // Step 2: 获取访问令牌
        setMessage('正在获取访问令牌...');
        setStep(1);

        let data = null;
        if (provider === 'google') data = await loginWithGoogle(code);
        else if (provider === 'github') data = await loginWithGitHub(code);
        else if (provider === 'outlook') data = await loginWithOutlook(code);
        else throw new Error('不支持的登录方式');

        console.log('[AuthCallback] Login response:', data);

        // [BUILD] 修改：使用统一格式的返回值
        const accessToken = data?.access;
        const refreshToken = data?.refresh;
        let user = data?.user;

        if (!accessToken) {
          throw new Error('未能获取访问令牌');
        }

        //  新增：如果 user 为空，手动获取用户信息
        if (!user || !user.email) {
          console.log('[AuthCallback] User info missing, fetching from /me...');
          setMessage('正在获取用户信息...');

          try {
            user = await getCurrentUser(accessToken);
            console.log('[AuthCallback] Fetched user info:', user);
          } catch (err) {
            console.error('[AuthCallback] Failed to fetch user info:', err);
            // 如果获取失败，使用默认值
            user = { email: 'user@example.com', name: '用户' };
          }
        }

        // Step 3: 保存认证信息
        setMessage('正在保存登录状态...');
        setStep(2);

        console.log('[AuthCallback] Setting auth:', {
          accessToken: accessToken?.substring(0, 10) + '...',
          refreshToken: refreshToken?.substring(0, 10) + '...',
          user,
        });

        setAuth({
          accessToken,
          refreshToken,
          user, // [OK] 确保 user 不为空
        });

        await new Promise((resolve) => setTimeout(resolve, 500));

        // 成功
        setStatus('success');
        setMessage(`欢迎回来，${user?.name || user?.email || '用户'}！`);

        console.log('[AuthCallback] Auth successful, redirecting...');
        setTimeout(() => navigate('/', { replace: true }), 1500);
      } catch (e) {
        console.error('[AuthCallback] Error:', e);
        setStatus('error');
        setMessage(e?.response?.data?.error || e?.message || '登录失败，请重试');
        setStep(0);
      }
    }

    handleAuth();
  }, []); // 空依赖数组

  const handleRetry = () => {
    window.location.href = '/'; // 返回首页重新登录
  };

  const handleBack = () => {
    navigate('/', { replace: true });
  };

  const providerInfo = PROVIDER_INFO[provider] || {
    name: '第三方',
    icon: Loader,
    color: '#ffd200',
  };

  const ProviderIcon = providerInfo.icon;

  return (
    <div className={styles.callbackPage}>
      <div className={styles.callbackCard}>
        {/* 状态图标 */}
        <div className={`${styles.iconWrapper} ${styles[status]}`}>
          {status === 'loading' && <Loader size={40} />}
          {status === 'success' && <CheckCircle size={40} />}
          {status === 'error' && <XCircle size={40} />}
        </div>

        {/* 标题 */}
        <h1 className={styles.title}>
          {status === 'loading' && '正在登录...'}
          {status === 'success' && '登录成功！'}
          {status === 'error' && '登录失败'}
        </h1>

        {/* 消息 */}
        <p className={styles.message}>{message}</p>

        {/* 进度条（仅在加载时显示） */}
        {status === 'loading' && (
          <div className={styles.progressBar}>
            <div className={styles.progressFill} />
          </div>
        )}

        {/* 提供商信息 */}
        <div className={styles.providerInfo}>
          <div
            className={styles.providerIcon}
            style={{
              '--provider-color': providerInfo.color,
            }}
          >
            <ProviderIcon size={20} />
          </div>
          <span className={styles.providerName}>通过 {providerInfo.name} 登录</span>
        </div>

        {/* 步骤指示器 */}
        {status === 'loading' && (
          <div className={styles.steps}>
            <div
              className={`${styles.step} ${step >= 0 ? styles.active : ''} ${
                step > 0 ? styles.completed : ''
              }`}
            />
            <div
              className={`${styles.step} ${step >= 1 ? styles.active : ''} ${
                step > 1 ? styles.completed : ''
              }`}
            />
            <div
              className={`${styles.step} ${step >= 2 ? styles.active : ''} ${
                step > 2 ? styles.completed : ''
              }`}
            />
          </div>
        )}

        {/* 操作按钮 */}
        {status === 'error' && (
          <div className={styles.actions}>
            <button onClick={handleRetry} className={styles.retryButton}>
              <RefreshCw size={18} />
              重新登录
            </button>
            <button onClick={handleBack} className={styles.backButton}>
              <ArrowLeft size={18} />
              返回首页
            </button>
          </div>
        )}

        {/* 提示信息 */}
        {status === 'loading' && (
          <div className={styles.hint}>
            首次登录可能需要几秒钟
            <br />
            请耐心等待...
          </div>
        )}

        {status === 'error' && (
          <div className={styles.hint}>
            如果问题持续存在，请联系技术支持
            <br />
            或尝试使用其他登录方式
          </div>
        )}
      </div>
    </div>
  );
}
