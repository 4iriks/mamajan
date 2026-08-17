import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  BadgePercent,
  CalendarClock,
  Check,
  ChevronRight,
  FileSpreadsheet,
  History,
  Loader2,
  RefreshCw,
  Save,
  Search,
  Settings,
  Upload,
  Users,
  X,
} from 'lucide-react';

import {
  applyBulkPriceChange,
  applyPriceImport,
  createPriceVersion,
  ConstructionPriceGroup,
  DealerPricingTerms,
  getDealerPricingTerms,
  getPriceHistory,
  getPricedCatalog,
  getPricingSettings,
  listPricingDealers,
  listConstructionPriceGroups,
  previewBulkPriceChange,
  previewPriceImport,
  PricedCatalogItem,
  PriceCategory,
  PriceVersion,
  PriceVersionInput,
  PricingSettings,
  rollbackPrice,
  updateDealerPricingTerms,
  updateConstructionPriceGroup,
  updatePricingSettings,
} from '../api/pricing';
import { toast } from '../store/toastStore';
import { useAuthStore } from '../store/authStore';

type Tab = 'catalog' | 'dealers' | 'settings';

interface PriceDraft {
  cost: string;
  profile_markup_percent: string;
  profile_discount_percent: string;
  waste_markup_percent: string;
  construction_markup_percent: string;
  construction_discount_percent: string;
  category: PriceCategory;
  unit: string;
  min_margin_percent: string;
  effective_from: string;
  reason: string;
}

const CATEGORY_LABELS: Record<PriceCategory, string> = {
  profile: 'Профиль',
  construction: 'Изделие / конструкция',
  component: 'Комплектующие',
  service: 'Услуги',
};

const INPUT = 'w-full rounded-xl border border-tint/30 bg-hi/5 px-3 py-2.5 text-sm outline-none transition-colors focus:border-accent/60';

