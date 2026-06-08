import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ArrowLeft, BadgePercent, Box, Check, Edit2, Package,
  ImageIcon, Plus, Ruler, Save, Scale, Search, SlidersHorizontal, Trash2, X,
} from 'lucide-react';
import {
  listHardwareCatalog,
  type CatalogUnit,
  type HardwareCatalogItem,
  type HardwareGroup,
  type PaintMode,
} from '../api/catalog';
import { useAuthStore } from '../store/authStore';
import { toast } from '../store/toastStore';

type HardwareItem = HardwareCatalogItem;

const STORAGE_KEY = 'raluma-hardware-catalog-draft-v1';

const GROUPS: HardwareGroup[] = ['Профили', 'Ручки', 'Замки', 'Защёлки', 'Уплотнители', 'Крепёж', 'Расходники'];
const UNITS: CatalogUnit[] = ['шт', 'м.п.', 'компл.', 'кг'];
const PAINT_MODES: PaintMode[] = ['Красится', 'Не красится', 'Частично'];
const DEFAULT_COLOR_VARIANTS = ['Анод', 'RAL стандарт', 'RAL нестандарт'];

const GROUP_COLORS: Record<HardwareGroup, string> = {
  'Профили': 'bg-teal-500/15 text-teal-300 border-teal-500/25',
  'Ручки': 'bg-blue-500/15 text-blue-300 border-blue-500/25',
  'Замки': 'bg-amber-500/15 text-amber-300 border-amber-500/25',
  'Защёлки': 'bg-emerald-500/15 text-emerald-300 border-emerald-500/25',
  'Уплотнители': 'bg-cyan-500/15 text-cyan-300 border-cyan-500/25',
  'Крепёж': 'bg-violet-500/15 text-violet-300 border-violet-500/25',
  'Расходники': 'bg-rose-500/15 text-rose-300 border-rose-500/25',
};

const INPUT_CLS = 'w-full bg-hi/8 border border-tint/35 rounded-2xl px-5 py-3.5 outline-none focus:border-accent/60 transition-all text-fg';
const SELECT_CLS = `${INPUT_CLS} appearance-none`;

function profileAssetUrl(filename: string) {
  return filename ? `/api/catalog/profile-assets/${encodeURIComponent(filename)}` : '';
}

