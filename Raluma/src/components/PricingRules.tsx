import { useCallback, useEffect, useState } from 'react';
import { applyRuleBindings, listPricingRules, listRuleBindings, previewPricingRule, previewRuleBindings, pricingFields, savePricingRule } from '../api/pricingRules';
import type { BindingInput, PricingRule, RuleBinding, RuleInput, RulePreview } from '../api/pricingRules';
import { money, validMoney } from '../utils/money';
import { toast } from '../store/toastStore';

const input = 'h-10 w-full rounded-lg border border-tint/30 bg-page/40 px-3 text-sm';
const button = 'rounded-lg border border-accent/30 bg-accent/10 px-4 py-2 text-sm font-semibold text-accent disabled:opacity-40';
const emptyRule = (): RuleInput => ({ name: '', scope: 'default', is_active: true, effective_from: '', reason: '', profile_markup_percent: '0', profile_discount_percent: '0', waste_markup_percent: '0', construction_markup_percent: '0', construction_discount_percent: '0' });
const ruleDate = (value: string) => new Date(/(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? value : `${value}Z`);
const localDateInput = (value: string) => { const date = ruleDate(value); return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16); };
const message = (error: unknown) => {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  return typeof detail === 'string' ? detail : 'Не удалось выполнить действие. Проверьте данные и повторите.';
};

export function RulePreviewTable({ preview }: { preview: RulePreview }) {
  return <div className="mt-4 overflow-auto rounded-xl border border-tint/25"><p className="p-3 text-sm">Затронуто исполнений: <b>{preview.count ?? preview.rows.length}</b>. Показаны первые 30.</p><table className="min-w-[650px] w-full text-left text-xs"><thead><tr>{['Позиция / исполнение', 'Источник после', 'Профиль: было → станет', 'Конструкция: было → станет'].map(title => <th key={title} className="p-3 font-medium">{title}</th>)}</tr></thead><tbody>{preview.rows.slice(0, 30).map(row => <tr key={row.finish_variant_id} className="border-t border-tint/20"><td className="p-3"><b>{row.sku}</b> · {row.name}<div>{row.finish_name}</div></td><td className="p-3">{row.after.source?.label || row.after.source?.name || row.after.source?.mode}</td><td className="p-3">{money(row.before.profile?.final)} → <b>{money(row.after.profile?.final)}</b></td><td className="p-3">{money(row.before.construction?.final)} → <b>{money(row.after.construction?.final)}</b></td></tr>)}</tbody></table></div>;
}

