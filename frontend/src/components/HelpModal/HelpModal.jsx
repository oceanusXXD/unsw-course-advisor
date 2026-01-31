// src/components/HelpModal/HelpModal.jsx
import React, { useState } from 'react';
import { X, HelpCircle, ChevronDown } from 'lucide-react';
import { useUIStore } from '../../store/ui';
import styles from './HelpModal.module.scss';

const FAQ_DATA = [
  {
    id: 'how-to-use',
    question: '如何开始使用 Course Advisor？',
    answer:
      '1. 首先点击左侧"新对话"创建一个新的对话\n2. 在个人资料中填写你的专业代码（如COMPA1）和目标学期\n3. 输入你已经修过的课程\n4. 开始询问课程推荐或任何学习规划相关的问题',
  },
  {
    id: 'course-recommend',
    question: '如何获得个性化的课程推荐？',
    answer:
      '系统会根据以下信息为你推荐课程：\n• 你的专业和学位要求\n• 已修课程和先修要求\n• 当前学期的可选课程\n• 你的学习目标和兴趣方向\n\n请确保在个人资料中填写完整信息以获得更准确的推荐。',
  },
  {
    id: 'student-profile',
    question: '为什么需要填写学生档案？',
    answer:
      '学生档案帮助系统了解你的学习情况，包括：\n• 专业代码：确定你的学位要求\n• 已修课程：避免重复选课，检查先修要求\n• 目标学期：推荐当前可选的课程\n• WAM/UOC：评估学业负担和选课建议',
  },
  {
    id: 'file-upload',
    question: '可以上传什么类型的文件？',
    answer:
      '支持上传以下类型的文件：\n• PDF格式的成绩单\n• 课程大纲或Handbook页面截图\n• 学习计划表格\n• 其他相关的学习文档\n\n文件大小限制为10MB。',
  },
  {
    id: 'citation-panel',
    question: '右侧的引用面板是什么？',
    answer:
      '引用面板显示对话中提到的课程详细信息：\n• 课程代码和名称\n• 学分（UOC）\n• 开课学期\n• 先修要求\n• 课程描述\n\n点击课程可以查看更多详情或访问官方Handbook页面。',
  },
  {
    id: 'chat-history',
    question: '如何管理我的对话历史？',
    answer:
      '在左侧对话历史中你可以：\n• 切换不同的对话\n• 重命名对话标题\n• 删除不需要的对话\n• 搜索历史对话\n\n所有对话都会自动保存在本地。',
  },
  {
    id: 'shortcuts',
    question: '有哪些快捷键可以使用？',
    answer:
      '常用快捷键：\n• Enter - 发送消息\n• Shift + Enter - 换行\n• Ctrl/Cmd + K - 清空输入框\n• Ctrl/Cmd + / - 打开快捷键列表\n• Esc - 关闭弹窗',
  },
  {
    id: 'data-privacy',
    question: '我的数据安全吗？',
    answer:
      '我们非常重视数据安全：\n• 所有对话数据都保存在本地浏览器中\n• 不会未经允许分享你的个人信息\n• 你可以随时清除本地数据\n• 使用端到端加密保护敏感信息',
  },
];

export default function HelpModal() {
  const { helpOpen, closeHelp } = useUIStore();
  const [expandedItems, setExpandedItems] = useState(new Set());

  const toggleItem = (id) => {
    setExpandedItems((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(id)) {
        newSet.delete(id);
      } else {
        newSet.add(id);
      }
      return newSet;
    });
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') {
      closeHelp();
    }
  };

  React.useEffect(() => {
    if (helpOpen) {
      document.addEventListener('keydown', handleKeyDown);
      return () => {
        document.removeEventListener('keydown', handleKeyDown);
      };
    }
  }, [helpOpen]); // 添加helpOpen作为依赖

  if (!helpOpen) return null;

  if (!helpOpen) return null;

  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget) {
      closeHelp();
    }
  };
  return (
    <div className={styles.modalOverlay} onClick={handleOverlayClick}>
      <div className={styles.modalContainer}>
        {/* Header */}
        <div className={styles.modalHeader}>
          <div className={styles.headerLeft}>
            <div className={styles.iconWrapper}>
              <HelpCircle size={24} />
            </div>
            <div className={styles.headerText}>
              <h2 className={styles.modalTitle}>常见问题</h2>
              <p className={styles.modalSubtitle}>快速了解如何使用 Course Advisor</p>
            </div>
          </div>
          <button className={styles.closeBtn} onClick={closeHelp}>
            <X size={20} />
          </button>
        </div>

        {/* Body */}
        <div className={styles.modalBody}>
          <div className={styles.faqList}>
            {FAQ_DATA.map((item) => {
              const isExpanded = expandedItems.has(item.id);
              return (
                <div key={item.id} className={styles.faqItem}>
                  <button
                    className={`${styles.faqQuestion} ${isExpanded ? styles.expanded : ''}`}
                    onClick={() => toggleItem(item.id)}
                  >
                    <span>{item.question}</span>
                    <ChevronDown
                      size={20}
                      className={`${styles.chevron} ${isExpanded ? styles.rotated : ''}`}
                    />
                  </button>
                  <div className={`${styles.faqAnswer} ${isExpanded ? styles.expanded : ''}`}>
                    <div className={styles.answerContent}>
                      {item.answer.split('\n').map((line, index) => (
                        <p key={index}>{line}</p>
                      ))}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Footer Tip */}
          <div className={styles.footerTip}>
            <p>没有找到答案？点击右下角的&quot;反馈建议&quot;告诉我们！</p>
          </div>
        </div>
      </div>
    </div>
  );
}