const seedItems: HardwareItem[] = [
  {
    id: 101,
    sku: 'RS1313',
    name: 'Верхний направляющий профиль 3-рельсовый',
    group: 'Профили',
    system: 'СЛАЙД 3',
    unit: 'м.п.',
    purchasePrice: 420,
    markupPercent: 35,
    weight: 0.72,
    wastePercent: 4,
    sectionWidthMm: 72,
    sectionHeightMm: 53,
    imageFile: 'RS1313.png',
    paintMode: 'Красится',
    colorVariants: DEFAULT_COLOR_VARIANTS,
    supplier: 'Raluma',
    isActive: true,
    updatedAt: '2026-06-08',
    note: 'Длина считается формулой, сечение используется для схем и документов',
  },
  {
    id: 102,
    sku: 'RS1315',
    name: 'Верхний направляющий профиль 5-рельсовый',
    group: 'Профили',
    system: 'СЛАЙД 5',
    unit: 'м.п.',
    purchasePrice: 580,
    markupPercent: 35,
    weight: 0.96,
    wastePercent: 4,
    sectionWidthMm: 119,
    sectionHeightMm: 53,
    imageFile: 'RS1315.png',
    paintMode: 'Красится',
    colorVariants: DEFAULT_COLOR_VARIANTS,
    supplier: 'Raluma',
    isActive: true,
    updatedAt: '2026-06-08',
    note: 'Пять рельсов, геометрия нужна для масштабной схемы',
  },
  {
    id: 103,
    sku: 'RS2323',
    name: 'Порог 3-рельсовый',
    group: 'Профили',
    system: 'СЛАЙД 3',
    unit: 'м.п.',
    purchasePrice: 380,
    markupPercent: 35,
    weight: 0.61,
    wastePercent: 4,
    sectionWidthMm: 76,
    sectionHeightMm: 23,
    imageFile: 'RS2323.jpg',
    paintMode: 'Частично',
    colorVariants: DEFAULT_COLOR_VARIANTS,
    supplier: 'Raluma',
    isActive: true,
    updatedAt: '2026-06-08',
    note: 'В заявке на покраску отмечать область, которую не красить',
  },
  {
    id: 104,
    sku: 'RS2325',
    name: 'Порог 5-рельсовый',
    group: 'Профили',
    system: 'СЛАЙД 5',
    unit: 'м.п.',
    purchasePrice: 520,
    markupPercent: 35,
    weight: 0.88,
    wastePercent: 4,
    sectionWidthMm: 122,
    sectionHeightMm: 23,
    imageFile: 'RS1325.jpg',
    paintMode: 'Красится',
    colorVariants: DEFAULT_COLOR_VARIANTS,
    supplier: 'Raluma',
    isActive: true,
    updatedAt: '2026-06-08',
    note: 'Стандартный нижний направляющий профиль',
  },
  {
    id: 105,
    sku: 'RS2333',
    name: 'Пристеночный профиль 3-рельсовый',
    group: 'Профили',
    system: 'СЛАЙД 3',
    unit: 'м.п.',
    purchasePrice: 330,
    markupPercent: 35,
    weight: 0.42,
    wastePercent: 4,
    sectionWidthMm: 76,
    sectionHeightMm: 16,
    imageFile: 'RS2333.jpg',
    paintMode: 'Красится',
    colorVariants: DEFAULT_COLOR_VARIANTS,
    supplier: 'Raluma',
    isActive: true,
    updatedAt: '2026-06-08',
    note: 'На схеме сверху добавляет 16 мм с выбранной стороны',
  },
  {
    id: 106,
    sku: 'RS2335',
    name: 'Пристеночный профиль 5-рельсовый',
    group: 'Профили',
    system: 'СЛАЙД 5',
    unit: 'м.п.',
    purchasePrice: 450,
    markupPercent: 35,
    weight: 0.58,
    wastePercent: 4,
    sectionWidthMm: 122,
    sectionHeightMm: 16,
    imageFile: 'RS2335.jpg',
    paintMode: 'Красится',
    colorVariants: DEFAULT_COLOR_VARIANTS,
    supplier: 'Raluma',
    isActive: true,
    updatedAt: '2026-06-08',
    note: 'На схеме сверху добавляет 16 мм с выбранной стороны',
  },
  {
    id: 107,
    sku: 'RS2081',
    name: 'Боковой П-образный профиль-замок',
    group: 'Профили',
    system: 'СЛАЙД',
    unit: 'м.п.',
    purchasePrice: 510,
    markupPercent: 38,
    weight: 0.82,
    wastePercent: 4,
    sectionWidthMm: 57,
    sectionHeightMm: 25,
    imageFile: 'RS2081.jpg',
    paintMode: 'Красится',
    colorVariants: DEFAULT_COLOR_VARIANTS,
    supplier: 'Raluma',
    isActive: true,
    updatedAt: '2026-06-08',
    note: 'Используется при боковом замыкании, красить весь периметр',
  },
  {
    id: 108,
    sku: 'RS1082',
    name: 'Боковой П-профиль',
    group: 'Профили',
    system: 'СЛАЙД',
    unit: 'м.п.',
    purchasePrice: 260,
    markupPercent: 35,
    weight: 0.36,
    wastePercent: 4,
    sectionWidthMm: 25,
    sectionHeightMm: 25,
    imageFile: 'RS1082.jpg',
    paintMode: 'Красится',
    colorVariants: DEFAULT_COLOR_VARIANTS,
    supplier: 'Raluma',
    isActive: true,
    updatedAt: '2026-06-08',
    note: 'Боковой профиль без замка',
  },
  {
    id: 109,
    sku: 'RS112',
    name: 'Профиль-ручка',
    group: 'Профили',
    system: 'СЛАЙД',
    unit: 'м.п.',
    purchasePrice: 420,
    markupPercent: 35,
    weight: 0.74,
    wastePercent: 4,
    sectionWidthMm: 52,
    sectionHeightMm: 40,
    imageFile: 'RS112.jpg',
    paintMode: 'Красится',
    colorVariants: DEFAULT_COLOR_VARIANTS,
    supplier: 'Raluma',
    isActive: true,
    updatedAt: '2026-06-08',
    note: 'Основная ручка для стандартного СЛАЙД',
  },
  {
    id: 110,
    sku: 'RS2061',
    name: 'Межстекольный профиль',
    group: 'Профили',
    system: 'СЛАЙД',
    unit: 'м.п.',
    purchasePrice: 210,
    markupPercent: 35,
    weight: 0.28,
    wastePercent: 4,
    sectionWidthMm: 20,
    sectionHeightMm: 12,
    imageFile: 'RS2061.jpg',
    paintMode: 'Красится',
    colorVariants: DEFAULT_COLOR_VARIANTS,
    supplier: 'Raluma',
    isActive: true,
    updatedAt: '2026-06-08',
    note: 'В схеме сверху зеркалится по направлению первой панели',
  },
  {
    id: 111,
    sku: 'RS2021',
    name: 'Стекольный профиль',
    group: 'Профили',
    system: 'СЛАЙД',
    unit: 'м.п.',
    purchasePrice: 190,
    markupPercent: 35,
    weight: 0.24,
    wastePercent: 4,
    sectionWidthMm: 75,
    sectionHeightMm: 18,
    imageFile: 'RS2021.jpg',
    paintMode: 'Красится',
    colorVariants: DEFAULT_COLOR_VARIANTS,
    supplier: 'Raluma',
    isActive: true,
    updatedAt: '2026-06-08',
    note: 'Длина считается отдельно по каждому стеклу',
  },
  {
    id: 112,
    sku: 'RS1002',
    name: 'Пузырьковый уплотнитель',
    group: 'Уплотнители',
    system: 'СЛАЙД',
    unit: 'м.п.',
    purchasePrice: 86,
    markupPercent: 45,
    weight: 0.09,
    wastePercent: 8,
    sectionWidthMm: 0,
    sectionHeightMm: 0,
    imageFile: 'RS1002.jpg',
    paintMode: 'Не красится',
    colorVariants: ['Без цвета'],
    supplier: 'Склад',
    isActive: true,
    updatedAt: '2026-06-08',
    note: 'Норма зависит от стороны установки',
  },
  {
    id: 113,
    sku: 'RS205',
    name: 'Защёлка в пол',
    group: 'Защёлки',
    system: 'СЛАЙД',
    unit: 'шт',
    purchasePrice: 185,
    markupPercent: 40,
    weight: 0.12,
    wastePercent: 0,
    sectionWidthMm: 0,
    sectionHeightMm: 0,
    imageFile: 'RS205.jpg',
    paintMode: 'Не красится',
    colorVariants: ['Без цвета'],
    supplier: 'Фурнитура СПБ',
    isActive: true,
    updatedAt: '2026-06-08',
    note: 'Ставится слева/справа по настройкам секции',
  },
  {
    id: 114,
    sku: 'DIN7504M',
    name: 'Саморез сверлоконечный',
    group: 'Крепёж',
    system: 'Все',
    unit: 'шт',
    purchasePrice: 3.8,
    markupPercent: 60,
    weight: 0.004,
    wastePercent: 3,
    sectionWidthMm: 0,
    sectionHeightMm: 0,
    imageFile: 'DIN7504M.png',
    paintMode: 'Не красится',
    colorVariants: ['Без цвета'],
    supplier: 'Метизы',
    isActive: true,
    updatedAt: '2026-06-08',
    note: 'Формула количества будет уточняться отдельно',
  },
];

