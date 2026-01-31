// src/components/SettingsModal/TabNav.jsx
import React from 'react';
import { Palette, Shield, Key, Lock, Trash2 } from 'lucide-react';
import styles from './styles/SettingsModal.module.scss';

const tabs = [
  { key: 'appearance', label: '外观', icon: Palette },
  { key: 'security', label: '安全', icon: Shield },
  { key: 'license', label: '许可证', icon: Key },
  { key: 'crypto', label: '加解密', icon: Lock },
  { key: 'account', label: '账户', icon: Trash2 },
];

export default function TabNav({ activeTab, onChange }) {
  return (
    <nav className={styles.tabNav}>
      {tabs.map((tab) => {
        const Icon = tab.icon;
        return (
          <button
            key={tab.key}
            className={`${styles.tabBtn} ${activeTab === tab.key ? styles.active : ''}`}
            onClick={() => onChange(tab.key)}
          >
            <Icon size={18} />
            <span>{tab.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
