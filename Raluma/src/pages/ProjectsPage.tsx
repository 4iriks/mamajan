/**
 * ProjectsPage — список проектов с поиском, фильтрами, CRUD.
 * Извлечено из App.tsx.
 */

import React, { useState, useMemo, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  User, ArrowRight, Search, Plus,
  Edit2, Copy, Trash2,
  LogOut, X, LayoutGrid, List, Shield, Check, Sun, Moon
} from 'lucide-react';
import { useAuthStore } from '../store/authStore';
import { useThemeStore } from '../store/themeStore';
import { getProjects, createProject, updateProject, deleteProject, copyProject, ProjectList } from '../api/projects';
import { toast } from '../store/toastStore';

// ── Status helpers ────────────────────────────────────────────────────────────

const STATUS_COLORS: Record<string, string> = {
  'РАСЧЕТ':                'bg-hi/10 text-fg/50',
  'В работе':              'bg-blue-500/20 text-blue-300',
  'Запущен в производство':'bg-teal-500/20 text-teal-300',
  'Готов':                 'bg-emerald-500/20 text-emerald-300',
  'Отгружен полностью':    'bg-emerald-600/25 text-emerald-200',
  'Отгружен частично':     'bg-amber-500/20 text-amber-300',
  'Отгружен 1 этап':       'bg-amber-500/20 text-amber-300',
  'Рекламация':            'bg-red-500/20 text-red-300',
  'Архив':                 'bg-hi/5 text-fg/30',
};

const GLASS_COLORS: Record<string, string> = {
  'Без стекла':    'bg-hi/5 text-fg/30',
  'Стекла заказаны': 'bg-amber-500/20 text-amber-300',
  'Стекла в цеху': 'bg-emerald-500/20 text-emerald-300',
};

const PAINT_COLORS: Record<string, string> = {
  'Без покраски':               'bg-hi/5 text-fg/30',
  'Задание на покраску в цеху': 'bg-blue-500/20 text-blue-300',
  'Отгружен на покраску':       'bg-amber-500/20 text-amber-300',
  'Получен с покраски':         'bg-emerald-500/20 text-emerald-300',
};

function StatusBadge({ value, colors }: { value?: string; colors: Record<string, string> }) {
  if (!value) return null;
  const cls = colors[value] ?? 'bg-hi/5 text-fg/40';
  return (
    <span className={`inline-block px-2 py-0.5 rounded-lg text-[10px] font-bold border border-hi/5 whitespace-nowrap ${cls}`}>
      {value}
    </span>
  );
}

function SkeletonRow() {
  return (
    <tr className="border-b border-tint/10">
      {[60, 80, 55, 15, 30, 20, 20, 20].map((w, i) => (
        <td key={i} className="px-5 py-5">
          <div className="h-4 rounded-lg bg-hi/[0.06] animate-pulse" style={{ width: `${w}%` }} />
        </td>
      ))}
    </tr>
  );
}

// ── Main component ───────────────────────────────────────────────────────────