const emptyDraft = (): HardwareItem => ({
  id: Date.now(),
  sku: '',
  name: '',
  group: 'Профили',
  system: 'СЛАЙД',
  unit: 'шт',
  purchasePrice: 0,
  markupPercent: 0,
  weight: 0,
  wastePercent: 0,
  sectionWidthMm: 0,
  sectionHeightMm: 0,
  imageFile: '',
  paintMode: 'Красится',
  colorVariants: DEFAULT_COLOR_VARIANTS,
  supplier: '',
  isActive: true,
  updatedAt: new Date().toISOString().slice(0, 10),
  note: '',
});

function normalizeItem(item: Partial<HardwareItem>): HardwareItem {
  return {
    id: item.id ?? Date.now(),
    sku: item.sku ?? '',
    name: item.name ?? '',
    group: item.group ?? 'Профили',
    system: item.system ?? 'СЛАЙД',
    unit: item.unit ?? 'шт',
    purchasePrice: item.purchasePrice ?? 0,
    markupPercent: item.markupPercent ?? 0,
    weight: item.weight ?? 0,
    wastePercent: item.wastePercent ?? 0,
    sectionWidthMm: item.sectionWidthMm ?? 0,
    sectionHeightMm: item.sectionHeightMm ?? 0,
    imageFile: item.imageFile ?? '',
    paintMode: item.paintMode ?? 'Красится',
    colorVariants: item.colorVariants?.length ? item.colorVariants : DEFAULT_COLOR_VARIANTS,
    supplier: item.supplier ?? '',
    isActive: item.isActive ?? true,
    updatedAt: item.updatedAt ?? new Date().toISOString().slice(0, 10),
    note: item.note ?? '',
  };
}

function mergeCatalogItems(seed: HardwareItem[], localItems: HardwareItem[]) {
  const localBySku = new Map(
    localItems
      .filter(item => item.sku.trim())
      .map(item => [item.sku.trim().toUpperCase(), item]),
  );
  const seedSkus = new Set(seed.map(item => item.sku.trim().toUpperCase()));

  const mergedSeed = seed.map(item => {
    const local = localBySku.get(item.sku.trim().toUpperCase());
    if (!local) return item;

    return normalizeItem({
      ...item,
      purchasePrice: local.purchasePrice,
      markupPercent: local.markupPercent,
      weight: local.weight,
      wastePercent: local.wastePercent,
      supplier: local.supplier,
      isActive: local.isActive,
      updatedAt: local.updatedAt,
      note: local.note || item.note,
    });
  });

  const customItems = localItems.filter(item => !seedSkus.has(item.sku.trim().toUpperCase()));
  return [...mergedSeed, ...customItems];
}

