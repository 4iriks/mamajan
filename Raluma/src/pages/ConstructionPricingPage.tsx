import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Check, History, Loader2, Plus, RefreshCw, RotateCcw, Save, Search, Trash2 } from 'lucide-react';
import {
  getSystemPricingHistory, listPricingSamples, loadSystemPricing, previewSystemPricing, saveSystemPricing,
  type ComponentSettings, type GeneralSettings, type PricingDraft, type PricingHistory, type PricingPreview,
  type SampleOption, type SampleResult, type SystemCode, type SystemComponent, type SystemConfiguration,
} from '../api/constructionPricing';
import { isCsCalcPreview, isBookCalcPreview } from '../api/projects';
import { apiToLocal } from '../components/editor/converters';
import { CsRoomView } from '../components/editor/EditorVisualizer';
import { SlideRoomViewSVG } from '../components/editor/SlideDiagrams';
import { useAuthStore } from '../store/authStore';
import { toast } from '../store/toastStore';
import { money } from '../utils/money';
import './ConstructionPricingPage.css';

const SYSTEMS: { code: SystemCode; name: string; subtitle: string }[] = [
  { code: 'SLIDE_1', name: 'Слайд 1 ряд', subtitle: 'Раздвижное остекление' },
  { code: 'SLIDE_2', name: 'Слайд 2 ряда', subtitle: 'Раздвижное остекление' },
  { code: 'CS', name: 'ЦС', subtitle: 'Цельностеклянные конструкции' },
];
const FIELDS = ['waste_percent', 'markup_percent', 'discount_percent'] as const;
const LABELS = { waste_percent: 'Отходы', markup_percent: 'Наценка', discount_percent: 'Скидка' };
const card = 'rounded-2xl border border-tint/30 bg-surface/40';
const button = 'inline-flex items-center justify-center gap-2 rounded-xl border border-tint/35 px-3 py-2 text-sm font-semibold hover:bg-hi/5 disabled:cursor-not-allowed disabled:opacity-40';
const input = 'w-full min-w-0 rounded-xl border border-tint/35 bg-page/60 px-3 py-2.5 text-sm text-fg outline-none focus:border-primary';
const pct = (value: string) => {
  const text = value.trim().replace(',', '.');
  return /^\d+(?:\.\d{0,4})?$/.test(text) && Number(text) < 10000 ? String(Number(text)) : null;
};
const valid = (field: string, value: string) => pct(value) !== null && (!field.includes('discount') || Number(pct(value)) <= 100);
const same = (a: string, b: string) => pct(a) !== null && pct(a) === pct(b);
const errorText = (error: unknown) => {
  const detail = (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail;
  return typeof detail === 'string' ? detail : 'Не удалось загрузить данные. Введённые значения сохранены.';
};
const zero: ComponentSettings = { waste_percent: '0', markup_percent: '0', discount_percent: '0' };
type Workspace = {
  config: SystemConfiguration; general: GeneralSettings; edits: Record<string, ComponentSettings>;
  examples: number[]; selected: number | null; unavailable?: SystemComponent[];
};
// Rebase only fields the user actually edited; untouched fields follow the server.
const rebaseWorkspace = (current: Workspace, config: SystemConfiguration): Workspace => {
  const previous = new Map([...current.config.components, ...(current.unavailable || [])].map(row => [row.key, row]));
  const available = new Map(config.components.map(row => [row.key, row]));
  const edits: Workspace['edits'] = {};
  for (const [key, values] of Object.entries(current.edits)) {
    const next = available.get(key);
    if (!next) { edits[key] = values; continue; }
    const before = previous.get(key)?.settings || zero;
    const merged = Object.fromEntries(FIELDS.map(field => [field,
      same(values[field], before[field]) ? (next.settings || zero)[field] : values[field],
    ])) as ComponentSettings;
    if (!next.settings || FIELDS.some(field => !same(merged[field], next.settings![field]))) edits[key] = merged;
  }
  return { ...current, config, edits,
    unavailable: [...previous.values()].filter(row => edits[row.key] && !available.has(row.key)),
    general: {
      markup_percent: same(current.general.markup_percent, current.config.general.markup_percent) ? config.general.markup_percent : current.general.markup_percent,
      discount_percent: same(current.general.discount_percent, current.config.general.discount_percent) ? config.general.discount_percent : current.general.discount_percent,
    } };
};
const storageKey = (user: number, code: SystemCode, kind: string) => `raluma-system-pricing-${kind}-${user}-${code}`;
const initialWorkspace = (config: SystemConfiguration, options: SampleOption[], user: number): Workspace => {
  try {
    const saved = JSON.parse(sessionStorage.getItem(storageKey(user, config.code, 'draft')) || 'null') as Workspace | null;
    if (saved?.config?.code === config.code && saved.general && saved.edits && Array.isArray(saved.examples)) return rebaseWorkspace(saved, config);
  } catch { /* A damaged local draft must not prevent loading server settings. */ }
  let examples = options.slice(0, 3).map(row => row.section_id);
  try {
    const ids = JSON.parse(localStorage.getItem(storageKey(user, config.code, 'examples')) || 'null');
    if (Array.isArray(ids)) examples = [...new Set(ids.filter((id): id is number => Number.isInteger(id) && id > 0))];
  } catch { /* Use available server samples. */ }
  return { config, general: { ...config.general }, edits: {}, examples, selected: examples[0] ?? null };
};

function PercentField({ label, value, before, field, onChange, disabled }: {
  label: string; value: string; before?: string; field: keyof ComponentSettings;
  onChange: (value: string) => void; disabled?: boolean;
}) {
  const changed = before !== undefined && !same(value, before);
  return <label className="pricing-percent-field block min-w-0">
    <span className="mb-1.5 block text-[10px] font-bold uppercase tracking-wide text-fg/55">{LABELS[field]}</span>
    <span className="relative block"><input aria-label={label} inputMode="decimal" value={value}
      disabled={disabled} aria-invalid={!valid(field, value)} onChange={event => onChange(event.target.value)}
      className={`${input} pr-7 font-mono aria-[invalid=true]:border-amber-500/60 ${changed ? 'border-amber-500/60 bg-amber-500/5' : ''}`} />
      <span className="pointer-events-none absolute right-2 top-3 text-xs text-fg/40">%</span></span>
    <span className="mt-1 block min-h-3.5 text-[10px] text-amber-700 dark:text-amber-300">{changed ? `Было ${before}%` : '\u00a0'}</span>
  </label>;
}

function PriceOutput({ label, value }: { label: string; value?: string | null }) {
  return <div className="pricing-price-output min-w-0"><span className="mb-1.5 block text-[10px] font-bold uppercase tracking-wide text-fg/55">{label}</span>
    <div className="break-words rounded-xl border border-primary/20 bg-primary/5 px-2.5 py-2.5 font-mono text-sm font-semibold tabular-nums text-fg">{value == null ? '—' : money(value)}</div></div>;
}

function Delta({ before, after }: { before?: string | null; after?: string | null }) {
  if (before == null || after == null) return <span className="text-fg/45">—</span>;
  const difference = Math.round((Number(after) - Number(before)) * 100) / 100;
  const percent = Number(before) === 0 ? null : difference / Number(before) * 100;
  return <span className={difference === 0 ? 'text-fg/45' : 'text-amber-700 dark:text-amber-300'}>
    <span className="block whitespace-nowrap font-semibold">{difference > 0 ? '+' : ''}{money(difference)}</span>
    {percent !== null && <span className="block text-xs">{percent > 0 ? '+' : ''}{percent.toLocaleString('ru-RU', { maximumFractionDigits: 2 })}%</span>}
  </span>;
}

function SampleDiagram({ result }: { result: SampleResult }) {
  if (!result.section || !result.calculation) return null;
  const section = apiToLocal(result.section);
  return <div className="my-4 rounded-xl bg-white p-4 text-[#123f47]">
    {isCsCalcPreview(result.calculation) ? <CsRoomView section={section} calc={result.calculation} />
      : !isBookCalcPreview(result.calculation) ? <SlideRoomViewSVG section={section} calc={result.calculation} fit /> : null}
  </div>;
}

export default function ConstructionPricingPage() {
  const navigate = useNavigate();
  const { user, token, canManagePrices, isAdmin } = useAuthStore();
  const allowed = canManagePrices();
  const [code, setCode] = useState<SystemCode>('SLIDE_1');
  const [workspaces, setWorkspaces] = useState<Partial<Record<SystemCode, Workspace>>>({});
  const [options, setOptions] = useState<Partial<Record<SystemCode, SampleOption[]>>>({});
  const [search, setSearch] = useState('');
  const [group, setGroup] = useState('');
  const [finish, setFinish] = useState('');
  const [usedOnly, setUsedOnly] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [previews, setPreviews] = useState<Partial<Record<SystemCode, { key: string; data: PricingPreview }>>>({});
  const [previewError, setPreviewError] = useState('');
  const [history, setHistory] = useState<PricingHistory[] | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const workspace = workspaces[code] as Workspace | undefined;
  const config = workspace?.config;
  const change = useCallback((update: (value: Workspace) => Workspace) => {
    setWorkspaces(current => current[code] ? { ...current, [code]: update(current[code]!) } : current);
  }, [code]);

  useEffect(() => {
    if (!token) navigate('/login', { replace: true });
    else if (user && !allowed) navigate('/', { replace: true });
  }, [allowed, navigate, token, user]);

  useEffect(() => {
    if (!allowed || !user) return;
    let cancelled = false;
    setError('');
    Promise.all([loadSystemPricing(code), listPricingSamples(code)]).then(([loaded, samples]) => {
      if (cancelled) return;
      setOptions(current => ({ ...current, [code]: samples }));
      setWorkspaces(current => ({ ...current, [code]: current[code] ? rebaseWorkspace(current[code]!, loaded) : initialWorkspace(loaded, samples, user.id) }));
    }).catch(error => { if (!cancelled) setError(errorText(error)); });
    return () => { cancelled = true; };
  }, [allowed, code, user, refresh]);

  const dirty = Boolean(workspace && (Object.keys(workspace.edits).length ||
    !same(workspace.general.markup_percent, workspace.config.general.markup_percent) ||
    !same(workspace.general.discount_percent, workspace.config.general.discount_percent)));
  const anyDirty = (Object.values(workspaces) as Workspace[]).some(value => value && (Object.keys(value.edits).length ||
    !same(value.general.markup_percent, value.config.general.markup_percent) ||
    !same(value.general.discount_percent, value.config.general.discount_percent)));
  useEffect(() => {
    const beforeUnload = (event: BeforeUnloadEvent) => { if (anyDirty) { event.preventDefault(); event.returnValue = ''; } };
    window.addEventListener('beforeunload', beforeUnload);
    return () => window.removeEventListener('beforeunload', beforeUnload);
  }, [anyDirty]);
  useEffect(() => {
    if (!user) return;
    try {
      (Object.entries(workspaces) as [SystemCode, Workspace][]).forEach(([system, value]) => {
        if (!value) return;
        sessionStorage.setItem(storageKey(user.id, system as SystemCode, 'draft'), JSON.stringify(value));
        localStorage.setItem(storageKey(user.id, system as SystemCode, 'examples'), JSON.stringify(value.examples));
      });
    } catch { /* Storage can be disabled. The active in-memory draft remains. */ }
  }, [user, workspaces]);

  const validDraft = Boolean(workspace && Object.entries(workspace.general).every(([field, value]) => valid(field, value)) &&
    Object.values(workspace.edits).every(row => FIELDS.every(field => valid(field, row[field]))));
  const draft: PricingDraft | null = useMemo(() => !workspace || !validDraft ? null : ({
    general: { markup_percent: pct(workspace.general.markup_percent)!, discount_percent: pct(workspace.general.discount_percent)! },
    components: Object.fromEntries(Object.entries(workspace.edits).filter(([key]) => workspace.config.components.some(row => row.key === key)).map(([key, row]) => [key,
      { waste_percent: pct(row.waste_percent)!, markup_percent: pct(row.markup_percent)!, discount_percent: pct(row.discount_percent)! }])),
    section_ids: workspace.examples,
  }), [workspace, validDraft]);
  const preview = previews[code];
  const requestKey = JSON.stringify([config?.token, draft]);
  const fallback = useMemo(() => !draft && workspace && !preview ? {
    general: workspace.config.general, components: {}, section_ids: workspace.examples,
  } : null, [draft, workspace, preview]);
  useEffect(() => {
    const payload = draft || fallback;
    if (!payload || !allowed) return;
    const controller = new AbortController();
    setPreviewError('');
    const timer = window.setTimeout(() => {
      previewSystemPricing(code, payload, controller.signal).then(data => {
        if (!controller.signal.aborted) setPreviews(current => ({ ...current, [code]: { key: requestKey, data } }));
      }).catch(error => { if (!controller.signal.aborted) setPreviewError(errorText(error)); });
    }, 250);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [allowed, code, draft, fallback, requestKey, refresh]);
  // A temporarily empty field must not unmount the focused card or the drawing.
  const view = preview?.key === requestKey && validDraft ? preview.data : null;
  const displayed = view || preview?.data;
  const pending = validDraft && !view && !previewError;
  const stale = Boolean(view && config && view.token !== config.token);
  const outdated = Boolean(displayed && !view);
  const selected = displayed?.samples.find(row => row.section_id === workspace?.selected);
  const samples = options[code] || [];
  const totals = useMemo(() => {
    const values = new Map<string, { quantity: number; saved: number | null; draft: number | null }>();
    for (const [kind, result] of [['saved', selected?.saved], ['draft', selected?.draft]] as const) {
      const quantities = new Map<string, number>();
      for (const row of result?.bom || []) {
        const value = values.get(row.component_key) || { quantity: 0, saved: null, draft: null };
        value[kind] = (value[kind] || 0) + Math.round(Number(row.internal_total) * 100);
        quantities.set(row.component_key, (quantities.get(row.component_key) || 0) + Number(row.quantity));
        values.set(row.component_key, value);
      }
      for (const issue of result?.issues || []) {
        if (!issue.component_key) continue;
        const value = values.get(issue.component_key) || { quantity: 0, saved: null, draft: null };
        value[kind] = null;
        quantities.set(issue.component_key, (quantities.get(issue.component_key) || 0) + Number(issue.quantity || 0));
        values.set(issue.component_key, value);
      }
      quantities.forEach((quantity, key) => { values.get(key)!.quantity = quantity; });
    }
    return values;
  }, [selected]);
  const unavailable = (workspace?.unavailable || []).filter(row => workspace?.edits[row.key]);
  const filtered = [...(config?.components || []), ...unavailable].filter(row =>
    (!search.trim() || `${row.sku} ${row.name} ${row.finish}`.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase())) &&
    (!group || row.group === group) && (!finish || row.finish_code === finish) && (!usedOnly || totals.has(row.key)));
  const previewRows = new Map<string, SystemComponent>(displayed?.components.map(row => [row.key, row]));

  const editComponent = (row: SystemComponent, field: keyof ComponentSettings, value: string) => change(current => {
    const next = { ...(current.edits[row.key] || row.settings || zero), [field]: value };
    const edits = { ...current.edits, [row.key]: next };
    if (row.settings && FIELDS.every(key => same(next[key], row.settings![key]))) delete edits[row.key];
    return { ...current, edits };
  });
  const refreshSource = async () => {
    setBusy(true); setError('');
    try {
      const loaded = await loadSystemPricing(code);
      change(current => rebaseWorkspace(current, loaded));
      setRefresh(value => value + 1);
    } catch (error) { setError(errorText(error)); } finally { setBusy(false); }
  };
  const save = async () => {
    if (!workspace || !draft || busy || unavailable.length) return;
    setBusy(true); setError('');
    try {
      const loaded = await saveSystemPricing(code, workspace.config.token, draft);
      change(current => ({ ...current, config: loaded, general: loaded.general, edits: {} }));
      setHistory(null); setRefresh(value => value + 1); toast.success(`${loaded.name}: настройки сохранены`);
    } catch (error) { setError(errorText(error)); } finally { setBusy(false); }
  };
  const leave = () => {
    if (!anyDirty || window.confirm('Есть несохранённые настройки. Вернуться к проектам? Черновик останется в этой вкладке.')) navigate('/');
  };
  useEffect(() => {
    if (!historyOpen) return;
    let cancelled = false;
    getSystemPricingHistory(code).then(value => { if (!cancelled) setHistory(value); })
      .catch(error => { if (!cancelled) setError(errorText(error)); });
    return () => { cancelled = true; };
  }, [code, historyOpen, refresh]);
  const replaceExample = (oldId: number, newId: number) => change(current => ({ ...current,
    examples: [...new Set(current.examples.map(id => id === oldId ? newId : id))],
    selected: current.selected === oldId ? newId : current.selected }));

  if (!allowed) return null;
  return <div className="min-h-screen bg-page text-fg">
    <header className="sticky top-0 z-30 border-b border-tint/25 bg-page/95 px-4 py-3 backdrop-blur-md sm:px-7">
      <div className="mx-auto flex max-w-[1680px] flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3"><button className={button} onClick={leave} aria-label="К проектам"><ArrowLeft size={17} /></button>
          <div><h1 className="text-lg font-bold sm:text-xl">Настройка конструкций</h1><p className="text-xs text-fg/50">Расценки системы и проверка на ваших конструкциях</p></div></div>
        <div className="flex flex-wrap items-center gap-2">
          {dirty && <span className="text-xs text-amber-700 dark:text-amber-300">Есть изменения</span>}
          <button className={button} disabled={busy || !dirty} onClick={() => change(current => ({ ...current, general: { ...current.config.general }, edits: {} }))}><RotateCcw size={15} />Сбросить</button>
          <button className={`${button} border-primary bg-primary text-white hover:bg-primary-h`} disabled={!dirty || !validDraft || busy || stale || pending || !!previewError || !!unavailable.length} onClick={() => void save()}>
            {busy ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}Сохранить систему</button>
        </div>
      </div>
    </header>
    <main className="mx-auto max-w-[1680px] space-y-5 p-4 sm:p-7">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap gap-2" aria-label="Выбор системы">{SYSTEMS.map(system => <button key={system.code} disabled={busy}
          onClick={() => { setCode(system.code); setSearch(''); setGroup(''); setFinish(''); setHistory(null); setHistoryOpen(false); }}
          aria-pressed={code === system.code} className={`${card} min-w-36 px-5 py-3 text-left ${code === system.code ? 'border-primary bg-primary/10 ring-1 ring-primary/30' : 'hover:bg-hi/5'}`}>
          <span className="flex items-center justify-between gap-5 font-bold">{system.name}{code === system.code && <Check size={16} className="text-primary" />}</span><span className="mt-1 block text-xs text-fg/50">{system.subtitle}</span>
        </button>)}</div>
        <button className={button} disabled={busy} onClick={() => void refreshSource()}><RefreshCw size={15} />Обновить исходные цены</button>
      </div>
      {error && <div role="alert" className="rounded-xl border border-red-500/30 bg-red-500/5 p-4 text-sm">{error}<button className={`${button} ml-3`} onClick={() => setRefresh(value => value + 1)}>Повторить</button></div>}
      {!workspace && !error && <div className="flex items-center gap-2 py-14 text-fg/55"><Loader2 className="animate-spin" size={20} />Загружаем настройки системы…</div>}
      {workspace && <>
        {(previewError || stale) && <div role="alert" className="rounded-xl border border-amber-500/40 bg-amber-500/5 p-4 text-sm">
          {previewError || 'Исходные цены изменились. Нажмите «Обновить исходные цены», проверьте результат и сохраните. Ваши проценты останутся.'}
          {previewError && <button className={`${button} ml-3`} onClick={() => setRefresh(value => value + 1)}>Повторить расчёт</button>}
        </div>}
        {!!unavailable.length && <p role="alert" className="text-sm text-amber-700 dark:text-amber-300">Некоторые изменённые позиции больше недоступны. Их ввод сохранён в карточках; перед сохранением системы отмените эти строки.</p>}
        <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_350px] 2xl:grid-cols-[minmax(0,1fr)_370px]">
          <section className={`${card} pricing-components-container min-w-0 overflow-hidden`} aria-label="Комплектующие системы">
            <div className="space-y-3 border-b border-tint/25 p-4 sm:p-5">
              <div className="flex flex-wrap justify-between gap-2"><h2 className="font-bold">Комплектующие · {config?.name}</h2><span className="text-xs text-fg/50">{filtered.length} исполнений</span></div>
              <p className="text-xs leading-relaxed text-fg/55">Себестоимость общая из каталога. Проценты действуют только в этой системе. Расход показан для выбранного образца.</p>
              <div className="grid gap-2 sm:grid-cols-3"><label className="relative"><Search size={15} className="absolute left-3 top-3 text-fg/40" /><input aria-label="Поиск комплектующих" placeholder="Артикул или название" value={search} onChange={event => setSearch(event.target.value)} className={`${input} pl-9`} /></label>
                <select aria-label="Группа комплектующих" value={group} onChange={event => setGroup(event.target.value)} className={input}><option value="">Все группы</option>{[...new Set(config?.components.map(row => row.group))].map(value => <option key={value}>{value}</option>)}</select>
                <select aria-label="Исполнение комплектующих" value={finish} onChange={event => setFinish(event.target.value)} className={input}><option value="">Все исполнения</option>{[...new Map(config?.components.map(row => [row.finish_code, row.finish])).entries()].map(([key, name]) => <option value={key} key={key}>{name}</option>)}</select></div>
              <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={usedOnly} onChange={event => setUsedOnly(event.target.checked)} />Используются в образце</label>
            </div>
            <div className="pricing-component-scroll max-h-[78vh] overflow-y-auto overscroll-contain p-3">
              {!filtered.length && <p className="p-6 text-center text-sm text-fg/55">По этим условиям комплектующих нет.</p>}
              <div className="pricing-component-grid">{filtered.map(row => {
                const values = workspace.edits[row.key] || row.settings;
                const changed = Boolean(workspace.edits[row.key]);
                const computed = previewRows.get(row.key);
                const usage = totals.get(row.key);
                return <article key={row.key} data-component-key={row.key} className={`pricing-component-card rounded-xl border p-3 ${changed ? 'border-amber-500/40 bg-amber-500/[0.035]' : 'border-tint/25 bg-page/30'}`}>
                  <div className="pricing-component-heading mb-3"><div className="min-w-0"><h3 className="text-sm font-semibold leading-snug">{row.name}</h3><p className="mt-1 text-xs text-fg/55">{row.sku} · {row.finish} · {row.unit}</p></div>
                    <div className="text-right"><span className="block text-[10px] uppercase text-fg/50">Себестоимость / {row.unit}</span><strong className="font-mono text-sm">{row.cost_is_set ? money(row.cost) : 'Не заполнена'}</strong>
                      {isAdmin() && <a href={`/admin/catalog/hardware?item=${row.catalog_item_id}`} target="_blank" rel="noreferrer" className="mt-1 block text-[10px] text-accent underline">В каталоге ↗</a>}</div></div>
                  <div className="pricing-card-stages">
                    <div className="pricing-stage-pair">
                    <PercentField label={`${row.sku} ${row.finish}: отходы`} field="waste_percent" value={values?.waste_percent ?? ''} before={row.settings?.waste_percent} disabled={busy} onChange={value => editComponent(row, 'waste_percent', value)} />
                    <PriceOutput label="После отходов" value={computed?.draft_stages?.after_waste} />
                    </div><div className="pricing-stage-pair">
                    <PercentField label={`${row.sku} ${row.finish}: наценка`} field="markup_percent" value={values?.markup_percent ?? ''} before={row.settings?.markup_percent} disabled={busy} onChange={value => editComponent(row, 'markup_percent', value)} />
                    <PriceOutput label="После наценки" value={computed?.draft_stages?.after_markup} />
                    </div><div className="pricing-stage-pair">
                    <PercentField label={`${row.sku} ${row.finish}: скидка`} field="discount_percent" value={values?.discount_percent ?? ''} before={row.settings?.discount_percent} disabled={busy} onChange={value => editComponent(row, 'discount_percent', value)} />
                    <PriceOutput label={`Цена / ${row.unit}`} value={computed?.draft_stages?.final} />
                    </div>
                  </div>
                  {unavailable.some(value => value.key === row.key) && <p className="mt-2 text-xs text-amber-700 dark:text-amber-300">Позиция больше недоступна. Ваш ввод сохранён.</p>}
                  {!row.configured && !changed && <p className="mt-2 text-xs text-amber-700 dark:text-amber-300">Не настроено. Введите проценты для этой системы.</p>}
                  <div className="pricing-component-footer mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-tint/20 pt-2 text-xs">
                    <span className="text-fg/55">Расход в образце <b className="ml-2 text-fg">{usage ? `${usage.quantity.toLocaleString('ru-RU', { maximumFractionDigits: 4 })} ${row.unit}` : '—'}</b></span>
                    <span>Сумма <b className="ml-2 font-mono">{usage?.draft != null ? money(usage.draft / 100) : '—'}</b></span>
                    {changed && <button disabled={busy} className="flex items-center gap-1 text-accent" onClick={() => change(current => { const edits = { ...current.edits }; delete edits[row.key]; return { ...current, edits }; })}><RotateCcw size={12} />Отменить строку</button>}
                    {usage?.saved != null && usage.saved !== usage.draft && <span className="text-amber-700 dark:text-amber-300">Было {money(usage.saved / 100)}</span>}
                  </div>
                </article>;
              })}</div>
            </div>
          </section>

          <aside className="min-w-0 space-y-4 xl:sticky xl:top-24">
            <section className={`${card} p-5`} aria-label="Общее для системы"><h2 className="font-bold">Общее для системы</h2><p className="mb-4 mt-1 text-xs leading-relaxed text-fg/55">Применяется к сумме комплектующих после их собственных процентов.</p>
              <div className="grid grid-cols-2 gap-3">{(['markup_percent', 'discount_percent'] as const).map(field => <div key={field}><PercentField label={`Общее для системы: ${LABELS[field].toLowerCase()}`} field={field} value={workspace.general[field]} before={config?.general[field]} disabled={busy} onChange={value => change(current => ({ ...current, general: { ...current.general, [field]: value } }))} /></div>)}</div>
            </section>
            <section className={`${card} p-5`} aria-label="Проверка на конструкции" aria-busy={pending}>
              <div className="mb-3 flex items-center justify-between"><h2 className="font-bold">Проверка на конструкции</h2>{pending && <Loader2 size={16} className="animate-spin text-primary" />}</div>
              <p role="status" className="mb-3 min-h-12 text-xs leading-4 text-fg/55">{!validDraft ? 'Завершите ввод процентов: от 0 до 9999,9999, скидка до 100%. Пока показан предыдущий расчёт.' : outdated ? pending ? 'Пересчитываем… Пока показаны предыдущие суммы.' : 'Показан последний расчёт. Повторите обновление.' : 'Суммы обновляются при изменении процентов.'}</p>
              <select className={input} aria-label="Выбранная конструкция" value={workspace.selected ?? ''} onChange={event => {
                const id = Number(event.target.value); change(current => ({ ...current, selected: id, examples: [...new Set([...current.examples, id])] }));
              }}><option value="" disabled>Выберите сохранённую конструкцию</option>{samples.map(row => <option key={row.section_id} value={row.section_id}>{row.label}</option>)}{workspace.selected && !samples.some(row => row.section_id === workspace.selected) && <option value={workspace.selected}>Недоступный пример №{workspace.selected}</option>}</select>
              {!samples.length && <p className="mt-3 text-sm text-fg/55">Сохранённых конструкций этой системы пока нет. Настройки можно заполнить сейчас.</p>}
              {selected?.available && selected.section && <>
                <p className="mt-3 text-xs text-fg/55">{selected.section.width} × {selected.section.height} мм · {selected.section.painting_type} · {selected.section.quantity} изд.</p>
                <SampleDiagram result={selected} />
                <dl className="pricing-sample-totals space-y-2 text-sm"><div className="flex justify-between gap-3"><dt className="text-fg/60">{selected.draft?.complete ? 'Сумма комплектующих' : 'Учтённые комплектующие (неполный расчёт)'}</dt><dd className="font-mono">{money(selected.draft?.stages.subtotal)}</dd></div>
                  <div className="flex justify-between gap-3"><dt className="text-fg/60">После общей наценки {selected.draft?.stages.markup_percent}%</dt><dd className="font-mono">{money(selected.draft?.stages.after_markup)}</dd></div>
                  <div className="flex justify-between gap-3"><dt className="text-fg/60">Общая скидка</dt><dd>{selected.draft?.stages.discount_percent}%</dd></div></dl>
                <div className="mt-4 rounded-xl border border-primary/25 bg-primary/5 p-4"><span className="text-xs text-fg/60">По настройкам системы</span><div className="mt-1 text-2xl font-bold tabular-nums" data-testid="sample-total">{selected.draft?.total == null ? 'Расчёт неполный' : money(selected.draft.total)}</div>
                  <div className="mt-3 flex items-end justify-between gap-3 text-xs"><span className="text-fg/55">Сохранено<br /><b>{selected.saved?.total == null ? 'Нет действующей цены' : money(selected.saved.total)}</b></span><Delta before={selected.saved?.total} after={selected.draft?.total} /></div></div>
                {!!selected.draft?.issues.length && <div className="mt-3 text-xs text-amber-700 dark:text-amber-300"><b>Нужно заполнить:</b><ul className="mt-1 space-y-1">{selected.draft.issues.map((issue, i) => <li key={i}>{issue.sku || issue.name}: {issue.detail || 'проверьте цену, исполнение и единицу'}</li>)}</ul></div>}
                {selected.draft?.below_minimum && <p className="mt-3 text-xs text-amber-700 dark:text-amber-300">Цена ниже минимальной {money(selected.draft.minimum_total)}. В заказе потребуется согласование администратора.</p>}
              </>}
              {selected && !selected.available && <p role="alert" className="mt-4 text-sm text-amber-700 dark:text-amber-300">{selected.error}</p>}
              <p className="mt-4 text-[11px] leading-relaxed text-fg/50">Без условий дилера и скидок заказа. Исходная конструкция и сохранённое КП не меняются.</p>
            </section>
          </aside>
        </div>

        <section className={`${card} relative min-w-0 overflow-hidden`} aria-label="Проверка на других примерах"><div className="flex flex-wrap items-center justify-between gap-3 p-5">
          <div><h2 className="font-bold">Проверка на других примерах</h2><p className="mt-1 text-xs text-fg/55">Одни расценки — разные комплектации. Нажмите пример для подробного расчёта.</p></div>
          <button className={button} disabled={!samples.some(row => !workspace.examples.includes(row.section_id)) || workspace.examples.length >= 100} onClick={() => {
            const next = samples.find(row => !workspace.examples.includes(row.section_id)); if (next) change(current => ({ ...current, examples: [...current.examples, next.section_id], selected: current.selected ?? next.section_id }));
          }}><Plus size={15} />Добавить пример</button></div>
          <div className="overflow-x-auto"><table className="w-full text-left text-sm sm:min-w-[660px]"><thead className="hidden border-y border-tint/25 bg-hi/5 text-xs text-fg/55 sm:table-header-group"><tr><th className="p-4">Конструкция / заменить</th><th className="p-4 text-right">Сохранённая цена</th><th className="p-4 text-right">Новая цена</th><th className="p-4 text-right">Разница</th><th className="w-12"><span className="sr-only">Удалить</span></th></tr></thead>
            <tbody className="block sm:table-row-group">{workspace.examples.map(id => {
              const option = samples.find(row => row.section_id === id); const result = displayed?.samples.find(row => row.section_id === id);
              return <tr key={id} className={`grid grid-cols-2 border-b border-tint/15 sm:table-row ${workspace.selected === id ? 'bg-primary/10' : ''}`}>
                <td className="col-span-2 min-w-0 p-4"><button className="mb-2 block text-left font-semibold hover:text-primary" onClick={() => change(current => ({ ...current, selected: id }))}>{option?.label || `Недоступный пример №${id}`}</button>
                  <select aria-label={`Заменить пример ${id}`} value={id} className={`${input} max-w-sm text-xs`} onChange={event => replaceExample(id, Number(event.target.value))}>
                    {!option && <option value={id}>Выберите замену</option>}{samples.filter(row => row.section_id === id || !workspace.examples.includes(row.section_id)).map(row => <option value={row.section_id} key={row.section_id}>{row.label}</option>)}</select>
                  {option && <p className="mt-1 text-xs text-fg/50">{option.width} × {option.height} мм · {option.finish} · {option.quantity} изд.</p>}
                  {result?.error && <p className="mt-1 text-xs text-amber-700 dark:text-amber-300">{result.error}</p>}</td>
                <td className="min-w-0 px-4 pb-3 text-right tabular-nums sm:p-4"><span className="mb-1 block text-xs text-fg/55 sm:hidden">Сохранённая цена</span>{result?.saved?.total == null ? result?.available ? 'Нет действующей цены' : '—' : money(result.saved.total)}</td>
                <td className="min-w-0 px-4 pb-3 text-right font-bold tabular-nums sm:p-4"><span className="mb-1 block text-xs font-normal text-fg/55 sm:hidden">Новая цена</span>{result?.draft?.total == null ? result?.available ? 'Неполный расчёт' : '—' : money(result.draft.total)}</td>
                <td className="min-w-0 p-4 text-right"><span className="mb-1 block text-xs text-fg/55 sm:hidden">Разница</span><Delta before={result?.saved?.total} after={result?.draft?.total} /></td>
                <td className="p-3 text-right"><button aria-label={`Удалить пример ${id}`} className="rounded-lg p-2 text-fg/45 hover:bg-red-500/10 hover:text-red-600" onClick={() => change(current => { const examples = current.examples.filter(value => value !== id); return { ...current, examples, selected: current.selected === id ? examples[0] ?? null : current.selected }; })}><Trash2 size={16} /></button></td>
              </tr>;
            })}</tbody></table></div>
          {!workspace.examples.length && <p className="p-6 text-sm text-fg/55">Добавьте существующие конструкции для сравнения.</p>}
        </section>
        <section className={`${card} p-5`}><button className="flex items-center gap-2 text-sm font-semibold" onClick={() => setHistoryOpen(value => !value)}><History size={16} />История и запланированные изменения</button>
          {historyOpen && <div className="mt-4 max-h-72 space-y-2 overflow-auto">{!history && <p className="text-sm text-fg/55">Загрузка истории…</p>}{history?.map(row => <div key={`${row.kind}-${row.id}`} className="border-t border-tint/20 py-2 text-xs"><b>{row.label}</b> · {new Date(row.effective_from).toLocaleString('ru-RU')}{row.scheduled && <span className="ml-2 text-amber-700 dark:text-amber-300">Запланировано</span>}<div className="mt-1 text-fg/60">{Object.entries(row.settings).map(([field, value]) => `${LABELS[field as keyof ComponentSettings]} ${value}%`).join(' · ')} · {row.reason}</div></div>)}</div>}
        </section>
      </>}
    </main>
  </div>;
}
