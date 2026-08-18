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
  'Профили': 'bg-teal-500/20 text-fg border-teal-500/45',
  'Фурнитура': 'bg-sky-500/20 text-fg border-sky-500/45',
  'Ручки': 'bg-blue-500/20 text-fg border-blue-500/45',
  'Замки': 'bg-amber-500/20 text-fg border-amber-500/45',
  'Защёлки': 'bg-emerald-500/20 text-fg border-emerald-500/45',
  'Уплотнители': 'bg-cyan-500/20 text-fg border-cyan-500/45',
  'Крепёж': 'bg-violet-500/20 text-fg border-violet-500/45',
  'Расходники': 'bg-rose-500/20 text-fg border-rose-500/45',
  'Услуги': 'bg-lime-500/20 text-fg border-lime-500/45',
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

function PriceField({
  label, value, suffix, max, onChange,
}: {
  label: string;
  value: number | string;
  suffix: string;
  max?: number;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block min-w-0">
      <span className="mb-1.5 block text-[9px] font-bold uppercase leading-tight tracking-wider text-fg/40">{label}</span>
      <span className="relative block">
        <input
          type="number"
          min="0"
          max={max}
          step="0.01"
          value={value}
          onChange={event => onChange(event.target.value)}
          className="h-11 w-full rounded-xl border border-tint/30 bg-hi/[0.04] px-3 pr-8 font-mono text-sm outline-none transition-colors focus:border-accent/60"
        />
        <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[10px] text-fg/35">{suffix}</span>
      </span>
    </label>
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
  const [systemGroup, setSystemGroup] = useState<'Все' | SystemGroupCode>('Все');
  const [status, setStatus] = useState<'all' | 'active' | 'inactive'>('active');
  const [activeCatalogTab, setActiveCatalogTab] = useState<'items' | 'markups'>('items');
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
      const matchesSystemGroup = systemGroup === 'Все' || (item.systemGroups || []).includes(systemGroup);
      const matchesStatus =
        status === 'all' ||
        (status === 'active' && item.isActive) ||
        (status === 'inactive' && !item.isActive);
      return matchesSearch && matchesGroup && matchesSystemGroup && matchesStatus;
    });
  }, [group, items, search, status, systemGroup]);

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

        <div className="mb-5 inline-flex rounded-2xl border border-tint/30 bg-surface/30 p-1">
          <button
            type="button"
            onClick={() => setActiveCatalogTab('items')}
            className={`flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-bold transition-colors ${
              activeCatalogTab === 'items' ? 'bg-primary text-white shadow-sm' : 'text-fg/55 hover:bg-hi/[0.04] hover:text-fg'
            }`}
          >
            <Package className="h-4 w-4" />
            Позиции
          </button>
          <button
            type="button"
            onClick={() => setActiveCatalogTab('markups')}
            className={`flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-bold transition-colors ${
              activeCatalogTab === 'markups' ? 'bg-primary text-white shadow-sm' : 'text-fg/55 hover:bg-hi/[0.04] hover:text-fg'
            }`}
          >
            <BadgePercent className="h-4 w-4" />
            Наценки систем
          </button>
        </div>

        {activeCatalogTab === 'items' && <div className="flex flex-col xl:flex-row gap-3 mb-5">
          <div className="relative flex-1 group">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-fg/25 group-focus-within:text-accent transition-colors" />
            <input
              value={search}
              onChange={event => setSearch(event.target.value)}
              placeholder="Поиск по артикулу, названию или исполнению..."
              className="w-full bg-surface/30 border border-tint/30 rounded-2xl pl-12 pr-4 py-4 outline-none focus:border-accent/50 transition-all text-fg"
            />
          </div>
          <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
            <div className="flex items-center gap-2 bg-surface/30 border border-tint/30 rounded-2xl px-3 py-2">
              <SlidersHorizontal className="w-4 h-4 text-accent/60" />
              <select value={group} onChange={event => setGroup(event.target.value as typeof group)}
                aria-label="Тип детали"
                className="bg-transparent outline-none text-sm font-bold text-fg min-w-[160px]">
                <option value="Все">Все типы деталей</option>
                {GROUPS.map(item => <option key={item} value={item}>{item}</option>)}
              </select>
            </div>
            <div className="flex items-center gap-2 bg-surface/30 border border-tint/30 rounded-2xl px-3 py-2">
              <Package className="w-4 h-4 text-accent/60" />
              <select value={systemGroup} onChange={event => setSystemGroup(event.target.value as typeof systemGroup)}
                aria-label="Тип секции"
                className="bg-transparent outline-none text-sm font-bold text-fg min-w-[160px]">
                <option value="Все">Все типы секций</option>
                {SYSTEM_GROUPS.map(item => <option key={item.code} value={item.code}>{item.label}</option>)}
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
        </div>}

        {activeCatalogTab === 'markups' && <section className="mx-auto mb-5 w-full max-w-5xl rounded-2xl border border-tint/25 bg-surface/30 p-5 sm:p-6">
          <div className="mb-5 flex items-start gap-3 border-b border-tint/20 pb-4">
            <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-accent/15 text-accent">
              <BadgePercent className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold">Наценка на конструкцию</h2>
              <p className="mt-1 text-sm text-fg/45">Общее значение применяется ко всем позициям выбранной системы.</p>
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {SYSTEM_GROUPS.map(systemGroup => {
              const state = systemMarkups.find(row => row.code === systemGroup.code);
              return (
                <div key={systemGroup.code} className="flex min-w-0 items-center gap-3 rounded-xl border border-tint/25 bg-hi/[0.025] p-3">
                  <div className="min-w-0 flex-1 px-1">
                    <div className="truncate text-sm font-bold">{systemGroup.label}</div>
                    {state?.mixed && <div className="text-[10px] text-amber-300">Разные значения</div>}
                  </div>
                  <div className="relative w-28 flex-shrink-0">
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={systemMarkupDrafts[systemGroup.code]}
                      placeholder={state?.mixed ? 'Разные' : '0'}
                      onChange={event => setSystemMarkupDrafts(current => ({ ...current, [systemGroup.code]: event.target.value }))}
                      className="h-10 w-full rounded-lg border border-tint/30 bg-page/40 px-3 pr-7 font-mono text-sm outline-none focus:border-accent/60"
                    />
                    <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[10px] text-fg/35">%</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleSystemMarkupSave(systemGroup.code)}
                    disabled={savingSystemGroup === systemGroup.code}
                    className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-primary text-white transition-colors hover:bg-primary-h disabled:opacity-50"
                    title={`Сохранить наценку ${systemGroup.label}`}
                  >
                    <Save className="h-4 w-4" />
                  </button>
                </div>
              );
            })}
          </div>
        </section>}

        {activeCatalogTab === 'items' && <div className="mx-auto w-full max-w-6xl overflow-hidden rounded-[2rem] border border-tint/25 bg-surface/30 shadow-2xl backdrop-blur-xl">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1080px] table-fixed border-collapse text-left">
              <colgroup>
                <col className="w-[8%]" />
                <col className="w-[31%]" />
                <col className="w-[11%]" />
                <col className="w-[10%]" />
                <col className="w-[9%]" />
                <col className="w-[10%]" />
                <col className="w-[8%]" />
                <col className="w-[7%]" />
                <col className="w-[6%]" />
              </colgroup>
              <thead>
                <tr className="border-b border-tint/20 bg-hi/[0.03]">
                  <th className="px-2.5 py-3.5 text-[10px] font-bold uppercase tracking-wider text-fg/45">Артикул</th>
                  <th className="px-2.5 py-3.5 text-[10px] font-bold uppercase tracking-wider text-fg/45">Позиция</th>
                  <th className="px-2.5 py-3.5 text-[10px] font-bold uppercase tracking-wider text-fg/45">Группа</th>
                  <th className="px-2.5 py-3.5 text-[10px] font-bold uppercase tracking-wider text-fg/45">Закупка</th>
                  <th className="px-2.5 py-3.5 text-[10px] font-bold uppercase tracking-wider text-fg/45">Наценка</th>
                  <th className="px-2.5 py-3.5 text-[10px] font-bold uppercase tracking-wider text-fg/45">Продажа</th>
                  <th className="px-2.5 py-3.5 text-[10px] font-bold uppercase tracking-wider text-fg/45">Вес</th>
                  <th className="px-2.5 py-3.5 text-[10px] font-bold uppercase tracking-wider text-fg/45">Отход</th>
                  <th className="px-2.5 py-3.5 text-right text-[10px] font-bold uppercase tracking-wider text-fg/45">Действия</th>
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="py-20 text-center">
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
                    <td className="break-words px-2.5 py-3 font-mono text-sm font-bold text-accent">{item.sku}</td>
                    <td className="px-2.5 py-3">
                      <div className="flex min-w-0 items-center gap-3">
                        <div className="flex h-14 w-16 flex-shrink-0 items-center justify-center overflow-hidden rounded-xl border border-tint/20 bg-white p-1">
                          {item.imageFile ? (
                            <img src={profileAssetUrl(item.imageFile)} alt={item.sku} className="max-w-full max-h-full object-contain" />
                          ) : (
                            <ImageIcon className="w-5 h-5 text-black/25" />
                          )}
                        </div>
                        <div className="min-w-0">
                          <div className="text-sm font-bold leading-snug text-fg">{item.name}</div>
                          <div className="mt-0.5 truncate text-[10px] text-fg/35">
                            {(item.systemGroups || []).map(code => SYSTEM_GROUPS.find(row => row.code === code)?.label).filter(Boolean).join(' · ') || 'Без группы'}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="px-2.5 py-3">
                      <span className={`inline-flex max-w-full items-center rounded-full border px-2 py-1 text-[10px] font-bold ${GROUP_COLORS[item.group]}`}>
                        {item.group}
                      </span>
                    </td>
                    <td className="px-2.5 py-3 font-mono text-sm">{formatPriceRange(pricingCosts(item))}</td>
                    <td className="px-2.5 py-3 font-mono text-sm text-amber-400">{percentRange(item, 'profileMarkupPercent')}</td>
                    <td className="px-2.5 py-3 font-mono text-sm text-emerald-400">{priceRange(item, (_item, variant) => profileSale(variant))}</td>
                    <td className="px-2.5 py-3 font-mono text-sm text-fg/65">{item.weight}</td>
                    <td className="px-2.5 py-3 font-mono text-sm text-fg/65">{item.wastePercent}%</td>
                    <td className="px-1.5 py-3 text-right">
                      <div className="flex items-center justify-end gap-1">
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
        </div>}
      </main>

      <AnimatePresence>
        {draft && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => setDraft(null)} className="absolute inset-0 bg-black/75 backdrop-blur-sm" />
            <motion.div initial={{ scale: 0.94, opacity: 0, y: 20 }} animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.94, opacity: 0, y: 20 }}
              className="relative z-10 flex max-h-[95vh] w-full max-w-6xl flex-col overflow-hidden rounded-[2rem] border border-tint/40 bg-modal shadow-2xl">
              <button onClick={() => setDraft(null)} className="absolute right-6 top-6 z-10 text-fg/30 hover:text-fg transition-colors">
                <X className="w-6 h-6" />
              </button>

              <div className="flex items-center gap-3 border-b border-tint/20 px-6 py-5 pr-16 sm:px-8">
                <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-tint/40 bg-tint/25">
                  <Package className="w-5 h-5 text-accent" />
                </div>
                <div className="min-w-0">
                  <h2 className="text-xl font-bold">Позиция каталога</h2>
                  <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-fg/40">
                    <span>{draft.sku || 'Новая позиция'}</span>
                    <span className="font-mono font-bold text-emerald-300">{priceRange(draft, (_item, variant) => profileSale(variant))}</span>
                  </div>
                </div>
              </div>

              <div className="custom-scrollbar overflow-y-auto px-6 py-5 sm:px-8">
                <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_240px]">
                  <div className="space-y-4">
                    <div className="grid gap-4 sm:grid-cols-[180px_minmax(0,1fr)]">
                      <div className="space-y-2">
                        <label className="ml-1 text-[10px] font-bold uppercase tracking-widest text-accent/45">Артикул</label>
                        <input value={draft.sku} onChange={event => setDraft({ ...draft, sku: event.target.value })}
                          className={`${INPUT_CLS} font-mono`} placeholder="RS112" />
                      </div>
                      <div className="space-y-2">
                        <label className="ml-1 text-[10px] font-bold uppercase tracking-widest text-accent/45">Название</label>
                        <input value={draft.name} onChange={event => setDraft({ ...draft, name: event.target.value })}
                          className={INPUT_CLS} placeholder="Ручка-профиль" />
                      </div>
                    </div>

                    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                      <div className="space-y-2">
                        <label className="ml-1 text-[10px] font-bold uppercase tracking-widest text-accent/45">Группа</label>
                        <select value={draft.group} onChange={event => setDraft({ ...draft, group: event.target.value as HardwareGroup })}
                          className={SELECT_CLS}>
                          {GROUPS.map(item => <option key={item} value={item}>{item}</option>)}
                        </select>
                      </div>
                      <div className="space-y-2">
                        <label className="ml-1 text-[10px] font-bold uppercase tracking-widest text-accent/45">Единица</label>
                        <select value={draft.unit} onChange={event => setDraft({ ...draft, unit: event.target.value as CatalogUnit })}
                          className={SELECT_CLS}>
                          {UNITS.map(item => <option key={item} value={item}>{item}</option>)}
                        </select>
                      </div>
                      <NumberInput label="Ширина" value={draft.sectionWidthMm} suffix="мм" onChange={value => setDraft({ ...draft, sectionWidthMm: value })} />
                      <NumberInput label="Высота" value={draft.sectionHeightMm} suffix="мм" onChange={value => setDraft({ ...draft, sectionHeightMm: value })} />
                    </div>

                    <div className="flex flex-wrap items-center gap-2 rounded-xl border border-tint/20 bg-hi/[0.025] px-3 py-2.5">
                      <span className="mr-1 text-[9px] font-bold uppercase tracking-wider text-fg/35">Системы</span>
                      {(draft.systemGroups || []).map(code => (
                        <span key={code} className="rounded-lg bg-accent/10 px-2.5 py-1 text-[10px] font-bold text-accent/80">
                          {SYSTEM_GROUPS.find(row => row.code === code)?.label}
                        </span>
                      ))}
                    </div>

                    <div className="grid gap-4 sm:grid-cols-2">
                      <NumberInput label="Вес на единицу" value={draft.weight} suffix="кг" onChange={value => setDraft({ ...draft, weight: value })} />
                      {!['шт', 'компл.'].includes(draft.unit) && (
                        <NumberInput label="Наценка на отходы" value={draft.wastePercent} suffix="%" onChange={value => setDraft({ ...draft, wastePercent: value })} />
                      )}
                    </div>
                  </div>

                  <div className="rounded-2xl border border-tint/25 bg-hi/[0.035] p-3">
                    <div className="mb-2 flex items-center justify-between">
                      <span className="text-[9px] font-bold uppercase tracking-widest text-fg/35">Сечение</span>
                      <ImageIcon className="h-3.5 w-3.5 text-accent/55" />
                    </div>
                    <div className="flex h-44 items-center justify-center overflow-hidden rounded-xl bg-white p-3">
                      {draft.imageFile ? (
                        <img src={profileAssetUrl(draft.imageFile)} alt={draft.sku || 'Сечение'} className="max-w-full max-h-full object-contain" />
                      ) : (
                        <ImageIcon className="w-10 h-10 text-black/20" />
                      )}
                    </div>
                  </div>
                </div>

                <section className="mt-6">
                  <h3 className="mb-3 text-sm font-bold">Цены по исполнениям</h3>
                  <div className="space-y-2">
                    {(draft.finishVariants || []).map((variant, index) => (
                      <div key={variant.code} className="grid gap-3 rounded-2xl border border-tint/25 bg-hi/[0.025] p-3 sm:grid-cols-2 lg:grid-cols-[130px_repeat(5,minmax(0,1fr))] lg:items-end">
                        <div className="flex min-h-11 items-center text-sm font-bold sm:col-span-2 lg:col-span-1">
                          {FINISHES[variant.code].name}
                        </div>
                        {([
                          ['cost', 'Себестоимость', variant.cost ?? 0, '₽'],
                          ['profileMarkupPercent', 'Наценка профиль', variant.profileMarkupPercent, '%'],
                          ['profileDiscountPercent', 'Скидка профиль', variant.profileDiscountPercent, '%'],
                          ['constructionMarkupPercent', 'Наценка конструкция', variant.constructionMarkupPercent, '%'],
                          ['constructionDiscountPercent', 'Скидка конструкция', variant.constructionDiscountPercent, '%'],
                        ] as const).map(([field, label, value, suffix]) => (
                          <div key={field} className="min-w-0">
                            <PriceField
                              label={label}
                              value={value}
                              suffix={suffix}
                              max={field.includes('Discount') ? 100 : undefined}
                              onChange={nextValue => setDraft({
                                ...draft,
                                finishVariants: (draft.finishVariants || []).map((row, rowIndex) => rowIndex === index ? { ...row, [field]: nextValue } : row),
                              })}
                            />
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                </section>

                <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  <div className="grid grid-cols-3 gap-2 sm:col-span-2 lg:col-span-3">
                    {[
                      { label: 'Цена профиля', value: priceRange(draft, (_item, variant) => profileSale(variant)), icon: BadgePercent },
                      { label: 'С отходами', value: priceRange(draft, costWithWaste), icon: Ruler },
                      { label: 'Цена в конструкции', value: priceRange(draft, constructionPrice), icon: Scale },
                    ].map(card => (
                      <div key={card.label} className="rounded-xl border border-tint/25 bg-hi/[0.04] p-3">
                        <div className="mb-1.5 flex items-center justify-between gap-2">
                          <span className="text-[9px] font-bold uppercase leading-tight tracking-wider text-fg/35">{card.label}</span>
                          <card.icon className="w-3.5 h-3.5 text-accent/55" />
                        </div>
                        <div className="font-mono text-xs font-bold text-fg/80">{card.value}</div>
                      </div>
                    ))}
                  </div>

                  <button onClick={() => setDraft({ ...draft, isActive: !draft.isActive })}
                    className={`flex min-h-16 w-full items-center justify-between rounded-xl border px-4 py-3 transition-all ${
                      draft.isActive ? 'bg-emerald-500/10 border-emerald-500/25 text-emerald-300' : 'bg-hi/5 border-tint/25 text-fg/45'
                    }`}>
                    <span className="text-xs font-bold">{draft.isActive ? 'Позиция активна' : 'Позиция в архиве'}</span>
                    <span className={`w-12 h-6 rounded-full transition-colors relative ${draft.isActive ? 'bg-emerald-500' : 'bg-hi/15'}`}>
                      <span className={`absolute top-1 w-4 h-4 rounded-full bg-hi shadow transition-transform ${draft.isActive ? 'translate-x-7' : 'translate-x-1'}`} />
                    </span>
                  </button>
                </div>
              </div>

              <div className="flex gap-3 border-t border-tint/20 bg-modal px-6 py-4 sm:justify-end sm:px-8">
                <button onClick={() => setDraft(null)}
                  className="flex-1 rounded-xl bg-hi/5 px-6 py-3 font-bold transition-all hover:bg-hi/10 sm:flex-none">Отмена</button>
                <button onClick={handleSave}
                  className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-primary px-8 py-3 font-bold text-white shadow-lg shadow-primary/20 transition-all hover:bg-primary-h sm:flex-none">
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
