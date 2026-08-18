import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ArrowLeft, BadgePercent, Box, Check, Edit2, Package,
  ImageIcon, Plus, Ruler, Save, Scale, Search, SlidersHorizontal, Trash2, X,
} from 'lucide-react';
import {
  archiveHardwareCatalogItem,
  createHardwareCatalogItem,
  listHardwareCatalog,
  listSystemMarkups,
  updateSystemMarkup,
  updateHardwareCatalogItem,
  type CatalogUnit,
  type CatalogFinishVariant,
  type FinishCode,
  type HardwareCatalogItem,
  type HardwareGroup,
  type PaintMode,
  type SystemGroupCode,
  type SystemMarkup,
} from '../api/catalog';
import { useAuthStore } from '../store/authStore';
import { toast } from '../store/toastStore';

type HardwareItem = HardwareCatalogItem;

const STORAGE_KEY = 'raluma-hardware-catalog-draft-v1';

const GROUPS: HardwareGroup[] = ['Профили', 'Фурнитура', 'Ручки', 'Замки', 'Защёлки', 'Уплотнители', 'Крепёж', 'Расходники', 'Услуги'];
const UNITS: CatalogUnit[] = ['шт', 'м.п.', 'м²', 'компл.', 'кг'];
const DEFAULT_COLOR_VARIANTS = ['Анод', 'RAL стандарт', 'RAL нестандарт'];
const SYSTEM_GROUPS: Array<{ code: SystemGroupCode; label: string }> = [
  { code: 'SLIDE_1', label: 'СЛАЙД 1 ряд' },
  { code: 'SLIDE_2', label: 'СЛАЙД 2 ряда' },
];
const FINISHES: Record<FinishCode, { name: string; requiresPaint: boolean }> = {
  BASE: { name: 'Без окраски', requiresPaint: false },
  ANOD: { name: 'Анод', requiresPaint: false },
  RAL_STANDARD: { name: 'RAL стандарт', requiresPaint: true },
  RAL_NONSTANDARD: { name: 'RAL нестандарт', requiresPaint: true },
};

function finishCodes(paintMode: PaintMode): FinishCode[] {
  return paintMode === 'Не красится'
    ? ['BASE']
    : ['ANOD', 'RAL_STANDARD', 'RAL_NONSTANDARD'];
}

function defaultFinish(code: FinishCode, cost = 0): CatalogFinishVariant {
  return {
    code,
    name: FINISHES[code].name,
    cost,
    profileMarkupPercent: 0,
    profileDiscountPercent: 0,
    constructionMarkupPercent: 0,
    constructionDiscountPercent: 0,
    requiresPaint: FINISHES[code].requiresPaint,
    isActive: true,
  };
}

