// src/components/HelpDock/HelpDock.jsx
import React, { useEffect, useRef } from 'react';
import { HelpCircle, MessageSquare, Mail, Lightbulb, X } from 'lucide-react';
import { useUIStore } from '../../store/ui';
import styles from './HelpDock.module.scss';

const HELP_OPTIONS = [
  {
    id: 'feedback',
    icon: MessageSquare,
    label: '反馈建议',
    description: '告诉我们您的想法',
    action: 'openFeedback',
  },
  {
    id: 'contact',
    icon: Mail,
    label: '联系我',
    description: '获取技术支持',
    action: 'openContact',
  },
  {
    id: 'help',
    icon: Lightbulb,
    label: '使用帮助',
    description: '查看使用指南',
    action: 'openHelp',
  },
];

export default function HelpDock({ collapsed, onToggle }) {
  const { openFeedback, openContact, openHelp } = useUIStore();
  const panelRef = useRef(null);

  const handleAction = (action) => {
    switch (action) {
      case 'openFeedback':
        openFeedback();
        break;
      case 'openContact':
        openContact();
        break;
      case 'openHelp':
        openHelp();
        break;
      default:
        break;
    }
  };

  // [OK] 点击外部关闭
  useEffect(() => {
    if (collapsed) return;
    const handleClickOutside = (e) => {
      if (panelRef.current && !panelRef.current.contains(e.target)) {
        onToggle();
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [collapsed, onToggle]);

  return (
    <div className={`${styles.helpDock} ${collapsed ? styles.collapsed : styles.expanded}`}>
      {collapsed && (
        <button
          className={`${styles.toggleButton} glass-liquid`}
          onClick={onToggle}
          aria-label="打开帮助菜单"
        >
          <HelpCircle size={20} />
        </button>
      )}

      {!collapsed && (
        <div ref={panelRef} className={`${styles.optionsPanel} glass-liquid`}>
          <div className={styles.panelHeader}>
            <HelpCircle size={20} />
            <span>帮助中心</span>
          </div>

          <div className={styles.optionsList}>
            {HELP_OPTIONS.map((option) => {
              const Icon = option.icon;
              return (
                <button
                  key={option.id}
                  className={styles.optionItem}
                  onClick={() => handleAction(option.action)}
                >
                  <div className={styles.optionIcon}>
                    <Icon size={20} />
                  </div>
                  <div className={styles.optionContent}>
                    <div className={styles.optionLabel}>{option.label}</div>
                    <div className={styles.optionDescription}>{option.description}</div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
