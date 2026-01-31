import React, { useState, useEffect } from 'react';
import styles from './EmptyState.module.scss';
import '../../styles/glass.css';
import { Search, BookOpen, Compass } from 'lucide-react';

// 将多组预设合并为一个数组
const ALL_PRESETS = [
  {
    icon: <Search />,
    title: '课程查询',
    desc: '介绍一下COMP9517',
    gradient: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
  },
  {
    icon: <Compass />,
    title: '选课建议',
    desc: '推荐几个COMPIH的课',
    gradient: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
  },

  {
    icon: <BookOpen />,
    title: '先修查询',
    desc: 'COMP9444的先修要求',
    gradient: 'linear-gradient(135deg, #30cfd0 0%, #330867 100%)',
  },
];

export default function EmptyState() {
  const [highlightIndex, setHighlightIndex] = useState(-1);

  // 空闲时间检测和边框闪烁
  useEffect(() => {
    let idleTimer;
    let flashTimer;

    const resetIdle = () => {
      setHighlightIndex(-1);
      clearTimeout(idleTimer);
      clearInterval(flashTimer);

      idleTimer = setTimeout(() => {
        // 7秒后开始闪烁
        flashTimer = setInterval(() => {
          // 在所有9个卡片中随机选择
          const newIndex = Math.floor(Math.random() * ALL_PRESETS.length);
          setHighlightIndex(newIndex);
        }, 3000);
      }, 7000);
    };

    // 监听用户活动
    const events = ['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart'];
    events.forEach((event) => document.addEventListener(event, resetIdle));
    resetIdle();

    return () => {
      events.forEach((event) => document.removeEventListener(event, resetIdle));
      clearTimeout(idleTimer);
      clearInterval(flashTimer);
    };
  }, []);

  const handleCardClick = (desc) => {
    window.dispatchEvent(
      new CustomEvent('app:quickSend', {
        detail: { text: desc, meta: { source: 'empty-preset' } },
        bubbles: true,
      }),
    );
  };

  return (
    <div className={styles.container}>
      {/* 大标题 */}
      <div className={styles.hero}>
        <h1 className={styles.welcomeText}>WELCOME TO</h1>
        <h2 className={styles.brandName}>UNSW Course Advisor</h2>
      </div>

      {/* 预设卡片组 */}
      <div className={styles.cardsGrid}>
        {ALL_PRESETS.map((preset, i) => (
          <button
            key={preset.title} // 使用唯一的title作为key
            className={`${styles.presetCard} ${styles.fadeIn} ${
              highlightIndex === i ? styles.highlight : ''
            }`}
            onClick={() => handleCardClick(preset.desc)}
            style={{ '--delay': `${i * 0.05}s` }} // 减小延迟让动画更快
          >
            <div className={styles.iconBox} style={{ background: preset.gradient }}>
              {preset.icon}
            </div>
            <h3 className={styles.cardTitle}>{preset.title}</h3>
            <p className={styles.cardDesc}>{preset.desc}</p>
          </button>
        ))}
      </div>
    </div>
  );
}