const GROUP_COLORS: Record<HardwareGroup, string> = {
  'Профили': 'bg-teal-500/15 text-teal-300 border-teal-500/25',
  'Фурнитура': 'bg-sky-500/15 text-sky-300 border-sky-500/25',
  'Ручки': 'bg-blue-500/15 text-blue-300 border-blue-500/25',
  'Замки': 'bg-amber-500/15 text-amber-300 border-amber-500/25',
  'Защёлки': 'bg-emerald-500/15 text-emerald-300 border-emerald-500/25',
  'Уплотнители': 'bg-cyan-500/15 text-cyan-300 border-cyan-500/25',
  'Крепёж': 'bg-violet-500/15 text-violet-300 border-violet-500/25',
  'Расходники': 'bg-rose-500/15 text-rose-300 border-rose-500/25',
  'Услуги': 'bg-lime-500/15 text-lime-300 border-lime-500/25',
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
    profileDiscountPercent: 0,
    weight: 0.72,
    wastePercent: 4,
    constructionMarkupPercent: 0,
    constructionDiscountPercent: 0,
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
    imageFile: 'RS2323.png',
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
    imageFile: 'RS2325.png',
    paintMode: 'Красится',
    colorVariants: DEFAULT_COLOR_VARIANTS,
    supplier: 'Raluma',
    isActive: true,
    updatedAt: '2026-06-08',
    note: 'Стандартный нижний направляющий профиль',
  },
  {
    id: 1041,
    sku: 'RS23231',
    name: 'Порог накладной 3-рельсовый',
    group: 'Профили',
    system: 'СЛАЙД 3',
    unit: 'м.п.',
    purchasePrice: 340,
    markupPercent: 35,
    weight: 0.32,
    wastePercent: 4,
    sectionWidthMm: 76,
    sectionHeightMm: 11,
    imageFile: 'RS23231.png',
    paintMode: 'Частично',
    colorVariants: DEFAULT_COLOR_VARIANTS,
    supplier: 'Raluma',
    isActive: true,
    updatedAt: '2026-06-29',
    note: 'Накладной порог, верхние бобышки не красить',
  },
  {
    id: 1042,
    sku: 'RS23251',
    name: 'Порог накладной 5-рельсовый',
    group: 'Профили',
    system: 'СЛАЙД 5',
    unit: 'м.п.',
    purchasePrice: 460,
    markupPercent: 35,
    weight: 0.46,
    wastePercent: 4,
    sectionWidthMm: 122,
    sectionHeightMm: 11,
    imageFile: 'RS23251.png',
    paintMode: 'Частично',
    colorVariants: DEFAULT_COLOR_VARIANTS,
    supplier: 'Raluma',
    isActive: true,
    updatedAt: '2026-06-29',
    note: 'Накладной порог, верхние бобышки не красить',
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
    imageFile: 'RS2333.png',
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
    imageFile: 'RS2335.png',
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
    imageFile: 'RS2081.png',
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
    imageFile: 'RS1082.png',
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
    imageFile: 'RS112.png',
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
    imageFile: 'RS2061.png',
    paintMode: 'Красится',
    colorVariants: DEFAULT_COLOR_VARIANTS,
    supplier: 'Raluma',
    isActive: true,
    updatedAt: '2026-06-08',
    note: 'В схеме сверху зеркалится по направлению первой панели',
  },
  {
    id: 1101,
    sku: 'RS1006',
    name: 'Прозрачный межстекольный',
    group: 'Профили',
    system: 'СЛАЙД',
    unit: 'м.п.',
    purchasePrice: 0,
    markupPercent: 35,
    weight: 0,
    wastePercent: 4,
    sectionWidthMm: 20,
    sectionHeightMm: 12,
    imageFile: 'RS1006.png',
    paintMode: 'Не красится',
    colorVariants: ['Без цвета'],
    supplier: 'Raluma',
    isActive: true,
    updatedAt: '2026-06-29',
    note: 'Прозрачный межстекольный профиль, перехлест между стеклами 9,5 мм',
  },
  {
    id: 1102,
    sku: 'RS3061',
    name: 'Профиль с зацепом',
    group: 'Профили',
    system: 'СЛАЙД',
    unit: 'м.п.',
    purchasePrice: 0,
    markupPercent: 35,
    weight: 0,
    wastePercent: 4,
    sectionWidthMm: 18.8,
    sectionHeightMm: 18.8,
    imageFile: 'RS3061.png',
    paintMode: 'Не красится',
    colorVariants: ['Без цвета'],
    supplier: 'Raluma',
    isActive: true,
    updatedAt: '2026-06-26',
    note: 'Заменяет старый h-профиль RS1004, перехлест между стеклами 11,5 мм',
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
    imageFile: 'RS2021.png',
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
    imageFile: 'RS1002.png',
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
    imageFile: 'RS205.png',
    paintMode: 'Не красится',
    colorVariants: ['Без цвета'],
    supplier: 'Фурнитура СПБ',
    isActive: true,
    updatedAt: '2026-06-08',
    note: 'Ставится слева/справа по настройкам секции',
  },
  {
    id: 1131,
    sku: 'RS108',
    name: 'Заглушка стекольного центральная',
    group: 'Фурнитура',
    system: 'СЛАЙД',
    unit: 'шт',
    purchasePrice: 0,
    markupPercent: 40,
    weight: 0,
    wastePercent: 0,
    sectionWidthMm: 0,
    sectionHeightMm: 0,
    imageFile: 'RS108.png',
    paintMode: 'Не красится',
    colorVariants: ['Без цвета'],
    supplier: 'Фурнитура СПБ',
    isActive: true,
    updatedAt: '2026-06-29',
    note: 'Центральные створки СЛАЙД 2 ряда',
  },
  {
    id: 1132,
    sku: 'RU003',
    name: 'Ролик 2-колесный',
    group: 'Фурнитура',
    system: 'СЛАЙД',
    unit: 'шт',
    purchasePrice: 0,
    markupPercent: 40,
    weight: 0,
    wastePercent: 0,
    sectionWidthMm: 0,
    sectionHeightMm: 0,
    imageFile: 'RU003.png',
    paintMode: 'Не красится',
    colorVariants: ['Без цвета'],
    supplier: 'Фурнитура СПБ',
    isActive: true,
    updatedAt: '2026-06-29',
    note: 'Для панелей шириной до 500 мм',
  },
  {
    id: 1133,
    sku: 'RU005',
    name: 'Ролик 4-колесный',
    group: 'Фурнитура',
    system: 'СЛАЙД',
    unit: 'шт',
    purchasePrice: 0,
    markupPercent: 40,
    weight: 0,
    wastePercent: 0,
    sectionWidthMm: 0,
    sectionHeightMm: 0,
    imageFile: 'RU005.png',
    paintMode: 'Не красится',
    colorVariants: ['Без цвета'],
    supplier: 'Фурнитура СПБ',
    isActive: true,
    updatedAt: '2026-06-29',
    note: 'Для панелей шириной больше 500 мм',
  },
  {
    id: 1134,
    sku: 'RS3110',
    name: 'h-уплотнитель центрального стыка',
    group: 'Профили',
    system: 'СЛАЙД',
    unit: 'м.п.',
    purchasePrice: 0,
    markupPercent: 35,
    weight: 0,
    wastePercent: 4,
    sectionWidthMm: 0,
    sectionHeightMm: 0,
    imageFile: 'RS3110.jpg',
    paintMode: 'Не красится',
    colorVariants: ['Без цвета'],
    supplier: 'Склад',
    isActive: true,
    updatedAt: '2026-07-14',
    note: 'Для центрального стыка СЛАЙД 2 ряда, кроме варианта с центральными RS112',
  },
  {
    id: 1135,
    sku: 'RS123',
    name: 'Ответная планка замка RS3020',
    group: 'Фурнитура',
    system: 'СЛАЙД',
    unit: 'шт',
    purchasePrice: 0,
    markupPercent: 40,
    weight: 0,
    wastePercent: 0,
    sectionWidthMm: 0,
    sectionHeightMm: 0,
    imageFile: 'RS123.jpg',
    paintMode: 'Не красится',
    colorVariants: ['Без цвета'],
    supplier: 'Фурнитура СПБ',
    isActive: true,
    updatedAt: '2026-07-14',
    note: 'Ставится по одной планке на каждый замок RS3020',
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
  {
    id: 1301,
    sku: 'RS30201',
    name: 'Ручка-скоба 600мм',
    group: 'Ручки',
    system: 'СЛАЙД',
    unit: 'шт',
    purchasePrice: 0,
    markupPercent: 40,
    weight: 0,
    wastePercent: 0,
    sectionWidthMm: 0,
    sectionHeightMm: 0,
    imageFile: 'RS30201.png',
    paintMode: 'Не красится',
    colorVariants: ['Без цвета'],
    supplier: 'Фурнитура СПБ',
    isActive: true,
    updatedAt: '2026-06-26',
    note: 'Боковые и центральные панели СЛАЙД',
  },
];

