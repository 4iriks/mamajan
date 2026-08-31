export const SLIDE_GLASS_TYPE_OPTIONS = [
  '10ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ',
  '10ММ ЗАКАЛЕННОЕ БРОНЗА В МАССЕ',
  '10ММ ЗАКАЛЕННОЕ СЕРОЕ В МАССЕ',
  '10ММ ЗАКАЛЕННОЕ МАТОВОЕ',
  '10ММ ЗАКАЛЕННОЕ ПРОСВЕТЛЕННОЕ',
  'ТРИПЛЕКС 4.1.4 ЗАКАЛЕННЫЙ',
] as const;

export const SLIDE_DEFAULT_GLASS_TYPE = SLIDE_GLASS_TYPE_OPTIONS[0];
export const BOOK_GLASS_TYPE_OPTIONS = SLIDE_GLASS_TYPE_OPTIONS.slice(0, 5);
export const BOOK_DEFAULT_GLASS_TYPE = BOOK_GLASS_TYPE_OPTIONS[0];
export const LEGACY_DEFAULT_GLASS_TYPE = '10ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ';

const SLIDE_GLASS_ALIASES: Readonly<Record<string, string>> = {
  '10ММ ПРОЗРАЧНОЕ': SLIDE_GLASS_TYPE_OPTIONS[0],
  '10ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ': SLIDE_GLASS_TYPE_OPTIONS[0],
  '10ММ БРОНЗА В МАССЕ': SLIDE_GLASS_TYPE_OPTIONS[1],
  '10ММ ЗАКАЛЕННОЕ БРОНЗА В МАССЕ': SLIDE_GLASS_TYPE_OPTIONS[1],
  '10ММ СЕРОЕ В МАССЕ': SLIDE_GLASS_TYPE_OPTIONS[2],
  '10ММ ЗАКАЛЕННОЕ СЕРОЕ В МАССЕ': SLIDE_GLASS_TYPE_OPTIONS[2],
  '10ММ МАТОВОЕ': SLIDE_GLASS_TYPE_OPTIONS[3],
  '10ММ ЗАКАЛЕННОЕ МАТОВОЕ': SLIDE_GLASS_TYPE_OPTIONS[3],
  '10ММ ПРОСВЕТЛЕННОЕ': SLIDE_GLASS_TYPE_OPTIONS[4],
  '10ММ ЗАКАЛЕННОЕ ПРОСВЕТЛЕННОЕ': SLIDE_GLASS_TYPE_OPTIONS[4],
  'ТРИПЛЕКС 4.1.4': SLIDE_GLASS_TYPE_OPTIONS[5],
  'ТРИПЛЕКС 4.1.4 ЗАКАЛЕННЫЙ': SLIDE_GLASS_TYPE_OPTIONS[5],
};

export function normalizeSlideGlassType(value: string | null | undefined): string {
  const text = (value ?? '')
    .trim()
    .toLocaleUpperCase('ru-RU')
    .replace(/Ё/g, 'Е')
    .replace(/\s+/g, ' ');
  if (!text) return SLIDE_DEFAULT_GLASS_TYPE;
  if (SLIDE_GLASS_ALIASES[text]) return SLIDE_GLASS_ALIASES[text];
  if (/\bЗАКАЛЕНН[А-ЯA-Z]*\b/i.test(text)) return text;
  if (text.startsWith('ТРИПЛЕКС')) return `${text} ЗАКАЛЕННЫЙ`;
  const thickness = text.match(/^(.*?\b\d+(?:[.,]\d+)?\s*ММ)\b(.*)$/i);
  if (thickness) return `${thickness[1]} ЗАКАЛЕННОЕ${thickness[2]}`.replace(/\s+/g, ' ').trim();
  return `ЗАКАЛЕННОЕ ${text}`;
}

export function normalizeGlassType(
  value: string | null | undefined,
  system: string,
): string {
  if (system === 'СЛАЙД' || system === 'КНИЖКА') return normalizeSlideGlassType(value);
  return value?.trim() || LEGACY_DEFAULT_GLASS_TYPE;
}

export const GLASS_FILL_COLORS = {
  clear: '#dceff3',
  bronze: '#e4c39f',
  gray: '#c9d0d3',
  matte: '#e5e8e7',
  clarified: '#eefaf8',
  triplex: '#d3eadb',
} as const;

const LEGACY_GLASS_TYPE_OPTIONS = [
  LEGACY_DEFAULT_GLASS_TYPE,
  '10ММ ЗАКАЛЕННОЕ МАТОВОЕ',
  '8ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ',
  '8ММ ЗАКАЛЕННОЕ МАТОВОЕ',
  '6ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ',
  '6ММ ЗАКАЛЕННОЕ МАТОВОЕ',
] as const;

export function glassFillColor(glassType: string | null | undefined): string {
  const normalized = (glassType ?? '').toLocaleUpperCase('ru-RU');
  if (normalized.includes('БРОНЗ')) return GLASS_FILL_COLORS.bronze;
  if (normalized.includes('СЕРО')) return GLASS_FILL_COLORS.gray;
  if (normalized.includes('МАТ')) return GLASS_FILL_COLORS.matte;
  if (normalized.includes('ПРОСВЕТ')) return GLASS_FILL_COLORS.clarified;
  if (normalized.includes('ТРИПЛЕКС')) return GLASS_FILL_COLORS.triplex;
  return GLASS_FILL_COLORS.clear;
}

export function diagramGlassFillColor(glassType: string | null | undefined): string {
  const normalized = (glassType ?? '').toLocaleUpperCase('ru-RU');
  if (normalized.includes('БРОНЗ')) return 'var(--diagram-glass-bronze)';
  if (normalized.includes('СЕРО')) return 'var(--diagram-glass-gray)';
  if (normalized.includes('МАТ')) return 'var(--diagram-glass-matte)';
  if (normalized.includes('ПРОСВЕТ')) return 'var(--diagram-glass-clarified)';
  if (normalized.includes('ТРИПЛЕКС')) return 'var(--diagram-glass-triplex)';
  return 'var(--diagram-glass-clear)';
}

export function isMatteGlass(glassType: string | null | undefined): boolean {
  return (glassType ?? '').toLocaleUpperCase('ru-RU').includes('МАТ');
}

export function glassTypeOptions(system: string): readonly string[] {
  if (system === 'СЛАЙД') return SLIDE_GLASS_TYPE_OPTIONS;
  if (system === 'КНИЖКА') return BOOK_GLASS_TYPE_OPTIONS;
  return LEGACY_GLASS_TYPE_OPTIONS;
}

export function defaultGlassType(system: string): string {
  if (system === 'СЛАЙД') return SLIDE_DEFAULT_GLASS_TYPE;
  if (system === 'КНИЖКА') return BOOK_DEFAULT_GLASS_TYPE;
  return LEGACY_DEFAULT_GLASS_TYPE;
}
