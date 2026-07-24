export const LIFT_DEFAULT_FILLING = 'СТЕКЛО 8мм ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ';
export const LIFT_DEFAULT_CONTROL = 'Пульт ДУ';
export const LIFT_DEFAULT_CABLE_SIDE = 'Справа';
export const LIFT_DEFAULT_OPENING = 'Сдвиг вниз';
export const LIFT_SPLIT_OPENING = 'Верх/низ глухие, сдвиг вниз';

export const LIFT_FILLING_OPTIONS = [
  LIFT_DEFAULT_FILLING,
  'СТЕКЛО 8мм ЗАКАЛЕННОЕ ПРОСВЕТЛЕННОЕ',
  'СТЕКЛО 8мм ЗАКАЛЕННОЕ БРОНЗА В МАССЕ',
  'СТЕКЛО 8мм ЗАКАЛЕННОЕ СЕРОЕ В МАССЕ',
  'СТЕКЛО 8мм ЗАКАЛЕННОЕ МАТОВОЕ',
  'СТЕКЛОПАКЕТ 20мм (6зак-8-6зак)',
  'ДРУГОЕ 8мм',
  'ДРУГОЕ 20мм',
] as const;

export function liftOpeningOptions(panels: number): string[] {
  return panels === 4
    ? ['Сдвиг вниз', 'Сдвиг вверх', LIFT_SPLIT_OPENING]
    : ['Сдвиг вниз', 'Сдвиг вверх'];
}