function readItems(seed: HardwareItem[] = seedItems) {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return seed;
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.map(item => normalizeItem(item)) : seed;
  } catch {
    return seed;
  }
}

function saveItems(items: HardwareItem[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
}

function formatMoney(value: number) {
  return new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    maximumFractionDigits: value < 10 ? 1 : 0,
  }).format(value);
}

function salePrice(item: HardwareItem) {
  return item.purchasePrice * (1 + item.markupPercent / 100);
}

function NumberInput({
  label, value, suffix, onChange,
}: {
  label: string;
  value: number;
  suffix?: string;
  onChange: (value: number) => void;
}) {
  return (
    <div className="space-y-2">
      <label className="text-[10px] font-bold uppercase tracking-widest text-accent/45 ml-1">{label}</label>
      <div className="relative">
        <input
          type="number"
          value={value}
          onChange={event => onChange(Number(event.target.value))}
          className={`${INPUT_CLS} pr-14 font-mono`}
          min={0}
          step="0.01"
        />
        {suffix && <span className="absolute right-5 top-1/2 -translate-y-1/2 text-xs font-bold text-fg/35">{suffix}</span>}
      </div>
    </div>
  );
}

export default function HardwareCatalogPage() {
  const navigate = useNavigate();
  const { user: me, isAdmin } = useAuthStore();
  const [items, setItems] = useState<HardwareItem[]>(readItems);
  const [isCatalogLoading, setIsCatalogLoading] = useState(false);
  const [catalogError, setCatalogError] = useState(false);
  const [search, setSearch] = useState('');
  const [group, setGroup] = useState<'Все' | HardwareGroup>('Все');
  const [status, setStatus] = useState<'all' | 'active' | 'inactive'>('active');
  const [draft, setDraft] = useState<HardwareItem | null>(null);

  useEffect(() => {
    if (!isAdmin()) navigate('/');
  }, [isAdmin, navigate]);

  useEffect(() => {
    if (!isAdmin()) return;

    let cancelled = false;
    setIsCatalogLoading(true);
    setCatalogError(false);

    listHardwareCatalog()
      .then(remoteItems => {
        if (cancelled) return;
        const seed = remoteItems.map(item => normalizeItem(item));
        const next = mergeCatalogItems(seed, readItems(seed));
        setItems(next);
        saveItems(next);
      })
      .catch(() => {
        if (!cancelled) setCatalogError(true);
      })
      .finally(() => {
        if (!cancelled) setIsCatalogLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [isAdmin]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return items.filter(item => {
      const matchesSearch = !q ||
        item.sku.toLowerCase().includes(q) ||
        item.name.toLowerCase().includes(q) ||
        item.supplier.toLowerCase().includes(q) ||
        item.paintMode.toLowerCase().includes(q) ||
        item.colorVariants.some(variant => variant.toLowerCase().includes(q));
      const matchesGroup = group === 'Все' || item.group === group;
      const matchesStatus =
        status === 'all' ||
        (status === 'active' && item.isActive) ||
        (status === 'inactive' && !item.isActive);
      return matchesSearch && matchesGroup && matchesStatus;
    });
  }, [group, items, search, status]);

  const stats = useMemo(() => {
    const active = items.filter(item => item.isActive);
    const avgMarkup = active.length
      ? active.reduce((sum, item) => sum + item.markupPercent, 0) / active.length
      : 0;
    const avgWeight = active.length
      ? active.reduce((sum, item) => sum + item.weight, 0) / active.length
      : 0;
    return {
      total: items.length,
      active: active.length,
      avgMarkup,
      avgWeight,
    };
  }, [items]);

  const persist = (next: HardwareItem[]) => {
    setItems(next);
    saveItems(next);
  };

  const handleSave = () => {
    if (!draft) return;
    if (!draft.sku.trim() || !draft.name.trim()) {
      toast.error('Заполните артикул и название');
      return;
    }
    const normalized = {
      ...draft,
      sku: draft.sku.trim(),
      name: draft.name.trim(),
      supplier: draft.supplier.trim(),
      updatedAt: new Date().toISOString().slice(0, 10),
    };
    const exists = items.some(item => item.id === normalized.id);
    const next = exists
      ? items.map(item => item.id === normalized.id ? normalized : item)
      : [normalized, ...items];
    persist(next);
    setDraft(null);
    toast.success('Позиция сохранена');
  };

  const handleDelete = (id: number) => {
    persist(items.filter(item => item.id !== id));
    toast.success('Позиция удалена');
  };

  return (
    <div className="min-h-screen bg-page text-fg font-sans flex flex-col">
      <nav className="sticky top-0 z-40 bg-page/90 backdrop-blur-md border-b border-tint/25 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-tint/25 border border-tint/40 flex items-center justify-center">
            <Package className="w-6 h-6 text-accent" />
          </div>
          <span className="text-xl font-bold tracking-tight uppercase">Каталог фурнитуры</span>
        </div>
        <div className="flex items-center gap-3 text-sm text-fg/50">
          <span>{me?.display_name}</span>
          <span className="px-2 py-0.5 rounded bg-accent/15 text-accent text-[10px] font-bold uppercase">
            Админ
          </span>
        </div>
      </nav>

      <main className="flex-1 p-4 sm:p-8 max-w-7xl mx-auto w-full z-10">
        <div className="flex flex-col gap-5 mb-7">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <button onClick={() => navigate('/admin')}
                className="flex items-center gap-2 text-fg/50 hover:text-accent transition-colors group">
                <ArrowLeft className="w-4 h-4 group-hover:-translate-x-1 transition-transform" />
                <span className="text-sm font-bold uppercase tracking-wider">Администрирование</span>
              </button>
              <div className="h-6 w-px bg-tint/25 hidden sm:block" />
              <div>
                <h1 className="text-2xl sm:text-3xl font-bold">Справочник позиций</h1>
                <div className="mt-2 inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-300 text-[10px] font-bold uppercase tracking-wider">
                  {isCatalogLoading ? 'Загрузка справочника' : catalogError ? 'Локальный черновик' : 'Расчётный каталог'}
                </div>
              </div>
            </div>
            <button onClick={() => setDraft(emptyDraft())}
              className="flex items-center justify-center gap-2 px-6 py-3.5 bg-primary hover:bg-primary-h text-white font-bold rounded-2xl transition-all shadow-lg shadow-primary/20">
              <Plus className="w-5 h-5" />
              Добавить позицию
            </button>
          </div>

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {[
              { label: 'Позиций', value: stats.total, icon: Box },
              { label: 'Активных', value: stats.active, icon: Check },
              { label: 'Средняя наценка', value: `${stats.avgMarkup.toFixed(1)}%`, icon: BadgePercent },
              { label: 'Средний вес', value: `${stats.avgWeight.toFixed(3)} кг`, icon: Scale },
            ].map(card => (
              <div key={card.label} className="bg-surface/35 border border-tint/25 rounded-2xl p-4">
                <div className="flex items-center justify-between gap-3 mb-3">
                  <span className="text-[10px] font-bold uppercase tracking-widest text-fg/35">{card.label}</span>
                  <card.icon className="w-4 h-4 text-accent/65" />
                </div>
                <div className="text-2xl font-bold">{card.value}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="flex flex-col xl:flex-row gap-3 mb-5">
          <div className="relative flex-1 group">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-fg/25 group-focus-within:text-accent transition-colors" />
            <input
              value={search}
              onChange={event => setSearch(event.target.value)}
              placeholder="Поиск по артикулу, названию или поставщику..."
              className="w-full bg-surface/30 border border-tint/30 rounded-2xl pl-12 pr-4 py-4 outline-none focus:border-accent/50 transition-all text-fg"
            />
          </div>
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="flex items-center gap-2 bg-surface/30 border border-tint/30 rounded-2xl px-3 py-2">
              <SlidersHorizontal className="w-4 h-4 text-accent/60" />
              <select value={group} onChange={event => setGroup(event.target.value as typeof group)}
                className="bg-transparent outline-none text-sm font-bold text-fg min-w-[150px]">
                <option value="Все">Все группы</option>
                {GROUPS.map(item => <option key={item} value={item}>{item}</option>)}
              </select>
            </div>
            <div className="grid grid-cols-3 rounded-2xl bg-surface/30 border border-tint/30 p-1 min-w-[270px]">
              {[
                { id: 'active', label: 'Активные' },
                { id: 'all', label: 'Все' },
                { id: 'inactive', label: 'Архив' },
              ].map(item => (
                <button key={item.id} onClick={() => setStatus(item.id as typeof status)}
                  className={`py-2.5 rounded-xl text-xs font-bold transition-all ${
                    status === item.id ? 'bg-accent/15 text-accent border border-accent/30' : 'text-fg/35 border border-transparent hover:text-fg/60'
                  }`}>
                  {item.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="bg-surface/30 backdrop-blur-xl border border-tint/25 rounded-[2rem] overflow-hidden shadow-2xl">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1040px] text-left border-collapse">
              <thead>
                <tr className="border-b border-tint/20 bg-hi/[0.03]">
                  <th className="px-5 py-5 text-[10px] font-bold uppercase tracking-widest text-fg/45">Артикул</th>
                  <th className="px-5 py-5 text-[10px] font-bold uppercase tracking-widest text-fg/45">Позиция</th>
                  <th className="px-5 py-5 text-[10px] font-bold uppercase tracking-widest text-fg/45">Группа</th>
                  <th className="px-5 py-5 text-[10px] font-bold uppercase tracking-widest text-fg/45">Ед.</th>
                  <th className="px-5 py-5 text-[10px] font-bold uppercase tracking-widest text-fg/45">Закупка</th>
                  <th className="px-5 py-5 text-[10px] font-bold uppercase tracking-widest text-fg/45">Наценка</th>
                  <th className="px-5 py-5 text-[10px] font-bold uppercase tracking-widest text-fg/45">Продажа</th>
                  <th className="px-5 py-5 text-[10px] font-bold uppercase tracking-widest text-fg/45">Вес</th>
                  <th className="px-5 py-5 text-[10px] font-bold uppercase tracking-widest text-fg/45">Отход</th>
                  <th className="px-5 py-5 text-[10px] font-bold uppercase tracking-widest text-fg/45 text-right">Действия</th>
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr>
                    <td colSpan={10} className="py-20 text-center">
                      <div className="flex flex-col items-center gap-4">
                        <div className="w-20 h-20 rounded-full bg-tint/15 border border-tint/25 flex items-center justify-center">
                          <Package className="w-10 h-10 text-fg/25" />
                        </div>
                        <div>
                          <h3 className="text-xl font-bold mb-1">Позиции не найдены</h3>
                          <p className="text-fg/40 text-sm">Измените фильтр или добавьте новую позицию</p>
                        </div>
                      </div>
                    </td>
                  </tr>
                ) : filtered.map(item => (
                  <motion.tr key={item.id} initial={{ opacity: 0 }} animate={{ opacity: item.isActive ? 1 : 0.45 }}
                    className="border-b border-tint/10 hover:bg-hi/[0.03] transition-colors group">
                    <td className="px-5 py-4 font-mono text-sm text-accent font-bold">{item.sku}</td>
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="w-16 h-12 rounded-xl bg-hi border border-tint/20 flex items-center justify-center overflow-hidden flex-shrink-0">
                          {item.imageFile ? (
                            <img src={profileAssetUrl(item.imageFile)} alt={item.sku} className="max-w-full max-h-full object-contain" />
                          ) : (
                            <ImageIcon className="w-5 h-5 text-black/25" />
                          )}
                        </div>
                        <div className="min-w-0">
                          <div className="font-bold text-sm text-fg truncate">{item.name}</div>
                          <div className="text-[11px] text-fg/35 mt-1">
                            {item.system} · {item.supplier || 'поставщик не указан'}
                          </div>
                          <div className="flex flex-wrap items-center gap-1.5 mt-2">
                            {(item.sectionWidthMm > 0 || item.sectionHeightMm > 0) && (
                              <span className="px-2 py-0.5 rounded-md bg-tint/15 border border-tint/25 text-[10px] font-bold text-fg/45">
                                {item.sectionWidthMm}×{item.sectionHeightMm} мм
                              </span>
                            )}
                            <span className="px-2 py-0.5 rounded-md bg-accent/10 border border-accent/20 text-[10px] font-bold text-accent/80">
                              {item.paintMode}
                            </span>
                            <span className="px-2 py-0.5 rounded-md bg-hi/[0.04] border border-tint/20 text-[10px] font-bold text-fg/35">
                              {item.colorVariants.join(', ')}
                            </span>
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-[10px] font-bold border ${GROUP_COLORS[item.group]}`}>
                        {item.group}
                      </span>
                    </td>
                    <td className="px-5 py-4 text-sm font-bold text-fg/60">{item.unit}</td>
                    <td className="px-5 py-4 text-sm font-mono">{formatMoney(item.purchasePrice)}</td>
                    <td className="px-5 py-4 text-sm font-mono text-amber-300">{item.markupPercent}%</td>
                    <td className="px-5 py-4 text-sm font-mono text-emerald-300">{formatMoney(salePrice(item))}</td>
                    <td className="px-5 py-4 text-sm font-mono text-fg/60">{item.weight} кг</td>
                    <td className="px-5 py-4 text-sm font-mono text-fg/60">{item.wastePercent}%</td>
                    <td className="px-5 py-4 text-right">
                      <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button onClick={() => setDraft(item)}
                          className="p-2 rounded-lg hover:bg-tint/25 text-accent transition-colors" title="Изменить">
                          <Edit2 className="w-4 h-4" />
                        </button>
                        <button onClick={() => handleDelete(item.id)}
                          className="p-2 rounded-lg hover:bg-red-500/20 text-red-400 transition-colors" title="Удалить">
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="px-8 py-4 bg-hi/[0.02] border-t border-tint/20 text-xs text-fg/40">
            Показано <span className="text-fg font-bold">{filtered.length}</span> из <span className="text-fg font-bold">{items.length}</span>
          </div>
        </div>
      </main>

      <AnimatePresence>
        {draft && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => setDraft(null)} className="absolute inset-0 bg-black/75 backdrop-blur-sm" />
            <motion.div initial={{ scale: 0.94, opacity: 0, y: 20 }} animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.94, opacity: 0, y: 20 }}
              className="relative w-full max-w-4xl bg-modal border border-tint/40 rounded-[2.5rem] p-6 sm:p-8 shadow-2xl z-10 overflow-y-auto max-h-[95vh]">
              <button onClick={() => setDraft(null)} className="absolute right-7 top-7 text-fg/30 hover:text-fg transition-colors">
                <X className="w-6 h-6" />
              </button>

              <div className="flex items-center gap-4 mb-8 pr-10">
                <div className="w-14 h-14 rounded-2xl bg-tint/25 border border-tint/40 flex items-center justify-center">
                  <Package className="w-7 h-7 text-accent" />
                </div>
                <div>
                  <h2 className="text-2xl font-bold">Позиция каталога</h2>
                  <p className="text-sm text-fg/40 mt-1">Цена продажи: <span className="text-emerald-300 font-mono font-bold">{formatMoney(salePrice(draft))}</span></p>
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-[1.2fr_0.8fr] gap-6">
                <div className="space-y-5">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <label className="text-[10px] font-bold uppercase tracking-widest text-accent/45 ml-1">Артикул</label>
                      <input value={draft.sku} onChange={event => setDraft({ ...draft, sku: event.target.value })}
                        className={`${INPUT_CLS} font-mono`} placeholder="RS112" />
                    </div>
                    <div className="space-y-2">
                      <label className="text-[10px] font-bold uppercase tracking-widest text-accent/45 ml-1">Система</label>
                      <input value={draft.system} onChange={event => setDraft({ ...draft, system: event.target.value })}
                        className={INPUT_CLS} placeholder="СЛАЙД" />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <label className="text-[10px] font-bold uppercase tracking-widest text-accent/45 ml-1">Название</label>
                    <input value={draft.name} onChange={event => setDraft({ ...draft, name: event.target.value })}
                      className={INPUT_CLS} placeholder="Ручка-профиль" />
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    <div className="space-y-2">
                      <label className="text-[10px] font-bold uppercase tracking-widest text-accent/45 ml-1">Группа</label>
                      <select value={draft.group} onChange={event => setDraft({ ...draft, group: event.target.value as HardwareGroup })}
                        className={SELECT_CLS}>
                        {GROUPS.map(item => <option key={item} value={item}>{item}</option>)}
                      </select>
                    </div>
                    <div className="space-y-2">
                      <label className="text-[10px] font-bold uppercase tracking-widest text-accent/45 ml-1">Единица</label>
                      <select value={draft.unit} onChange={event => setDraft({ ...draft, unit: event.target.value as CatalogUnit })}
                        className={SELECT_CLS}>
                        {UNITS.map(item => <option key={item} value={item}>{item}</option>)}
                      </select>
                    </div>
                    <div className="space-y-2">
                      <label className="text-[10px] font-bold uppercase tracking-widest text-accent/45 ml-1">Поставщик</label>
                      <input value={draft.supplier} onChange={event => setDraft({ ...draft, supplier: event.target.value })}
                        className={INPUT_CLS} placeholder="Склад" />
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-[1fr_120px_120px] gap-4">
                    <div className="space-y-2">
                      <label className="text-[10px] font-bold uppercase tracking-widest text-accent/45 ml-1">Картинка сечения</label>
                      <input value={draft.imageFile} onChange={event => setDraft({ ...draft, imageFile: event.target.value })}
                        className={`${INPUT_CLS} font-mono`} placeholder="RS112.jpg" />
                    </div>
                    <NumberInput label="Ширина сечения" value={draft.sectionWidthMm} suffix="мм" onChange={value => setDraft({ ...draft, sectionWidthMm: value })} />
                    <NumberInput label="Высота сечения" value={draft.sectionHeightMm} suffix="мм" onChange={value => setDraft({ ...draft, sectionHeightMm: value })} />
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-[220px_1fr] gap-4">
                    <div className="space-y-2">
                      <label className="text-[10px] font-bold uppercase tracking-widest text-accent/45 ml-1">Покраска</label>
                      <select value={draft.paintMode} onChange={event => setDraft({ ...draft, paintMode: event.target.value as PaintMode })}
                        className={SELECT_CLS}>
                        {PAINT_MODES.map(item => <option key={item} value={item}>{item}</option>)}
                      </select>
                    </div>
                    <div className="space-y-2">
                      <label className="text-[10px] font-bold uppercase tracking-widest text-accent/45 ml-1">Варианты цвета</label>
                      <input
                        value={draft.colorVariants.join(', ')}
                        onChange={event => setDraft({
                          ...draft,
                          colorVariants: event.target.value.split(',').map(item => item.trim()).filter(Boolean),
                        })}
                        className={INPUT_CLS}
                        placeholder="Анод, RAL стандарт, RAL нестандарт"
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <label className="text-[10px] font-bold uppercase tracking-widest text-accent/45 ml-1">Комментарий</label>
                    <textarea value={draft.note} onChange={event => setDraft({ ...draft, note: event.target.value })}
                      rows={3}
                      className={`${INPUT_CLS} resize-none`}
                      placeholder="Как позиция участвует в расчёте" />
                  </div>
                </div>

                <div className="space-y-4">
                  <div className="bg-hi/[0.04] border border-tint/25 rounded-2xl p-4">
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-[9px] font-bold uppercase tracking-widest text-fg/30">Сечение</span>
                      <ImageIcon className="w-3.5 h-3.5 text-accent/55" />
                    </div>
                    <div className="h-40 rounded-xl bg-hi flex items-center justify-center overflow-hidden">
                      {draft.imageFile ? (
                        <img src={profileAssetUrl(draft.imageFile)} alt={draft.sku || 'Сечение'} className="max-w-full max-h-full object-contain" />
                      ) : (
                        <ImageIcon className="w-10 h-10 text-black/20" />
                      )}
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-1 gap-4">
                    <NumberInput label="Закупочная цена" value={draft.purchasePrice} suffix="₽" onChange={value => setDraft({ ...draft, purchasePrice: value })} />
                    <NumberInput label="Наценка" value={draft.markupPercent} suffix="%" onChange={value => setDraft({ ...draft, markupPercent: value })} />
                    <NumberInput label="Вес на единицу" value={draft.weight} suffix="кг" onChange={value => setDraft({ ...draft, weight: value })} />
                    <NumberInput label="Норма отхода" value={draft.wastePercent} suffix="%" onChange={value => setDraft({ ...draft, wastePercent: value })} />
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    {[
                      { label: 'Продажа', value: formatMoney(salePrice(draft)), icon: BadgePercent },
                      { label: 'Вес', value: `${draft.weight} кг/${draft.unit}`, icon: Scale },
                      { label: 'Отход', value: `${draft.wastePercent}%`, icon: Ruler },
                      { label: 'Дата', value: draft.updatedAt, icon: SlidersHorizontal },
                    ].map(card => (
                      <div key={card.label} className="bg-hi/[0.04] border border-tint/25 rounded-2xl p-4">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-[9px] font-bold uppercase tracking-widest text-fg/30">{card.label}</span>
                          <card.icon className="w-3.5 h-3.5 text-accent/55" />
                        </div>
                        <div className="text-sm font-bold font-mono text-fg/80">{card.value}</div>
                      </div>
                    ))}
                  </div>

                  <button onClick={() => setDraft({ ...draft, isActive: !draft.isActive })}
                    className={`w-full flex items-center justify-between px-5 py-4 rounded-2xl border transition-all ${
                      draft.isActive ? 'bg-emerald-500/10 border-emerald-500/25 text-emerald-300' : 'bg-hi/5 border-tint/25 text-fg/45'
                    }`}>
                    <span className="text-sm font-bold">{draft.isActive ? 'Позиция активна' : 'Позиция в архиве'}</span>
                    <span className={`w-12 h-6 rounded-full transition-colors relative ${draft.isActive ? 'bg-emerald-500' : 'bg-hi/15'}`}>
                      <span className={`absolute top-1 w-4 h-4 rounded-full bg-hi shadow transition-transform ${draft.isActive ? 'translate-x-7' : 'translate-x-1'}`} />
                    </span>
                  </button>
                </div>
              </div>

              <div className="flex gap-4 mt-8">
                <button onClick={() => setDraft(null)}
                  className="flex-1 py-4 rounded-2xl bg-hi/5 hover:bg-hi/10 font-bold transition-all">Отмена</button>
                <button onClick={handleSave}
                  className="flex-1 py-4 rounded-2xl bg-primary hover:bg-primary-h text-white font-bold transition-all shadow-lg shadow-primary/20 flex items-center justify-center gap-2">
                  <Save className="w-4 h-4" />
                  Сохранить
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