export function PricingRules({ onApplied }: { onApplied: () => void }) {
  const [rules, setRules] = useState<PricingRule[]>([]);
  const [groups, setGroups] = useState<string[]>([]);
  const [bindings, setBindings] = useState<RuleBinding[]>([]);
  const [ruleId, setRuleId] = useState<number>();
  const [draft, setDraft] = useState<RuleInput | null>(null);
  const [preview, setPreview] = useState<RulePreview | null>(null);
  const [previewInput, setPreviewInput] = useState<RuleInput | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState('');
  const [selected, setSelected] = useState<number[]>([]);
  const [bindingPreview, setBindingPreview] = useState<RulePreview | null>(null);
  const [bindingInput, setBindingInput] = useState<BindingInput | null>(null);
  const [bindingReason, setBindingReason] = useState('');
  const load = useCallback(async () => {
    try {
      const [result, linked] = await Promise.all([listPricingRules(), listRuleBindings()]);
      setRules(result.rules); setGroups(result.groups); setBindings(linked.rows); setError('');
    } catch (cause) { setError(message(cause)); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  const edit = (rule?: PricingRule) => {
    const version = rule?.active_version || rule?.next_version;
    setRuleId(rule?.id); setDraft(rule ? { ...emptyRule(), ...version, name: version?.name || rule.name, scope: rule.scope, group_name: rule.group_name || undefined, is_active: version?.is_active ?? rule.is_active, effective_from: !rule.active_version && rule.next_version ? localDateInput(rule.next_version.effective_from) : '', reason: '' } : emptyRule()); setPreview(null); setPreviewInput(null);
  };
  const change = (values: Partial<RuleInput>) => { setDraft(current => current ? { ...current, ...values } : null); setPreview(null); setPreviewInput(null); };
  const prepare = async () => {
    if (!draft) return;
    if (!draft.name.trim() || !draft.reason.trim() || (draft.scope === 'group' && !draft.group_name) || pricingFields.some(([field]) => !validMoney(draft[field], field.includes('discount') ? 100 : undefined))) { setError('Укажите название, группу при необходимости, причину и корректные проценты (скидки 0–100%).'); return; }
    const effective = draft.effective_from ? new Date(draft.effective_from) : new Date();
    if (Number.isNaN(effective.getTime())) { setError('Некорректная дата начала действия.'); return; }
    const payload = { ...draft, effective_from: effective.toISOString(), ...Object.fromEntries(pricingFields.map(([field]) => [field, draft[field].replace(',', '.')])) };
    setBusy(true);
    try { setPreview(await previewPricingRule({ ...payload, rule_id: ruleId })); setPreviewInput(payload); setError(''); } catch (cause) { setError(message(cause)); } finally { setBusy(false); }
  };
  const apply = async () => {
    if (!previewInput) return;
    setBusy(true);
    try { await savePricingRule(previewInput, ruleId); setDraft(null); setPreview(null); setPreviewInput(null); await load(); onApplied(); toast.success('Версия правила сохранена'); } catch (cause) { setError(message(cause)); } finally { setBusy(false); }
  };
  const prepareBindings = async (mode: 'auto' | 'individual') => {
    if (!selected.length || !bindingReason.trim()) { setError('Выберите исполнения и укажите причину смены источника цены.'); return; }
    const payload = { finish_variant_ids: selected, mode, reason: bindingReason.trim() };
    setBusy(true);
    try { setBindingPreview(await previewRuleBindings(payload)); setBindingInput(payload); setError(''); } catch (cause) { setError(message(cause)); } finally { setBusy(false); }
  };
  const applyBindings = async () => {
    if (!bindingInput) return;
    setBusy(true);
    try { await applyRuleBindings(bindingInput); setSelected([]); setBindingInput(null); setBindingPreview(null); await load(); onApplied(); toast.success('Источник цен обновлён'); } catch (cause) { setError(message(cause)); } finally { setBusy(false); }
  };
  const filtered = bindings.filter(row => `${row.sku} ${row.name} ${row.group_name} ${row.finish_name}`.toLowerCase().includes(filter.toLowerCase()));
  return <section className="mx-auto mb-5 w-full max-w-6xl space-y-4">
    <div className="rounded-2xl border border-tint/25 bg-surface/30 p-5"><div className="flex justify-between gap-3"><h2 className="text-lg font-bold">Готовые правила цен</h2><button className={button} onClick={() => edit()}>+ Правило</button></div><p className="mt-2 text-sm text-fg/65">Для автоматического исполнения: правило группы каталога, иначе общее правило. Индивидуальные значения имеют приоритет. Проценты не складываются между уровнями — выбирается один источник.</p><p className="mt-2 text-xs text-fg/60">Существующие исполнения остаются индивидуальными, пока вы явно не подключите правило. Себестоимость берётся из позиции, а не из правила. Старые зафиксированные КП не изменяются.</p></div>
    {error && <p role="alert" className="rounded-lg border border-red-500/30 p-3 text-sm text-red-600">{error}</p>}
    <div className="grid gap-3 md:grid-cols-2">{rules.map(rule => <div key={rule.id} className="rounded-xl border border-tint/25 bg-surface/30 p-4"><div className="flex justify-between gap-2"><b>{rule.name}</b><button className={button} onClick={() => edit(rule)}>Изменить</button></div><p className="my-2 text-sm">{rule.scope === 'default' ? 'Общее правило' : `Группа: ${rule.group_name}`} · {rule.is_active ? 'активно' : 'отключено'}</p>{rule.active_version && <p className="text-xs text-fg/65">Профиль: +{rule.active_version.profile_markup_percent}% / −{rule.active_version.profile_discount_percent}%. Конструкция: отходы +{rule.active_version.waste_markup_percent}%, наценка +{rule.active_version.construction_markup_percent}%, скидка −{rule.active_version.construction_discount_percent}%.</p>}{rule.next_version && <p className="mt-2 text-xs text-amber-700">Новая версия с {ruleDate(rule.next_version.effective_from).toLocaleString('ru-RU')}</p>}<details className="mt-2 text-xs"><summary className="cursor-pointer">История версий ({rule.versions.length})</summary>{rule.versions.map(version => <p key={version.id} className="mt-2">№{version.id} · {ruleDate(version.effective_from).toLocaleString('ru-RU')} · {version.reason || version.name}</p>)}</details></div>)}</div>
    {draft && <div className="rounded-2xl border border-accent/35 bg-surface/40 p-5"><h3 className="font-bold mb-3">{ruleId ? 'Новая версия правила' : 'Новое правило'}</h3><fieldset disabled={busy} className="space-y-3"><div className="grid gap-3 sm:grid-cols-2"><label className="text-xs">Название<input className={input} value={draft.name} onChange={event => change({ name: event.target.value })} /></label><label className="text-xs">Уровень<select className={input} disabled={!!ruleId} value={draft.scope} onChange={event => change({ scope: event.target.value as RuleInput['scope'] })}><option value="default">Общее правило</option><option value="group">Группа каталога</option></select></label>{draft.scope === 'group' && <label className="text-xs">Группа<select className={input} disabled={!!ruleId} value={draft.group_name || ''} onChange={event => change({ group_name: event.target.value })}><option value="">Выберите группу</option>{groups.map(group => <option key={group}>{group}</option>)}</select></label>}<label className="text-xs">Начало действия<input type="datetime-local" className={input} value={draft.effective_from} onChange={event => change({ effective_from: event.target.value })} /><span className="text-fg/60">Пусто — применить сейчас; время вашего устройства.</span></label></div><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">{pricingFields.map(([field, label]) => <label className="text-xs" key={field}>{label}, %<input className={input} inputMode="decimal" value={draft[field]} onChange={event => change({ [field]: event.target.value })} /></label>)}</div><label className="block text-xs">Причина изменения<input className={input} value={draft.reason} onChange={event => change({ reason: event.target.value })} /></label><label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={draft.is_active} onChange={event => change({ is_active: event.target.checked })} />Правило активно</label><div className="flex gap-2"><button className={button} onClick={() => void prepare()}>Проверить изменения</button><button className={button} disabled={!previewInput} onClick={() => void apply()}>Подтвердить и сохранить</button><button className={button} onClick={() => setDraft(null)}>Отмена</button></div></fieldset>{preview && <RulePreviewTable preview={preview} />}</div>}
    <div className="rounded-2xl border border-tint/25 bg-surface/30 p-5"><h3 className="font-bold">Какие исполнения используют правила</h3><input className={`${input} mt-3`} placeholder="Артикул, название, группа или исполнение" value={filter} onChange={event => setFilter(event.target.value)} /><div className="mt-3 max-h-96 overflow-auto"><table className="w-full min-w-[550px] text-left text-xs"><thead><tr><th className="p-2"><input aria-label="Выбрать все отфильтрованные исполнения" type="checkbox" checked={filtered.length > 0 && filtered.every(row => selected.includes(row.finish_variant_id))} onChange={event => { setSelected(event.target.checked ? [...new Set([...selected, ...filtered.map(row => row.finish_variant_id)])] : selected.filter(id => !filtered.some(row => row.finish_variant_id === id))); setBindingPreview(null); setBindingInput(null); }} /></th><th>Позиция / исполнение</th><th>Источник</th></tr></thead><tbody>{filtered.map(row => <tr key={row.finish_variant_id} className="border-t border-tint/20"><td className="p-2"><input aria-label={`Выбрать ${row.sku} ${row.finish_name}`} type="checkbox" checked={selected.includes(row.finish_variant_id)} onChange={event => { setSelected(event.target.checked ? [...selected, row.finish_variant_id] : selected.filter(id => id !== row.finish_variant_id)); setBindingInput(null); setBindingPreview(null); }} /></td><td className="p-2"><b>{row.sku}</b> · {row.name}<p className="text-fg/60">{row.finish_name} · {row.group_name}</p></td><td>{!row.resolved ? 'Нет действующей цены' : row.mode === 'individual' ? 'Индивидуальные значения' : row.resolved.source?.label || row.resolved.source?.name || 'По правилу'}</td></tr>)}</tbody></table></div><p className="mt-3 text-xs">Выбрано: {selected.length}. Перевод в индивидуальные значения сохраняет текущие коэффициенты.</p><input className={`${input} my-3`} placeholder="Причина смены источника" value={bindingReason} onChange={event => { setBindingReason(event.target.value); setBindingInput(null); setBindingPreview(null); }} /><div className="flex flex-wrap gap-2"><button className={button} disabled={busy || !selected.length} onClick={() => void prepareBindings('auto')}>Подключить / вернуть правило</button><button className={button} disabled={busy || !selected.length} onClick={() => void prepareBindings('individual')}>Индивидуальные значения</button>{bindingInput && <button className={button} disabled={busy} onClick={() => void applyBindings()}>Подтвердить применение</button>}</div>{bindingPreview && <RulePreviewTable preview={bindingPreview} />}</div>
  </section>;
}
