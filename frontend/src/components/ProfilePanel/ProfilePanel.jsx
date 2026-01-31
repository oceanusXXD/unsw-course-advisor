import React, { useMemo, useCallback, useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../../store/auth.js';
import { useUIStore } from '../../store/ui.js';
import {
  User,
  Settings,
  LogOut,
  FileText,
  ChevronDown,
  Zap,
  TrendingUp,
  Sun,
  Moon,
  Monitor,
} from 'lucide-react';
import styles from './ProfilePanel.module.scss';
import '../../styles/glass.css';

const THEME_ICONS = { light: Sun, dark: Moon, system: Monitor };
const THEMES = ['light', 'dark', 'system'];

/**
 * 尝试从各种可能的 store 返回结构中提取实际的 user 对象
 * 支持形如： user, { user: {...} }, { data: {...} }, { profile: {...} } 等
 */
function extractUser(raw) {
  if (!raw) return null;
  // 如果就是一个 user-like 对象（包含 email 或 username 或 id）
  if (typeof raw === 'object' && (raw.email || raw.username || raw.id)) {
    return raw;
  }
  // 常见包装字段
  const candidates = ['user', 'data', 'profile', 'currentUser'];
  for (const key of candidates) {
    if (raw[key]) {
      return extractUser(raw[key]);
    }
  }
  return null;
}

const Avatar = ({ size = 'compact', onClick, onMouseEnter, onMouseLeave, innerRef }) => (
  <div
    ref={innerRef}
    className={styles[`avatar${size === 'large' ? 'Large' : 'Compact'}`]}
    onClick={onClick}
    onMouseEnter={onMouseEnter}
    onMouseLeave={onMouseLeave}
  >
    <User size={size === 'large' ? 32 : size === 'collapsed' ? 56 : 28} />
    {size === 'large' && <div className={styles.statusDot} />}
  </div>
);

const UserStats = ({ stats = { days: 28, conversations: 156 } }) => (
  <div className={styles.userStats}>
    <div className={styles.statItem}>
      <Zap size={14} />
      <span>{stats.days} 天</span>
    </div>
    <div className={styles.statDivider} />
    <div className={styles.statItem}>
      <TrendingUp size={14} />
      <span>{stats.conversations} 对话</span>
    </div>
  </div>
);

const ActionButton = ({ icon: Icon, label, onClick, title }) => (
  <button className={styles.actionBtn} onClick={onClick} title={title} aria-label={label}>
    <Icon size={18} />
    <span>{label}</span>
  </button>
);

const HoverMenu = ({ actions, isVisible, onMouseEnter, onMouseLeave, menuRef }) => (
  <div
    ref={menuRef}
    className={`${styles.hoverMenu} ${isVisible ? styles.visible : ''} glass-menu`}
    onMouseEnter={onMouseEnter}
    onMouseLeave={onMouseLeave}
  >
    {actions.map((action, index) => (
      <button
        key={index}
        className={styles.hoverMenuItem}
        onClick={(e) => {
          e.stopPropagation();
          action.onClick();
        }}
        title={action.title}
      >
        <action.icon size={16} />
        <span>{action.label}</span>
      </button>
    ))}
  </div>
);

export default function ProfilePanel({ state = 'expanded', onToggle }) {
  const navigate = useNavigate();
  // 不直接解构，而是取到整个 store 实例以便兼容多种返回结构
  const authStore = useAuthStore();
  const uiStore = useUIStore();

  // 尝试从 store 中拿 logout（不同实现可能叫 signOut 等）
  const logout = authStore?.logout ?? authStore?.signOut ?? authStore?.sign_off ?? (() => {});
  // UI actions
  const { theme, setTheme, setAuthOpen, openSettings, openProfile } = uiStore ?? {};

  // 本地状态：用于稳定显示，避免 render 时访问到 undefined
  const [localUser, setLocalUser] = useState(() => extractUser(authStore));
  const [showHoverMenu, setShowHoverMenu] = useState(false);
  const hoverTimeoutRef = useRef(null);
  const menuRef = useRef(null);
  const avatarRef = useRef(null);

  // 主题图标
  const ThemeIcon = useMemo(() => THEME_ICONS[theme] || Monitor, [theme]);

  // 当 store 改变时同步 localUser（处理异步加载）
  useEffect(() => {
    const u = extractUser(authStore);
    setLocalUser(u);
  }, [authStore]);

  // displayName / email 都从 localUser 安全读取（不会造成 undefined 报错）
  const displayName = useMemo(() => {
    if (!localUser) return '用户';
    // 优先顺序：display name 字段 -> username -> email -> id -> 用户
    return (
      localUser.name ||
      localUser.displayName ||
      localUser.username ||
      localUser.email ||
      `用户${localUser.id ?? ''}` ||
      '用户'
    );
  }, [localUser]);

  const userEmail = useMemo(() => {
    return localUser?.email ?? '';
  }, [localUser]);

  const cycleTheme = useCallback(() => {
    const currentIndex = THEMES.indexOf(theme);
    const nextTheme = THEMES[(currentIndex + 1) % THEMES.length];
    setTheme?.(nextTheme);
    setShowHoverMenu(false);
  }, [theme, setTheme]);

  const handleLogout = useCallback(() => {
    if (window.confirm('确定要退出登录吗？')) {
      logout();
      setShowHoverMenu(false);
    }
  }, [logout]);

  const actions = useMemo(
    () => [
      {
        icon: FileText,
        label: '资料',
        onClick: () => {
          openProfile?.();
          setShowHoverMenu(false);
        },
        title: '个人资料设置',
      },
      {
        icon: ThemeIcon,
        label: '主题',
        onClick: cycleTheme,
        title: `当前: ${theme}`,
      },
      {
        icon: Settings,
        label: '设置',
        onClick: () => {
          openSettings?.();
          setShowHoverMenu(false);
        },
        title: '系统设置',
      },
      {
        icon: LogOut,
        label: '退出',
        onClick: handleLogout,
        title: '退出登录',
      },
    ],
    [ThemeIcon, cycleTheme, theme, openProfile, openSettings, handleLogout],
  );

  // 悬浮菜单 hover 管理（同你原来的逻辑）
  const handleMouseEnter = useCallback(
    (e) => {
      if (state === 'expanded' || e.buttons === 1) return;
      clearTimeout(hoverTimeoutRef.current);
      hoverTimeoutRef.current = setTimeout(() => setShowHoverMenu(true), 200);
    },
    [state],
  );

  const handleMouseLeave = useCallback((e) => {
    clearTimeout(hoverTimeoutRef.current);
    hoverTimeoutRef.current = setTimeout(() => {
      if (!e.relatedTarget || !e.currentTarget.contains(e.relatedTarget)) {
        setShowHoverMenu(false);
      }
    }, 250);
  }, []);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (
        showHoverMenu &&
        menuRef.current &&
        avatarRef.current &&
        !menuRef.current.contains(event.target) &&
        !avatarRef.current.contains(event.target)
      ) {
        setShowHoverMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [showHoverMenu]);

  useEffect(() => {
    return () => clearTimeout(hoverTimeoutRef.current);
  }, []);

  // 未登录（localUser 为空时显示占位并触发登录）
  if (!localUser) {
    return (
      <div
        className={`${styles.profileCompact} glass-liquid`}
        onClick={() => setAuthOpen?.(true)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && setAuthOpen?.(true)}
        aria-label="登录或注册"
        style={{ width: '100%' }}
      >
        <Avatar size="compact" />
        <div className={styles.compactInfo}>
          <span className={styles.compactId}>登录 / 注册</span>
          <span className={styles.compactEmail} />
        </div>
      </div>
    );
  }

  // 折叠模式（collapsed）
  if (state === 'collapsed') {
    return (
      <div className={styles.profileWrapper}>
        <Avatar
          size="collapsed"
          innerRef={avatarRef}
          onClick={() => {
            setShowHoverMenu(false);
            onToggle();
          }}
          onMouseEnter={handleMouseEnter}
          onMouseLeave={handleMouseLeave}
        />
        <HoverMenu
          menuRef={menuRef}
          actions={actions}
          isVisible={showHoverMenu}
          onMouseEnter={handleMouseEnter}
          onMouseLeave={handleMouseLeave}
        />
      </div>
    );
  }

  // 紧凑模式（compact）
  if (state === 'compact') {
    const handleCompactActivate = () => {
      setShowHoverMenu(false);
      onToggle();
    };
    const handleCompactKey = (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        handleCompactActivate();
      }
    };

    return (
      <div className={styles.profileWrapper}>
        <div
          className={`${styles.profileCompact} glass-liquid`}
          role="button"
          tabIndex={0}
          aria-expanded="false"
          onClick={handleCompactActivate}
          onKeyDown={handleCompactKey}
          style={{ width: '100%' }}
        >
          <Avatar
            size="compact"
            innerRef={avatarRef}
            onMouseEnter={handleMouseEnter}
            onMouseLeave={handleMouseLeave}
          />
          <div className={styles.compactInfo}>
            <span className={styles.compactId} title={displayName}>
              {displayName}
            </span>
            <span className={styles.compactEmail} title={userEmail}>
              {userEmail || '—'}
            </span>
          </div>
        </div>
        <HoverMenu
          menuRef={menuRef}
          actions={actions}
          isVisible={showHoverMenu}
          onMouseEnter={handleMouseEnter}
          onMouseLeave={handleMouseLeave}
        />
      </div>
    );
  }

  // 展开模式（expanded）
  return (
    <div className={`${styles.profilePanel} glass-liquid`} role="region" aria-label="个人中心">
      <div className={styles.userCard}>
        <Avatar size="large" />
        <div className={styles.userInfo}>
          <h3 className={styles.userName}>{displayName}</h3>
          <p className={styles.userEmail}>{userEmail || '未提供邮箱'}</p>
          <UserStats />
        </div>
        <button
          className={styles.collapseBtn}
          onClick={onToggle}
          title="收起"
          aria-label="收起个人信息"
          aria-expanded="true"
        >
          <ChevronDown size={16} />
        </button>
      </div>

      <nav className={styles.actionGrid} aria-label="快捷操作">
        {actions.map((action, index) => (
          <ActionButton key={index} {...action} />
        ))}
      </nav>
    </div>
  );
}
