/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useMemo, useEffect, useRef } from 'react';
import { Routes, Route, Navigate, useNavigate, useParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  LogIn, User, Lock, ArrowRight, Search, Plus,
  Edit2, Copy, Trash2, ChevronLeft, ChevronRight,
  LogOut, X, LayoutGrid, List, Shield, Check
} from 'lucide-react';
import { ProjectEditor, SystemType } from './components/ProjectEditor';
import { useAuthStore } from './store/authStore';
import { login as apiLogin, getMe } from './api/auth';
import { getProjects, createProject, updateProject, deleteProject, copyProject, ProjectList } from './api/projects';
import AdminPage from './pages/AdminPage';

// ── Helpers ──────────────────────────────────────────────────────────────────

const SYSTEM_COLORS: Record<SystemType, string> = {
  'СЛАЙД':  'bg-blue-500/20 text-blue-400 border-blue-500/30',
  'КНИЖКА': 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  'ЛИФТ':   'bg-orange-500/20 text-orange-400 border-orange-500/30',
  'ЦС':     'bg-purple-500/20 text-purple-400 border-purple-500/30',
  'ДВЕРЬ':  'bg-rose-500/20 text-rose-400 border-rose-500/30',
};

const SYSTEM_SUBTYPES: Record<SystemType, string[]> = {
  'СЛАЙД':  ['Стандарт 1 ряд', 'Стандарт от центра 2 ряда'],
  'КНИЖКА': ['Секция с дверями', 'Секция с углом', 'Секция с дверями и углом'],
  'ЛИФТ':   ['2 панели', '3 панели', '4 панели'],
  'ЦС':     ['Треугольник', 'Прямоугольник', 'Трапеция', 'Сложная форма'],
  'ДВЕРЬ':  ['Одностворчатая', 'Двустворчатая'],
};

const Badge = ({ type }: { type: SystemType }) => (
  <span className={`px-2.5 py-1 rounded-full text-[10px] font-bold border ${SYSTEM_COLORS[type]}`}>
    {type}
  </span>
);

// ── Login Page ────────────────────────────────────────────────────────────────

