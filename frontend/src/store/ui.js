// src/store/ui.js
import { create } from 'zustand';

export const useUIStore = create((set, get) => ({
  theme: localStorage.getItem('theme') || 'system',

  setTheme: (t) => {
    localStorage.setItem('theme', t);
    set({ theme: t });
    const root = document.documentElement;
    if (t === 'system') {
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      root.setAttribute('data-theme', prefersDark ? 'dark' : 'light');
    } else {
      root.setAttribute('data-theme', t);
    }
  },

  navCollapsed: false,
  setNavCollapsed: (v) => set({ navCollapsed: v }),

  commandOpen: false,
  setCommandOpen: (v) => set({ commandOpen: v }),

  authOpen: false,
  setAuthOpen: (v) => set({ authOpen: v }),

  settingsOpen: false,
  openSettings: () => set({ settingsOpen: true }),
  closeSettings: () => set({ settingsOpen: false }),
  toggleSettings: () => set((state) => ({ settingsOpen: !state.settingsOpen })),

  //  新增：个人资料弹窗
  profileOpen: false,
  openProfile: () => set({ profileOpen: true }),
  closeProfile: () => set({ profileOpen: false }),
  toggleProfile: () => set((state) => ({ profileOpen: !state.profileOpen })),
  helpOpen: false,
  contactOpen: false,
  feedbackOpen: false,
  openHelp: () => set({ helpOpen: true }),
  closeHelp: () => set({ helpOpen: false }),

  openContact: () => set({ contactOpen: true }),
  closeContact: () => set({ contactOpen: false }),

  openFeedback: () => set({ feedbackOpen: true }),
  closeFeedback: () => set({ feedbackOpen: false }),
}));
