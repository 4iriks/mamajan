export const DEFAULT_GLASS_TYPE = '10ММ ПРОЗРАЧНОЕ';

export const SLIDE_GLASS_TYPE_OPTIONS = [
  DEFAULT_GLASS_TYPE,
  '10ММ БРОНЗА В МАССЕ',
  '10ММ СЕРОЕ В МАССЕ',
  '10ММ МАТОВОЕ',
  '10ММ ПРОСВЕТЛЕННОЕ',
  'ТРИПЛЕКС 4.1.4',
] as const;

const LEGACY_GLASS_TYPE_OPTIONS = [
  '10ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ',
  '10ММ ЗАКАЛЕННОЕ МАТОВОЕ',
  '8ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ',
  '8ММ ЗАКАЛЕННОЕ МАТОВОЕ',
  '6ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ',
  '6ММ ЗАКАЛЕННОЕ МАТОВОЕ',
] as const;

export function glassTypeOptions(system: string): readonly string[] {
  return system === 'СЛАЙД'
    ? SLIDE_GLASS_TYPE_OPTIONS
    : LEGACY_GLASS_TYPE_OPTIONS;
}