const emptyDraft = (): HardwareItem => ({
  id: Date.now(),
  sku: '',
  name: '',
  group: 'Профили',
  system: 'СЛАЙД',
  systemGroups: ['SLIDE_1', 'SLIDE_2'],
  unit: 'шт',
  purchasePrice: 0,
  markupPercent: 0,
  profileDiscountPercent: 0,
  weight: 0,
  wastePercent: 0,
  constructionMarkupPercent: 0,
  constructionDiscountPercent: 0,
  sectionWidthMm: 0,
  sectionHeightMm: 0,
  imageFile: '',
  paintMode: 'Не красится',
  colorVariants: ['Без окраски'],
  finishVariants: [defaultFinish('BASE')],
  supplier: '',
  isActive: true,
  updatedAt: new Date().toISOString().slice(0, 10),
  note: '',
});

function normalizeItem(item: Partial<HardwareItem>): HardwareItem {
  const fallbackPrice = (item.purchasePrice ?? 0) * (1 + (item.markupPercent ?? 0) / 100);
  const paintMode = item.paintMode ?? 'Не красится';
  const existingVariants = new Map(
    (item.finishVariants || []).map(variant => [
      variant.code || (
        variant.name.toLowerCase().includes('нестандарт') ? 'RAL_NONSTANDARD'
          : variant.name.toLowerCase().includes('ral') ? 'RAL_STANDARD'
            : variant.name.toLowerCase().includes('анод') ? 'ANOD' : 'BASE'
      ),
      variant,
    ]),
  );
  const variants = finishCodes(paintMode).map(code => {
    const existing = existingVariants.get(code);
    return {
      ...defaultFinish(code, Number(item.purchasePrice ?? fallbackPrice)),
      ...existing,
      code,
      name: FINISHES[code].name,
      profileMarkupPercent: Number(existing?.profileMarkupPercent ?? item.markupPercent ?? 0),
      profileDiscountPercent: Number(existing?.profileDiscountPercent ?? item.profileDiscountPercent ?? 0),
      constructionMarkupPercent: Number(existing?.constructionMarkupPercent ?? item.constructionMarkupPercent ?? 0),
      constructionDiscountPercent: Number(existing?.constructionDiscountPercent ?? item.constructionDiscountPercent ?? 0),
      requiresPaint: FINISHES[code].requiresPaint,
      isActive: true,
    };
  });
  return {
    id: item.id ?? Date.now(),
    sku: item.sku ?? '',
    name: item.name ?? '',
    group: item.group ?? 'Профили',
    system: item.system ?? 'СЛАЙД',
    systemGroups: item.systemGroups ?? (item.system?.toUpperCase().includes('СЛАЙД') ? ['SLIDE_1', 'SLIDE_2'] : []),
    unit: item.unit ?? 'шт',
    purchasePrice: item.purchasePrice ?? 0,
    markupPercent: item.markupPercent ?? 0,
    profileDiscountPercent: item.profileDiscountPercent ?? 0,
    weight: item.weight ?? 0,
    wastePercent: item.wastePercent ?? 0,
    constructionMarkupPercent: item.constructionMarkupPercent ?? 0,
    constructionDiscountPercent: item.constructionDiscountPercent ?? 0,
    sectionWidthMm: item.sectionWidthMm ?? 0,
    sectionHeightMm: item.sectionHeightMm ?? 0,
    imageFile: item.imageFile ?? '',
    paintMode,
    colorVariants: variants.map(variant => variant.name),
    finishVariants: variants,
    supplier: item.supplier ?? '',
    isActive: item.isActive ?? true,
    updatedAt: item.updatedAt ?? new Date().toISOString().slice(0, 10),
    note: item.note ?? '',
  };
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

function formatMoney(value: number) {
  return new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    maximumFractionDigits: value < 10 ? 1 : 0,
  }).format(value);
}

