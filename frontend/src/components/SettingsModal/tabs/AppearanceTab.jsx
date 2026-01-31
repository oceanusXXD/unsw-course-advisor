// src/components/SettingsModal/tabs/AppearanceTab.jsx
import React from 'react';
import { useUIStore } from '../../../store/ui';
import { Sun, Moon, Monitor, Check, Palette } from 'lucide-react';
import styles from '../styles/SettingsModal.module.scss';

const themes = [
  { key: 'light', label: '浅色', icon: Sun, desc: '明亮清爽，适合白天使用' },
  { key: 'dark', label: '深色', icon: Moon, desc: '护眼模式，适合夜间使用' },
  { key: 'system', label: '跟随系统', icon: Monitor, desc: '自动切换，跟随系统设置' },
];

export default function AppearanceTab() {
  const { theme, setTheme } = useUIStore();

  const handleThemeChange = (newTheme) => {
    document.documentElement.classList.add('theme-transition');
    setTheme(newTheme);
    setTimeout(() => {
      document.documentElement.classList.remove('theme-transition');
    }, 300);
  };

  return (
    <section className={styles.section}>
      <h3 className={styles.sectionTitle}>
        <Palette size={20} />
        外观设置
      </h3>
      <div className={styles.themeGrid}>
        {themes.map((t) => {
          const Icon = t.icon;
          return (
            <button
              key={t.key}
              className={`${styles.themeCard} ${theme === t.key ? styles.active : ''}`}
              onClick={() => handleThemeChange(t.key)}
            >
              <Icon size={24} />
              <strong>{t.label}</strong>
              <p>{t.desc}</p>
              {theme === t.key && (
                <div className={styles.checkMark}>
                  <Check size={16} />
                </div>
              )}
            </button>
          );
        })}
      </div>
    </section>
  );
}
