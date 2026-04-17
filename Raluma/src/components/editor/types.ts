// ── Types & constants for ProjectEditor ──────────────────────────────────────

export type SystemType = 'СЛАЙД' | 'КНИЖКА' | 'ЛИФТ' | 'ЦС' | 'КОМПЛЕКТАЦИЯ';

export interface Section {
  id: string;
  name: string;
  system: SystemType;
  width: number;
  height: number;
  panels: number;
  quantity: number;
  glassType: string;
  paintingType: 'RAL стандарт' | 'RAL нестандарт' | 'Анодированный';
  ralColor?: string;
  cornerLeft: boolean;
  cornerRight: boolean;
  externalWidth?: number;
  // СЛАЙД
  rails?: 3 | 5;
  threshold?: string;
  firstPanelInside?: string;
  unusedTrack?: string;
  interGlassProfile?: string;
  profileLeft?: string;
  profileRight?: string;
  lock?: string;
  handle?: string;
  floorLatchesLeft: boolean;
  floorLatchesRight: boolean;
  handleOffset?: number;
  handleOffsetLeft?: number;
  handleOffsetRight?: number;
  // СЛАЙД — профили
  profileLeftWall: boolean;
  profileLeftLockBar: boolean;
  profileLeftPBar: boolean;
  profileLeftHandleBar: boolean;
  profileLeftBubble: boolean;
  profileRightWall: boolean;
  profileRightLockBar: boolean;
  profileRightPBar: boolean;
  profileRightHandleBar: boolean;
  profileRightBubble: boolean;
  lockLeft?: string;
  lockRight?: string;
  // СЛАЙД 2 ряда
  slideRows?: number;
  centerHandle?: string;
  centerLock?: string;
  centerHandleOffset?: number;
  centerFloorLatchesLeft?: boolean;
  centerFloorLatchesRight?: boolean;
  bookSubtype?: string;
  handleLeft?: string;
  handleRight?: string;
  // КНИЖКА
  doors?: number;
  doorSide?: string;
  doorType?: string;
  doorOpening?: string;
  compensator?: string;
  angleLeft?: number;
  angleRight?: number;
  bookSystem?: string;
  // ДВЕРЬ / ЦС
  doorSystem?: string;
  csShape?: string;
  csWidth2?: number;
  // Примечания к секции
  extraParts?: string;
  comments?: string;
  documentOverrides?: string;
}

export interface OrderItem {
  id: string;
  name: string;
  invoice: string;
  paidDate: string;
  deliveredDate: string;
}

export interface ProjectEditorProps {
  projectId: number;
  onBack: () => void;
}

// ── Style constants ───────────────────────────────────────────────────────────

export const LBL = 'text-[10px] font-bold uppercase tracking-widest text-accent/40 ml-1';
export const INP = 'w-full bg-hi/8 border border-tint/30 rounded-xl px-3 py-2 outline-none focus:border-accent/50 transition-all font-mono text-fg text-sm';
export const SEL = 'w-full bg-hi/8 border border-tint/30 rounded-xl px-3 py-2 outline-none focus:border-accent/50 transition-all appearance-none text-fg text-sm';

// ── System colors ─────────────────────────────────────────────────────────────

export const SYSTEM_COLORS: Record<SystemType, string> = {
  'СЛАЙД':        'bg-blue-500/20 text-blue-300 border-blue-500/30',
  'КНИЖКА':       'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
  'ЛИФТ':         'bg-orange-500/20 text-orange-300 border-orange-500/30',
  'ЦС':           'bg-purple-500/20 text-purple-300 border-purple-500/30',
  'КОМПЛЕКТАЦИЯ': 'bg-rose-500/20 text-rose-300 border-rose-500/30',
};

export const SYSTEM_ACCENT_BG: Record<SystemType, string> = {
  'СЛАЙД':        'bg-blue-400',
  'КНИЖКА':       'bg-emerald-400',
  'ЛИФТ':         'bg-orange-400',
  'ЦС':           'bg-violet-400',
  'КОМПЛЕКТАЦИЯ': 'bg-rose-400',
};

export const SYSTEM_PICKER_COLORS: Record<SystemType, string> = {
  'СЛАЙД':        'bg-blue-500/10 border-blue-500/30 text-blue-300 hover:bg-blue-500/20',
  'КНИЖКА':       'bg-emerald-500/10 border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/20',
  'ЛИФТ':         'bg-orange-500/10 border-orange-500/30 text-orange-300 hover:bg-orange-500/20',
  'ЦС':           'bg-purple-500/10 border-purple-500/30 text-purple-300 hover:bg-purple-500/20',
  'КОМПЛЕКТАЦИЯ': 'bg-rose-500/10 border-rose-500/30 text-rose-300 hover:bg-rose-500/20',
};
