import { useEffect, useState } from 'react';
import client from '../api/client';
import { useAuthStore } from '../store/authStore';
import { toast } from '../store/toastStore';

export type Customer = { id: number; name: string; is_active: boolean };
const defaults = ['ООО ПРОЗРАЧНЫЕ РЕШЕНИЯ', 'ООО КРОКНА ИНЖИНИРИНГ'];
export const changed = 'raluma-customers-changed';

export function useCustomerOptions() {
  const token = useAuthStore(state => state.token);
  const [names, setNames] = useState<string[]>(token ? [] : defaults);
  useEffect(() => {
    let cancelled = false;
    const load = () => {
      if (!token) { setNames(defaults); return; }
      client.get<Customer[]>('/api/customers').then(({ data }) => {
        if (!cancelled) setNames(data.map(row => row.name));
      }).catch(() => { if (!cancelled) { setNames([]); toast.error('Не удалось загрузить справочник заказчиков'); } });
    };
    load(); window.addEventListener(changed, load);
    return () => { cancelled = true; window.removeEventListener(changed, load); };
  }, [token]);
  return names;
}
