export type BookProfileSystem = 'B25' | 'B16' | 'B17' | 'C16' | 'C17';

export const BOOK_PROFILE_SYSTEMS: Array<{
  value: BookProfileSystem;
  label: string;
}> = [
  { value: 'B25', label: 'B25' },
  { value: 'B16', label: 'B16' },
  { value: 'B17', label: 'B17' },
  { value: 'C16', label: 'C16' },
  { value: 'C17', label: 'C17' },
];

const BOOK_SYSTEM_ALIASES: Record<string, BookProfileSystem> = {
  'В25': 'B25',
  'В16': 'B16',
  'В17': 'B17',
  'С16': 'C16',
  'С17': 'C17',
  // Первая версия формы сохраняла эти значения, но считала их как B25.
  'С КАРЕТКОЙ': 'B25',
  'БЕЗ КАРЕТКИ': 'B25',
};

export function normalizeBookSystem(value?: string): BookProfileSystem {
  const raw = (value || '').trim().toUpperCase().replaceAll('Ё', 'Е');
  if (!raw) return 'B25';
  if (BOOK_PROFILE_SYSTEMS.some(item => item.value === raw)) {
    return raw as BookProfileSystem;
  }
  return BOOK_SYSTEM_ALIASES[raw] || 'B25';
}

export function bookExtraDoorPanelOptions({
  panelCount,
  doorLayout,
  extraFixedEnabled,
  extraFixedSide,
}: {
  panelCount: number;
  doorLayout?: string;
  extraFixedEnabled?: boolean;
  extraFixedSide?: string;
}): number[] {
  const physicalCount = panelCount + (extraFixedEnabled ? 1 : 0);
  const allPanels = Array.from({ length: physicalCount }, (_, index) => index + 1);
  const fixedPanel = extraFixedEnabled
    ? extraFixedSide === 'right' ? physicalCount : 1
    : undefined;
  const foldingPanels = allPanels.filter(number => number !== fixedPanel);
  const excluded = new Set<number>();
  if (fixedPanel) excluded.add(fixedPanel);
  if (doorLayout === 'left' || doorLayout === 'both') {
    if (foldingPanels[0]) excluded.add(foldingPanels[0]);
  }
  if (doorLayout === 'right' || doorLayout === 'both') {
    const last = foldingPanels.at(-1);
    if (last) excluded.add(last);
  }
  return allPanels.filter(number => !excluded.has(number));
}