function pricingCosts(item: HardwareItem) {
  const variants = (item.finishVariants || [])
    .filter(row => row.isActive)
    .map(row => Number(row.cost))
    .filter(Number.isFinite);
  return variants.length > 0 ? variants : [item.purchasePrice];
}

function activeFinishes(item: HardwareItem) {
  return (item.finishVariants || []).filter(variant => variant.isActive);
}

function profileSale(variant: CatalogFinishVariant) {
  return Number(variant.cost || 0)
    * (1 + Number(variant.profileMarkupPercent || 0) / 100)
    * (1 - Number(variant.profileDiscountPercent || 0) / 100);
}

function costWithWaste(item: HardwareItem, variant: CatalogFinishVariant) {
  const waste = ['шт', 'компл.'].includes(item.unit) ? 0 : item.wastePercent;
  return profileSale(variant) * (1 + waste / 100);
}

function constructionPrice(item: HardwareItem, variant: CatalogFinishVariant) {
  return costWithWaste(item, variant)
    * (1 + Number(variant.constructionMarkupPercent || 0) / 100)
    * (1 - Number(variant.constructionDiscountPercent || 0) / 100);
}

function formatPriceRange(values: number[]) {
  const ordered = [...values].sort((left, right) => left - right);
  const first = ordered[0] ?? 0;
  const last = ordered[ordered.length - 1] ?? first;
  return first === last
    ? formatMoney(first)
    : `${formatMoney(first)} – ${formatMoney(last)}`;
}

