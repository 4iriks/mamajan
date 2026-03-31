/**
 * LoginPage — страница авторизации.
 * Извлечено из App.tsx.
 */

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { LogIn, User, Lock, ArrowRight, Sun, Moon } from 'lucide-react';
import { useAuthStore } from '../store/authStore';
import { useThemeStore } from '../store/themeStore';
import { login as apiLogin, getMe } from '../api/auth';

export default function LoginPage() {
  const navigate = useNavigate();
  const { setAuth, token } = useAuthStore();
  const { theme, toggle: toggleTheme } = useThemeStore();
  const [loginVal, setLoginVal] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (token) navigate('/', { replace: true });
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);
    try {
      const token = await apiLogin(loginVal, password);
      localStorage.setItem('access_token', token);
      const user = await getMe();
      setAuth(token, user);
      navigate('/', { replace: true });
    } catch (err: any) {
      localStorage.removeItem('access_token');
      setError(err.response?.data?.detail || 'Неверный логин или пароль');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-page text-fg font-sans flex items-center justify-center p-4 overflow-hidden relative">
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-[-20%] left-[-10%] w-[70%] h-[70%] bg-tint/20 rounded-full blur-[140px]" />
        <div className="absolute bottom-[-20%] right-[-10%] w-[60%] h-[60%] bg-glow2/10 rounded-full blur-[140px]" />
      </div>
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="w-full max-w-[440px] z-10">
        <div className="bg-surface/60 backdrop-blur-2xl border border-tint/20 rounded-[2.5rem] p-8 md:p-10 shadow-2xl shadow-black/20">
          <div className="mb-10 text-center">
            <motion.div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-tint/20 border border-tint/30 mb-6">
              <LogIn className="w-8 h-8 text-accent" />
            </motion.div>
            <h1 className="text-3xl font-semibold tracking-tight mb-2">Ралюма</h1>
            <p className="text-accent/60 text-sm">Введите данные для входа в систему</p>
          </div>
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-2">
              <label className="text-[10px] font-bold uppercase tracking-[0.2em] text-accent/40 ml-1">Логин</label>
              <div className="relative group">
                <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                  <User className="h-5 w-5 text-accent/30 group-focus-within:text-accent transition-colors" />
                </div>
                <input type="text" required value={loginVal} onChange={e => setLoginVal(e.target.value)}
                  className="block w-full pl-11 pr-4 py-4 bg-hi/8 border border-tint/20 rounded-2xl focus:ring-2 focus:ring-accent/20 focus:border-accent/50 transition-all outline-none placeholder:text-accent/10 text-sm"
                  placeholder="Ваш логин" />
              </div>
            </div>
            <div className="space-y-2">
              <label className="text-[10px] font-bold uppercase tracking-[0.2em] text-accent/40 ml-1">Пароль</label>
              <div className="relative group">
                <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                  <Lock className="h-5 w-5 text-accent/30 group-focus-within:text-accent transition-colors" />
                </div>
                <input type="password" required value={password} onChange={e => setPassword(e.target.value)}
                  className="block w-full pl-11 pr-4 py-4 bg-hi/8 border border-tint/20 rounded-2xl focus:ring-2 focus:ring-accent/20 focus:border-accent/50 transition-all outline-none placeholder:text-accent/10 text-sm"
                  placeholder="••••••••" />
              </div>
            </div>
            {error && (
              <div className="px-4 py-3 bg-red-500/10 border border-red-500/20 rounded-xl text-sm text-red-400 font-medium">
                {error}
              </div>
            )}
            <button type="submit" disabled={isLoading}
              className="relative w-full group overflow-hidden bg-primary hover:bg-primary-h text-white font-bold py-4 rounded-2xl transition-all active:scale-[0.98] disabled:opacity-70 disabled:cursor-not-allowed mt-4 shadow-lg shadow-primary/20"
            >
              <AnimatePresence mode="wait">
                {isLoading ? (
                  <motion.div key="loading" className="flex items-center justify-center">
                    <div className="w-5 h-5 border-2 border-black/30 border-t-black rounded-full animate-spin" />
                  </motion.div>
                ) : (
                  <motion.div key="text" className="flex items-center justify-center gap-2">
                    Войти <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                  </motion.div>
                )}
              </AnimatePresence>
            </button>
          </form>
        </div>
      </motion.div>
      <button onClick={toggleTheme}
        className="fixed bottom-6 right-6 z-50 w-11 h-11 rounded-full bg-tint/20 border border-tint/30 text-accent hover:bg-tint/30 transition-all shadow-lg flex items-center justify-center"
        title={theme === 'dark' ? 'Светлая тема' : 'Тёмная тема'}>
        {theme === 'dark' ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
      </button>
    </div>
  );
}
