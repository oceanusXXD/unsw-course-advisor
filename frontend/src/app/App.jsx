import React, { useRef, useState, useEffect } from 'react';
import { Virtuoso } from 'react-virtuoso';
import ChatHistory from '../components/ChatHistory/ChatHistory.jsx';
import ProfilePanel from '../components/ProfilePanel/ProfilePanel.jsx';
import CitationPanel from '../components/CitationPanel/CitationPanel.jsx';
import InputDock from '../components/InputDock/InputDock.jsx';
import HelpDock from '../components/HelpDock/HelpDock.jsx';
import ChatMessage from '../components/ChatMessage/ChatMessage.jsx';
import EmptyState from '../components/EmptyState/EmptyState.jsx';
import AuthModal from '../components/AuthModal/AuthModal.jsx';
import SettingsModal from '../components/SettingsModal/SettingsModal.jsx';
import ProfileModal from '../components/ProfileModal/ProfileModal.jsx';
import HelpModal from '../components/HelpModal/HelpModal.jsx';
import ContactModal from '../components/ContactModal/ContactModal.jsx';
import FeedbackModal from '../components/FeedbackModal/FeedbackModal.jsx';
import { useTabsStore } from '../store/tabs.js';
import { useChatStore } from '../store/chat';
import { useUIStore } from '../store/ui.js';
import { useAuthStore } from '../store/auth.js'; //  新增
import { useChatScroll } from '../hooks/useChatScroll.js';
import styles from './App.module.scss';
import { ArrowDown } from 'lucide-react';

