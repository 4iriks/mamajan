/**
 * LoginPage — страница авторизации.
 * Извлечено из App.tsx.
 */

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { LogIn, User, Lock, ArrowRight } from 'lucide-react';
import { useAuthStore } from '../store/authStore';
import { login as apiLogin, getMe } from '../api/auth';

export default function LoginPage() {
  const navigate = useNavigate();
  const { setAuth, token } = useAuthStore();
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
    <div className="min-h-screen bg-[#0c1d2d] text-white font-sans flex items-center justify-center p-4 overflow-hidden relative">
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-[-20%] left-[-10%] w-[70%] h-[70%] bg-[#2a7a8a]/20 rounded-full blur-[140px]" />
        <div className="absolute bottom-[-20%] right-[-10%] w-[60%] h-[60%] bg-[#1a5f7a]/10 rounded-full blur-[140px]" />
      </div>
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="w-full max-w-[440px] z-10">
        <div className="bg-[#1a4b54]/40 backdrop-blur-2xl border border-[#2a7a8a]/30 rounded-[2.5rem] p-8 md:p-10 shadow-2xl shadow-black/50">
          <div className="mb-10 text-center">
            <motion.div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-[#2a7a8a]/20 border border-[#2a7a8a]/30 mb-6">
              <LogIn className="w-8 h-8 text-[#4fd1c5]" />
            </motion.div>
            <h1 className="text-3xl font-semibold tracking-tight mb-2">Ралюма</h1>
            <p className="text-[#4fd1c5]/60 text-sm">Введите данные для входа в систему</p>
          </div>
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-2">
              <label className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#4fd1c5]/40 ml-1">Логин</label>
              <div className="relative group">
                <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                  <User className="h-5 w-5 text-[#4fd1c5]/30 group-focus-within:text-[#4fd1c5] transition-colors" />
                </div>
                <input type="text" required value={loginVal} onChange={e => setLoginVal(e.target.value)}
                  className="block w-full pl-11 pr-4 py-4 bg-black/20 border border-[#2a7a8a]/20 rounded-2xl focus:ring-2 focus:ring-[#4fd1c5]/20 focus:border-[#4fd1c5]/50 transition-all outline-none placeholder:text-[#4fd1c5]/10 text-sm"
                  placeholder="Ваш логин" />
              </div>
            </div>
            <div className="space-y-2">
              <label className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#4fd1c5]/40 ml-1">Пароль</label>
              <div className="relative group">
                <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                  <Lock className="h-5 w-5 text-[#4fd1c5]/30 group-focus-within:text-[#4fd1c5] transition-colors" />
                </div>
                <input type="password" required value={password} onChange={e => setPassword(e.target.value)}
                  className="block w-full pl-11 pr-4 py-4 bg-black/20 border border-[#2a7a8a]/20 rounded-2xl focus:ring-2 focus:ring-[#4fd1c5]/20 focus:border-[#4fd1c5]/50 transition-all outline-none placeholder:text-[#4fd1c5]/10 text-sm"
                  placeholder="••••••••" />
              </div>
            </div>
            {error && (
              <div className="px-4 py-3 bg-red-500/10 border border-red-500/20 rounded-xl text-sm text-red-400 font-medium">
                {error}
              </div>
            )}
            <button type="submit" disabled={isLoading}
              className="relative w-full group overflow-hidden bg-[#00b894] hover:bg-[#00d1a7] text-white font-bold py-4 rounded-2xl transition-all active:scale-[0.98] disabled:opacity-70 disabled:cursor-not-allowed mt-4 shadow-lg shadow-[#00b894]/20"
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
    </div>
  );
}
