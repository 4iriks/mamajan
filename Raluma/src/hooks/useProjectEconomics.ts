import { useCallback, useEffect, useRef, useState } from 'react';
import { getInternalQuote, getPublicQuote, updateQuoteConfig } from '../api/quotes';
import type { PublicQuote, QuoteConfig } from '../api/quotes';
import { toast } from '../store/toastStore';

export function useProjectEconomics(projectId: number, enabled: boolean, editable: boolean) {
  const [quote, setQuote] = useState<PublicQuote | null>(null);
  const [config, setConfig] = useState<QuoteConfig | null>(null);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
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
  }, [projectId]);

  const reload = useCallback(async () => {
    if (!enabled) return;
    const owner = generation.current;
    try {
      const publicQuote = await getPublicQuote(projectId);
      const internal = editable ? await getInternalQuote(projectId) : null;
      if (!mounted.current || owner !== generation.current) return;
      setQuote(publicQuote);
      // A background refresh must never replace an unsaved input.
      if (internal && (!draft.current || JSON.stringify(draft.current) === saved.current)) {
        saved.current = JSON.stringify(internal.config);
        draft.current = internal.config;
        setConfig(internal.config);
        setDirty(false);
      }
      setError('');
    } catch {
      if (mounted.current && owner === generation.current) setError('Не удалось загрузить стоимость. Повторите загрузку.');
    }
  }, [enabled, editable, projectId]);
  useEffect(() => { void reload(); }, [reload]);

  const patch = (changes: Partial<QuoteConfig>) => {
    if (!draft.current) return;
    const next = { ...draft.current, ...changes };
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
            || current.discounts.some(rule => !rule.value.trim() || !Number.isFinite(Number(rule.value))
              || Number(rule.value) < 0 || (rule.mode === 'percent' && Number(rule.value) > 100))) {
            throw new Error('Проверьте скидки (0–100% или сумма от 0) и срок действия (1–365 дней).');
          }
          const result = await updateQuoteConfig(projectId, {
            validity_days: current.validity_days, manufacturing_term: current.manufacturing_term,
            payment_terms: current.payment_terms, services: current.services, discounts: current.discounts,
          });
          if (!mounted.current || owner !== generation.current) return false;
          saved.current = JSON.stringify(current);
          if (mounted.current) setQuote(result);
        }
        if (mounted.current) { setDirty(false); setError(''); }
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
  return { quote, config, dirty, busy, error, patch, save, reload };
}
