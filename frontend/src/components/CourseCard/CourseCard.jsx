import React from 'react';
import styles from './CourseCard.module.scss';
import '../../styles/glass.css';

export default function CourseCard({ course, index }) {
  return (
    <div className={`${styles.card} glass-card`} style={{ scrollSnapAlign: 'start' }}>
      <div className={styles.head}>
        <strong>{course.code}</strong>
        <span className={styles.uoc}>{course.uoc} UOC</span>
      </div>
      <div className={styles.title}>{course.name}</div>
      <div className={styles.meta}>
        <span>学期 {course.term}</span>
        <span>先修 {course.prereq}</span>
      </div>
      <p className={styles.brief}>{course.brief}</p>
      <div className={styles.actions}>
        <button className="btn">加入对比</button>
        <button className="btn">加入规划</button>
        <button className="btn">详情</button>
        <button className="btn" onClick={() => navigator.clipboard?.writeText(`#${course.code}`)}>
          复制链接
        </button>
      </div>
      <div className={styles.source}>
        来源: {course.source} [{index + 1}]
      </div>
    </div>
  );
}