export default function App() {
  const { activeTabId } = useTabsStore();
  const { isGenerating, sendMessage, stopGeneration, getMessages } = useChatStore();
  const { authOpen } = useUIStore();
  const { loaded: authLoaded, user } = useAuthStore(); //  新增

  const messages = getMessages(activeTabId);

  const virtuosoRef = useRef(null);
  const [atBottom, setAtBottom] = useState(true);

  // 左侧面板状态
  const [historyState, setHistoryState] = useState(() => {
    return localStorage.getItem('historyState') || 'expanded';
  });

  // Profile 三态：collapsed(1) / compact(2) / expanded(3)
  const [profileState, setProfileState] = useState(() => {
    return localStorage.getItem('profileState') || 'compact';
  });

  // 右侧面板状态
  const [citationState, setCitationState] = useState(() => {
    return localStorage.getItem('citationPanelState') || 'expanded';
  });

  const [helpState, setHelpState] = useState(() => {
    return localStorage.getItem('helpPanelState') || 'expanded';
  });

  const showEmpty = messages.length === 0;
  const { scrollToBottom } = useChatScroll(virtuosoRef);

  //  修改：初始化流程
  useEffect(() => {
    const initApp = async () => {
      console.log('[App] Initializing app...');

      // 1. 先恢复认证状态
      await useAuthStore.getState().hydrateFromStorage();

      console.log('[App] App initialized');
    };

    initApp();
  }, []);

  //  新增：当 auth 加载完成后，确保聊天数据已初始化
  useEffect(() => {
    if (!authLoaded) return;

    const currentUserId = user?.id ? String(user.id) : 'anonymous';
    const tabsState = useTabsStore.getState();

    // 如果还没有初始化过（比如匿名用户），手动初始化
    if (!tabsState.currentUserId) {
      console.log(`[App] Initializing chat data for ${currentUserId}`);
      const messagesToRestore = tabsState.init(currentUserId);

      if (messagesToRestore) {
        useChatStore.setState({ tabMessages: messagesToRestore });
      }
    }
  }, [authLoaded, user?.id]);

  // --- 联动状态机 ---
  const toggleHistory = () => {
    const next = historyState === 'expanded' ? 'collapsed' : 'expanded';
    setHistoryState(next);
    localStorage.setItem('historyState', next);

    if (next === 'collapsed') {
      if (profileState !== 'collapsed') {
        setProfileState('collapsed');
        localStorage.setItem('profileState', 'collapsed');
      }
    } else {
      if (profileState !== 'compact') {
        setProfileState('compact');
        localStorage.setItem('profileState', 'compact');
      }
    }
  };

  // 保底同步（防外部改写造成的脱节）
  useEffect(() => {
    if (historyState === 'collapsed' && profileState !== 'collapsed') {
      setProfileState('collapsed');
      localStorage.setItem('profileState', 'collapsed');
    }
    if (historyState === 'expanded' && profileState === 'collapsed') {
      setProfileState('compact');
      localStorage.setItem('profileState', 'compact');
    }
  }, [historyState]); // eslint-disable-line

  // Profile 只在 history 展开时在 2/3 间切换
  const cycleProfileState = () => {
    if (historyState === 'collapsed') return; // 锁定 1 形态
    setProfileState((prev) => {
      const next = prev === 'compact' ? 'expanded' : 'compact';
      localStorage.setItem('profileState', next);
      return next;
    });
  };

  const toggleCitationPanel = () => {
    const next = citationState === 'expanded' ? 'collapsed' : 'expanded';
    setCitationState(next);
    localStorage.setItem('citationPanelState', next);
  };

  const toggleHelpPanel = () => {
    const next = helpState === 'expanded' ? 'collapsed' : 'expanded';
    setHelpState(next);
    localStorage.setItem('helpPanelState', next);
  };

  const handleSend = async (text, files, meta) => {
    if (!activeTabId) {
      console.error('[App] No active tab');
      return;
    }
    await sendMessage(activeTabId, text, files, meta);
    setTimeout(scrollToBottom, 100);
  };

  // 这些布尔样式仅用于细节 class（布局靠 CSS 变量驱动）
  const messageWide = historyState === 'collapsed';
  const inputTall = false; // 不再让 input 高度随 Profile 第三态变化，避免上移
  const chatNarrow = citationState === 'expanded';
  const inputNarrow = helpState === 'expanded';

  return (
    <div className={styles.appContainer}>
      <div
        className={`${styles.shell} 
          ${styles[`history-${historyState}`]} 
          ${styles[`profile-${profileState}`]} 
          ${styles[`citation-${citationState}`]} 
          ${styles[`help-${helpState}`]}`}
      >
        {/* 左侧 */}
        <div className={styles.historySlot}>
          <ChatHistory collapsed={historyState === 'collapsed'} onToggle={toggleHistory} />
        </div>

        <aside className={styles.profileSlot}>
          <ProfilePanel state={profileState} onToggle={cycleProfileState} />
        </aside>

        {/* 中间 */}
        <section
          className={`${styles.chatArea} 
            ${messageWide ? styles.messageWide : ''} 
            ${chatNarrow ? styles.chatNarrow : ''}`}
        >
          {showEmpty ? (
            <div className={styles.emptyWrapper}>
              <EmptyState />
            </div>
          ) : (
            <>
              <Virtuoso
                ref={virtuosoRef}
                className={styles.chatFeed}
                data={messages}
                increaseViewportBy={{ top: 300, bottom: 300 }}
                followOutput={isGenerating ? 'smooth' : atBottom ? 'smooth' : false}
                atBottomStateChange={setAtBottom}
                itemContent={(index, item) => (
                  <div className={styles.messageWrapper}>
                    <ChatMessage
                      key={item.id}
                      message={item}
                      isStreaming={isGenerating && index === messages.length - 1}
                    />
                  </div>
                )}
              />
              <div className={`${styles.scrollHint} ${atBottom ? styles.hidden : ''}`}>
                <button className={`${styles.backToLatest} glass-liquid`} onClick={scrollToBottom}>
                  <ArrowDown size={16} /> 回到最新
                </button>
              </div>
            </>
          )}
        </section>

        <div
          className={`${styles.inputSlot} 
            ${messageWide ? styles.messageWide : ''} 
            ${inputTall ? styles.inputTall : ''} 
            ${inputNarrow ? styles.inputNarrow : ''}`}
        >
          <InputDock
            onSend={handleSend}
            onStop={() => stopGeneration()}
            generating={isGenerating}
          />
        </div>

        {/* 右侧 */}
        <aside className={styles.citationSlot}>
          <CitationPanel collapsed={citationState === 'collapsed'} onToggle={toggleCitationPanel} />
        </aside>

        <aside className={styles.helpSlot}>
          <HelpDock collapsed={helpState === 'collapsed'} onToggle={toggleHelpPanel} />
        </aside>
      </div>

      {authOpen && <AuthModal />}
      <SettingsModal />
      <ProfileModal />
      <HelpModal />
      <ContactModal />
      <FeedbackModal />
    </div>
  );
}
