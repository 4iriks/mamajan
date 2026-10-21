import React, { useEffect, useState } from 'react';
import { useCustomerOptions } from '../../hooks/useCustomerOptions';
import { SEL } from './types';

export const ProjectCustomerField: React.FC<{
  value: string;
  onSave: (customer: string) => Promise<void>;
}> = ({ value, onSave }) => {
  const options = useCustomerOptions();
  const [draft, setDraft] = useState(value);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => { setDraft(value); setError(''); }, [value]);
  const dirty = draft !== value;
  const valid = options.includes(draft);

  const save = async () => {
    if (!dirty || !valid || saving) return;
    setSaving(true);
    setError('');
    try {
      await onSave(draft);
    } catch {
      setError('Не удалось сохранить заказчика. Выбор сохранён на экране — попробуйте ещё раз.');
    } finally {
      setSaving(false);
    }
  };

  return <div className="mb-3 space-y-2" data-project-customer>
    <div className="flex flex-wrap items-center gap-2">
      <label htmlFor="project-customer" className="text-sm font-bold">Заказчик</label>
      <select id="project-customer" value={draft} disabled={saving}
        onChange={event => { setDraft(event.target.value); setError(''); }}
        className={`${SEL} min-w-0 flex-1 basis-60 disabled:opacity-60`}>
        {!value && <option value="" disabled>Выберите заказчика</option>}
        {value && !options.includes(value) && <option value={value}>{value} (текущий)</option>}
        {options.map(name => <option key={name} value={name}>{name}</option>)}
      </select>
      {dirty && <>
        <button type="button" disabled={saving || !valid} onClick={() => void save()}
          className="rounded-lg bg-primary px-3 py-1.5 text-xs font-bold text-white disabled:opacity-50">
          {saving ? 'Сохранение…' : 'Сохранить заказчика'}
        </button>
        <button type="button" disabled={saving} onClick={() => { setDraft(value); setError(''); }}
          className="rounded-lg border border-tint/30 px-3 py-1.5 text-xs disabled:opacity-50">Отмена</button>
      </>}
    </div>
    {dirty && <p className="text-xs text-fg/60">Сменится заказчик проекта. Зафиксированные КП останутся без изменений.</p>}
    {error && <p role="alert" className="text-xs text-red-500">{error}</p>}
  </div>;
};
