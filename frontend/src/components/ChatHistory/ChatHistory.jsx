import React, { useState } from 'react';
import { useTabsStore } from '../../store/tabs.js';
import {
  Plus,
  Search,
  MessageSquare,
  Pin,
  Grid3x3,
  List,
  Filter,
  Clock,
  Star,
  X,
  ChevronLeft,
  ChevronRight,
  Trash2,
  Edit2,
  Square,
  CheckSquare,
} from 'lucide-react';
import styles from './ChatHistory.module.scss';
import '../../styles/glass.css';

export default function ChatHistory({ collapsed, onToggle }) {
  const { tabs, activeTabId, setActive, create, remove, togglePin, updateTitle } = useTabsStore();

  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState(() => localStorage.getItem('chatViewMode') || 'grid');
  const [filterMode, setFilterMode] = useState('all');
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [editTitle, setEditTitle] = useState('');
  const [batchMode, setBatchMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState(new Set());

  const toggleViewMode = () => {
    const nextMode = viewMode === 'grid' ? 'list' : 'grid';
    setViewMode(nextMode);
    localStorage.setItem('chatViewMode', nextMode);
  };

  const handleDelete = (id, e) => {
    e.stopPropagation();
    setDeleteConfirm(id);
  };

  const confirmDelete = () => {
    if (deleteConfirm) {
      if (Array.isArray(deleteConfirm)) {
        deleteConfirm.forEach((id) => remove(id));
        setSelectedIds(new Set());
        setBatchMode(false);
      } else {
        remove(deleteConfirm);
      }
      setDeleteConfirm(null);
    }
  };

  const handleTogglePin = (id, e) => {
    e.stopPropagation();
    togglePin(id);
  };

  const startEdit = (tab, e) => {
    e.stopPropagation();
    setEditingId(tab.id);
    setEditTitle(tab.title || '');
  };

  const saveTitle = (id) => {
    if (editTitle.trim()) {
      updateTitle(id, editTitle.trim());
    }
    setEditingId(null);
    setEditTitle('');
  };

  const toggleBatchMode = () => {
    setBatchMode(!batchMode);
    setSelectedIds(new Set());
  };

  const toggleSelect = (id, e) => {
    e.stopPropagation();
    const newSelected = new Set(selectedIds);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelectedIds(newSelected);
  };

  const selectAll = () => {
    const allIds = new Set(filteredTabs.map((t) => t.id));
    setSelectedIds(allIds);
  };

  const deselectAll = () => {
    setSelectedIds(new Set());
  };

  const handleBatchDelete = () => {
    if (selectedIds.size > 0) {
      setDeleteConfirm(Array.from(selectedIds));
    }
  };

  const handleCardClick = (tab) => {
    if (batchMode) {
      toggleSelect(tab.id, { stopPropagation: () => {} });
    } else {
      setActive(tab.id);
    }
  };

  const filteredTabs = (tabs || [])
    .filter((t) => {
      if (searchQuery && !(t.title || '').toLowerCase().includes(searchQuery.toLowerCase())) {
        return false;
      }
      if (filterMode === 'pinned' && !t.pinned) return false;
      if (filterMode === 'recent') {
        const oneDayAgo = Date.now() - 24 * 60 * 60 * 1000;
        return t.updatedAt > oneDayAgo;
      }
      return true;
    })
    .sort((a, b) => {
      if (a.pinned && !b.pinned) return -1;
      if (!a.pinned && b.pinned) return 1;
      return (b.updatedAt || 0) - (a.updatedAt || 0);
    });

  const allSelected = filteredTabs.length > 0 && selectedIds.size === filteredTabs.length;

  if (collapsed) {
    return (
      <div className={`${styles.chatHistoryCollapsed} glass-liquid`}>
        <button className={`${styles.expandBtn} glass-btn`} onClick={onToggle} title="展开对话列表">
          <ChevronRight size={20} />
        </button>
        <div className={styles.collapsedTabs}>
          {tabs.slice(0, 5).map((tab) => (
            <button
              key={tab.id}
              className={`${styles.miniTabBtn} glass-btn ${
                tab.id === activeTabId ? styles.active : ''
              }`}
              onClick={() => setActive(tab.id)}
              title={tab.title || '未命名对话'}
            >
              <MessageSquare size={18} />
              {tab.pinned && <Star size={8} className={styles.miniStar} fill="currentColor" />}
            </button>
          ))}
        </div>
        <button className={styles.miniNewBtn} onClick={() => create('新对话')} title="新建对话">
          <Plus size={18} />
        </button>
      </div>
    );
  }

  return (
    <div className={`${styles.chatHistory} glass-liquid`}>
      <div className={styles.header}>
        {!batchMode ? (
          <>
            <button className={`${styles.newChatBtn} btn primary`} onClick={() => create('新对话')}>
              <Plus size={18} />
              <span>新建对话</span>
            </button>
            <div className={styles.headerActions}>
              <button className="btn icon" onClick={toggleBatchMode} title="批量管理">
                <CheckSquare size={16} />
              </button>
              <button
                className="btn icon"
                onClick={toggleViewMode}
                title={viewMode === 'grid' ? '切换到列表视图' : '切换到卡片视图'}
              >
                {viewMode === 'grid' ? <List size={16} /> : <Grid3x3 size={16} />}
              </button>
              <button className="btn icon" onClick={onToggle} title="收起">
                <ChevronLeft size={16} />
              </button>
            </div>
          </>
        ) : (
          <>
            <div className={styles.batchHeader}>
              <button className="btn ghost" onClick={toggleBatchMode}>
                <X size={18} />
                <span>取消</span>
              </button>
              <span className={styles.selectedCount}>已选 {selectedIds.size} 项</span>
            </div>
            <div className={styles.batchActions}>
              <button
                className="btn icon"
                onClick={allSelected ? deselectAll : selectAll}
                title={allSelected ? '取消全选' : '全选'}
              >
                {allSelected ? <CheckSquare size={16} /> : <Square size={16} />}
              </button>
              <button
                className="btn icon danger"
                onClick={handleBatchDelete}
                disabled={selectedIds.size === 0}
                title="删除选中"
              >
                <Trash2 size={16} />
              </button>
            </div>
          </>
        )}
      </div>

      <div className={styles.searchBox}>
        <Search size={16} className={styles.searchIcon} />
        <input
          type="text"
          placeholder="搜索对话..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className={`${styles.searchInput} glass-input`}
        />
        {searchQuery && (
          <button className={styles.clearBtn} onClick={() => setSearchQuery('')}>
            <X size={14} />
          </button>
        )}
      </div>

      <div className={styles.filterTabs}>
        <button
          className={`${styles.filterTab} glass-tab ${filterMode === 'all' ? 'active' : ''}`}
          onClick={() => setFilterMode('all')}
        >
          <Filter size={14} />
          <span className={styles.tabText}>
            全部 <span className={styles.count}>({tabs.length})</span>
          </span>
        </button>
        <button
          className={`${styles.filterTab} glass-tab ${filterMode === 'pinned' ? 'active' : ''}`}
          onClick={() => setFilterMode('pinned')}
        >
          <Pin size={14} />
          <span className={styles.tabText}>
            置顶 <span className={styles.count}>({tabs.filter((t) => t.pinned).length})</span>
          </span>
        </button>
        <button
          className={`${styles.filterTab} glass-tab ${filterMode === 'recent' ? 'active' : ''}`}
          onClick={() => setFilterMode('recent')}
        >
          <Clock size={14} />
          <span className={styles.tabText}>最近</span>
        </button>
      </div>

      <div
        className={`${styles.tabList} ${viewMode === 'list' ? styles.listMode : styles.gridMode}`}
      >
        {filteredTabs.length === 0 ? (
          <div className={styles.emptyState}>
            <MessageSquare size={48} className={styles.emptyIcon} />
            <p>暂无对话</p>
            <span>开始一个新的对话吧 [Result]</span>
          </div>
        ) : (
          filteredTabs.map((tab) => (
            <div
              key={tab.id}
              className={`${styles.tabCard} glass-card ${
                tab.id === activeTabId && !batchMode ? 'active' : ''
              } ${tab.pinned ? styles.pinned : ''} ${
                viewMode === 'list' ? styles.listCard : styles.gridCard
              } ${batchMode ? styles.selectable : ''} ${
                selectedIds.has(tab.id) ? styles.selected : ''
              }`}
              onClick={() => handleCardClick(tab)}
            >
              {batchMode && (
                <div className={styles.checkbox} onClick={(e) => toggleSelect(tab.id, e)}>
                  {selectedIds.has(tab.id) ? (
                    <CheckSquare size={20} className={styles.checked} />
                  ) : (
                    <Square size={20} />
                  )}
                </div>
              )}
              <div className={styles.tabIcon}>
                <MessageSquare size={viewMode === 'grid' ? 20 : 18} />
              </div>
              <div className={styles.tabContent}>
                {editingId === tab.id ? (
                  <input
                    type="text"
                    className={`${styles.editTitleInput} glass-input`}
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    onBlur={() => saveTitle(tab.id)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') saveTitle(tab.id);
                      if (e.key === 'Escape') {
                        setEditingId(null);
                        setEditTitle('');
                      }
                    }}
                    onClick={(e) => e.stopPropagation()}
                    autoFocus
                  />
                ) : (
                  <div className={styles.titleRow}>
                    {tab.pinned && (
                      <Star size={12} className={styles.pinIcon} fill="currentColor" />
                    )}
                    <span className={styles.tabTitle}>{tab.title || '未命名对话'}</span>
                  </div>
                )}
                {viewMode === 'grid' && (
                  <span className={styles.tabMeta}>
                    {tab.messageCount || 0} 条消息 · {formatTime(tab.updatedAt)}
                  </span>
                )}
              </div>
              {!batchMode && (
                <div className={styles.tabActions}>
                  <button
                    className={`${styles.actionBtn} glass-btn ${
                      tab.pinned ? styles.pinnedBtn : ''
                    }`}
                    onClick={(e) => handleTogglePin(tab.id, e)}
                    title={tab.pinned ? '取消置顶' : '置顶'}
                  >
                    <Pin size={16} fill={tab.pinned ? 'currentColor' : 'none'} />
                  </button>
                  <button
                    className={`${styles.actionBtn} glass-btn`}
                    onClick={(e) => startEdit(tab, e)}
                    title="重命名"
                  >
                    <Edit2 size={16} />
                  </button>
                  <button
                    className={`${styles.actionBtn} glass-btn ${styles.dangerBtn}`}
                    onClick={(e) => handleDelete(tab.id, e)}
                    title="删除"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              )}
              {tab.id === activeTabId && !batchMode && <div className={styles.activeIndicator} />}
            </div>
          ))
        )}
      </div>

      {deleteConfirm && (
        <div className={styles.modalOverlay} onClick={() => setDeleteConfirm(null)}>
          <div
            className={`${styles.confirmDialog} glass-liquid`}
            onClick={(e) => e.stopPropagation()}
          >
            <div className={styles.dialogIcon}>
              <Trash2 size={28} />
            </div>
            <h3>确认删除</h3>
            <p>
              {Array.isArray(deleteConfirm)
                ? `确定要删除 ${deleteConfirm.length} 个对话吗？`
                : '确定要删除这个对话吗？'}
              <br />
              此操作无法撤销
            </p>
            <div className={styles.dialogActions}>
              <button className="btn secondary" onClick={() => setDeleteConfirm(null)}>
                取消
              </button>
              <button className="btn danger" onClick={confirmDelete}>
                删除
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function formatTime(timestamp) {
  if (!timestamp) return '刚刚';
  const now = Date.now();
  const diff = now - timestamp;
  const minute = 60 * 1000;
  const hour = 60 * minute;
  const day = 24 * hour;

  if (diff < minute) return '刚刚';
  if (diff < hour) return `${Math.floor(diff / minute)} 分钟前`;
  if (diff < day) return `${Math.floor(diff / hour)} 小时前`;
  if (diff < 7 * day) return `${Math.floor(diff / day)} 天前`;
  return new Date(timestamp).toLocaleDateString();
}
