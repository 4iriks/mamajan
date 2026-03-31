import { create } from 'zustand';

type Theme = 'dark' | 'light';

interface ThemeState {
  theme: Theme;
  toggle: () => void;
}

const getInitial = (): Theme => {
  try {
    const saved = localStorage.getItem('raluma-theme');
    if (saved === 'light' || saved === 'dark') return saved;
  } catch { /* localStorage unavailable */ }
  return 'light';
};

const applyTheme = (theme: Theme) => {
  document.documentElement.classList.toggle('light', theme === 'light');
  try { localStorage.setItem('raluma-theme', theme); } catch { /* localStorage unavailable */ }
};

// Apply on load
applyTheme(getInitial());

export const useThemeStore = create<ThemeState>((set) => ({
  theme: getInitial(),
  toggle: () => set(state => {
    const next: Theme = state.theme === 'dark' ? 'light' : 'dark';
    applyTheme(next);
    return { theme: next };
  }),
}));
