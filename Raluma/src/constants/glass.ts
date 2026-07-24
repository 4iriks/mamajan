export const SLIDE_DEFAULT_GLASS_TYPE = '10ММ ПРОЗРАЧНОЕ';
export const LEGACY_DEFAULT_GLASS_TYPE = '10ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ';

export const SLIDE_GLASS_TYPE_OPTIONS = [
  SLIDE_DEFAULT_GLASS_TYPE,
  '10ММ БРОНЗА В МАССЕ',
  '10ММ СЕРОЕ В МАССЕ',
  '10ММ МАТОВОЕ',
  '10ММ ПРОСВЕТЛЕННОЕ',
  'ТРИПЛЕКС 4.1.4',
] as const;

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

export function isMatteGlass(glassType: string | null | undefined): boolean {
  return (glassType ?? '').toLocaleUpperCase('ru-RU').includes('МАТ');
}

export function glassTypeOptions(system: string): readonly string[] {
  return system === 'СЛАЙД'
    ? SLIDE_GLASS_TYPE_OPTIONS
    : LEGACY_GLASS_TYPE_OPTIONS;
}

export function defaultGlassType(system: string): string {
  return system === 'СЛАЙД'
    ? SLIDE_DEFAULT_GLASS_TYPE
    : LEGACY_DEFAULT_GLASS_TYPE;
}