export default function ProjectsPage() {
  const navigate = useNavigate();
  const { user, clearAuth, isAdmin } = useAuthStore();
  const { theme, toggle: toggleTheme } = useThemeStore();

  const [projects, setProjects] = useState<ProjectList[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');

  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [projectToDelete, setProjectToDelete] = useState<ProjectList | null>(null);

  const [newNumber, setNewNumber] = useState('');
  const [newCustomer, setNewCustomer] = useState('');
  const [newStages, setNewStages] = useState<1 | 2>(1);
  const [showCustomerDrop, setShowCustomerDrop] = useState(false);
  const [viewTab, setViewTab] = useState<'current' | 'archive'>('current');

  const formatProjectNumber = (raw: string) => {
    const clean = raw.replace(/[^a-zA-ZА-Яа-яёЁ0-9]/gi, '').slice(0, 8);
    if (clean.length <= 3) return clean;
    if (clean.length === 4) return clean.slice(0, 3) + '-' + clean[3];
    return clean.slice(0, 3) + '-' + clean[3] + '-' + clean.slice(4);
  };

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

  const filteredProjects = useMemo(() => {
    const byTab = projects.filter(p => viewTab === 'archive' ? p.status === 'Архив' : p.status !== 'Архив');
    return byTab.filter(p => p.number.includes(searchQuery) || p.customer.toLowerCase().includes(searchQuery.toLowerCase()));
  }, [projects, searchQuery, viewTab]);

  const customerOptions = useMemo(() => {
    const seen = new Set<string>(['ООО КРОКНА ИНЖИНИРИНГ', 'ООО ПРОЗРАЧНЫЕ РЕШЕНИЯ', 'ООО СТУДИЯ СПК']);
    if (user?.customer) seen.add(user.customer);
    projects.forEach(p => { if (p.customer) seen.add(p.customer); });
    return [...seen];
  }, [projects, user]);

  const filteredCustomers = useMemo(() =>
    customerOptions.filter(c => c.toLowerCase().includes(newCustomer.toLowerCase())),
    [customerOptions, newCustomer]
  );

  const openCreateModal = () => {
    setNewNumber('');
    setNewCustomer('');
    setNewStages(1);
    setShowCustomerDrop(false);
    setIsCreateModalOpen(true);
  };

  const handleCreate = async () => {
    if (isCreating) return;
    setIsCreating(true);
    try {
      const project = await createProject({ number: newNumber, customer: newCustomer, production_stages: newStages });
      setIsCreateModalOpen(false);
      navigate(`/projects/${project.id}`);
    } catch (e: any) {
      toast.error(e.response?.data?.detail || 'Ошибка создания проекта');
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
      toast.success('Проект удалён');
    } catch (e: any) {
      toast.error(e.response?.data?.detail || 'Ошибка удаления проекта');
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
    } catch (e: any) {
      toast.error(e.response?.data?.detail || 'Не удалось переименовать');
    }
    setRenamingId(null);
  };

  const handleCopy = async (e: React.MouseEvent, id: number) => {
    e.stopPropagation();
    try {
      const copy = await copyProject(id);
      navigate(`/projects/${copy.id}`);
    } catch (e: any) {
      toast.error(e.response?.data?.detail || 'Ошибка копирования проекта');
    }
  };

  const handleLogout = () => {
    clearAuth();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-page text-fg font-sans relative flex flex-col">
      <div className="fixed inset-0 overflow-hidden pointer-events-none z-0">
        <div className="absolute top-[-10%] right-[-5%] w-[50%] h-[50%] bg-tint/10 rounded-full blur-[120px]" />
        <div className="absolute bottom-[-10%] left-[-5%] w-[40%] h-[40%] bg-glow2/5 rounded-full blur-[120px]" />
      </div>

      <nav className="sticky top-0 z-40 bg-page/90 backdrop-blur-md border-b border-tint/25 px-4 sm:px-6 py-3 sm:py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 sm:w-10 sm:h-10 rounded-xl bg-tint/20 border border-tint/30 flex items-center justify-center">
            <LayoutGrid className="w-5 h-5 sm:w-6 sm:h-6 text-accent" />
          </div>
          <span className="text-lg sm:text-xl font-bold tracking-tight uppercase">Ралюма</span>
        </div>
        <div className="flex items-center gap-2 sm:gap-6">
          <div className="flex items-center gap-3 sm:pr-6 sm:border-r sm:border-tint/20">
            <div className="text-right hidden sm:block">
              <div className="text-sm font-medium">{user?.display_name}</div>
              <div className="text-[10px] text-accent font-bold uppercase tracking-wider">{user?.role}</div>
            </div>
            <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-full bg-gradient-to-br from-tint to-surface flex items-center justify-center border border-hi/10">
              <User className="w-4 h-4 sm:w-5 sm:h-5" />
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={toggleTheme}
              className="p-2.5 rounded-xl bg-tint/10 hover:bg-tint/20 text-accent transition-all border border-tint/20"
              title={theme === 'dark' ? 'Светлая тема' : 'Тёмная тема'}>
              {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>
            {isAdmin() && (
              <button onClick={() => navigate('/admin')}
                className="flex items-center gap-2 px-2.5 sm:px-4 py-2.5 rounded-xl bg-tint/10 hover:bg-tint/20 text-accent transition-all border border-tint/20"
              >
                <Shield className="w-4 h-4" />
                <span className="hidden sm:inline text-sm font-bold">Администрирование</span>
              </button>
            )}
            <button onClick={handleLogout}
              className="flex items-center gap-2 px-2.5 sm:px-4 py-2.5 rounded-xl bg-red-500/10 hover:bg-red-500/20 text-red-400 transition-all border border-red-500/20"
            >
              <LogOut className="w-4 h-4" />
              <span className="hidden sm:inline text-sm font-bold">Выйти</span>
            </button>
          </div>
        </div>
      </nav>

      <main className="flex-1 p-4 sm:p-8 max-w-7xl mx-auto w-full z-10">
        <div className="flex flex-col md:flex-row gap-4 mb-8 items-center">
          <div className="relative flex-1 group w-full">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-fg/20 group-focus-within:text-accent transition-colors" />
            <input type="text" placeholder="Поиск по номеру, заказчику..." value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="w-full bg-surface/20 border border-tint/20 rounded-2xl pl-12 pr-4 py-4 outline-none focus:border-accent/50 focus:ring-2 focus:ring-accent/10 transition-all"
            />
          </div>
          <button onClick={openCreateModal}
            className="w-full md:w-auto flex items-center justify-center gap-2 px-8 py-4 bg-primary hover:bg-primary-h text-white font-bold rounded-2xl transition-all shadow-lg shadow-primary/20 whitespace-nowrap"
          >
            <Plus className="w-5 h-5" /> Новый проект
          </button>
        </div>

        <div className="flex gap-2 mb-4">
          {(['current', 'archive'] as const).map(tab => (
            <button key={tab} onClick={() => setViewTab(tab)}
              className={`px-5 py-2.5 rounded-xl font-bold text-sm transition-all border ${viewTab === tab ? 'bg-accent/10 border-accent/40 text-accent' : 'bg-hi/[0.03] border-hi/[0.08] text-fg/70 hover:border-tint/40'}`}>
              {tab === 'current' ? 'Текущие проекты' : 'Архив'}
            </button>
          ))}
        </div>

        <div className="bg-surface/30 backdrop-blur-xl border border-tint/30 rounded-[2rem] overflow-hidden shadow-2xl">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[840px] text-left border-collapse">
              <thead>
                <tr className="border-b border-tint/20 bg-hi/[0.02]">
                  <th className="px-5 py-5 text-[10px] font-bold uppercase tracking-widest text-fg/40">Проект</th>
                  <th className="px-5 py-5 text-[10px] font-bold uppercase tracking-widest text-fg/40">Заказчик</th>
                  <th className="px-5 py-5 text-[10px] font-bold uppercase tracking-widest text-fg/40">Дата</th>
                  <th className="px-5 py-5 text-[10px] font-bold uppercase tracking-widest text-fg/40">Этап</th>
                  <th className="px-5 py-5 text-[10px] font-bold uppercase tracking-widest text-fg/40">Статус</th>
                  <th className="px-5 py-5 text-[10px] font-bold uppercase tracking-widest text-fg/40">Стекла</th>
                  <th className="px-5 py-5 text-[10px] font-bold uppercase tracking-widest text-fg/40">Покраска</th>
                  <th className="px-5 py-5 text-[10px] font-bold uppercase tracking-widest text-fg/40 text-right">Действия</th>
                </tr>
              </thead>
              <tbody>
                <AnimatePresence mode="popLayout">
                  {loading ? (
                    Array.from({ length: 6 }).map((_, i) => <SkeletonRow key={i} />)
                  ) : filteredProjects.length > 0 ? filteredProjects.map(project => (
                    <motion.tr key={project.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                      onClick={() => navigate(`/projects/${project.id}`)}
                      className="border-b border-tint/10 hover:bg-hi/[0.03] transition-colors cursor-pointer group"
                    >
                      <td className="px-5 py-4 font-mono text-sm text-accent font-bold" onClick={e => e.stopPropagation()}>
                        {renamingId === project.id ? (
                          <div className="flex items-center gap-1">
                            <input
                              ref={renameInputRef}
                              value={renameValue}
                              onChange={e => setRenameValue(e.target.value)}
                              onBlur={commitRename}
                              onKeyDown={e => { if (e.key === 'Enter') commitRename(); if (e.key === 'Escape') setRenamingId(null); }}
                              className="bg-tint/20 border border-accent/40 rounded-lg px-2 py-1 outline-none text-accent font-mono text-sm w-24"
                            />
                            <button onClick={commitRename} className="p-1 rounded text-emerald-400 hover:text-emerald-300">
                              <Check className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        ) : (
                          <span className="cursor-pointer hover:text-fg transition-colors group-hover:underline" onDoubleClick={e => startRename(e, project)}>
                            {project.number}
                          </span>
                        )}
                      </td>
                      <td className="px-5 py-4 text-sm font-medium">{project.customer}</td>
                      <td className="px-5 py-4 text-sm text-fg/40">
                        {new Date(project.updated_at).toLocaleDateString('ru-RU')}
                      </td>
                      <td className="px-5 py-4 text-sm font-bold text-fg/50">
                        {project.production_stages === 2 ? (project.current_stage ?? 1) : ''}
                      </td>
                      <td className="px-5 py-4">
                        <StatusBadge value={project.status} colors={STATUS_COLORS} />
                      </td>
                      <td className="px-5 py-4">
                        <StatusBadge value={project.glass_status} colors={GLASS_COLORS} />
                      </td>
                      <td className="px-5 py-4">
                        <StatusBadge value={project.paint_status} colors={PAINT_COLORS} />
                      </td>
                      <td className="px-5 py-4 text-right">
                        <div className="flex items-center justify-end gap-2 opacity-20 group-hover:opacity-100 transition-opacity">
                          <button onClick={e => startRename(e, project)}
                            className="p-2 rounded-lg hover:bg-tint/20 text-accent transition-colors" title="Переименовать">
                            <Edit2 className="w-4 h-4" />
                          </button>
                          <button onClick={e => handleCopy(e, project.id)}
                            className="p-2 rounded-lg hover:bg-tint/20 text-accent transition-colors">
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
                      <td colSpan={8} className="py-20 text-center">
                        <div className="flex flex-col items-center gap-4">
                          <div className="w-20 h-20 rounded-full bg-tint/10 flex items-center justify-center border border-tint/20">
                            {searchQuery ? <Search className="w-10 h-10 text-fg/20" /> : <List className="w-10 h-10 text-fg/20" />}
                          </div>
                          <div>
                            <h3 className="text-xl font-bold mb-1">{searchQuery ? 'Ничего не найдено' : 'Проектов пока нет'}</h3>
                            <p className="text-fg/40 text-sm">{searchQuery ? 'Попробуйте другой запрос' : 'Создайте свой первый проект'}</p>
                          </div>
                          {!searchQuery && (
                            <button onClick={openCreateModal}
                              className="mt-4 flex items-center gap-2 px-6 py-3 bg-primary hover:bg-primary-h text-white font-bold rounded-xl transition-all">
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
          </div>
          <div className="px-8 py-6 bg-hi/[0.02] flex items-center justify-between border-t border-tint/20">
            <div className="text-xs text-fg/40">
              Показано <span className="text-fg font-bold">{filteredProjects.length}</span> из <span className="text-fg font-bold">{projects.length}</span>
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
              className="relative w-full max-w-md bg-modal border border-red-500/30 rounded-[2rem] p-8 shadow-2xl z-10"
            >
              <button onClick={() => setIsDeleteModalOpen(false)} className="absolute right-6 top-6 text-fg/20 hover:text-fg transition-colors">
                <X className="w-6 h-6" />
              </button>
              <div className="w-16 h-16 rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center mb-6">
                <Trash2 className="w-8 h-8 text-red-400" />
              </div>
              <h2 className="text-2xl font-bold mb-2">Удалить проект?</h2>
              <p className="text-fg/60 leading-relaxed mb-8">
                Проект <span className="text-fg font-bold">№ {projectToDelete?.number}</span> будет удалён безвозвратно.
              </p>
              <div className="flex gap-4">
                <button onClick={() => setIsDeleteModalOpen(false)} className="flex-1 py-4 rounded-2xl bg-hi/5 hover:bg-hi/10 font-bold transition-all">Отмена</button>
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
              className="relative w-full max-w-xl bg-modal border border-tint/35 rounded-[2.5rem] p-5 sm:p-10 shadow-2xl overflow-y-auto max-h-[95vh] z-10"
            >
              <button onClick={() => setIsCreateModalOpen(false)} className="absolute right-8 top-8 text-fg/20 hover:text-fg transition-colors">
                <X className="w-6 h-6" />
              </button>
              <h2 className="text-2xl sm:text-3xl font-bold mb-5 sm:mb-8">Новый проект</h2>
              <div className="space-y-5 sm:space-y-8">
                <div className="space-y-3">
                  <label className="text-[10px] font-bold uppercase tracking-widest text-accent/40 ml-1">Номер проекта</label>
                  <input type="text" value={newNumber}
                    onChange={e => setNewNumber(formatProjectNumber(e.target.value))}
                    className="w-full bg-hi/8 border border-tint/35 rounded-2xl px-6 py-4 outline-none focus:border-accent/50 transition-all font-mono text-lg text-fg tracking-widest"
                    placeholder="Х00-0-0000"
                  />
                </div>
                <div className="space-y-3">
                  <label className="text-[10px] font-bold uppercase tracking-widest text-accent/40 ml-1">Производство</label>
                  <div className="flex gap-3">
                    {([1, 2] as const).map(n => (
                      <button key={n} type="button" onClick={() => setNewStages(n)}
                        className={`flex-1 py-3.5 rounded-2xl border font-bold text-sm transition-all ${newStages === n ? 'bg-accent/10 border-accent/50 text-accent' : 'bg-black/10 border-tint/25 text-fg/70 hover:border-tint/50'}`}>
                        {n === 1 ? 'в 1 этап' : 'в 2 этапа'}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="space-y-3">
                  <label className="text-[10px] font-bold uppercase tracking-widest text-accent/40 ml-1">Заказчик</label>
                  <div>
                    <input
                      value={newCustomer}
                      onChange={e => { setNewCustomer(e.target.value); setShowCustomerDrop(true); }}
                      onFocus={() => setShowCustomerDrop(true)}
                      onBlur={() => setTimeout(() => setShowCustomerDrop(false), 150)}
                      className="w-full bg-hi/[0.08] border border-tint/35 rounded-2xl px-6 py-4 outline-none focus:border-accent/50 transition-all text-fg placeholder-fg/20"
                      placeholder="Введите или выберите заказчика"
                    />
                    {showCustomerDrop && filteredCustomers.length > 0 && (
                      <div className="mt-2 w-full bg-[var(--theme-dropdown)] border border-tint/40 rounded-2xl overflow-y-auto shadow-2xl shadow-black/50" style={{ maxHeight: '172px' }}>
                        {filteredCustomers.map(c => (
                          <button key={c} type="button"
                            onMouseDown={() => { setNewCustomer(c); setShowCustomerDrop(false); }}
                            className="w-full text-left px-6 py-3.5 text-sm text-fg/70 hover:bg-tint/20 hover:text-fg transition-colors border-b border-tint/10 last:border-0">
                            {c}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
              <div className="flex gap-4 mt-6 sm:mt-10">
                <button onClick={() => setIsCreateModalOpen(false)} className="flex-1 py-4 rounded-2xl bg-hi/5 hover:bg-hi/10 font-bold transition-all">Отмена</button>
                <button onClick={handleCreate} disabled={!newNumber.trim() || isCreating}
                  className="flex-1 py-4 rounded-2xl bg-primary hover:bg-primary-h text-white font-bold transition-all shadow-lg shadow-primary/20 flex items-center justify-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {isCreating ? (
                    <div className="w-5 h-5 border-2 border-hi/30 border-t-white rounded-full animate-spin" />
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
