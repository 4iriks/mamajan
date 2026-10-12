import rules from '../../../backend/engine/slide_side_segments.json';
import type { Section } from './types';

export function slideSideSegments(section: Section, side: 'left' | 'right') {
  const prefix = side === 'left' ? 'profileLeft' : 'profileRight';
  const selected = (flag: string) => Boolean(section[`${prefix}${flag.split('_').map(word => word[0].toUpperCase() + word.slice(1)).join('')}` as keyof Section]);
  let offset = 0;
  return rules.flatMap(rule => {
    if (!selected(rule.flag) || rule.unless?.some(selected)) return [];
    const width_mm = rule.with_handle_mm && selected('handle_bar') ? rule.with_handle_mm : rule.width_mm;
    const segment = { role: rule.role, width_mm, offset_mm: offset };
    offset += width_mm;
    return [segment];
  });
}
