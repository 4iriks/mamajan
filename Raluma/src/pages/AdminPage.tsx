import React, { useEffect, useState } from 'react';
import { toast } from '../store/toastStore';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import {
  ArrowLeft, Plus, Search, Edit2, Key, Trash2, X,
  User, Shield, Crown, Check, RefreshCw, Copy, LayoutGrid, Users
} from 'lucide-react';
import { useAuthStore } from '../store/authStore';
import {
  UserOut, UserCreate, UserUpdate,
  getUsers, createUser, updateUser, deleteUser, resetPassword
} from '../api/users';

const ROLE_LABELS: Record<string, string> = {
  user: 'Сотрудник',
  admin: 'Администратор',
  superadmin: 'Суперадмин',
};

const ROLE_COLORS: Record<string, string> = {
  user: 'bg-hi/10 text-fg/70 border-hi/15',
  admin: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
  superadmin: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
};

const RoleIcon = ({ role }: { role: string }) => {
  if (role === 'superadmin') return <Crown className="w-3.5 h-3.5" />;
  if (role === 'admin') return <Shield className="w-3.5 h-3.5" />;
  return <User className="w-3.5 h-3.5" />;
};

const CUSTOMERS = ['ПРОЗРАЧНЫЕ РЕШЕНИЯ', 'КРОКНА ИНЖИНИРИНГ', 'СТУДИЯ СПК'];

const INPUT_CLS = "w-full bg-hi/8 border border-tint/40 rounded-2xl px-5 py-3.5 outline-none focus:border-accent/60 transition-all text-fg";
const SELECT_CLS = "w-full bg-hi/8 border border-tint/40 rounded-2xl px-5 py-3.5 outline-none focus:border-accent/60 transition-all text-fg appearance-none";

const emptyForm: UserCreate = {
  username: '',
  display_name: '',
  password: '',
  role: 'user',
  customer: null,
  is_active: true,
};

function genPassword() {
  const chars = 'ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789!@#';
  return Array.from({ length: 12 }, () => chars[Math.floor(Math.random() * chars.length)]).join('');
}