function LoginPage() {
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

// ── Projects Page ─────────────────────────────────────────────────────────────

function ProjectsPage() {
  const navigate = useNavigate();
  const { user, clearAuth, isAdmin } = useAuthStore();

  const [projects, setProjects] = useState<ProjectList[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [systemFilter, setSystemFilter] = useState('Все системы');

  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [projectToDelete, setProjectToDelete] = useState<ProjectList | null>(null);

  const [newNumber, setNewNumber] = useState('');
  const [newCustomer, setNewCustomer] = useState('ПРОЗРАЧНЫЕ РЕШЕНИЯ');
  const [newSystem, setNewSystem] = useState<SystemType>('СЛАЙД');
  const [newSubtype, setNewSubtype] = useState(SYSTEM_SUBTYPES['СЛАЙД'][0]);

  const [isCreating, setIsCreating] = useState(false);
  const [renamingId, setRenamingId] = useState<number | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const renameInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { loadProjects(); }, []);

  const loadProjects = async () => {
    setLoading(true);
    try { setProjects(await getProjects()); }
    finally { setLoading(false); }
  };

  const filteredProjects = useMemo(() => projects.filter(p => {
    const matchSearch = p.number.includes(searchQuery) || p.customer.toLowerCase().includes(searchQuery.toLowerCase());
    const matchFilter = systemFilter === 'Все системы' || p.system === systemFilter;
    return matchSearch && matchFilter;
  }), [projects, searchQuery, systemFilter]);

  const handleCreate = async () => {
    if (isCreating) return;
    setIsCreating(true);
    try {
      const project = await createProject({ number: newNumber, customer: newCustomer, system: newSystem, subtype: newSubtype });
      setIsCreateModalOpen(false);
      navigate(`/projects/${project.id}`);
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Ошибка создания');
    } finally {
      setIsCreating(false);
    }
  };

  const handleDelete = async () => {
    if (!projectToDelete) return;
    try {
      await deleteProject(projectToDelete.id);
      setIsDeleteModalOpen(false);
      setProjectToDelete(null);
      await loadProjects();
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Ошибка удаления');
    }
  };

  const startRename = (e: React.MouseEvent, project: ProjectList) => {
    e.stopPropagation();
    setRenamingId(project.id);
    setRenameValue(project.number);
    setTimeout(() => renameInputRef.current?.select(), 50);
  };

  const commitRename = async () => {
    if (!renamingId || !renameValue.trim()) { setRenamingId(null); return; }
    try {
      await updateProject(renamingId, { number: renameValue.trim() });
      setProjects(ps => ps.map(p => p.id === renamingId ? { ...p, number: renameValue.trim() } : p));
    } catch { /* silent */ }
    setRenamingId(null);
  };

  const handleCopy = async (e: React.MouseEvent, id: number) => {
    e.stopPropagation();
    try {
      const copy = await copyProject(id);
      navigate(`/projects/${copy.id}`);
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Ошибка копирования');
    }
  };

  const handleLogout = () => {
    clearAuth();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-[#0c1d2d] text-white font-sans relative flex flex-col">
      <div className="fixed inset-0 overflow-hidden pointer-events-none z-0">
        <div className="absolute top-[-10%] right-[-5%] w-[50%] h-[50%] bg-[#2a7a8a]/10 rounded-full blur-[120px]" />
        <div className="absolute bottom-[-10%] left-[-5%] w-[40%] h-[40%] bg-[#1a5f7a]/5 rounded-full blur-[120px]" />
      </div>

      <nav className="sticky top-0 z-40 bg-[#0c1d2d]/90 backdrop-blur-md border-b border-[#2a7a8a]/25 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#2a7a8a]/20 border border-[#2a7a8a]/30 flex items-center justify-center">
            <LayoutGrid className="w-6 h-6 text-[#4fd1c5]" />
          </div>
          <span className="text-xl font-bold tracking-tight uppercase">Ралюма</span>
        </div>
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-3 pr-6 border-r border-[#2a7a8a]/20">
            <div className="text-right">
              <div className="text-sm font-medium">{user?.display_name}</div>
              <div className="text-[10px] text-[#4fd1c5] font-bold uppercase tracking-wider">{user?.role}</div>
            </div>
            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-[#2a7a8a] to-[#1a4b54] flex items-center justify-center border border-white/10">
              <User className="w-5 h-5" />
            </div>
          </div>
          <div className="flex items-center gap-2">
            {isAdmin() && (
              <button onClick={() => navigate('/admin')}
                className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-[#2a7a8a]/10 hover:bg-[#2a7a8a]/20 text-[#4fd1c5] transition-all border border-[#2a7a8a]/20"
              >
                <Shield className="w-4 h-4" />
                <span className="text-sm font-bold">Администрирование</span>
              </button>
            )}
            <button onClick={handleLogout}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-red-500/10 hover:bg-red-500/20 text-red-400 transition-all border border-red-500/20"
            >
              <LogOut className="w-4 h-4" />
              <span className="text-sm font-bold">Выйти</span>
            </button>
          </div>
        </div>
      </nav>

      <main className="flex-1 p-8 max-w-7xl mx-auto w-full z-10">
        <div className="flex flex-col md:flex-row gap-4 mb-8 items-center">
          <div className="relative flex-1 group w-full">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-white/20 group-focus-within:text-[#4fd1c5] transition-colors" />
            <input type="text" placeholder="Поиск по номеру, заказчику..." value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="w-full bg-[#1a4b54]/20 border border-[#2a7a8a]/20 rounded-2xl pl-12 pr-4 py-4 outline-none focus:border-[#4fd1c5]/50 focus:ring-2 focus:ring-[#4fd1c5]/10 transition-all"
            />
          </div>
          <div className="flex gap-4 w-full md:w-auto">
            <select value={systemFilter} onChange={e => setSystemFilter(e.target.value)}
              className="bg-[#1a4b54]/20 border border-[#2a7a8a]/20 rounded-2xl px-6 py-4 outline-none focus:border-[#4fd1c5]/50 transition-all appearance-none cursor-pointer min-w-[180px]"
            >
              <option>Все системы</option>
              {(['СЛАЙД','КНИЖКА','ЛИФТ','ЦС','ДВЕРЬ'] as SystemType[]).map(s => <option key={s}>{s}</option>)}
            </select>
            <button onClick={() => { setNewNumber(''); setIsCreateModalOpen(true); }}
              className="flex items-center gap-2 px-8 py-4 bg-[#00b894] hover:bg-[#00d1a7] text-white font-bold rounded-2xl transition-all shadow-lg shadow-[#00b894]/20 whitespace-nowrap"
            >
              <Plus className="w-5 h-5" /> Новый проект
            </button>
          </div>
        </div>

        <div className="bg-[#1a4b54]/30 backdrop-blur-xl border border-[#2a7a8a]/30 rounded-[2rem] overflow-hidden shadow-2xl">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-[#2a7a8a]/20 bg-white/[0.02]">
                <th className="px-8 py-5 text-[10px] font-bold uppercase tracking-widest text-white/40">Проект</th>
                <th className="px-8 py-5 text-[10px] font-bold uppercase tracking-widest text-white/40">Заказчик</th>
                <th className="px-8 py-5 text-[10px] font-bold uppercase tracking-widest text-white/40">Система</th>
                <th className="px-8 py-5 text-[10px] font-bold uppercase tracking-widest text-white/40">Дата</th>
                <th className="px-8 py-5 text-[10px] font-bold uppercase tracking-widest text-white/40 text-right">Действия</th>
              </tr>
            </thead>
            <tbody>
              <AnimatePresence mode="popLayout">
                {loading ? (
                  <tr><td colSpan={5} className="py-20 text-center text-white/40">Загрузка...</td></tr>
                ) : filteredProjects.length > 0 ? filteredProjects.map(project => (
                  <motion.tr key={project.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                    onClick={() => navigate(`/projects/${project.id}`)}
                    className="border-b border-[#2a7a8a]/10 hover:bg-white/[0.03] transition-colors cursor-pointer group"
                  >
                    <td className="px-8 py-5 font-mono text-sm text-[#4fd1c5] font-bold" onClick={e => e.stopPropagation()}>
                      {renamingId === project.id ? (
                        <div className="flex items-center gap-1">
                          <input
                            ref={renameInputRef}
                            value={renameValue}
                            onChange={e => setRenameValue(e.target.value)}
                            onBlur={commitRename}
                            onKeyDown={e => { if (e.key === 'Enter') commitRename(); if (e.key === 'Escape') setRenamingId(null); }}
                            className="bg-[#2a7a8a]/20 border border-[#4fd1c5]/40 rounded-lg px-2 py-1 outline-none text-[#4fd1c5] font-mono text-sm w-24"
                          />
                          <button onClick={commitRename} className="p-1 rounded text-emerald-400 hover:text-emerald-300">
                            <Check className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      ) : (
                        <span className="cursor-pointer hover:text-white transition-colors group-hover:underline" onDoubleClick={e => startRename(e, project)}>
                          {project.number}
                        </span>
                      )}
                    </td>
                    <td className="px-8 py-5 text-sm font-medium">{project.customer}</td>
                    <td className="px-8 py-5"><Badge type={project.system as SystemType} /></td>
                    <td className="px-8 py-5 text-sm text-white/40">
                      {new Date(project.created_at).toLocaleDateString('ru-RU')}
                    </td>
                    <td className="px-8 py-5 text-right">
                      <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button onClick={e => startRename(e, project)}
                          className="p-2 rounded-lg hover:bg-[#2a7a8a]/20 text-[#4fd1c5] transition-colors" title="Переименовать">
                          <Edit2 className="w-4 h-4" />
                        </button>
                        <button onClick={e => handleCopy(e, project.id)}
                          className="p-2 rounded-lg hover:bg-[#2a7a8a]/20 text-[#4fd1c5] transition-colors">
                          <Copy className="w-4 h-4" />
                        </button>
                        <button onClick={e => { e.stopPropagation(); setProjectToDelete(project); setIsDeleteModalOpen(true); }}
                          className="p-2 rounded-lg hover:bg-red-500/20 text-red-400 transition-colors">
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </motion.tr>
                )) : (
                  <tr>
                    <td colSpan={5} className="py-20 text-center">
                      <div className="flex flex-col items-center gap-4">
                        <div className="w-20 h-20 rounded-full bg-[#2a7a8a]/10 flex items-center justify-center border border-[#2a7a8a]/20">
                          {searchQuery ? <Search className="w-10 h-10 text-white/20" /> : <List className="w-10 h-10 text-white/20" />}
                        </div>
                        <div>
                          <h3 className="text-xl font-bold mb-1">{searchQuery ? 'Ничего не найдено' : 'Проектов пока нет'}</h3>
                          <p className="text-white/40 text-sm">{searchQuery ? 'Попробуйте другой запрос' : 'Создайте свой первый проект'}</p>
                        </div>
                        {!searchQuery && (
                          <button onClick={() => setIsCreateModalOpen(true)}
                            className="mt-4 flex items-center gap-2 px-6 py-3 bg-[#00b894] hover:bg-[#00d1a7] text-white font-bold rounded-xl transition-all">
                            <Plus className="w-4 h-4" /> Новый проект
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                )}
              </AnimatePresence>
            </tbody>
          </table>
          <div className="px-8 py-6 bg-white/[0.02] flex items-center justify-between border-t border-[#2a7a8a]/20">
            <div className="text-xs text-white/40">
              Показано <span className="text-white font-bold">{filteredProjects.length}</span> из <span className="text-white font-bold">{projects.length}</span>
            </div>
          </div>
        </div>
      </main>

      {/* Delete Modal */}
      <AnimatePresence>
        {isDeleteModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => setIsDeleteModalOpen(false)} className="absolute inset-0 bg-black/80 backdrop-blur-sm" />
            <motion.div initial={{ scale: 0.9, opacity: 0, y: 20 }} animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.9, opacity: 0, y: 20 }}
              className="relative w-full max-w-md bg-[#122433] border border-red-500/30 rounded-[2rem] p-8 shadow-2xl z-10"
            >
              <button onClick={() => setIsDeleteModalOpen(false)} className="absolute right-6 top-6 text-white/20 hover:text-white transition-colors">
                <X className="w-6 h-6" />
              </button>
              <div className="w-16 h-16 rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center mb-6">
                <Trash2 className="w-8 h-8 text-red-400" />
              </div>
              <h2 className="text-2xl font-bold mb-2">Удалить проект?</h2>
              <p className="text-white/60 leading-relaxed mb-8">
                Проект <span className="text-white font-bold">№ {projectToDelete?.number}</span> будет удалён безвозвратно.
              </p>
              <div className="flex gap-4">
                <button onClick={() => setIsDeleteModalOpen(false)} className="flex-1 py-4 rounded-2xl bg-white/5 hover:bg-white/10 font-bold transition-all">Отмена</button>
                <button onClick={handleDelete} className="flex-1 py-4 rounded-2xl bg-red-500 hover:bg-red-400 text-white font-bold transition-all shadow-lg shadow-red-500/20">Удалить</button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Create Modal */}
      <AnimatePresence>
        {isCreateModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => setIsCreateModalOpen(false)} className="absolute inset-0 bg-black/80 backdrop-blur-sm" />
            <motion.div initial={{ scale: 0.9, opacity: 0, y: 20 }} animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.9, opacity: 0, y: 20 }}
              className="relative w-full max-w-xl bg-[#122433] border border-[#2a7a8a]/35 rounded-[2.5rem] p-10 shadow-2xl overflow-hidden z-10"
            >
              <button onClick={() => setIsCreateModalOpen(false)} className="absolute right-8 top-8 text-white/20 hover:text-white transition-colors">
                <X className="w-6 h-6" />
              </button>
              <h2 className="text-3xl font-bold mb-8">Новый проект</h2>
              <div className="space-y-8">
                <div className="space-y-3">
                  <label className="text-[10px] font-bold uppercase tracking-widest text-[#4fd1c5]/40 ml-1">Номер проекта</label>
                  <input type="text" value={newNumber} onChange={e => setNewNumber(e.target.value)}
                    className="w-full bg-white/8 border border-[#2a7a8a]/35 rounded-2xl px-6 py-4 outline-none focus:border-[#4fd1c5]/50 transition-all font-mono text-lg text-white"
                    placeholder="2042"
                  />
                </div>
                <div className="space-y-3">
                  <label className="text-[10px] font-bold uppercase tracking-widest text-[#4fd1c5]/40 ml-1">Заказчик</label>
                  <div className="grid grid-cols-1 gap-3">
                    {['ПРОЗРАЧНЫЕ РЕШЕНИЯ','КРОКНА ИНЖИНИРИНГ','СТУДИЯ СПК'].map(c => (
                      <button key={c} onClick={() => setNewCustomer(c)}
                        className={`flex items-center gap-4 px-6 py-4 rounded-2xl border transition-all text-left ${
                          newCustomer === c ? 'bg-[#4fd1c5]/10 border-[#4fd1c5]/50 text-[#4fd1c5]' : 'bg-black/10 border-[#2a7a8a]/20 text-white/40 hover:border-[#2a7a8a]/50'
                        }`}
                      >
                        <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${newCustomer === c ? 'border-[#4fd1c5]' : 'border-white/10'}`}>
                          {newCustomer === c && <div className="w-2.5 h-2.5 rounded-full bg-[#4fd1c5]" />}
                        </div>
                        <span className="font-medium">{c}</span>
                      </button>
                    ))}
                  </div>
                </div>
                <div className="space-y-3">
                  <label className="text-[10px] font-bold uppercase tracking-widest text-[#4fd1c5]/40 ml-1">Тип системы</label>
                  <div className="flex p-1 bg-black/20 rounded-2xl border border-[#2a7a8a]/20">
                    {(['СЛАЙД','КНИЖКА','ЛИФТ','ЦС','ДВЕРЬ'] as SystemType[]).map(s => (
                      <button key={s} onClick={() => { setNewSystem(s); setNewSubtype(SYSTEM_SUBTYPES[s][0]); }}
                        className={`flex-1 py-3 rounded-xl text-[10px] font-bold transition-all ${newSystem === s ? 'bg-[#2a7a8a] text-white shadow-lg' : 'text-white/30 hover:text-white/60'}`}
                      >{s}</button>
                    ))}
                  </div>
                </div>
                <div className="space-y-3">
                  <label className="text-[10px] font-bold uppercase tracking-widest text-[#4fd1c5]/40 ml-1">Подтип</label>
                  <div className="grid grid-cols-1 gap-2">
                    {SYSTEM_SUBTYPES[newSystem].map(sub => (
                      <button key={sub} onClick={() => setNewSubtype(sub)}
                        className={`flex items-center gap-3 px-4 py-3 rounded-xl border transition-all text-left ${
                          newSubtype === sub ? 'bg-[#4fd1c5]/10 border-[#4fd1c5]/50 text-[#4fd1c5]' : 'bg-black/10 border-[#2a7a8a]/20 text-white/40 hover:border-[#2a7a8a]/50'
                        }`}
                      >
                        <div className={`w-4 h-4 rounded-full border flex items-center justify-center flex-shrink-0 ${newSubtype === sub ? 'border-[#4fd1c5]' : 'border-white/10'}`}>
                          {newSubtype === sub && <div className="w-2 h-2 rounded-full bg-[#4fd1c5]" />}
                        </div>
                        <span className="text-xs font-medium">{sub}</span>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
              <div className="flex gap-4 mt-10">
                <button onClick={() => setIsCreateModalOpen(false)} className="flex-1 py-4 rounded-2xl bg-white/5 hover:bg-white/10 font-bold transition-all">Отмена</button>
                <button onClick={handleCreate} disabled={!newNumber.trim() || isCreating}
                  className="flex-1 py-4 rounded-2xl bg-[#00b894] hover:bg-[#00d1a7] text-white font-bold transition-all shadow-lg shadow-[#00b894]/20 flex items-center justify-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {isCreating ? (
                    <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  ) : (
                    <>Создать <ArrowRight className="w-5 h-5" /></>
                  )}
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ── Editor Page wrapper ───────────────────────────────────────────────────────

function EditorPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  return <ProjectEditor projectId={Number(id)} onBack={() => navigate('/')} />;
}

// ── Protected Route ───────────────────────────────────────────────────────────

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { token } = useAuthStore();
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

// ── App (Router) ──────────────────────────────────────────────────────────────

export default function App() {
  const { token, setAuth, clearAuth } = useAuthStore();

  useEffect(() => {
    if (token) {
      getMe().then(user => setAuth(token, user)).catch(() => clearAuth());
    }
  }, []);

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<ProtectedRoute><ProjectsPage /></ProtectedRoute>} />
      <Route path="/projects/:id" element={<ProtectedRoute><EditorPage /></ProtectedRoute>} />
      <Route path="/admin" element={<ProtectedRoute><AdminPage /></ProtectedRoute>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