function localDateTime(value?: string) {
  const date = value ? new Date(value) : new Date();
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

function inferCategory(item: PricedCatalogItem): PriceCategory {
  const group = item.group.toLowerCase();
  if (group.includes('проф') || group.includes('уплотн')) return 'profile';
  if (group.includes('услуг') || group.includes('работ') || item.sku.startsWith('PAINT|')) return 'service';
  if (group.includes('конструк') || item.sku === 'WORK-SLIDE') return 'construction';
  return 'component';
}

function priceDraft(item: PricedCatalogItem): PriceDraft {
  const source = item.active_price || item.next_price;
  return {
    cost: source?.cost || '0.00',
    profile_markup_percent: source?.profile_markup_percent || '0',
    profile_discount_percent: source?.profile_discount_percent || '0',
    waste_markup_percent: source?.waste_markup_percent || '0',
    construction_markup_percent: source?.construction_markup_percent || '0',
    construction_discount_percent: source?.construction_discount_percent || '0',
    category: source?.category || inferCategory(item),
    unit: source?.unit || item.catalog_unit || 'шт',
    min_margin_percent: source?.min_margin_percent || '0',
    effective_from: localDateTime(),
    reason: '',
  };
}

function errorMessage(error: unknown, fallback: string) {
  const response = (error as { response?: { data?: { detail?: unknown } } }).response;
  const detail = response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (detail && typeof detail === 'object' && 'message' in detail) {
    return String((detail as { message: unknown }).message);
  }
  return fallback;
}

function money(value?: string | number | null) {
  if (value === null || value === undefined || value === '') return '—';
  return `${Number(value).toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ₽`;
}

export default function PricingPage() {
  const navigate = useNavigate();
  const { user, canManagePrices } = useAuthStore();
  const [tab, setTab] = useState<Tab>('dealers');
  const [items, setItems] = useState<PricedCatalogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [onlyMissing, setOnlyMissing] = useState(false);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [editing, setEditing] = useState<PricedCatalogItem | null>(null);
  const [draft, setDraft] = useState<PriceDraft | null>(null);
  const [saving, setSaving] = useState(false);
  const [historyItem, setHistoryItem] = useState<PricedCatalogItem | null>(null);
  const [history, setHistory] = useState<PriceVersion[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [bulkPercent, setBulkPercent] = useState('0');
  const [bulkReason, setBulkReason] = useState('Массовое изменение цен');
  const [bulkDate, setBulkDate] = useState(localDateTime());
  const [bulkPreview, setBulkPreview] = useState<Array<{ item_id: number; sku: string; name: string; old_cost: string; new_cost: string }>>([]);
  const [bulkLoading, setBulkLoading] = useState(false);
  const [importPreview, setImportPreview] = useState<{ valid: boolean; rows: Array<Record<string, string>>; errors: string[] } | null>(null);
  const [importReason, setImportReason] = useState('Импорт цен из Excel');
  const [importLoading, setImportLoading] = useState(false);
  const [settings, setSettings] = useState<PricingSettings | null>(null);
  const [dealers, setDealers] = useState<Array<{ id: number; display_name: string; company: string }>>([]);
  const [dealerId, setDealerId] = useState<number | null>(null);
  const [dealerTerms, setDealerTerms] = useState<DealerPricingTerms | null>(null);
  const [priceGroups, setPriceGroups] = useState<ConstructionPriceGroup[]>([]);

  const loadCatalog = async () => {
    setLoading(true);
    try {
      const data = await getPricedCatalog();
      setItems(data.items);
    } catch (error) {
      toast.error(errorMessage(error, 'Не удалось загрузить каталог цен'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!canManagePrices()) {
      navigate('/');
      return;
    }
    void Promise.all([
      loadCatalog(),
      getPricingSettings().then(setSettings),
      listConstructionPriceGroups().then(setPriceGroups),
      listPricingDealers().then(rows => {
        setDealers(rows);
        if (rows.length) setDealerId(current => current ?? rows[0].id);
      }),
    ]).catch(error => toast.error(errorMessage(error, 'Не удалось загрузить настройки цен')));
  }, [canManagePrices, navigate]);

  useEffect(() => {
    if (!dealerId) {
      setDealerTerms(null);
      return;
    }
    getDealerPricingTerms(dealerId)
      .then(setDealerTerms)
      .catch(error => toast.error(errorMessage(error, 'Не удалось загрузить условия дилера')));
  }, [dealerId]);

  const filtered = useMemo(() => {
    const query = search.trim().toLocaleLowerCase('ru');
    return items.filter(item => {
      if (onlyMissing && item.active_price) return false;
      return !query || `${item.sku} ${item.name} ${item.group} ${item.supplier}`.toLocaleLowerCase('ru').includes(query);
    });
  }, [items, onlyMissing, search]);

  const openPrice = (item: PricedCatalogItem) => {
    setEditing(item);
    setDraft(priceDraft(item));
  };

  const savePrice = async () => {
    if (!editing || !draft) return;
    setSaving(true);
    try {
      const payload: PriceVersionInput = {
        cost: draft.cost,
        profile_markup_percent: draft.profile_markup_percent,
        profile_discount_percent: draft.profile_discount_percent,
        waste_markup_percent: draft.waste_markup_percent,
        construction_markup_percent: draft.construction_markup_percent,
        construction_discount_percent: draft.construction_discount_percent,
        category: draft.category,
        unit: draft.unit,
        min_margin_percent: draft.min_margin_percent,
        effective_from: new Date(draft.effective_from).toISOString(),
        reason: draft.reason,
      };
      await createPriceVersion(editing.id, payload);
      setEditing(null);
      setDraft(null);
      await loadCatalog();
      toast.success('Создана новая версия цены');
    } catch (error) {
      toast.error(errorMessage(error, 'Не удалось сохранить цену'));
    } finally {
      setSaving(false);
    }
  };

  const openHistory = async (item: PricedCatalogItem) => {
    setHistoryItem(item);
    setHistoryLoading(true);
    try {
      setHistory((await getPriceHistory(item.id)).versions);
    } catch (error) {
      toast.error(errorMessage(error, 'Не удалось загрузить историю'));
    } finally {
      setHistoryLoading(false);
    }
  };

  const rollback = async (version: PriceVersion) => {
    if (!historyItem) return;
    const reason = window.prompt('Причина отката', `Откат к версии ${version.id}`)?.trim();
    if (!reason) return;
    try {
      await rollbackPrice(historyItem.id, version.id, reason, new Date().toISOString());
      setHistory((await getPriceHistory(historyItem.id)).versions);
      await loadCatalog();
      toast.success('Откат создан новой версией');
    } catch (error) {
      toast.error(errorMessage(error, 'Не удалось выполнить откат'));
    }
  };

  const bulkRequest = () => ({
    item_ids: [...selected],
    percent: bulkPercent,
    effective_from: new Date(bulkDate).toISOString(),
    reason: bulkReason,
  });

  const previewBulk = async () => {
    setBulkLoading(true);
    try {
      setBulkPreview((await previewBulkPriceChange(bulkRequest())).rows);
    } catch (error) {
      toast.error(errorMessage(error, 'Не удалось проверить массовое изменение'));
    } finally {
      setBulkLoading(false);
    }
  };

  const applyBulk = async () => {
    setBulkLoading(true);
    try {
      await applyBulkPriceChange(bulkRequest());
      setBulkPreview([]);
      setSelected(new Set());
      await loadCatalog();
      toast.success('Новые версии цен созданы');
    } catch (error) {
      toast.error(errorMessage(error, 'Не удалось применить изменение'));
    } finally {
      setBulkLoading(false);
    }
  };

  const inspectImport = async (file?: File) => {
    if (!file) return;
    setImportLoading(true);
    try {
      setImportPreview(await previewPriceImport(file));
    } catch (error) {
      toast.error(errorMessage(error, 'Не удалось проверить Excel'));
    } finally {
      setImportLoading(false);
    }
  };

  const applyImport = async () => {
    if (!importPreview?.valid) return;
    setImportLoading(true);
    try {
      await applyPriceImport(importPreview.rows, importReason);
      setImportPreview(null);
      await loadCatalog();
      toast.success('Импорт применён атомарно');
    } catch (error) {
      toast.error(errorMessage(error, 'Не удалось применить импорт'));
    } finally {
      setImportLoading(false);
    }
  };

  const saveDealerTerms = async () => {
    if (!dealerTerms || !dealerId) return;
    try {
      const updated = await updateDealerPricingTerms(dealerId, {
        dealer_markup_percent: '0',
        profile_discount_percent: dealerTerms.profile_discount_percent,
        construction_discount_percent: dealerTerms.construction_discount_percent,
        component_discount_percent: dealerTerms.component_discount_percent,
        service_discount_percent: dealerTerms.service_discount_percent,
      });
      setDealerTerms(updated);
      toast.success('Условия дилера сохранены');
    } catch (error) {
      toast.error(errorMessage(error, 'Не удалось сохранить условия дилера'));
    }
  };

  const savePriceGroup = async (group: ConstructionPriceGroup) => {
    try {
      const updated = await updateConstructionPriceGroup(group.id, {
        code: group.code,
        name: group.name,
        markup_percent: group.markup_percent,
        is_active: group.is_active,
      });
      setPriceGroups(rows => rows.map(row => row.id === group.id ? updated : row));
      toast.success('Ценовая группа сохранена');
    } catch (error) {
      toast.error(errorMessage(error, 'Не удалось сохранить ценовую группу'));
    }
  };

  const saveSettings = async () => {
    if (!settings) return;
    try {
      setSettings(await updatePricingSettings({
        include_waste_markup: settings.include_waste_markup,
        default_vat_rate: settings.default_vat_rate,
      }));
      toast.success('Настройки сохранены');
    } catch (error) {
      toast.error(errorMessage(error, 'Не удалось сохранить настройки'));
    }
  };

  return (
    <div className="min-h-screen bg-page text-fg">
      <nav className="sticky top-0 z-30 flex items-center justify-between border-b border-tint/25 bg-page/90 px-5 py-4 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-tint/40 bg-tint/20">
            <BadgePercent className="h-5 w-5 text-accent" />
          </div>
          <div>
            <div className="text-lg font-bold">Ценообразование</div>
            <div className="text-[11px] text-fg/40">Дилерские условия и группы конструкций</div>
          </div>
        </div>
        <div className="text-right text-xs text-fg/45">
          <div>{user?.display_name}</div>
          <div className="font-bold uppercase text-accent">доступ к ценам</div>
        </div>
      </nav>

      <main className="mx-auto w-full max-w-[1500px] p-4 sm:p-8">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <button onClick={() => navigate(user?.role === 'admin' || user?.role === 'superadmin' ? '/admin' : '/')}
            className="inline-flex items-center gap-2 text-sm font-bold text-fg/50 transition-colors hover:text-accent">
            <ArrowLeft className="h-4 w-4" /> Назад
          </button>
          <div className="flex rounded-2xl border border-tint/25 bg-surface/25 p-1">
            {([
              ['dealers', 'Дилеры', Users],
              ['settings', 'Настройки', Settings],
            ] as const).map(([value, label, Icon]) => (
              <button key={value} onClick={() => setTab(value)}
                className={`flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-bold transition-colors ${tab === value ? 'bg-primary text-white' : 'text-fg/50 hover:text-fg'}`}>
                <Icon className="h-4 w-4" /> {label}
              </button>
            ))}
          </div>
        </div>

        {tab === 'catalog' && (
          <div className="space-y-5">
            <div className="grid gap-3 lg:grid-cols-[1fr_auto_auto]">
              <div className="relative">
                <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-fg/25" />
                <input value={search} onChange={event => setSearch(event.target.value)}
                  className={`${INPUT} pl-11`} placeholder="Артикул, название, группа, поставщик" />
              </div>
              <button onClick={() => setOnlyMissing(value => !value)}
                className={`rounded-xl border px-4 py-2 text-sm font-bold ${onlyMissing ? 'border-amber-400/50 bg-amber-500/15 text-amber-200' : 'border-tint/30 text-fg/55'}`}>
                Без действующей цены: {items.filter(item => !item.active_price).length}
              </button>
              <label className="flex cursor-pointer items-center justify-center gap-2 rounded-xl border border-tint/30 bg-tint/10 px-4 py-2 text-sm font-bold text-accent hover:bg-tint/20">
                {importLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
                Импорт XLSX
                <input type="file" accept=".xlsx" className="hidden" onChange={event => void inspectImport(event.target.files?.[0])} />
              </label>
            </div>

            {selected.size > 0 && (
              <div className="rounded-2xl border border-accent/25 bg-accent/10 p-4">
                <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                  <div className="font-bold">Выбрано позиций: {selected.size}</div>
                  <button onClick={() => { setSelected(new Set()); setBulkPreview([]); }} className="text-xs text-fg/50 hover:text-fg">Снять выбор</button>
                </div>
                <div className="grid gap-2 md:grid-cols-[120px_210px_1fr_auto]">
                  <input type="number" step="0.1" value={bulkPercent} onChange={event => setBulkPercent(event.target.value)} className={INPUT} placeholder="Изменение, %" />
                  <input type="datetime-local" value={bulkDate} onChange={event => setBulkDate(event.target.value)} className={INPUT} />
                  <input value={bulkReason} onChange={event => setBulkReason(event.target.value)} className={INPUT} placeholder="Причина" />
                  <button onClick={() => void previewBulk()} disabled={bulkLoading} className="rounded-xl bg-primary px-5 py-2 font-bold text-white disabled:opacity-50">Предпросмотр</button>
                </div>
                {bulkPreview.length > 0 && (
                  <div className="mt-4 rounded-xl border border-tint/20 bg-page/40 p-3">
                    <div className="max-h-40 overflow-auto text-xs">
                      {bulkPreview.map(row => <div key={row.item_id} className="grid grid-cols-[100px_1fr_110px_110px] gap-3 border-b border-tint/10 py-1.5"><span>{row.sku}</span><span>{row.name}</span><span>{money(row.old_cost)}</span><span className="text-accent">{money(row.new_cost)}</span></div>)}
                    </div>
                    <button onClick={() => void applyBulk()} className="mt-3 inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-4 py-2 text-sm font-bold text-white"><Check className="h-4 w-4" /> Применить</button>
                  </div>
                )}
              </div>
            )}

            <div className="overflow-hidden rounded-2xl border border-tint/25 bg-surface/25">
              <div className="max-h-[68vh] overflow-auto">
                <table className="w-full min-w-[1050px] border-collapse text-left">
                  <thead className="sticky top-0 z-10 bg-page">
                    <tr className="border-b border-tint/20 text-[10px] font-bold uppercase tracking-wider text-fg/40">
                      <th className="w-10 px-3 py-4" />
                      <th className="px-3 py-4">Артикул / позиция</th>
                      <th className="px-3 py-4">Категория</th>
                      <th className="px-3 py-4">Себестоимость</th>
                      <th className="px-3 py-4">Действует с</th>
                      <th className="px-3 py-4">Будущая цена</th>
                      <th className="px-3 py-4">История</th>
                      <th className="px-3 py-4 text-right">Действия</th>
                    </tr>
                  </thead>
                  <tbody>
                    {loading ? (
                      <tr><td colSpan={8} className="py-16 text-center text-fg/40"><Loader2 className="mx-auto h-6 w-6 animate-spin" /></td></tr>
                    ) : filtered.map(item => (
                      <tr key={item.id} className={`border-b border-tint/10 text-sm hover:bg-hi/[0.03] ${!item.active_price ? 'bg-amber-500/[0.04]' : ''}`}>
                        <td className="px-3 py-3"><input type="checkbox" checked={selected.has(item.id)} onChange={() => setSelected(current => { const next = new Set(current); if (next.has(item.id)) next.delete(item.id); else next.add(item.id); return next; })} /></td>
                        <td className="px-3 py-3"><div className="font-mono font-bold text-accent">{item.sku}</div><div className="mt-0.5 text-xs text-fg/55">{item.name}</div></td>
                        <td className="px-3 py-3 text-xs text-fg/60">{item.active_price ? CATEGORY_LABELS[item.active_price.category] : '—'}<div className="text-fg/35">{item.active_price?.unit || item.catalog_unit}</div></td>
                        <td className="px-3 py-3 font-mono font-bold">{item.active_price ? money(item.active_price.cost) : <span className="text-amber-300">не задана</span>}</td>
                        <td className="px-3 py-3 text-xs text-fg/50">{item.active_price ? new Date(item.active_price.effective_from).toLocaleString('ru-RU') : '—'}</td>
                        <td className="px-3 py-3 text-xs">{item.next_price ? <><span className="font-mono text-accent">{money(item.next_price.cost)}</span><div className="text-fg/40">{new Date(item.next_price.effective_from).toLocaleString('ru-RU')}</div></> : '—'}</td>
                        <td className="px-3 py-3 text-xs text-fg/55">{item.history_count} верс.</td>
                        <td className="px-3 py-3"><div className="flex justify-end gap-2"><button onClick={() => void openHistory(item)} className="rounded-lg border border-tint/25 p-2 text-fg/55 hover:text-accent" title="История"><History className="h-4 w-4" /></button><button onClick={() => openPrice(item)} className="rounded-lg bg-primary px-3 py-2 text-xs font-bold text-white">Новая цена</button></div></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {tab === 'dealers' && (
          <div className="grid gap-5 lg:grid-cols-[320px_1fr]">
            <div className="rounded-2xl border border-tint/25 bg-surface/25 p-3">
              <div className="mb-3 px-2 text-xs font-bold uppercase tracking-widest text-fg/40">Дилерские аккаунты</div>
              <div className="space-y-1">
                {dealers.map(dealer => <button key={dealer.id} onClick={() => setDealerId(dealer.id)} className={`flex w-full items-center justify-between rounded-xl px-3 py-3 text-left ${dealerId === dealer.id ? 'bg-primary text-white' : 'hover:bg-hi/5'}`}><span><span className="block text-sm font-bold">{dealer.company || dealer.display_name}</span><span className="block text-[11px] opacity-60">{dealer.display_name}</span></span><ChevronRight className="h-4 w-4" /></button>)}
              </div>
            </div>
            <div className="rounded-2xl border border-tint/25 bg-surface/25 p-5 sm:p-7">
              <h2 className="text-xl font-bold">Условия дилера</h2>
              <p className="mt-1 text-sm text-fg/45">Используются только явно заданные скидки по категориям. Общая скрытая наценка не применяется.</p>
              {dealerTerms ? (
                <div className="mt-6 grid gap-4 sm:grid-cols-2">
                  {([
                    ['profile_discount_percent', 'Скидка: профиль (резерв для отдельной продажи)'],
                    ['construction_discount_percent', 'Скидка: изделие / конструкция'],
                    ['component_discount_percent', 'Скидка: комплектующие (резерв для отдельной продажи)'],
                    ['service_discount_percent', 'Скидка: услуги'],
                  ] as const).map(([field, label]) => <label key={field} className="space-y-1"><span className="text-xs font-bold text-fg/55">{label}, %</span><input type="number" min="0" step="0.1" value={dealerTerms[field]} onChange={event => setDealerTerms(current => current ? { ...current, [field]: event.target.value } : current)} className={INPUT} /></label>)}
                  <div className="sm:col-span-2"><button onClick={() => void saveDealerTerms()} className="inline-flex items-center gap-2 rounded-xl bg-primary px-5 py-3 font-bold text-white"><Save className="h-4 w-4" /> Сохранить</button></div>
                </div>
              ) : <div className="py-16 text-center text-fg/35">Выберите дилера</div>}
            </div>
          </div>
        )}

        {tab === 'settings' && settings && (
          <div className="space-y-5">
          <div className="max-w-2xl rounded-2xl border border-tint/25 bg-surface/25 p-6">
            <h2 className="text-xl font-bold">Настройки калькулятора</h2>
            <div className="mt-6 space-y-5">
              <div className="rounded-xl border border-tint/20 bg-hi/[0.03] p-4">
                <div className="font-bold">Наценка на отходы</div>
                <div className="mt-1 text-xs text-fg/45">Применяется автоматически к позициям в погонных метрах, квадратных метрах и килограммах. Для штук и комплектов не применяется.</div>
              </div>
              <label className="block max-w-xs space-y-1"><span className="text-xs font-bold text-fg/55">Ставка НДС по умолчанию, %</span><input type="number" min="0" max="100" step="0.1" value={settings.default_vat_rate} onChange={event => setSettings(current => current ? { ...current, default_vat_rate: event.target.value } : current)} className={INPUT} /></label>
              <button onClick={() => void saveSettings()} className="inline-flex items-center gap-2 rounded-xl bg-primary px-5 py-3 font-bold text-white"><Save className="h-4 w-4" /> Сохранить настройки</button>
            </div>
          </div>
          <div className="max-w-4xl rounded-2xl border border-tint/25 bg-surface/25 p-6">
            <div>
              <h2 className="text-xl font-bold">Наценка по системам</h2>
              <p className="mt-1 text-xs text-fg/45">Сохранение меняет поле «Наценка на конструкцию» у всех позиций выбранной системы. Второй наценки поверх состава нет.</p>
            </div>
            <div className="mt-5 space-y-2">
              {priceGroups.map(group => (
                <div key={group.id} className="grid gap-2 rounded-xl border border-tint/20 bg-hi/[0.03] p-3 sm:grid-cols-[120px_minmax(180px,1fr)_150px_120px] sm:items-center">
                  <span className="font-mono text-xs font-bold text-accent">{group.code}</span>
                  <span className="text-sm font-bold">{group.name}</span>
                  <label className="flex items-center gap-2"><input type="number" min="0" step="0.1" value={group.markup_percent} onChange={event => setPriceGroups(rows => rows.map(row => row.id === group.id ? { ...row, markup_percent: event.target.value } : row))} className={INPUT} /><span className="text-xs text-fg/40">%</span></label>
                  <button onClick={() => void savePriceGroup(group)} className="inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-3 py-2 text-xs font-bold text-white"><Save className="h-4 w-4" /> Сохранить</button>
                </div>
              ))}
            </div>
          </div>
          </div>
        )}
      </main>

      {editing && draft && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <button className="absolute inset-0 bg-black/75" onClick={() => setEditing(null)} aria-label="Закрыть" />
          <div className="relative max-h-[94vh] w-full max-w-3xl overflow-y-auto rounded-3xl border border-tint/30 bg-modal p-6 shadow-2xl sm:p-8">
            <button onClick={() => setEditing(null)} className="absolute right-5 top-5 text-fg/40 hover:text-fg"><X className="h-5 w-5" /></button>
            <div className="font-mono text-sm font-bold text-accent">{editing.sku}</div>
            <h2 className="mt-1 text-2xl font-bold">{editing.name}</h2>
            <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {([
                ['cost', 'Себестоимость, ₽'],
                ['profile_markup_percent', 'Наценка на профиль, %'],
                ['profile_discount_percent', 'Скидка на профиль, %'],
                ['waste_markup_percent', 'Наценка на отходы, %'],
                ['construction_markup_percent', 'Наценка на конструкцию, %'],
                ['construction_discount_percent', 'Скидка на конструкцию, %'],
                ['min_margin_percent', 'Минимальная маржа, %'],
              ] as const).map(([field, label]) => <label key={field} className="space-y-1"><span className="text-xs font-bold text-fg/55">{label}</span><input type="number" min="0" step="0.01" value={draft[field]} onChange={event => setDraft(current => current ? { ...current, [field]: event.target.value } : current)} className={INPUT} /></label>)}
              <label className="space-y-1"><span className="text-xs font-bold text-fg/55">Категория</span><select value={draft.category} onChange={event => setDraft(current => current ? { ...current, category: event.target.value as PriceCategory } : current)} className={INPUT}>{Object.entries(CATEGORY_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
              <label className="space-y-1"><span className="text-xs font-bold text-fg/55">Единица</span><input value={draft.unit} onChange={event => setDraft(current => current ? { ...current, unit: event.target.value } : current)} className={INPUT} /></label>
              <label className="space-y-1"><span className="text-xs font-bold text-fg/55">Начало действия</span><input type="datetime-local" value={draft.effective_from} onChange={event => setDraft(current => current ? { ...current, effective_from: event.target.value } : current)} className={INPUT} /></label>
              <label className="space-y-1 sm:col-span-2 lg:col-span-3"><span className="text-xs font-bold text-fg/55">Причина изменения</span><textarea value={draft.reason} onChange={event => setDraft(current => current ? { ...current, reason: event.target.value } : current)} rows={2} className={INPUT} /></label>
            </div>
            <button onClick={() => void savePrice()} disabled={saving} className="mt-6 inline-flex items-center gap-2 rounded-xl bg-primary px-6 py-3 font-bold text-white disabled:opacity-50">{saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Создать версию</button>
          </div>
        </div>
      )}

      {historyItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <button className="absolute inset-0 bg-black/75" onClick={() => setHistoryItem(null)} aria-label="Закрыть" />
          <div className="relative max-h-[90vh] w-full max-w-4xl overflow-y-auto rounded-3xl border border-tint/30 bg-modal p-6 shadow-2xl">
            <button onClick={() => setHistoryItem(null)} className="absolute right-5 top-5 text-fg/40 hover:text-fg"><X className="h-5 w-5" /></button>
            <h2 className="text-xl font-bold">История: {historyItem.sku}</h2>
            {historyLoading ? <Loader2 className="mx-auto my-16 h-6 w-6 animate-spin" /> : <div className="mt-5 space-y-2">{history.map(version => <div key={version.id} className="grid gap-3 rounded-xl border border-tint/20 bg-hi/[0.03] p-3 text-xs sm:grid-cols-[90px_110px_170px_1fr_auto]"><span className="font-mono text-accent">v{version.id}</span><span className="font-mono font-bold">{money(version.cost)}</span><span><CalendarClock className="mr-1 inline h-3 w-3" />{new Date(version.effective_from).toLocaleString('ru-RU')}</span><span className="text-fg/55">{version.reason}<span className="mt-1 block text-[10px] text-fg/30">Автор #{version.created_by}</span></span><button onClick={() => void rollback(version)} className="inline-flex items-center gap-1 rounded-lg border border-tint/25 px-2 py-1 font-bold text-accent"><RefreshCw className="h-3 w-3" /> Откатить</button></div>)}</div>}
          </div>
        </div>
      )}

      {importPreview && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <button className="absolute inset-0 bg-black/75" onClick={() => setImportPreview(null)} aria-label="Закрыть" />
          <div className="relative max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-3xl border border-tint/30 bg-modal p-6 shadow-2xl">
            <button onClick={() => setImportPreview(null)} className="absolute right-5 top-5 text-fg/40 hover:text-fg"><X className="h-5 w-5" /></button>
            <div className="flex items-center gap-3"><FileSpreadsheet className="h-6 w-6 text-accent" /><h2 className="text-xl font-bold">Проверка импорта</h2></div>
            <div className="mt-4 text-sm">Строк к применению: <b>{importPreview.rows.length}</b></div>
            {importPreview.errors.length > 0 && <div className="mt-4 rounded-xl border border-red-500/25 bg-red-500/10 p-3 text-sm text-red-200">{importPreview.errors.map(error => <div key={error}>{error}</div>)}</div>}
            {importPreview.rows.length > 0 && <div className="mt-4 max-h-52 overflow-auto rounded-xl border border-tint/20 bg-page/30 text-xs">{importPreview.rows.map((row, index) => <div key={`${row.sku}-${index}`} className="grid grid-cols-[110px_1fr_110px_90px] gap-3 border-b border-tint/10 px-3 py-2"><span className="font-mono text-accent">{row.sku}</span><span>{row.category}</span><span className="font-mono">{money(row.cost)}</span><span>{row.unit}</span></div>)}</div>}
            <input value={importReason} onChange={event => setImportReason(event.target.value)} className={`${INPUT} mt-4`} placeholder="Причина импорта" />
            <button onClick={() => void applyImport()} disabled={!importPreview.valid || importLoading} className="mt-4 inline-flex items-center gap-2 rounded-xl bg-primary px-5 py-3 font-bold text-white disabled:opacity-40">{importLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />} Применить атомарно</button>
          </div>
        </div>
      )}
    </div>
  );
}
