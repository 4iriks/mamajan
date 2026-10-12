import { useCallback, useEffect, useRef, useState } from 'react';
import { getInternalQuote, getPublicQuote, updateQuoteConfig, updateQuoteOverrides } from '../api/quotes';
import type { InternalQuoteState, PublicQuote, QuoteConfig, QuotePriceOverride } from '../api/quotes';
import { toast } from '../store/toastStore';
import { orderQuoteDiscounts } from '../utils/quoteDiscounts';
import { numericDraft, validMoney } from '../utils/money';
import { useAuthStore } from '../store/authStore';

export function useProjectEconomics(projectId: number, enabled: boolean, editable: boolean) {
  const [quote, setQuote] = useState<PublicQuote | null>(null);
  const [config, setConfig] = useState<QuoteConfig | null>(null);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [internal, setInternal] = useState<InternalQuoteState | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const reloadVersion = useRef(0);
  const draft = useRef<QuoteConfig | null>(null);
  const saved = useRef('');
  const inFlight = useRef<Promise<boolean> | null>(null);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const generation = useRef(0);
  useEffect(() => {
    generation.current += 1;
    draft.current = null;
    saved.current = '';
    inFlight.current = null;
    setQuote(null); setConfig(null); setDirty(false); setBusy(false); setError('');
    setInternal(null); setRefreshing(false);
  }, [projectId]);

  const reload = useCallback(async () => {
    if (!enabled) return;
    const owner = generation.current;
    const request = ++reloadVersion.current;
    setRefreshing(true);
    try {
      const publicQuote = await getPublicQuote(projectId);
      const internal = editable ? await getInternalQuote(projectId) : null;
      if (!mounted.current || owner !== generation.current || request !== reloadVersion.current) return;
      setQuote(publicQuote);
      setInternal(internal);
      // A background refresh must never replace an unsaved input.
      if (internal && (!draft.current || JSON.stringify(draft.current) === saved.current)) {
        saved.current = JSON.stringify(internal.config);
        draft.current = internal.config;
        setConfig(internal.config);
        setDirty(false);
      }
      setError('');
    } catch {
      if (mounted.current && owner === generation.current && request === reloadVersion.current) setError('Не удалось обновить стоимость. Показанные суммы могут быть устаревшими. Повторите загрузку.');
    } finally {
      if (mounted.current && owner === generation.current && request === reloadVersion.current) setRefreshing(false);
    }
  }, [enabled, editable, projectId]);
  useEffect(() => { void reload(); }, [reload]);

  const patch = (changes: Partial<QuoteConfig>) => {
    if (!draft.current) return;
    const next = { ...draft.current, ...changes };
    if (changes.discounts) next.discounts = orderQuoteDiscounts(changes.discounts);
    draft.current = next;
    setConfig(next);
    setDirty(JSON.stringify(next) !== saved.current);
  };

  const save = (): Promise<boolean> => {
    if (inFlight.current) return inFlight.current;
    if (!draft.current || JSON.stringify(draft.current) === saved.current) return Promise.resolve(true);
    const owner = generation.current;
    const task = async () => {
      setBusy(true);
      try {
        // Drain edits made while a request was in flight before allowing export/navigation.
        while (draft.current && JSON.stringify(draft.current) !== saved.current) {
          const current = draft.current;
          if (!(current.validity_days >= 1 && current.validity_days <= 365)
            || current.discounts.some(rule => !validMoney(rule.value, rule.mode === 'percent' ? 100 : undefined))) {
            throw new Error('Проверьте скидки (0–100% или сумма от 0) и срок действия (1–365 дней).');
          }
          if (current.services.some(service => !service.name.trim() || (numericDraft(service.quantity) ?? 0) <= 0
            || !validMoney(service.sale_price ?? service.base_cost)
            || (service.actual_cost != null && service.actual_cost !== '' && !validMoney(service.actual_cost)))) {
            throw new Error('Для каждой услуги укажите название, количество больше 0 и цену продажи. Себестоимость необязательна, но не может быть отрицательной.');
          }
          const result = await updateQuoteConfig(projectId, {
            validity_days: current.validity_days, manufacturing_term: current.manufacturing_term,
            payment_terms: current.payment_terms,
            services: current.services.map(service => {
              const { actual_cost, ...publicService } = service;
              return { ...publicService, quantity: service.quantity.replace(',', '.'), sale_price: (service.sale_price ?? service.base_cost ?? '').replace(',', '.'), ...(useAuthStore.getState().canManagePrices() && actual_cost !== undefined ? { actual_cost: actual_cost?.replace(',', '.') || null } : {}) };
            }),
            discounts: current.discounts.map(rule => ({ ...rule, value: rule.value.replace(',', '.') })),
          });
          if (!mounted.current || owner !== generation.current) return false;
          saved.current = JSON.stringify(current);
          if (mounted.current) setQuote(result);
        }
        if (mounted.current) { setDirty(false); setError(''); }
        void reload();
        return true;
      } catch (cause) {
        const message = cause instanceof Error && !('response' in cause) ? cause.message : 'Не удалось сохранить стоимость и скидки. Ввод сохранён на экране.';
        if (mounted.current && owner === generation.current) { setError(message); toast.error(message); }
        return false;
      } finally {
        if (mounted.current && owner === generation.current) setBusy(false);
      }
    };
    inFlight.current = task().finally(() => { if (owner === generation.current) inFlight.current = null; });
    return inFlight.current;
  };

  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ''; };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [dirty]);
  const saveOverrides = async (overrides: QuotePriceOverride[], approval?: string): Promise<boolean> => {
    if (!await save()) return false;
    setBusy(true);
    try {
      await updateQuoteOverrides(projectId, overrides, approval);
      await reload();
      return true;
    } catch (cause) {
      const detail = (cause as { response?: { data?: { detail?: unknown } } }).response?.data?.detail;
      const message = typeof detail === 'string' ? detail : 'Не удалось сохранить разовую цену или разрешение. Проверьте данные и права доступа.';
      setError(message); toast.error(message); return false;
    } finally { setBusy(false); }
  };
  return { quote, config, internal, dirty, busy, refreshing, error, patch, save, reload, saveOverrides };
}
