import { useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { Copy, Plus, Trash2, Wrench, X } from 'lucide-react';
import type { QuoteManualService } from '../../api/quotes';
import type { useProjectEconomics } from '../../hooks/useProjectEconomics';
import { useAuthStore } from '../../store/authStore';
import { toast } from '../../store/toastStore';
import { money, numericDraft } from '../../utils/money';
import { INP, LBL, SEL } from './types';

export function ProjectServicesModal({ state, onClose }: {
  state: ReturnType<typeof useProjectEconomics>;
  onClose: () => void;
}) {
  const { config, busy, dirty, error, patch, save } = state;
  const { canManagePrices } = useAuthStore();
  const panel = useRef<HTMLDivElement>(null);
  const pendingFocus = useRef<string | null>(null);
  const services = config?.services ?? [];

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    panel.current?.querySelector<HTMLElement>('input, [data-add-service]')?.focus();
    return () => { if (previous?.isConnected) previous.focus(); };
  }, []);
  useEffect(() => {
    if (!pendingFocus.current) return;
    panel.current?.querySelector<HTMLInputElement>(`[data-service-id="${pendingFocus.current}"] input`)?.focus();
    pendingFocus.current = null;
  }, [services.length]);

  const update = (id: string, changes: Partial<QuoteManualService>) => {
    patch({ services: services.map(row => row.id === id ? { ...row, ...changes } : row) });
  };
  const add = (source?: QuoteManualService) => {
    const service = { ...(source ?? { name: '', quantity: '1', unit: 'шт.', sale_price: '' }), id: crypto.randomUUID() };
    pendingFocus.current = service.id;
    patch({ services: [...services, service] });
  };
  const close = () => { if (!busy) onClose(); };
  const saveServices = async () => {
    if (await save()) {
      toast.success('Услуги проекта сохранены');
      onClose();
    }
  };

  return <div className="fixed inset-0 z-[60] flex items-center justify-center p-3 sm:p-6">
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      onClick={close} className="absolute inset-0 bg-black/80 backdrop-blur-sm" />
    <motion.div ref={panel} role="dialog" aria-modal="true" aria-labelledby="project-services-title"
      initial={{ scale: 0.96, opacity: 0, y: 15 }} animate={{ scale: 1, opacity: 1, y: 0 }} exit={{ scale: 0.96, opacity: 0, y: 15 }}
      className="relative z-10 flex max-h-[94vh] w-full max-w-6xl flex-col overflow-hidden rounded-[2rem] border border-tint/35 bg-modal shadow-2xl"
      onKeyDown={event => {
        if (event.key === 'Escape') { event.stopPropagation(); close(); }
        if (event.key !== 'Tab') return;
        const fields = [...(panel.current?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), select:not(:disabled)') ?? [])];
        const first = fields[0], last = fields.at(-1);
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }}>
      <div className="flex items-center justify-between gap-3 border-b border-tint/20 px-5 py-4 sm:px-8">
        <div>
          <h2 id="project-services-title" className="text-xl font-bold sm:text-2xl">Услуги проекта</h2>
          <p className="mt-1 text-xs text-fg/50">Учитываются один раз на весь проект с указанным количеством.</p>
        </div>
        <button type="button" aria-label="Закрыть услуги" onClick={close} disabled={busy} className="text-fg/30 hover:text-fg disabled:opacity-40"><X className="h-6 w-6" /></button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-4 sm:p-7">
        <p className="mb-4 text-xs text-fg/60">Укажите цену продажи за единицу услуги. К сумме применяются дилерские условия и скидки заказа.</p>
        {error && <p role="alert" className="mb-4 text-sm text-red-500">{error}</p>}
        <fieldset disabled={busy} className="min-w-0 space-y-3">
          {services.length === 0 && <div className="rounded-2xl border border-dashed border-tint/30 p-7 text-center text-sm text-fg/50">Услуги пока не добавлены.</div>}
          {services.map((service, index) => {
            const quantity = numericDraft(service.quantity);
            const price = numericDraft(service.sale_price ?? service.base_cost);
            const amount = quantity !== null && quantity > 0 && price !== null && price >= 0 ? quantity * price : null;
            return <article key={service.id} data-service-id={service.id} aria-label={`Услуга ${index + 1}`} className="rounded-2xl border border-tint/25 bg-surface/30 p-3 sm:p-4">
              <div className="flex items-center gap-3">
                <Wrench className="h-5 w-5 shrink-0 text-accent" />
                <h3 className="min-w-0 flex-1 break-words text-sm font-semibold">{service.name || `Услуга ${index + 1}`}</h3>
                <button type="button" aria-label={`Копировать услугу ${index + 1}`} className="rounded-xl border border-tint/30 p-2" onClick={() => add(service)}><Copy className="h-4 w-4" /></button>
                <button type="button" aria-label={`Удалить услугу ${index + 1}`} className="rounded-xl border border-red-500/25 bg-red-500/5 p-2 text-red-400 hover:bg-red-500/15" onClick={() => patch({ services: services.filter(row => row.id !== service.id) })}><Trash2 className="h-4 w-4" /></button>
              </div>
              <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <label className="space-y-1 sm:col-span-2"><span className={LBL}>Название</span><input className={INP} value={service.name} onChange={event => update(service.id, { name: event.target.value })} placeholder="Например, монтаж или доставка" /></label>
                <label className="space-y-1"><span className={LBL}>Количество</span><input className={INP} inputMode="decimal" value={service.quantity} onChange={event => update(service.id, { quantity: event.target.value })} /></label>
                <label className="space-y-1"><span className={LBL}>Единица</span><select className={SEL} value={service.unit} onChange={event => update(service.id, { unit: event.target.value })}>{[...new Set(['шт.', 'п.м.', 'кв.м.', service.unit])].map(unit => <option key={unit}>{unit}</option>)}</select></label>
                <label className="space-y-1"><span className={LBL}>Цена продажи, ₽/ед.</span><input className={INP} inputMode="decimal" value={service.sale_price ?? service.base_cost ?? ''} onChange={event => update(service.id, { sale_price: event.target.value })} /></label>
                {canManagePrices() && <label className="space-y-1"><span className={LBL}>Себестоимость, ₽/ед.</span><input className={INP} inputMode="decimal" placeholder="Не задана" value={service.actual_cost ?? ''} onChange={event => update(service.id, { actual_cost: event.target.value || null })} /></label>}
                <div className="space-y-1"><span className={LBL}>Сумма до скидок</span><div className="py-2 text-sm font-bold" aria-label="Сумма услуги">{amount === null ? '—' : money(amount)}</div></div>
              </div>
            </article>;
          })}
          <button type="button" data-add-service onClick={() => add()} className="flex items-center gap-2 rounded-xl border border-accent/35 px-4 py-3 text-sm font-bold text-accent"><Plus className="h-4 w-4" />Добавить услугу</button>
        </fieldset>
      </div>
      <div className="flex flex-wrap items-center justify-end gap-3 border-t border-tint/20 bg-black/10 px-5 py-4 sm:px-8">
        {dirty && <p className="mr-auto text-xs text-fg/60">Есть несохранённые изменения</p>}
        <button type="button" onClick={close} disabled={busy} className="rounded-xl border border-tint/25 px-5 py-2.5 text-sm font-bold text-fg/60 hover:bg-hi/5 disabled:opacity-40">Закрыть</button>
        <button type="button" onClick={() => void saveServices()} disabled={busy} className="rounded-xl bg-primary px-6 py-2.5 text-sm font-bold text-white hover:bg-primary-h disabled:opacity-40">{busy ? 'Сохранение…' : 'Сохранить и пересчитать'}</button>
      </div>
    </motion.div>
  </div>;
}