function priceRange(item: HardwareItem, transform: (item: HardwareItem, variant: CatalogFinishVariant) => number) {
  return formatPriceRange(activeFinishes(item).map(variant => transform(item, variant)));
}

function percentRange(item: HardwareItem, field: keyof CatalogFinishVariant) {
  const values = activeFinishes(item).map(variant => Number(variant[field] || 0));
  const min = values.length ? Math.min(...values) : 0;
  const max = values.length ? Math.max(...values) : 0;
  return min === max ? `${min}%` : `${min}%–${max}%`;
}

function NumberInput({
  label, value, suffix, max, onChange,
}: {
  label: string;
  value: number;
  suffix?: string;
  max?: number;
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
          max={max}
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
  const [systemMarkups, setSystemMarkups] = useState<SystemMarkup[]>([]);
  const [systemMarkupDrafts, setSystemMarkupDrafts] = useState<Record<SystemGroupCode, string>>({ SLIDE_1: '', SLIDE_2: '' });
  const [savingSystemGroup, setSavingSystemGroup] = useState<SystemGroupCode | null>(null);

  useEffect(() => {
    if (!isAdmin()) navigate('/');
  }, [isAdmin, navigate]);

  useEffect(() => {
    if (!isAdmin()) return;

    let cancelled = false;
    setIsCatalogLoading(true);
    setCatalogError(false);

    Promise.all([listHardwareCatalog(), listSystemMarkups()])
      .then(([remoteItems, markups]) => {
        if (cancelled) return;
        const next = remoteItems.map(item => normalizeItem(item));
        setItems(next);
        setSystemMarkups(markups);
        setSystemMarkupDrafts({
          SLIDE_1: markups.find(row => row.code === 'SLIDE_1')?.constructionMarkupPercent?.toString() ?? '',
          SLIDE_2: markups.find(row => row.code === 'SLIDE_2')?.constructionMarkupPercent?.toString() ?? '',
        });
      })
      .catch(() => {
        if (!cancelled) {
          setItems([]);
          setCatalogError(true);
        }
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
        item.paintMode.toLowerCase().includes(q) ||
        item.colorVariants.some(variant => variant.toLowerCase().includes(q)) ||
        (item.finishVariants || []).some(variant => variant.name.toLowerCase().includes(q));
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
    const markups = active.flatMap(item => activeFinishes(item).map(variant => Number(variant.profileMarkupPercent || 0)));
    const avgMarkup = markups.length
      ? markups.reduce((sum, value) => sum + value, 0) / markups.length
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

  const handleSave = async () => {
    if (!draft) return;
    if (catalogError) {
      toast.error('Каталог недоступен. Изменения не сохранены');
      return;
    }
    if (!draft.sku.trim() || !draft.name.trim()) {
      toast.error('Заполните артикул и название');
      return;
    }
    if (draft.system.toUpperCase().includes('СЛАЙД') && !(draft.systemGroups || []).length) {
      toast.error('Выберите хотя бы одну группу системы');
      return;
    }
    const normalized = normalizeItem({
      ...draft,
      sku: draft.sku.trim(),
      name: draft.name.trim(),
      system: draft.system || 'СЛАЙД',
      wastePercent: ['шт', 'компл.'].includes(draft.unit) ? 0 : draft.wastePercent,
      colorVariants: (draft.finishVariants || []).map(variant => variant.name),
      finishVariants: (draft.finishVariants || []).map(variant => ({
        ...variant,
        cost: Number(variant.cost) || 0,
        profileMarkupPercent: Number(variant.profileMarkupPercent) || 0,
        profileDiscountPercent: Number(variant.profileDiscountPercent) || 0,
        constructionMarkupPercent: Number(variant.constructionMarkupPercent) || 0,
        constructionDiscountPercent: Number(variant.constructionDiscountPercent) || 0,
      })),
      updatedAt: new Date().toISOString().slice(0, 10),
    });
    const exists = items.some(item => item.id === normalized.id);
    try {
      const saved = exists
        ? await updateHardwareCatalogItem(normalized.id, normalized)
        : await createHardwareCatalogItem(normalized);
      const normalizedSaved = normalizeItem(saved);
      setItems(prev => exists
        ? prev.map(item => item.id === normalizedSaved.id ? normalizedSaved : item)
        : [normalizedSaved, ...prev]);
      setDraft(null);
      toast.success('Позиция сохранена');
    } catch {
      toast.error('Не удалось сохранить позицию');
    }
  };

  const handleSystemMarkupSave = async (code: SystemGroupCode) => {
    const value = Number(systemMarkupDrafts[code]);
    if (!Number.isFinite(value) || value < 0) {
      toast.error('Укажите корректную наценку');
      return;
    }
    setSavingSystemGroup(code);
    try {
      await updateSystemMarkup(code, value);
      const [remoteItems, markups] = await Promise.all([listHardwareCatalog(), listSystemMarkups()]);
      setItems(remoteItems.map(item => normalizeItem(item)));
      setSystemMarkups(markups);
      setSystemMarkupDrafts(current => ({ ...current, [code]: value.toString() }));
      toast.success('Наценка группы сохранена');
    } catch {
      toast.error('Не удалось изменить наценку группы');
    } finally {
      setSavingSystemGroup(null);
    }
  };

  const handleDelete = async (id: number) => {
    if (catalogError) {
      toast.error('Каталог недоступен. Изменения не сохранены');
      return;
    }
    try {
      const archived = normalizeItem(await archiveHardwareCatalogItem(id));
      setItems(prev => prev.map(item => item.id === id ? archived : item));
      toast.success('Позиция перенесена в архив');
    } catch {
      toast.error('Не удалось архивировать позицию');
    }
  };

  return (
    <div className="min-h-screen bg-page text-fg font-sans flex flex-col">
      <nav className="sticky top-0 z-40 bg-page/90 backdrop-blur-md border-b border-tint/25 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-tint/25 border border-tint/40 flex items-center justify-center">
            <Package className="w-6 h-6 text-accent" />
          </div>
          <span className="text-xl font-bold tracking-tight uppercase">Каталог</span>
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
                  {isCatalogLoading ? 'Загрузка справочника' : catalogError ? 'Каталог недоступен' : 'Расчётный каталог'}
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

        <section className="mb-6 border-y border-tint/25 py-5">
          <div className="mb-4">
            <h2 className="text-lg font-bold">Наценка на конструкцию по системам</h2>
            <p className="mt-1 text-sm text-fg/45">Значение применяется ко всем исполнениям позиций выбранной группы. Если позиция входит в обе группы, действует последнее сохранение.</p>
          </div>
          <div className="grid gap-3 lg:grid-cols-2">
            {SYSTEM_GROUPS.map(systemGroup => {
              const state = systemMarkups.find(row => row.code === systemGroup.code);
              return (
                <div key={systemGroup.code} className="grid grid-cols-[minmax(0,1fr)_140px_auto] items-center gap-3 rounded-xl border border-tint/25 bg-surface/20 px-4 py-3">
                  <div>
                    <div className="font-bold">{systemGroup.label}</div>
                    <div className="mt-1 text-xs text-fg/40">{state?.mixed ? 'У позиций сейчас разные значения' : 'Общее значение группы'}</div>
                  </div>
                  <div className="relative">
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={systemMarkupDrafts[systemGroup.code]}
                      placeholder={state?.mixed ? 'Разные' : '0'}
                      onChange={event => setSystemMarkupDrafts(current => ({ ...current, [systemGroup.code]: event.target.value }))}
                      className={`${INPUT_CLS} pr-10 font-mono`}
                    />
                    <span className="absolute right-4 top-1/2 -translate-y-1/2 text-xs font-bold text-fg/35">%</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleSystemMarkupSave(systemGroup.code)}
                    disabled={savingSystemGroup === systemGroup.code}
                    className="inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-primary px-4 font-bold text-white transition-colors hover:bg-primary-h disabled:opacity-50"
                  >
                    <Save className="h-4 w-4" />
                    {savingSystemGroup === systemGroup.code ? '...' : 'Сохранить'}
                  </button>
                </div>
              );
            })}
          </div>
        </section>

        <div className="flex flex-col xl:flex-row gap-3 mb-5">
          <div className="relative flex-1 group">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-fg/25 group-focus-within:text-accent transition-colors" />
            <input
              value={search}
              onChange={event => setSearch(event.target.value)}
              placeholder="Поиск по артикулу, названию или исполнению..."
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
                        <div className="w-16 h-12 rounded-xl bg-white border border-tint/20 flex items-center justify-center overflow-hidden flex-shrink-0">
                          {item.imageFile ? (
                            <img src={profileAssetUrl(item.imageFile)} alt={item.sku} className="max-w-full max-h-full object-contain" />
                          ) : (
                            <ImageIcon className="w-5 h-5 text-black/25" />
                          )}
                        </div>
                        <div className="min-w-0">
                          <div className="font-bold text-sm text-fg truncate">{item.name}</div>
                          <div className="text-[11px] text-fg/35 mt-1">
                            {(item.systemGroups || []).map(code => SYSTEM_GROUPS.find(row => row.code === code)?.label).filter(Boolean).join(' · ') || 'Без группы'}
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
                    <td className="px-5 py-4 text-sm font-mono">{formatPriceRange(pricingCosts(item))}</td>
                    <td className="px-5 py-4 text-sm font-mono text-amber-300">{percentRange(item, 'profileMarkupPercent')}</td>
                    <td className="px-5 py-4 text-sm font-mono text-emerald-300">{priceRange(item, (_item, variant) => profileSale(variant))}</td>
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
                  <p className="text-sm text-fg/40 mt-1">Цена профиля: <span className="text-emerald-300 font-mono font-bold">{priceRange(draft, (_item, variant) => profileSale(variant))}</span></p>
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-[1.2fr_0.8fr] gap-6">
                <div className="space-y-5">
                  <div className="space-y-2">
                    <label className="text-[10px] font-bold uppercase tracking-widest text-accent/45 ml-1">Артикул</label>
                    <input value={draft.sku} onChange={event => setDraft({ ...draft, sku: event.target.value })}
                      className={`${INPUT_CLS} font-mono`} placeholder="RS112" />
                  </div>

                  <div className="space-y-2">
                    <label className="text-[10px] font-bold uppercase tracking-widest text-accent/45 ml-1">Название</label>
                    <input value={draft.name} onChange={event => setDraft({ ...draft, name: event.target.value })}
                      className={INPUT_CLS} placeholder="Ручка-профиль" />
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
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
                  </div>

                  <div className="space-y-2">
                    <label className="text-[10px] font-bold uppercase tracking-widest text-accent/45 ml-1">Группы системы</label>
                    <div className="grid grid-cols-2 gap-2">
                      {SYSTEM_GROUPS.map(systemGroup => {
                        const selected = (draft.systemGroups || []).includes(systemGroup.code);
                        return (
                          <button
                            key={systemGroup.code}
                            type="button"
                            onClick={() => setDraft({
                              ...draft,
                              systemGroups: selected
                                ? (draft.systemGroups || []).filter(code => code !== systemGroup.code)
                                : [...(draft.systemGroups || []), systemGroup.code],
                            })}
                            className={`rounded-xl border px-4 py-3 text-sm font-bold transition-colors ${selected ? 'border-accent/45 bg-accent/15 text-accent' : 'border-tint/25 bg-hi/[0.03] text-fg/45'}`}
                          >
                            {systemGroup.label}
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <NumberInput label="Ширина" value={draft.sectionWidthMm} suffix="мм" onChange={value => setDraft({ ...draft, sectionWidthMm: value })} />
                    <NumberInput label="Высота" value={draft.sectionHeightMm} suffix="мм" onChange={value => setDraft({ ...draft, sectionHeightMm: value })} />
                  </div>

                  <div className="space-y-2">
                    <label className="text-[10px] font-bold uppercase tracking-widest text-accent/45 ml-1">Окрашивание позиции</label>
                    <div className="grid grid-cols-3 gap-2">
                      {(['Не красится', 'Красится', 'Частично'] as PaintMode[]).map(mode => (
                        <button
                          key={mode}
                          type="button"
                          onClick={() => {
                            const current = new Map<FinishCode, CatalogFinishVariant>((draft.finishVariants || []).map(variant => [variant.code, variant]));
                            const variants = finishCodes(mode).map(code => current.get(code) || defaultFinish(code, draft.purchasePrice));
                            setDraft({ ...draft, paintMode: mode, finishVariants: variants, colorVariants: variants.map(variant => variant.name) });
                          }}
                          className={`rounded-xl border px-3 py-3 text-xs font-bold transition-colors ${draft.paintMode === mode ? 'border-accent/45 bg-accent/15 text-accent' : 'border-tint/25 bg-hi/[0.03] text-fg/45'}`}
                        >
                          {mode}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="space-y-2">
                    <label className="text-[10px] font-bold uppercase tracking-widest text-accent/45 ml-1">Цены по исполнениям</label>
                    <div className="overflow-x-auto rounded-xl border border-tint/25">
                      <div className="min-w-[900px]">
                        <div className="grid grid-cols-[160px_repeat(5,minmax(130px,1fr))] gap-px bg-tint/20 text-[9px] font-bold uppercase tracking-wider text-fg/45">
                          {['Исполнение', 'Себестоимость', 'Наценка на профиль', 'Скидка на профиль', 'Наценка на конструкцию', 'Скидка на конструкцию'].map(label => (
                            <div key={label} className="bg-modal px-3 py-2">{label}</div>
                          ))}
                        </div>
                        {(draft.finishVariants || []).map((variant, index) => (
                          <div key={variant.code} className="grid grid-cols-[160px_repeat(5,minmax(130px,1fr))] gap-px border-t border-tint/20 bg-tint/20">
                            <div className="flex items-center bg-modal px-3 py-2 text-sm font-bold">{FINISHES[variant.code].name}</div>
                            {([
                              ['cost', variant.cost ?? 0, '₽'],
                              ['profileMarkupPercent', variant.profileMarkupPercent, '%'],
                              ['profileDiscountPercent', variant.profileDiscountPercent, '%'],
                              ['constructionMarkupPercent', variant.constructionMarkupPercent, '%'],
                              ['constructionDiscountPercent', variant.constructionDiscountPercent, '%'],
                            ] as const).map(([field, value, suffix]) => (
                              <div key={field} className="relative bg-modal p-2">
                                <input
                                  type="number"
                                  min="0"
                                  max={field.includes('Discount') ? 100 : undefined}
                                  step="0.01"
                                  value={value}
                                  onChange={event => setDraft({
                                    ...draft,
                                    finishVariants: (draft.finishVariants || []).map((row, rowIndex) => rowIndex === index ? { ...row, [field]: event.target.value } : row),
                                  })}
                                  className="w-full rounded-lg border border-tint/25 bg-hi/[0.04] px-3 py-2 pr-8 font-mono text-sm outline-none focus:border-accent/60"
                                  aria-label={`${FINISHES[variant.code].name}: ${field}`}
                                />
                                <span className="absolute right-4 top-1/2 -translate-y-1/2 text-[10px] text-fg/35">{suffix}</span>
                              </div>
                            ))}
                          </div>
                        ))}
                      </div>
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
                    <div className="h-40 rounded-xl bg-white flex items-center justify-center overflow-hidden">
                      {draft.imageFile ? (
                        <img src={profileAssetUrl(draft.imageFile)} alt={draft.sku || 'Сечение'} className="max-w-full max-h-full object-contain" />
                      ) : (
                        <ImageIcon className="w-10 h-10 text-black/20" />
                      )}
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-1 gap-4">
                    <NumberInput label="Вес на единицу" value={draft.weight} suffix="кг" onChange={value => setDraft({ ...draft, weight: value })} />
                    {!['шт', 'компл.'].includes(draft.unit) && (
                      <NumberInput label="Наценка на отходы" value={draft.wastePercent} suffix="%" onChange={value => setDraft({ ...draft, wastePercent: value })} />
                    )}
                  </div>

                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                    {[
                      { label: 'Цена профиля', value: priceRange(draft, (_item, variant) => profileSale(variant)), icon: BadgePercent },
                      { label: 'С отходами', value: priceRange(draft, costWithWaste), icon: Ruler },
                      { label: 'Цена в конструкции', value: priceRange(draft, constructionPrice), icon: Scale },
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