export default function AdminPage() {
  const navigate = useNavigate();
  const { user: me, isAdmin, isSuperAdmin } = useAuthStore();

  const [users, setUsers] = useState<UserOut[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Модал создания/редактирования
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<UserOut | null>(null);
  const [form, setForm] = useState<UserCreate & { id?: number }>(emptyForm);

  // Модал сброса пароля
  const [resetResult, setResetResult] = useState<{ userId: number; name: string; password: string } | null>(null);
  const [copied, setCopied] = useState(false);

  // Модал удаления
  const [deleteTarget, setDeleteTarget] = useState<UserOut | null>(null);

  // Модал массового добавления
  const [isBulkOpen, setIsBulkOpen] = useState(false);
  const [bulkText, setBulkText] = useState('');
  const [bulkRole, setBulkRole] = useState('user');
  const [bulkCustomer, setBulkCustomer] = useState('');
  const [bulkLoading, setBulkLoading] = useState(false);
  const [bulkResults, setBulkResults] = useState<Array<{ username: string; password: string; status: 'ok' | 'error'; message?: string }>>([]);

  useEffect(() => {
    if (!isAdmin()) { navigate('/'); return; }
    loadUsers();
  }, []);

  const loadUsers = async () => {
    setLoading(true);
    setLoadError(null);
    try { setUsers(await getUsers()); }
    catch (e: any) {
      const msg = e.response?.data?.detail || 'Не удалось загрузить пользователей';
      setLoadError(msg);
      toast.error(msg);
    }
    finally { setLoading(false); }
  };

  const filtered = users.filter(u =>
    u.username.toLowerCase().includes(search.toLowerCase()) ||
    u.display_name.toLowerCase().includes(search.toLowerCase())
  );

  const openCreate = () => {
    setEditingUser(null);
    setForm(emptyForm);
    setIsEditOpen(true);
  };

  const openEdit = (u: UserOut) => {
    setEditingUser(u);
    setForm({ ...u, password: '' });
    setIsEditOpen(true);
  };

  const handleSave = async () => {
    try {
      if (editingUser) {
        const upd: UserUpdate = {
          display_name: form.display_name,
          role: form.role,
          customer: form.customer,
          is_active: form.is_active,
        };
        if (form.password) upd.password = form.password;
        await updateUser(editingUser.id, upd);
      } else {
        await createUser(form);
      }
      setIsEditOpen(false);
      await loadUsers();
    } catch (e: any) {
      toast.error(e.response?.data?.detail || 'Ошибка сохранения');
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await deleteUser(deleteTarget.id);
      setDeleteTarget(null);
      await loadUsers();
      toast.success('Пользователь удалён');
    } catch (e: any) {
      toast.error(e.response?.data?.detail || 'Ошибка удаления');
    }
  };

  const handleResetPassword = async (u: UserOut) => {
    try {
      const { new_password } = await resetPassword(u.id);
      setResetResult({ userId: u.id, name: u.display_name, password: new_password });
      setCopied(false);
    } catch (e: any) {
      toast.error(e.response?.data?.detail || 'Ошибка сброса пароля');
    }
  };

  const copyPassword = () => {
    if (resetResult) {
      navigator.clipboard.writeText(resetResult.password);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleBulkCreate = async () => {
    const lines = bulkText.split('\n').map(l => l.trim()).filter(l => l.length > 0);
    if (!lines.length) return;
    setBulkLoading(true);
    const results: typeof bulkResults = [];
    for (const username of lines) {
      const password = genPassword();
      try {
        await createUser({
          username,
          display_name: username,
          password,
          role: bulkRole,
          customer: bulkCustomer || null,
          is_active: true,
        });
        results.push({ username, password, status: 'ok' });
      } catch (e: any) {
        results.push({ username, password: '', status: 'error', message: e.response?.data?.detail || 'Ошибка' });
      }
    }
    setBulkResults(results);
    setBulkLoading(false);
    await loadUsers();
  };

  const copyBulkResults = () => {
    const text = bulkResults
      .filter(r => r.status === 'ok')
      .map(r => `${r.username} / ${r.password}`)
      .join('\n');
    navigator.clipboard.writeText(text);
  };

  return (
    <div className="min-h-screen bg-page text-fg font-sans flex flex-col">
      <div className="fixed inset-0 overflow-hidden pointer-events-none z-0">
        <div className="absolute top-[-10%] right-[-5%] w-[50%] h-[50%] bg-tint/12 rounded-full blur-[120px]" />
        <div className="absolute bottom-[-10%] left-[-5%] w-[40%] h-[40%] bg-glow2/8 rounded-full blur-[120px]" />
      </div>

      {/* Navbar */}
      <nav className="sticky top-0 z-40 bg-page/90 backdrop-blur-md border-b border-tint/25 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-tint/25 border border-tint/40 flex items-center justify-center">
            <LayoutGrid className="w-6 h-6 text-accent" />
          </div>
          <span className="text-xl font-bold tracking-tight uppercase">Ралюма</span>
        </div>
        <div className="flex items-center gap-3 text-sm text-fg/50">
          <span>{me?.display_name}</span>
          <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 text-[10px] font-bold uppercase">
            {ROLE_LABELS[me?.role || 'user']}
          </span>
        </div>
      </nav>

      <main className="flex-1 p-4 sm:p-8 max-w-5xl mx-auto w-full z-10">
        {/* Header */}
        <div className="flex items-center gap-4 mb-8">
          <button onClick={() => navigate('/')}
            className="flex items-center gap-2 text-fg/50 hover:text-accent transition-colors group">
            <ArrowLeft className="w-4 h-4 group-hover:-translate-x-1 transition-transform" />
            <span className="text-sm font-bold uppercase tracking-wider">К проектам</span>
          </button>
          <div className="h-6 w-px bg-tint/25" />
          <h1 className="text-2xl font-bold">Администрирование</h1>
        </div>

        {/* Toolbar */}
        <div className="flex flex-col sm:flex-row gap-3 mb-6">
          <div className="relative flex-1 group">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-fg/25 group-focus-within:text-accent transition-colors" />
            <input type="text" placeholder="Поиск по логину или имени..." value={search}
              onChange={e => setSearch(e.target.value)}
              className="w-full bg-surface/30 border border-tint/30 rounded-2xl pl-12 pr-4 py-4 outline-none focus:border-accent/50 transition-all text-fg"
            />
          </div>
          <div className="flex gap-3">
            <button onClick={() => { setIsBulkOpen(true); setBulkText(''); setBulkRole('user'); setBulkCustomer(''); setBulkResults([]); }}
              className="flex items-center gap-2 px-4 sm:px-6 py-4 bg-tint/25 hover:bg-tint/40 text-accent font-bold rounded-2xl transition-all border border-tint/35 whitespace-nowrap">
              <Users className="w-5 h-5" />
              <span className="hidden sm:inline">Массовое добавление</span>
            </button>
            <button onClick={openCreate}
              className="flex-1 sm:flex-none flex items-center justify-center gap-2 px-4 sm:px-6 py-4 bg-primary hover:bg-primary-h text-white font-bold rounded-2xl transition-all shadow-lg shadow-primary/20 whitespace-nowrap">
              <Plus className="w-5 h-5" />
              Создать сотрудника
            </button>
          </div>
        </div>

        {/* Table */}
        <div className="bg-surface/30 backdrop-blur-xl border border-tint/25 rounded-[2rem] overflow-hidden shadow-2xl">
          <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left border-collapse">
            <thead>
              <tr className="border-b border-tint/20 bg-hi/[0.03]">
                <th className="px-8 py-5 text-[10px] font-bold uppercase tracking-widest text-fg/50">Логин</th>
                <th className="px-8 py-5 text-[10px] font-bold uppercase tracking-widest text-fg/50">Имя</th>
                <th className="px-8 py-5 text-[10px] font-bold uppercase tracking-widest text-fg/50">Роль</th>
                <th className="px-8 py-5 text-[10px] font-bold uppercase tracking-widest text-fg/50">Заказчик</th>
                <th className="px-8 py-5 text-[10px] font-bold uppercase tracking-widest text-fg/50">Статус</th>
                <th className="px-8 py-5 text-[10px] font-bold uppercase tracking-widest text-fg/50 text-right">Действия</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={6} className="py-20 text-center text-fg/40">Загрузка...</td></tr>
              ) : loadError ? (
                <tr><td colSpan={6} className="py-20 text-center text-red-400">{loadError}</td></tr>
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-20 text-center">
                    <div className="flex flex-col items-center gap-4">
                      <div className="w-20 h-20 rounded-full bg-tint/15 border border-tint/25 flex items-center justify-center">
                        <User className="w-10 h-10 text-fg/25" />
                      </div>
                      <div>
                        <h3 className="text-xl font-bold mb-1">{search ? 'Ничего не найдено' : 'Сотрудников нет'}</h3>
                        <p className="text-fg/40 text-sm">{search ? 'Попробуйте другой запрос' : 'Создайте первого сотрудника'}</p>
                      </div>
                    </div>
                  </td>
                </tr>
              ) : filtered.map(u => (
                <motion.tr key={u.id} initial={{ opacity: 0 }} animate={{ opacity: u.is_active ? 1 : 0.45 }}
                  className="border-b border-tint/10 hover:bg-hi/[0.03] transition-colors group">
                  <td className="px-8 py-5 font-mono text-sm text-accent font-bold">{u.username}</td>
                  <td className="px-8 py-5 text-sm font-medium text-fg/90">{u.display_name}</td>
                  <td className="px-8 py-5">
                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold border ${ROLE_COLORS[u.role]}`}>
                      <RoleIcon role={u.role} />
                      {ROLE_LABELS[u.role]}
                    </span>
                  </td>
                  <td className="px-8 py-5 text-sm text-fg/50">{u.customer || '—'}</td>
                  <td className="px-8 py-5">
                    <span className={`inline-flex items-center gap-1.5 text-xs font-bold ${u.is_active ? 'text-emerald-400' : 'text-red-400'}`}>
                      <span className={`w-2 h-2 rounded-full ${u.is_active ? 'bg-emerald-400' : 'bg-red-400'}`} />
                      {u.is_active ? 'Активен' : 'Неактивен'}
                    </span>
                  </td>
                  <td className="px-8 py-5 text-right">
                    <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button onClick={() => openEdit(u)}
                        className="p-2 rounded-lg hover:bg-tint/25 text-accent transition-colors" title="Изменить">
                        <Edit2 className="w-4 h-4" />
                      </button>
                      <button onClick={() => handleResetPassword(u)}
                        className="p-2 rounded-lg hover:bg-tint/25 text-accent transition-colors" title="Сбросить пароль">
                        <Key className="w-4 h-4" />
                      </button>
                      {u.id !== me?.id && (
                        <button onClick={() => setDeleteTarget(u)}
                          className="p-2 rounded-lg hover:bg-red-500/20 text-red-400 transition-colors" title="Удалить">
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </td>
                </motion.tr>
              ))}
            </tbody>
          </table>
          </div>
          <div className="px-8 py-4 bg-hi/[0.02] border-t border-tint/20 text-xs text-fg/40">
            Всего сотрудников: <span className="text-fg font-bold">{users.length}</span>
          </div>
        </div>
      </main>

      {/* Модал создания/редактирования */}
      <AnimatePresence>
        {isEditOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => setIsEditOpen(false)} className="absolute inset-0 bg-black/75 backdrop-blur-sm" />
            <motion.div initial={{ scale: 0.9, opacity: 0, y: 20 }} animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.9, opacity: 0, y: 20 }}
              className="relative w-full max-w-lg bg-modal border border-tint/40 rounded-[2.5rem] p-6 sm:p-10 shadow-2xl z-10 overflow-y-auto max-h-[95vh]">
              <button onClick={() => setIsEditOpen(false)} className="absolute right-8 top-8 text-fg/30 hover:text-fg transition-colors">
                <X className="w-6 h-6" />
              </button>
              <h2 className="text-2xl font-bold mb-8">{editingUser ? 'Изменить сотрудника' : 'Новый сотрудник'}</h2>

              <div className="space-y-5">
                <div className="space-y-2">
                  <label className="text-[10px] font-bold uppercase tracking-widest text-accent/50 ml-1">Логин</label>
                  <input type="text" value={form.username}
                    onChange={e => setForm(f => ({ ...f, username: e.target.value }))}
                    disabled={!!editingUser}
                    className={INPUT_CLS + (editingUser ? ' opacity-40' : '') + ' font-mono'}
                    placeholder="ivan.petrov"
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-[10px] font-bold uppercase tracking-widest text-accent/50 ml-1">Имя</label>
                  <input type="text" value={form.display_name}
                    onChange={e => setForm(f => ({ ...f, display_name: e.target.value }))}
                    className={INPUT_CLS}
                    placeholder="Иван Петров"
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-[10px] font-bold uppercase tracking-widest text-accent/50 ml-1">
                    Пароль {editingUser && <span className="normal-case font-normal text-fg/30">(оставьте пустым чтобы не менять)</span>}
                  </label>
                  <div className="flex gap-2">
                    <input type="text" value={form.password}
                      onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                      className={INPUT_CLS + ' font-mono flex-1'}
                      placeholder="••••••••"
                    />
                    <button onClick={() => setForm(f => ({ ...f, password: genPassword() }))}
                      className="px-4 py-3.5 rounded-2xl bg-tint/25 border border-tint/40 text-accent hover:bg-tint/40 transition-colors"
                      title="Сгенерировать пароль">
                      <RefreshCw className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-[10px] font-bold uppercase tracking-widest text-accent/50 ml-1">Роль</label>
                  <div className="flex gap-2">
                    {(['user', 'admin', ...(isSuperAdmin() ? ['superadmin'] : [])] as string[]).map(role => (
                      <button key={role} onClick={() => setForm(f => ({ ...f, role }))}
                        className={`flex-1 py-3 rounded-xl border text-xs font-bold transition-all ${
                          form.role === role ? 'bg-accent/10 border-accent/50 text-accent' : 'bg-hi/5 border-tint/25 text-fg/50 hover:border-tint/50'
                        }`}>
                        {ROLE_LABELS[role]}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-[10px] font-bold uppercase tracking-widest text-accent/50 ml-1">Заказчик</label>
                  <select value={form.customer || ''} onChange={e => setForm(f => ({ ...f, customer: e.target.value || null }))}
                    className={SELECT_CLS}>
                    <option value="">Без привязки</option>
                    {CUSTOMERS.map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>

                <div className="flex items-center justify-between py-3 px-1">
                  <span className="text-sm font-medium text-fg/80">Активен</span>
                  <button onClick={() => setForm(f => ({ ...f, is_active: !f.is_active }))}
                    className={`w-12 h-6 rounded-full transition-colors relative ${form.is_active ? 'bg-primary' : 'bg-hi/15'}`}>
                    <span className={`absolute top-1 w-4 h-4 rounded-full bg-hi shadow transition-transform ${form.is_active ? 'translate-x-7' : 'translate-x-1'}`} />
                  </button>
                </div>
              </div>

              <div className="flex gap-4 mt-8">
                <button onClick={() => setIsEditOpen(false)}
                  className="flex-1 py-4 rounded-2xl bg-hi/5 hover:bg-hi/10 font-bold transition-all">Отмена</button>
                <button onClick={handleSave}
                  className="flex-1 py-4 rounded-2xl bg-primary hover:bg-primary-h text-white font-bold transition-all shadow-lg shadow-primary/20">Сохранить</button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Модал массового добавления */}
      <AnimatePresence>
        {isBulkOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => !bulkLoading && setIsBulkOpen(false)} className="absolute inset-0 bg-black/75 backdrop-blur-sm" />
            <motion.div initial={{ scale: 0.9, opacity: 0, y: 20 }} animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.9, opacity: 0, y: 20 }}
              className="relative w-full max-w-2xl bg-modal border border-tint/40 rounded-[2.5rem] p-10 shadow-2xl z-10 max-h-[90vh] overflow-y-auto custom-scrollbar">
              <button onClick={() => setIsBulkOpen(false)} className="absolute right-8 top-8 text-fg/30 hover:text-fg transition-colors">
                <X className="w-6 h-6" />
              </button>
              <div className="flex items-center gap-3 mb-8">
                <div className="w-12 h-12 rounded-2xl bg-tint/25 border border-tint/40 flex items-center justify-center">
                  <Users className="w-6 h-6 text-accent" />
                </div>
                <h2 className="text-2xl font-bold">Массовое добавление</h2>
              </div>

              {bulkResults.length === 0 ? (
                <div className="space-y-6">
                  <div className="space-y-2">
                    <label className="text-[10px] font-bold uppercase tracking-widest text-accent/50 ml-1">
                      Логины (по одному на строку)
                    </label>
                    <textarea
                      value={bulkText}
                      onChange={e => setBulkText(e.target.value)}
                      rows={6}
                      className="w-full bg-hi/8 border border-tint/40 rounded-2xl px-5 py-4 outline-none focus:border-accent/60 transition-all font-mono text-fg resize-none"
                      placeholder={"ivan.petrov\nanna.sidorova\npetr.ivanov"}
                    />
                    <p className="text-xs text-fg/30 ml-1">Пароли будут сгенерированы автоматически</p>
                  </div>

                  <div className="space-y-2">
                    <label className="text-[10px] font-bold uppercase tracking-widest text-accent/50 ml-1">Роль</label>
                    <div className="flex gap-2">
                      {(['user', 'admin', ...(isSuperAdmin() ? ['superadmin'] : [])] as string[]).map(role => (
                        <button key={role} onClick={() => setBulkRole(role)}
                          className={`flex-1 py-3 rounded-xl border text-xs font-bold transition-all ${
                            bulkRole === role ? 'bg-accent/10 border-accent/50 text-accent' : 'bg-hi/5 border-tint/25 text-fg/50 hover:border-tint/50'
                          }`}>
                          {ROLE_LABELS[role]}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="space-y-2">
                    <label className="text-[10px] font-bold uppercase tracking-widest text-accent/50 ml-1">Заказчик (необязательно)</label>
                    <select value={bulkCustomer} onChange={e => setBulkCustomer(e.target.value)} className={SELECT_CLS}>
                      <option value="">Без привязки</option>
                      {CUSTOMERS.map(c => <option key={c} value={c}>{c}</option>)}
                    </select>
                  </div>

                  <div className="flex gap-4">
                    <button onClick={() => setIsBulkOpen(false)}
                      className="flex-1 py-4 rounded-2xl bg-hi/5 hover:bg-hi/10 font-bold transition-all">Отмена</button>
                    <button
                      onClick={handleBulkCreate}
                      disabled={bulkLoading || !bulkText.trim()}
                      className="flex-1 py-4 rounded-2xl bg-primary hover:bg-primary-h text-white font-bold transition-all shadow-lg shadow-primary/20 disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                    >
                      {bulkLoading ? (
                        <><div className="w-5 h-5 border-2 border-black/30 border-t-black rounded-full animate-spin" /> Создаём...</>
                      ) : 'Создать всех'}
                    </button>
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  <p className="text-fg/60 text-sm mb-6">
                    Создано: <span className="text-emerald-400 font-bold">{bulkResults.filter(r => r.status === 'ok').length}</span> из {bulkResults.length}
                  </p>
                  <div className="space-y-2 max-h-64 overflow-y-auto custom-scrollbar">
                    {bulkResults.map((r, i) => (
                      <div key={i} className={`flex items-center gap-4 px-4 py-3 rounded-xl border ${r.status === 'ok' ? 'bg-emerald-500/10 border-emerald-500/20' : 'bg-red-500/10 border-red-500/20'}`}>
                        <span className={`text-sm font-mono font-bold ${r.status === 'ok' ? 'text-emerald-400' : 'text-red-400'}`}>{r.username}</span>
                        {r.status === 'ok' ? (
                          <span className="flex-1 font-mono text-accent text-sm">{r.password}</span>
                        ) : (
                          <span className="flex-1 text-red-400/70 text-xs">{r.message}</span>
                        )}
                      </div>
                    ))}
                  </div>
                  <div className="flex gap-4 mt-6">
                    <button onClick={copyBulkResults}
                      className="flex-1 py-4 rounded-2xl bg-tint/25 border border-tint/40 text-accent font-bold transition-all hover:bg-tint/40 flex items-center justify-center gap-2">
                      <Copy className="w-4 h-4" /> Скопировать логины/пароли
                    </button>
                    <button onClick={() => setIsBulkOpen(false)}
                      className="flex-1 py-4 rounded-2xl bg-primary hover:bg-primary-h text-white font-bold transition-all">
                      Готово
                    </button>
                  </div>
                </div>
              )}
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Модал сброса пароля */}
      <AnimatePresence>
        {resetResult && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => setResetResult(null)} className="absolute inset-0 bg-black/75 backdrop-blur-sm" />
            <motion.div initial={{ scale: 0.9, opacity: 0, y: 20 }} animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.9, opacity: 0, y: 20 }}
              className="relative w-full max-w-md bg-modal border border-tint/40 rounded-[2.5rem] p-6 sm:p-10 shadow-2xl z-10">
              <button onClick={() => setResetResult(null)} className="absolute right-8 top-8 text-fg/30 hover:text-fg transition-colors">
                <X className="w-6 h-6" />
              </button>
              <div className="w-16 h-16 rounded-2xl bg-tint/25 border border-tint/40 flex items-center justify-center mb-6">
                <Key className="w-8 h-8 text-accent" />
              </div>
              <h2 className="text-2xl font-bold mb-2">Новый пароль</h2>
              <p className="text-fg/60 mb-6">Сотрудник: <span className="text-fg font-bold">{resetResult.name}</span></p>
              <div className="flex items-center gap-3 bg-hi/8 border border-tint/40 rounded-2xl px-5 py-4 mb-4">
                <span className="flex-1 font-mono text-lg font-bold text-accent">{resetResult.password}</span>
                <button onClick={copyPassword} className="p-2 rounded-lg hover:bg-tint/25 text-accent transition-colors">
                  {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                </button>
              </div>
              <p className="text-amber-400/80 text-xs font-bold mb-8">⚠ Скопируйте пароль сейчас. После закрытия он не будет показан повторно.</p>
              <button onClick={() => setResetResult(null)}
                className="w-full py-4 rounded-2xl bg-primary hover:bg-primary-h text-white font-bold transition-all">Закрыть</button>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Модал удаления */}
      <AnimatePresence>
        {deleteTarget && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => setDeleteTarget(null)} className="absolute inset-0 bg-black/75 backdrop-blur-sm" />
            <motion.div initial={{ scale: 0.9, opacity: 0, y: 20 }} animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.9, opacity: 0, y: 20 }}
              className="relative w-full max-w-md bg-modal border border-red-500/30 rounded-[2rem] p-8 shadow-2xl z-10">
              <button onClick={() => setDeleteTarget(null)} className="absolute right-6 top-6 text-fg/30 hover:text-fg transition-colors">
                <X className="w-6 h-6" />
              </button>
              <div className="w-16 h-16 rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center mb-6">
                <Trash2 className="w-8 h-8 text-red-400" />
              </div>
              <h2 className="text-2xl font-bold mb-2">Удалить сотрудника?</h2>
              <p className="text-fg/60 mb-8">
                Сотрудник <span className="text-fg font-bold">{deleteTarget.username}</span> будет удалён безвозвратно.
              </p>
              <div className="flex gap-4">
                <button onClick={() => setDeleteTarget(null)} className="flex-1 py-4 rounded-2xl bg-hi/5 hover:bg-hi/10 font-bold transition-all">Отмена</button>
                <button onClick={handleDelete} className="flex-1 py-4 rounded-2xl bg-red-500 hover:bg-red-400 text-white font-bold transition-all">Удалить</button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
