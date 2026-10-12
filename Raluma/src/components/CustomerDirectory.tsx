import { useState } from 'react';
import client from '../api/client';
import { useAuthStore } from '../store/authStore';
import { toast } from '../store/toastStore';

import { changed, type Customer } from '../hooks/useCustomerOptions';

export function CustomerDirectory() {
  const user = useAuthStore(state => state.user);
  const [rows, setRows] = useState<Customer[]>([]);
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const load = async () => {
    try { setRows((await client.get<Customer[]>('/api/customers?include_inactive=true')).data); }
    catch { toast.error('Не удалось загрузить справочник'); }
  };
  const save = async (row?: Customer) => {
    if (busy) return;
    setBusy(true);
    try {
      if (row) await client.put(`/api/customers/${row.id}`, row);
      else { await client.post('/api/customers', { name }); setName(''); }
      await load(); window.dispatchEvent(new Event(changed));
    } catch { toast.error('Не удалось сохранить: проверьте название и отсутствие дубликата'); }
    finally { setBusy(false); }
  };
  if (user?.role !== 'superadmin') return null;
  return <details className="my-3 rounded-xl border border-tint/30 p-3" onToggle={event => { if (event.currentTarget.open) void load(); }}>
    <summary className="cursor-pointer text-sm font-bold">Справочник заказчиков</summary>
    <p className="my-2 text-xs text-fg/60">Изменения списка не переименовывают заказчиков в старых проектах.</p>
    {rows.map(row => <div key={row.id} className="my-2 flex flex-wrap gap-2">
      <input aria-label={`Название заказчика ${row.id}`} className="min-w-0 flex-1 rounded border border-tint/30 bg-surface px-2 py-1" value={row.name} onChange={e => setRows(rows.map(item => item.id === row.id ? { ...item, name: e.target.value } : item))} />
      <button disabled={busy} onClick={() => void save(row)}>Сохранить</button>
      <button disabled={busy} onClick={() => void save({ ...row, is_active: !row.is_active })}>{row.is_active ? 'Отключить' : 'Включить'}</button>
    </div>)}
    <div className="mt-3 flex gap-2"><input aria-label="Новый заказчик" placeholder="Название нового заказчика" className="min-w-0 flex-1 rounded border border-tint/30 bg-surface px-2 py-1" value={name} onChange={e => setName(e.target.value)} /><button disabled={busy || !name.trim()} onClick={() => void save()}>Добавить</button></div>
  </details>;
}
