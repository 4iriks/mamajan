import type { Section } from './types';

export interface SlideLayoutPreset {
  id: string;
  title: string;
  updates: Partial<Section>;
  match: Partial<Section>;
}

export interface SlideHardwarePreset {
  id: string;
  title: string;
  description: string;
  updates: Partial<Section>;
}

const ONE_ROW_COMMON: Partial<Section> = {
  slideRows: 1,
  threshold: 'Стандартный окраш',
  interGlassProfile: 'Алюминиевый RS2061',
  firstPanelInside: 'Справа',
  unusedTrack: undefined,
  cornerLeft: false,
  cornerRight: false,
  profileLeftWall: true,
  profileLeftLockBar: true,
  profileLeftPBar: false,
  profileLeftHandleBar: true,
  profileLeftBubble: false,
  profileRightWall: true,
  profileRightLockBar: true,
  profileRightPBar: false,
  profileRightHandleBar: true,
  profileRightBubble: false,
  lockLeft: 'ЗАМОК-ЗАЩЕЛКА 1стор RS3018',
  lockRight: 'ЗАМОК-ЗАЩЕЛКА 1стор RS3018',
  handleLeft: undefined,
  handleRight: undefined,
  floorLatchesLeft: false,
  floorLatchesRight: false,
  centerHandle: undefined,
  centerLock: undefined,
  centerHandleOffset: undefined,
  centerFloorLatchesLeft: false,
  centerFloorLatchesRight: false,
};

const TWO_ROW_COMMON: Partial<Section> = {
  slideRows: 2,
  threshold: 'Стандартный окраш',
  interGlassProfile: 'Алюминиевый RS2061',
  firstPanelInside: undefined,
  unusedTrack: 'Внешний',
  cornerLeft: false,
  cornerRight: false,
  profileLeftWall: true,
  profileLeftLockBar: false,
  profileLeftPBar: true,
  profileLeftHandleBar: false,
  profileLeftBubble: true,
  profileRightWall: true,
  profileRightLockBar: false,
  profileRightPBar: true,
  profileRightHandleBar: false,
  profileRightBubble: true,
  lockLeft: undefined,
  lockRight: undefined,
  handleLeft: 'Без ручки (глухая)',
  handleRight: 'Без ручки (глухая)',
  handleOffsetLeft: undefined,
  handleOffsetRight: undefined,
  floorLatchesLeft: false,
  floorLatchesRight: false,
};

function layout(
  id: string,
  width: number,
  panels: number,
  rails: 3 | 5,
  common: Partial<Section>,
): SlideLayoutPreset {
  const geometry: Partial<Section> = {
    width,
    height: 3000,
    panels,
    rails,
    slideRows: common.slideRows,
  };
  return {
    id,
    title: `${panels} пан. · ${rails} ${rails === 5 ? 'рельсов' : 'рельса'}`,
    match: geometry,
    updates: { ...common, ...geometry },
  };
}

export const SLIDE_ONE_ROW_LAYOUTS: SlideLayoutPreset[] = [
  layout('one-2-3', 2000, 2, 3, ONE_ROW_COMMON),
  layout('one-3-3', 3000, 3, 3, ONE_ROW_COMMON),
  layout('one-4-5', 4000, 4, 5, ONE_ROW_COMMON),
  layout('one-5-5', 5000, 5, 5, ONE_ROW_COMMON),
];

export const SLIDE_TWO_ROW_LAYOUTS: SlideLayoutPreset[] = [
  layout('two-4-3', 3500, 4, 3, TWO_ROW_COMMON),
  layout('two-6-3', 5000, 6, 3, TWO_ROW_COMMON),
  layout('two-8-5', 5000, 8, 5, TWO_ROW_COMMON),
  layout('two-10-5', 7000, 10, 5, TWO_ROW_COMMON),
];

export const SLIDE_HARDWARE_PRESETS: SlideHardwarePreset[] = [
  {
    id: 'knob-floor',
    title: 'Кноб + защёлки',
    description: 'RS3014 · защёлки в пол',
    updates: {
      centerHandle: 'Ручка-кноб RS3014',
      centerLock: undefined,
      centerHandleOffset: undefined,
      centerFloorLatchesLeft: true,
      centerFloorLatchesRight: true,
    },
  },
  {
    id: 'brace-lock',
    title: 'Скоба + замок',
    description: 'RS30201 · стекло–стекло',
    updates: {
      centerHandle: 'Ручка-скоба 600мм RS30201',
      centerLock: 'Замок стекло-стекло RS30301',
      centerHandleOffset: undefined,
      centerFloorLatchesLeft: false,
      centerFloorLatchesRight: false,
    },
  },
  {
    id: 'rs112-floor',
    title: 'Ручка-профиль',
    description: 'RS112 · защёлки в пол',
    updates: {
      centerHandle: 'Ручки-профиль RS112 (2шт)',
      centerLock: undefined,
      centerHandleOffset: undefined,
      centerFloorLatchesLeft: true,
      centerFloorLatchesRight: true,
    },
  },
];

export function sectionMatches(
  section: Section,
  expected: Partial<Section>,
): boolean {
  return (Object.keys(expected) as Array<keyof Section>).every(
    key => section[key] === expected[key],
  );
}

export function slideLayoutUpdates(
  section: Section,
  preset: SlideLayoutPreset,
): Partial<Section> {
  if (preset.updates.slideRows !== 2) return preset.updates;
  const hardware = SLIDE_HARDWARE_PRESETS.find(item =>
    sectionMatches(section, item.updates),
  ) ?? SLIDE_HARDWARE_PRESETS[0];
  return { ...preset.updates, ...hardware.updates };
}
