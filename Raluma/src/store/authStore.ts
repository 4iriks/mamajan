import { create } from 'zustand';
import { UserMe } from '../api/auth';

interface AuthState {
  user: UserMe | null;
  token: string | null;
  setAuth: (token: string, user: UserMe) => void;
  clearAuth: () => void;
  isAdmin: () => boolean;
  isSuperAdmin: () => boolean;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  token: localStorage.getItem('access_token'),

  setAuth: (token, user) => {
    localStorage.setItem('access_token', token);
    set({ token, user });
  },

  clearAuth: () => {
    localStorage.removeItem('access_token');
    set({ token: null, user: null });
  },

  isAdmin: () => {
    const role = get().user?.role;
    return role === 'admin' || role === 'superadmin';
  },

  isSuperAdmin: () => get().user?.role === 'superadmin',
}));
