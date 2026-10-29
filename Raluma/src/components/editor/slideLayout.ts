import type { Section } from './types';

export function firstPanelsPlacement(section: Pick<Section, 'firstPanelsPlacement' | 'unusedTrack'>): 'center' | 'outside' {
  return section.firstPanelsPlacement ?? ((section.unusedTrack || 'Внешний') === 'Внешний' ? 'center' : 'outside');
}

export function twoRowLayout(section: Section) {
  const count = Math.max(4, section.panels);
  const half = Math.floor(count / 2);
  const rails = section.rails ?? 3;
  const active = Math.min(rails, half);
  const start = (section.unusedTrack || 'Внешний') === 'Внешний' ? rails - active : 0;
  const left = Array.from({ length: half }, (_, index) => start + Math.min(index, active - 1));
  const inCenter = firstPanelsPlacement(section) === 'center';
  if (!inCenter) left.reverse();
  return {
    rails: [...left, ...left.slice().reverse()],
    numbers: Array.from({ length: count }, (_, index) => inCenter
      ? (index < half ? half - index : index - half + 1)
      : (index < half ? index + 1 : count - index)),
  };
}
