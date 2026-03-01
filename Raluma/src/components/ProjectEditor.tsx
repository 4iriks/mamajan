/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useMemo, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ArrowLeft, Save, Plus, Trash2, FileText,
  ClipboardList, Square as WindowIcon, Palette,
  ChevronRight, Loader2, X, ArrowRight,
} from 'lucide-react';
import { getProject, updateProject, createSection, updateSection, deleteSection, SectionOut } from '../api/projects';
import { toast } from '../store/toastStore';

// ── Types ────────────────────────────────────────────────────────────────────

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
}

interface OrderItem {
  id: string;
  name: string;
  invoice: string;
  paidDate: string;
  deliveredDate: string;
}

interface ProjectEditorProps {
  projectId: number;
  onBack: () => void;
}

// ── Style constants ───────────────────────────────────────────────────────────

const LBL = 'text-[10px] font-bold uppercase tracking-widest text-[#4fd1c5]/40 ml-1';
const INP = 'w-full bg-white/8 border border-[#2a7a8a]/30 rounded-xl px-3 py-2 outline-none focus:border-[#4fd1c5]/50 transition-all font-mono text-white text-sm';
const SEL = 'w-full bg-white/8 border border-[#2a7a8a]/30 rounded-xl px-3 py-2 outline-none focus:border-[#4fd1c5]/50 transition-all appearance-none text-white text-sm';

// ── System colors ─────────────────────────────────────────────────────────────

const SYSTEM_COLORS: Record<SystemType, string> = {
  'СЛАЙД':  'bg-blue-500/20 text-blue-300 border-blue-500/30',
  'КНИЖКА': 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
  'ЛИФТ':   'bg-orange-500/20 text-orange-300 border-orange-500/30',
  'ЦС':     'bg-purple-500/20 text-purple-300 border-purple-500/30',
  'КОМПЛЕКТАЦИЯ': 'bg-rose-500/20 text-rose-300 border-rose-500/30',
};

const SYSTEM_PICKER_COLORS: Record<SystemType, string> = {
  'СЛАЙД':  'bg-blue-500/10 border-blue-500/30 text-blue-300 hover:bg-blue-500/20',
  'КНИЖКА': 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/20',
  'ЛИФТ':   'bg-orange-500/10 border-orange-500/30 text-orange-300 hover:bg-orange-500/20',
  'ЦС':     'bg-purple-500/10 border-purple-500/30 text-purple-300 hover:bg-purple-500/20',
  'КОМПЛЕКТАЦИЯ': 'bg-rose-500/10 border-rose-500/30 text-rose-300 hover:bg-rose-500/20',
};

// ── Converters ────────────────────────────────────────────────────────────────

function apiToLocal(s: SectionOut): Section {
  // Backwards compat: migrate legacy 'ДВЕРЬ' value
  const rawSystem = s.system === 'ДВЕРЬ' ? 'КОМПЛЕКТАЦИЯ' : s.system;
  return {
    id: String(s.id),
    name: s.name,
    system: (rawSystem as SystemType) || 'СЛАЙД',
    width: s.width,
    height: s.height,
    panels: s.panels,
    quantity: s.quantity,
    glassType: s.glass_type,
    paintingType: s.painting_type as Section['paintingType'],
    ralColor: s.ral_color,
    cornerLeft: s.corner_left,
    cornerRight: s.corner_right,
    externalWidth: s.external_width,
    rails: s.rails as 3 | 5 | undefined,
    threshold: s.threshold,
    firstPanelInside: s.first_panel_inside,
    unusedTrack: s.unused_track,
    interGlassProfile: s.inter_glass_profile,
    profileLeft: s.profile_left,
    profileRight: s.profile_right,
    lock: s.lock,
    handle: s.handle,
    floorLatchesLeft: s.floor_latches_left,
    floorLatchesRight: s.floor_latches_right,
    handleOffset: s.handle_offset,
    profileLeftWall: s.profile_left_wall ?? false,
    profileLeftLockBar: s.profile_left_lock_bar ?? false,
    profileLeftPBar: s.profile_left_p_bar ?? false,
    profileLeftHandleBar: s.profile_left_handle_bar ?? false,
    profileLeftBubble: s.profile_left_bubble ?? false,
    profileRightWall: s.profile_right_wall ?? false,
    profileRightLockBar: s.profile_right_lock_bar ?? false,
    profileRightPBar: s.profile_right_p_bar ?? false,
    profileRightHandleBar: s.profile_right_handle_bar ?? false,
    profileRightBubble: s.profile_right_bubble ?? false,
    lockLeft: s.lock_left,
    lockRight: s.lock_right,
    bookSubtype: s.book_subtype,
    handleLeft: s.handle_left,
    handleRight: s.handle_right,
    doors: s.doors,
    doorSide: s.door_side,
    doorType: s.door_type,
    doorOpening: s.door_opening,
    compensator: s.compensator,
    angleLeft: s.angle_left,
    angleRight: s.angle_right,
    bookSystem: s.book_system,
    doorSystem: s.door_system,
    csShape: s.cs_shape,
    csWidth2: s.cs_width2,
    extraParts: s.extra_parts,
    comments: s.comments,
  };
}

function localToApi(s: Section, order: number): Omit<SectionOut, 'id' | 'project_id'> {
  return {
    name: s.name, order,
    system: s.system,
    width: s.width, height: s.height, panels: s.panels, quantity: s.quantity,
    glass_type: s.glassType, painting_type: s.paintingType,
    ral_color: s.ralColor, corner_left: s.cornerLeft, corner_right: s.cornerRight,
    external_width: s.externalWidth,
    rails: s.rails, threshold: s.threshold, first_panel_inside: s.firstPanelInside,
    unused_track: s.unusedTrack, inter_glass_profile: s.interGlassProfile,
    profile_left: s.profileLeft, profile_right: s.profileRight,
    lock: s.lock, handle: s.handle,
    floor_latches_left: s.floorLatchesLeft, floor_latches_right: s.floorLatchesRight,
    handle_offset: s.handleOffset,
    profile_left_wall: s.profileLeftWall,
    profile_left_lock_bar: s.profileLeftLockBar,
    profile_left_p_bar: s.profileLeftPBar,
    profile_left_handle_bar: s.profileLeftHandleBar,
    profile_left_bubble: s.profileLeftBubble,
    profile_right_wall: s.profileRightWall,
    profile_right_lock_bar: s.profileRightLockBar,
    profile_right_p_bar: s.profileRightPBar,
    profile_right_handle_bar: s.profileRightHandleBar,
    profile_right_bubble: s.profileRightBubble,
    lock_left: s.lockLeft,
    lock_right: s.lockRight,
    book_subtype: s.bookSubtype,
    handle_left: s.handleLeft,
    handle_right: s.handleRight,
    doors: s.doors, door_side: s.doorSide, door_type: s.doorType,
    door_opening: s.doorOpening, compensator: s.compensator,
    angle_left: s.angleLeft, angle_right: s.angleRight, book_system: s.bookSystem,
    door_system: s.doorSystem, cs_shape: s.csShape, cs_width2: s.csWidth2,
    extra_parts: s.extraParts, comments: s.comments,
  };
}

// ── Checkbox helper ───────────────────────────────────────────────────────────

function Checkbox({ checked, onChange, label }: { checked: boolean; onChange: () => void; label: string }) {
  return (
    <label className="flex items-center gap-2 cursor-pointer" onClick={onChange}>
      <div className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-all flex-shrink-0 ${checked ? 'bg-[#4fd1c5] border-[#4fd1c5]' : 'border-[#2a7a8a]/40 bg-black/20'}`}>
        {checked && <div className="w-2.5 h-2.5 bg-[#0c1d2d] rounded-sm" />}
      </div>
      <span className="text-xs font-medium text-white/60">{label}</span>
    </label>
  );
}

// ── Toggle buttons ────────────────────────────────────────────────────────────

function ToggleGroup({ value, options, onChange }: { value?: string; options: string[]; onChange: (v: string) => void }) {
  return (
    <div className="flex gap-2 flex-wrap">
      {options.map(opt => (
        <button key={opt} onClick={() => onChange(opt)}
          className={`flex-1 py-1.5 rounded-xl border font-bold text-xs transition-all min-w-0 ${
            value === opt ? 'bg-[#4fd1c5]/10 border-[#4fd1c5]/50 text-[#4fd1c5]' : 'bg-black/10 border-[#2a7a8a]/20 text-white/40 hover:border-[#2a7a8a]/50'
          }`}
        >{opt}</button>
      ))}
    </div>
  );
}

// ── Radio list ────────────────────────────────────────────────────────────────

function RadioList({ value, options, onChange, noneLabel }: { value?: string; options: string[]; onChange: (v: string | undefined) => void; noneLabel?: string }) {
  const allOptions = noneLabel ? [noneLabel, ...options] : options;
  return (
    <div className="space-y-1.5">
      {allOptions.map(opt => {
        const isNone = opt === noneLabel;
        const active = isNone ? !value : value === opt;
        return (
          <button key={opt} onClick={() => onChange(isNone ? undefined : opt)}
            className={`w-full text-left px-3 py-1.5 rounded-xl border transition-all text-xs ${
              active ? 'bg-[#4fd1c5]/10 border-[#4fd1c5]/50 text-[#4fd1c5]' : 'border-[#2a7a8a]/20 bg-black/10 text-white/40 hover:border-[#4fd1c5]/30'
            }`}
          >{opt}</button>
        );
      })}
    </div>
  );
}

// ── Section card helpers ──────────────────────────────────────────────────────

function getSectionTypeLabel(s: Section): string {
  switch (s.system) {
    case 'СЛАЙД': {
      const rows = s.rails === 5 ? '2 ряда от центра' : '1 ряд';
      return `${rows} · ${s.panels ?? 3} пан.`;
    }
    case 'КНИЖКА': {
      const sub = s.bookSubtype === 'angle' ? 'с углом' : s.bookSubtype === 'doors_and_angle' ? 'с дв. и углом' : 'с дверями';
      return `${sub} · ${s.panels ?? 3} пан.`;
    }
    case 'ЛИФТ':
      return `${s.panels ?? 2} пан.`;
    case 'ЦС':
      return s.csShape || '';
    case 'КОМПЛЕКТАЦИЯ':
      return s.doorSystem || '';
    default:
      return '';
  }
}

function getSectionColorLabel(s: Section): string {
  if (s.paintingType === 'Анодированный') return 'Анод.';
  if (s.paintingType.includes('RAL')) return s.ralColor ? `RAL ${s.ralColor}` : 'RAL';
  return '';
}

// ── Section divider ───────────────────────────────────────────────────────────

function SectionDivider({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3 pt-1">
      <span className="text-[10px] font-bold uppercase tracking-widest text-[#4fd1c5]/40 whitespace-nowrap">{label}</span>
      <div className="flex-1 h-px bg-[#2a7a8a]/20" />
    </div>
  );
}

// ── Tab: Основное (общая для всех систем) ────────────────────────────────────

function MainTab({ s, update }: { s: Section; update: (u: Partial<Section>) => void }) {
  return (
    <div className="space-y-4">
      {/* Название / Кол-во / Ширина / Высота */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="col-span-2 sm:col-span-2 space-y-1.5">
          <label className={LBL}>Название</label>
          <input value={s.name} onChange={e => update({ name: e.target.value })} className={INP} />
        </div>
        <div className="space-y-1.5">
          <label className={LBL}>Кол-во, шт</label>
          <input type="number" min="1" value={s.quantity} onChange={e => update({ quantity: parseInt(e.target.value) || 1 })} className={INP} />
        </div>
        <div className="hidden sm:block" />
        <div className="space-y-1.5">
          <label className={LBL}>Ширина, мм</label>
          <input type="number" value={s.width} onChange={e => update({ width: parseInt(e.target.value) || 0 })} className={INP} />
        </div>
        <div className="space-y-1.5">
          <label className={LBL}>Высота, мм</label>
          <input type="number" value={s.height} onChange={e => update({ height: parseInt(e.target.value) || 0 })} className={INP} />
        </div>
      </div>
      {/* Стекло / Окрашивание */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <label className={LBL}>Стекло</label>
          <select value={s.glassType} onChange={e => update({ glassType: e.target.value })} className={SEL}>
            <option>10ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ</option>
            <option>10ММ ЗАКАЛЕННОЕ МАТОВОЕ</option>
            <option>8ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ</option>
            <option>8ММ ЗАКАЛЕННОЕ МАТОВОЕ</option>
            <option>6ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ</option>
            <option>6ММ ЗАКАЛЕННОЕ МАТОВОЕ</option>
          </select>
        </div>
        <div className="space-y-1.5">
          <label className={LBL}>Окрашивание</label>
          <div className="flex flex-wrap gap-1.5">
            {(['RAL стандарт', 'RAL нестандарт', 'Анодированный'] as const).map(type => (
              <button key={type} onClick={() => update({ paintingType: type })}
                className={`flex items-center gap-1.5 flex-1 min-w-max px-2.5 py-1.5 rounded-xl border transition-all justify-center text-xs font-medium ${
                  s.paintingType === type ? 'bg-[#4fd1c5]/10 border-[#4fd1c5]/50 text-[#4fd1c5]' : 'bg-black/10 border-[#2a7a8a]/20 text-white/40 hover:border-[#2a7a8a]/50'
                }`}
              >
                <div className={`w-3 h-3 rounded-full border flex items-center justify-center flex-shrink-0 ${s.paintingType === type ? 'border-[#4fd1c5]' : 'border-white/15'}`}>
                  {s.paintingType === type && <div className="w-1.5 h-1.5 rounded-full bg-[#4fd1c5]" />}
                </div>
                {type}
              </button>
            ))}
          </div>
          {s.paintingType.includes('RAL') && (
            <div className="mt-1.5 space-y-1">
              <label className={LBL}>Цвет RAL</label>
              <input type="text" value={s.ralColor || ''} onChange={e => update({ ralColor: e.target.value })} className={INP} placeholder="Напр. 9016" />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Tab: СЛАЙД — Система + Профили + Фурнитура ────────────────────────────────

function ProfileCheckbox({ checked, onChange, label, indent, disabled }: { checked: boolean; onChange: () => void; label: string; indent?: boolean; disabled?: boolean }) {
  return (
    <label className={`flex items-center gap-2 py-1 ${indent ? 'pl-5' : ''} ${disabled ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}`} onClick={disabled ? undefined : onChange}>
      <div className={`w-4 h-4 rounded border-2 flex items-center justify-center flex-shrink-0 transition-all ${checked ? 'bg-[#4fd1c5] border-[#4fd1c5]' : 'border-[#2a7a8a]/40 bg-black/20'}`}>
        {checked && <div className="w-2 h-2 bg-[#0c1d2d] rounded-sm" />}
      </div>
      <span className="text-xs text-white/60">{label}</span>
    </label>
  );
}

function SlideSystemTab({ s, update }: { s: Section; update: (u: Partial<Section>) => void }) {
  const showLockLeft  = (s.profileLeftLockBar  || s.profileLeftHandleBar)  && !(s.profileLeftPBar  && s.profileLeftHandleBar);
  const showNoLockLeft  = s.profileLeftPBar  && s.profileLeftHandleBar;
  const showHandleLeft  = (s.profileLeftPBar  && s.profileLeftBubble)  || (s.profileLeftBubble  && !s.profileLeftLockBar  && !s.profileLeftPBar  && !s.profileLeftHandleBar);
  const showLockRight = (s.profileRightLockBar || s.profileRightHandleBar) && !(s.profileRightPBar && s.profileRightHandleBar);
  const showNoLockRight = s.profileRightPBar && s.profileRightHandleBar;
  const showHandleRight = (s.profileRightPBar && s.profileRightBubble) || (s.profileRightBubble && !s.profileRightLockBar && !s.profileRightPBar && !s.profileRightHandleBar);

  return (
    <div className="space-y-4">
      {/* Рельсы / Панели / 1-я панель — одна строка */}
      <div className="flex gap-3">
        <div className="flex-1 space-y-1.5">
          <label className={LBL}>Рельсы</label>
          <ToggleGroup
            value={s.rails === 5 ? '5ти рельсовая' : '3х рельсовая'}
            options={['3х рельсовая', '5ти рельсовая']}
            onChange={v => update({ rails: v.startsWith('3') ? 3 : 5 })}
          />
        </div>
        <div className="w-[5.5rem] flex-shrink-0 space-y-1.5">
          <label className={LBL}>Панели</label>
          <select value={s.panels} onChange={e => update({ panels: parseInt(e.target.value) })} className={SEL}>
            {[1, 2, 3, 4, 5].map(n => <option key={n} value={n}>{n}</option>)}
          </select>
        </div>
        <div className="flex-1 space-y-1.5">
          <label className={LBL}>1-я панель</label>
          <ToggleGroup value={s.firstPanelInside} options={['Слева', 'Справа']}
            onChange={v => update({ firstPanelInside: v })} />
        </div>
      </div>

      {/* Порог / Межстекольный */}
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <label className={LBL}>Порог</label>
          <select value={s.threshold || ''} onChange={e => update({ threshold: e.target.value || undefined })} className={SEL}>
            <option value="">— Без порога —</option>
            <option>Стандартный анод</option>
            <option>Стандартный окраш</option>
            <option>Накладной анод</option>
            <option>Накладной окраш</option>
          </select>
          {!s.threshold && (
            <p className="text-[10px] text-amber-400/70 font-bold uppercase tracking-wider pl-1">⚠ Без порога</p>
          )}
        </div>
        <div className="space-y-1.5">
          <label className={LBL}>Межстекольный профиль</label>
          <select value={s.interGlassProfile || ''} onChange={e => update({ interGlassProfile: e.target.value || undefined })} className={SEL}>
            <option value="">— Без —</option>
            <option>Алюминиевый RS1061</option>
            <option>Прозрачный с фетром RS1006</option>
            <option>h-профиль RS1004</option>
          </select>
        </div>
      </div>

      {/* Неиспользуемый рельс (только если есть неиспользуемые) */}
      {((s.rails !== 5 && (s.panels ?? 3) < 3) || (s.rails === 5 && (s.panels ?? 3) < 5)) && (
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <label className={LBL}>Неиспользуемый рельс</label>
            <ToggleGroup value={s.unusedTrack ?? 'Внутренний'} options={['Внутренний', 'Внешний']}
              onChange={v => update({ unusedTrack: v })} />
          </div>
        </div>
      )}

      {/* Профили слева / справа */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {/* Профили слева */}
        <div className="space-y-2">
          <label className={LBL}>Профили слева</label>
          <div className="bg-black/10 border border-[#2a7a8a]/20 rounded-xl px-3 py-2">
            <ProfileCheckbox checked={s.profileLeftWall} onChange={() => update({ profileLeftWall: !s.profileLeftWall })} label="Пристеночный RS1333/1335" />
            <ProfileCheckbox checked={s.profileLeftLockBar} onChange={() => { if (!s.profileLeftLockBar) update({ profileLeftLockBar: true, profileLeftPBar: false, profileLeftHandleBar: true, profileLeftBubble: false }); else update({ profileLeftLockBar: false }); }} label="Боковой профиль-замок RS1081" indent />
            <ProfileCheckbox checked={s.profileLeftPBar} onChange={() => { if (!s.profileLeftPBar) update({ profileLeftPBar: true, profileLeftLockBar: false }); else update({ profileLeftPBar: false }); }} label="Боковой П-профиль RS1082" indent />
            <ProfileCheckbox checked={s.profileLeftHandleBar} onChange={() => { if (!s.profileLeftHandleBar) update({ profileLeftHandleBar: true, profileLeftBubble: false }); else update({ profileLeftHandleBar: false }); }} label="Ручка-профиль RS112" />
            <ProfileCheckbox checked={s.profileLeftBubble} onChange={() => { if (!s.profileLeftBubble) update({ profileLeftBubble: true, profileLeftHandleBar: false }); else update({ profileLeftBubble: false }); }} label="Пузырьковый уплотнитель RS1002" disabled={s.profileLeftLockBar} />
          </div>
          {showLockLeft && (
            <div className="mt-2 space-y-1">
              <label className={LBL}>Замок слева</label>
              <RadioList value={s.lockLeft} noneLabel="Без замка"
                options={['ЗАМОК-ЗАЩЕЛКА 1стор', 'ЗАМОК-ЗАЩЕЛКА 2стор с ключом']}
                onChange={v => update({ lockLeft: v })} />
            </div>
          )}
          {showNoLockLeft && (
            <div className="mt-2 px-4 py-2 bg-black/10 border border-[#2a7a8a]/20 rounded-xl">
              <span className="text-xs text-white/40 font-bold">Без замков</span>
            </div>
          )}
          {showHandleLeft && (
            <div className="mt-2 space-y-1">
              <label className={LBL}>Ручка слева</label>
              <RadioList value={s.handleLeft} noneLabel="Без ручки (глухая)"
                options={['Без ручки (подвижная)', 'Ручка-кноб RS3014', 'Стеклянная ручка RS3017', 'Ручка-скоба']}
                onChange={v => update({ handleLeft: v })} />
            </div>
          )}
        </div>

        {/* Профили справа */}
        <div className="space-y-2">
          <label className={LBL}>Профили справа</label>
          <div className="bg-black/10 border border-[#2a7a8a]/20 rounded-xl px-3 py-2">
            <ProfileCheckbox checked={s.profileRightWall} onChange={() => update({ profileRightWall: !s.profileRightWall })} label="Пристеночный RS1333/1335" />
            <ProfileCheckbox checked={s.profileRightLockBar} onChange={() => { if (!s.profileRightLockBar) update({ profileRightLockBar: true, profileRightPBar: false, profileRightHandleBar: true, profileRightBubble: false }); else update({ profileRightLockBar: false }); }} label="Боковой профиль-замок RS1081" indent />
            <ProfileCheckbox checked={s.profileRightPBar} onChange={() => { if (!s.profileRightPBar) update({ profileRightPBar: true, profileRightLockBar: false }); else update({ profileRightPBar: false }); }} label="Боковой П-профиль RS1082" indent />
            <ProfileCheckbox checked={s.profileRightHandleBar} onChange={() => { if (!s.profileRightHandleBar) update({ profileRightHandleBar: true, profileRightBubble: false }); else update({ profileRightHandleBar: false }); }} label="Ручка-профиль RS112" />
            <ProfileCheckbox checked={s.profileRightBubble} onChange={() => { if (!s.profileRightBubble) update({ profileRightBubble: true, profileRightHandleBar: false }); else update({ profileRightBubble: false }); }} label="Пузырьковый уплотнитель RS1002" disabled={s.profileRightLockBar} />
          </div>
          {showLockRight && (
            <div className="mt-2 space-y-1">
              <label className={LBL}>Замок справа</label>
              <RadioList value={s.lockRight} noneLabel="Без замка"
                options={['ЗАМОК-ЗАЩЕЛКА 1стор', 'ЗАМОК-ЗАЩЕЛКА 2стор с ключом']}
                onChange={v => update({ lockRight: v })} />
            </div>
          )}
          {showNoLockRight && (
            <div className="mt-2 px-4 py-2 bg-black/10 border border-[#2a7a8a]/20 rounded-xl">
              <span className="text-xs text-white/40 font-bold">Без замков</span>
            </div>
          )}
          {showHandleRight && (
            <div className="mt-2 space-y-1">
              <label className={LBL}>Ручка справа</label>
              <RadioList value={s.handleRight} noneLabel="Без ручки (глухая)"
                options={['Без ручки (подвижная)', 'Ручка-кноб RS3014', 'Стеклянная ручка RS3017', 'Ручка-скоба']}
                onChange={v => update({ handleRight: v })} />
            </div>
          )}
        </div>
      </div>

      {/* Напольные защёлки */}
      <div className="space-y-2">
        <label className={LBL}>Защёлки в пол</label>
        <div className="flex gap-6">
          <Checkbox checked={s.floorLatchesLeft} onChange={() => update({ floorLatchesLeft: !s.floorLatchesLeft })} label="Слева" />
          <Checkbox checked={s.floorLatchesRight} onChange={() => update({ floorLatchesRight: !s.floorLatchesRight })} label="Справа" />
        </div>
      </div>

      {/* Отступ под ручку */}
      {(s.handleLeft === 'Стеклянная ручка RS3017' || s.handleLeft === 'Ручка-скоба' || s.handleRight === 'Стеклянная ручка RS3017' || s.handleRight === 'Ручка-скоба') && (
        <div className="space-y-2">
          <label className={LBL}>Отступ под ручку, мм</label>
          <input type="number" value={s.handleOffset || ''} onChange={e => update({ handleOffset: parseFloat(e.target.value) || undefined })} className={INP} placeholder="мм" />
        </div>
      )}
    </div>
  );
}

// ── Tab: КНИЖКА — Система ────────────────────────────────────────────────────

function BookSystemTab({ s, update }: { s: Section; update: (u: Partial<Section>) => void }) {
  const hasDoors = !s.bookSubtype || s.bookSubtype === 'doors' || s.bookSubtype === 'doors_and_angle';
  const hasAngle = s.bookSubtype === 'angle' || s.bookSubtype === 'doors_and_angle';
  return (
    <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 sm:gap-8">
      <div className="space-y-5">
        {hasDoors && (
          <>
            <div className="space-y-2">
              <label className={LBL}>Кол-во дверей</label>
              <ToggleGroup value={s.doors?.toString()} options={['1', '2']}
                onChange={v => update({ doors: parseInt(v) })} />
            </div>
            <div className="space-y-2">
              <label className={LBL}>Сторона двери</label>
              <ToggleGroup value={s.doorSide} options={['Левая', 'Правая']}
                onChange={v => update({ doorSide: v })} />
            </div>
            <div className="space-y-2">
              <label className={LBL}>Тип двери</label>
              <RadioList value={s.doorType}
                options={['Тип 1', 'Тип 4']}
                onChange={v => update({ doorType: v })} />
            </div>
            <div className="space-y-2">
              <label className={LBL}>Открывание</label>
              <ToggleGroup value={s.doorOpening} options={['Внутрь', 'Наружу']}
                onChange={v => update({ doorOpening: v })} />
            </div>
          </>
        )}
        <div className="space-y-2">
          <label className={LBL}>Кол-во панелей</label>
          <select value={s.panels} onChange={e => update({ panels: parseInt(e.target.value) })} className={SEL}>
            {[2, 3, 4, 5, 6].map(n => <option key={n} value={n}>{n}</option>)}
          </select>
        </div>
      </div>
      <div className="space-y-5">
        {hasDoors && (
          <>
            <div className="space-y-2">
              <label className={LBL}>Система книжки</label>
              <RadioList value={s.bookSystem} noneLabel="— Стандарт —"
                options={['С кареткой', 'Без каретки']}
                onChange={v => update({ bookSystem: v })} />
            </div>
            <div className="space-y-2">
              <label className={LBL}>Компенсатор</label>
              <RadioList value={s.compensator} noneLabel="— Нет —"
                options={['Левый', 'Правый', 'Оба']}
                onChange={v => update({ compensator: v })} />
            </div>
          </>
        )}
        {(hasDoors || hasAngle) && (
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className={LBL}>Угол лев., °</label>
              <input type="number" value={s.angleLeft || ''} onChange={e => update({ angleLeft: parseFloat(e.target.value) || undefined })} className={INP} placeholder="0" />
            </div>
            <div className="space-y-2">
              <label className={LBL}>Угол пр., °</label>
              <input type="number" value={s.angleRight || ''} onChange={e => update({ angleRight: parseFloat(e.target.value) || undefined })} className={INP} placeholder="0" />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Tab: ЛИФТ — Система ──────────────────────────────────────────────────────

function LiftSystemTab({ s, update }: { s: Section; update: (u: Partial<Section>) => void }) {
  return (
    <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 sm:gap-8">
      <div className="space-y-5">
        <div className="space-y-2">
          <label className={LBL}>Кол-во панелей</label>
          <ToggleGroup value={s.panels?.toString()} options={['2', '3', '4']}
            onChange={v => update({ panels: parseInt(v) })} />
        </div>
        <div className="space-y-2">
          <label className={LBL}>1-я панель</label>
          <ToggleGroup value={s.firstPanelInside} options={['Слева', 'Справа']}
            onChange={v => update({ firstPanelInside: v })} />
        </div>
        <div className="space-y-2">
          <label className={LBL}>Замок</label>
          <RadioList value={s.lock} noneLabel="Без замка"
            options={['RS3018 Замок-защёлка', 'С ключом']}
            onChange={v => update({ lock: v })} />
        </div>
      </div>
      <div className="space-y-5">
        <div className="space-y-2">
          <label className={LBL}>Профиль левый</label>
          <select value={s.profileLeft || ''} onChange={e => update({ profileLeft: e.target.value || undefined })} className={SEL}>
            <option value="">— Нет —</option>
            <option>Стойка</option>
            <option>Угол</option>
            <option>Торец</option>
          </select>
        </div>
        <div className="space-y-2">
          <label className={LBL}>Профиль правый</label>
          <select value={s.profileRight || ''} onChange={e => update({ profileRight: e.target.value || undefined })} className={SEL}>
            <option value="">— Нет —</option>
            <option>Стойка</option>
            <option>Угол</option>
            <option>Торец</option>
          </select>
        </div>
        <div className="space-y-2">
          <label className={LBL}>Ручка</label>
          <RadioList value={s.handle} noneLabel="Без ручки"
            options={['RS3014 Ручка-кноб', 'RS3017 Стеклянная ручка']}
            onChange={v => update({ handle: v })} />
        </div>
      </div>
    </div>
  );
}

// ── Tab: ЦС — Форма ──────────────────────────────────────────────────────────

function CsShapeTab({ s, update }: { s: Section; update: (u: Partial<Section>) => void }) {
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <label className={LBL}>Форма секции</label>
        <div className="grid grid-cols-2 gap-3">
          {['Треугольник', 'Прямоугольник', 'Трапеция', 'Сложная форма'].map(shape => (
            <button key={shape} onClick={() => update({ csShape: shape })}
              className={`py-4 rounded-xl border font-bold text-xs transition-all ${
                s.csShape === shape ? 'bg-[#4fd1c5]/10 border-[#4fd1c5]/50 text-[#4fd1c5]' : 'bg-black/10 border-[#2a7a8a]/20 text-white/40 hover:border-[#2a7a8a]/50'
              }`}
            >{shape}</button>
          ))}
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <label className={LBL}>Ширина (осн.), мм</label>
          <input type="number" value={s.width} onChange={e => update({ width: parseInt(e.target.value) || 0 })} className={INP} />
        </div>
        <div className="space-y-2">
          <label className={LBL}>Высота, мм</label>
          <input type="number" value={s.height} onChange={e => update({ height: parseInt(e.target.value) || 0 })} className={INP} />
        </div>
        {s.csShape === 'Трапеция' && (
          <div className="space-y-2">
            <label className={LBL}>Ширина 2, мм</label>
            <input type="number" value={s.csWidth2 || ''} onChange={e => update({ csWidth2: parseFloat(e.target.value) || undefined })} className={INP} placeholder="мм" />
          </div>
        )}
      </div>
    </div>
  );
}

// ── Tab: ДВЕРЬ — Система ─────────────────────────────────────────────────────

function DoorSystemTab({ s, update }: { s: Section; update: (u: Partial<Section>) => void }) {
  return (
    <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 sm:gap-8">
      <div className="space-y-5">
        <div className="space-y-2">
          <label className={LBL}>Тип системы</label>
          <RadioList value={s.doorSystem}
            options={['Одностворчатая', 'Двустворчатая', 'Маятниковая']}
            onChange={v => update({ doorSystem: v })} />
        </div>
        <div className="space-y-2">
          <label className={LBL}>Открывание</label>
          <ToggleGroup value={s.doorOpening} options={['Внутрь', 'Наружу']}
            onChange={v => update({ doorOpening: v })} />
        </div>
      </div>
      <div className="space-y-5">
        <div className="space-y-2">
          <label className={LBL}>Замок</label>
          <RadioList value={s.lock} noneLabel="Без замка"
            options={['RS3018 Защёлка', 'RS3019 С ключом', 'Магнитный']}
            onChange={v => update({ lock: v })} />
        </div>
        <div className="space-y-2">
          <label className={LBL}>Ручка</label>
          <RadioList value={s.handle} noneLabel="Без ручки"
            options={['RS3014 Ручка-кноб', 'RS3017 Стеклянная ручка', 'Ручка-скоба', 'Ручка-раковина']}
            onChange={v => update({ handle: v })} />
        </div>
      </div>
    </div>
  );
}

// ── SVG Схема сверху (СЛАЙД) ──────────────────────────────────────────────────

function SlideSchemeSVG({ section }: { section: Section }) {
  const {
    panels, rails = 3, firstPanelInside = 'Справа', unusedTrack, interGlassProfile,
    profileLeftWall, profileLeftLockBar, profileLeftPBar, profileLeftHandleBar, profileLeftBubble,
    profileRightWall, profileRightLockBar, profileRightPBar, profileRightHandleBar, profileRightBubble,
    width: sectionWidth, height: sectionHeight,
  } = section;
  const railCount = rails as number;

  // Layout constants
  const rowH   = 34;   // height per rail row
  const topPad = 22;   // space for "УЛИЦА" label
  const botPad = 36;   // space for "ПОМЕЩЕНИЕ" label + arrow
  const leftW  = 58;   // space for left profiles
  const rightW = 58;   // space for right profiles
  const railAreaW = 380;
  const svgW = leftW + railAreaW + rightW;
  const svgH = topPad + railCount * rowH + botPad;

  // Top = УЛИЦА (external/outermost rail, index 0)
  // Bottom = ПОМЕЩЕНИЕ (internal/innermost rail, index railCount-1)
  // unusedTrack 'Внешний'   → outermost = index 0        (top)
  // unusedTrack 'Внутренний' → innermost = index railCount-1 (bottom)
  // Apply same default as ToggleGroup: when panels < rails and track is unset → 'Внутренний'
  const effectiveUnusedTrack = unusedTrack ?? (panels < railCount ? 'Внутренний' : undefined);
  // For multi-rail systems (5-rail) multiple rails may be unused on one side
  const unusedCount = Math.max(0, railCount - panels);
  const unusedRailSet = new Set<number>(
    effectiveUnusedTrack === 'Внешний'
      ? Array.from({ length: unusedCount }, (_, i) => i)                   // top rails (УЛИЦА side)
      : effectiveUnusedTrack === 'Внутренний'
        ? Array.from({ length: unusedCount }, (_, i) => railCount - 1 - i)  // bottom rails (ПОМЕЩЕНИЕ side)
        : []
  );

  // Panels go on all rails except unused, from top to bottom
  const availableRails = Array.from({ length: railCount }, (_, i) => i)
    .filter(i => !unusedRailSet.has(i));
  const panelRailMap = Array.from({ length: panels }, (_, pi) => availableRails[pi] ?? availableRails[pi % availableRails.length] ?? pi % railCount);

  const panelW = railAreaW / panels;
  const slideLeft = firstPanelInside === 'Справа';
  const glassW = sectionWidth ? Math.round(sectionWidth / panels) : null;
  const glassH = sectionHeight ?? null;

  // Draw left-side profiles spanning full construction height
  const drawLeftProfiles = () => {
    const y1 = topPad;
    const h = railCount * rowH;
    const shapes: React.ReactElement[] = [];
    let x = leftW - 4;

    if (profileLeftWall) {
      shapes.push(<rect key="lw1" x={x - 14} y={y1} width={7} height={h} rx="1" fill="#4fd1c5" fillOpacity="0.18" stroke="#4fd1c5" strokeWidth="1.5" strokeOpacity="0.9" />);
      shapes.push(<rect key="lw2" x={x - 7}  y={y1} width={7} height={h} rx="1" fill="#4fd1c5" fillOpacity="0.08" stroke="#4fd1c5" strokeWidth="1" strokeOpacity="0.7" />);
      x -= 16;
    }
    if (profileLeftLockBar) {
      shapes.push(<rect key="ll1" x={x - 12} y={y1} width={4} height={h} rx="1" fill="#4fd1c5" fillOpacity="0.18" stroke="#4fd1c5" strokeWidth="1.5" strokeOpacity="0.9" />);
      shapes.push(<rect key="ll2" x={x - 5}  y={y1} width={4} height={h} rx="1" fill="#4fd1c5" fillOpacity="0.18" stroke="#4fd1c5" strokeWidth="1.5" strokeOpacity="0.9" />);
      Array.from({ length: railCount }, (_, ri) => {
        const cy = topPad + ri * rowH + rowH / 2;
        shapes.push(<line key={`llb${ri}`} x1={x - 10} y1={cy} x2={x - 3} y2={cy} stroke="#4fd1c5" strokeWidth="2" strokeOpacity="0.7" />);
      });
      x -= 14;
    }
    if (profileLeftPBar) {
      shapes.push(<path key="lp" d={`M${x-12},${y1} L${x-2},${y1} L${x-2},${y1+h} L${x-12},${y1+h}`} fill="none" stroke="#4fd1c5" strokeWidth="2.5" strokeOpacity="0.85" />);
      x -= 14;
    }
    if (profileLeftHandleBar) {
      shapes.push(<line key="lhv" x1={x-8} y1={y1} x2={x-8} y2={y1+h} stroke="#4fd1c5" strokeWidth="2.5" strokeOpacity="0.85" />);
      Array.from({ length: railCount }, (_, ri) => {
        const cy = topPad + ri * rowH + rowH / 2;
        shapes.push(<line key={`lhh${ri}`} x1={x-14} y1={cy} x2={x-2} y2={cy} stroke="#4fd1c5" strokeWidth="2" strokeOpacity="0.65" />);
      });
      x -= 16;
    }
    if (profileLeftBubble) {
      Array.from({ length: railCount }, (_, ri) => {
        const cy = topPad + ri * rowH + rowH / 2;
        shapes.push(<circle key={`lb${ri}`} cx={x-7} cy={cy} r={5} fill="#4fd1c5" fillOpacity="0.25" stroke="#4fd1c5" strokeWidth="1.5" strokeOpacity="0.85" />);
      });
    }
    return shapes;
  };

  // Draw right-side profiles spanning full construction height
  const drawRightProfiles = () => {
    const y1 = topPad;
    const h = railCount * rowH;
    const shapes: React.ReactElement[] = [];
    let x = leftW + railAreaW + 4;

    if (profileRightWall) {
      shapes.push(<rect key="rw1" x={x}     y={y1} width={7} height={h} rx="1" fill="#4fd1c5" fillOpacity="0.18" stroke="#4fd1c5" strokeWidth="1.5" strokeOpacity="0.9" />);
      shapes.push(<rect key="rw2" x={x + 7} y={y1} width={7} height={h} rx="1" fill="#4fd1c5" fillOpacity="0.08" stroke="#4fd1c5" strokeWidth="1" strokeOpacity="0.7" />);
      x += 16;
    }
    if (profileRightLockBar) {
      shapes.push(<rect key="rl1" x={x}     y={y1} width={4} height={h} rx="1" fill="#4fd1c5" fillOpacity="0.18" stroke="#4fd1c5" strokeWidth="1.5" strokeOpacity="0.9" />);
      shapes.push(<rect key="rl2" x={x + 8} y={y1} width={4} height={h} rx="1" fill="#4fd1c5" fillOpacity="0.18" stroke="#4fd1c5" strokeWidth="1.5" strokeOpacity="0.9" />);
      Array.from({ length: railCount }, (_, ri) => {
        const cy = topPad + ri * rowH + rowH / 2;
        shapes.push(<line key={`rlb${ri}`} x1={x+2} y1={cy} x2={x+10} y2={cy} stroke="#4fd1c5" strokeWidth="2" strokeOpacity="0.7" />);
      });
      x += 14;
    }
    if (profileRightPBar) {
      shapes.push(<path key="rp" d={`M${x+12},${y1} L${x+2},${y1} L${x+2},${y1+h} L${x+12},${y1+h}`} fill="none" stroke="#4fd1c5" strokeWidth="2.5" strokeOpacity="0.85" />);
      x += 14;
    }
    if (profileRightHandleBar) {
      shapes.push(<line key="rhv" x1={x+8} y1={y1} x2={x+8} y2={y1+h} stroke="#4fd1c5" strokeWidth="2.5" strokeOpacity="0.85" />);
      Array.from({ length: railCount }, (_, ri) => {
        const cy = topPad + ri * rowH + rowH / 2;
        shapes.push(<line key={`rhh${ri}`} x1={x+2} y1={cy} x2={x+14} y2={cy} stroke="#4fd1c5" strokeWidth="2" strokeOpacity="0.65" />);
      });
      x += 16;
    }
    if (profileRightBubble) {
      Array.from({ length: railCount }, (_, ri) => {
        const cy = topPad + ri * rowH + rowH / 2;
        shapes.push(<circle key={`rb${ri}`} cx={x+7} cy={cy} r={5} fill="#4fd1c5" fillOpacity="0.25" stroke="#4fd1c5" strokeWidth="1.5" strokeOpacity="0.85" />);
      });
    }
    return shapes;
  };

  return (
    <svg width={svgW} height={svgH} viewBox={`0 0 ${svgW} ${svgH}`} className="w-full drop-shadow-[0_0_15px_rgba(79,209,197,0.08)]" style={{ maxWidth: svgW }}>

      {/* УЛИЦА / ПОМЕЩЕНИЕ labels */}
      <text x={svgW / 2} y={13} textAnchor="middle" fontSize="8.5" fill="#4fd1c5" fillOpacity="0.35" fontWeight="bold" letterSpacing="3">УЛИЦА</text>
      <text x={svgW / 2} y={svgH - 5} textAnchor="middle" fontSize="8.5" fill="#4fd1c5" fillOpacity="0.35" fontWeight="bold" letterSpacing="3">ПОМЕЩЕНИЕ</text>

      {/* Wall jambs */}
      <rect x={leftW - 2} y={topPad - 2} width={4} height={railCount * rowH + 4} rx="1" fill="#2a7a8a" fillOpacity="0.4" />
      <rect x={leftW + railAreaW - 2} y={topPad - 2} width={4} height={railCount * rowH + 4} rx="1" fill="#2a7a8a" fillOpacity="0.4" />

      {/* Rails */}
      {Array.from({ length: railCount }, (_, ri) => {
        const cy = topPad + ri * rowH + rowH / 2;
        const isUnused = unusedRailSet.has(ri);
        return (
          <g key={ri}>
            <line
              x1={leftW} y1={cy} x2={leftW + railAreaW} y2={cy}
              stroke={isUnused ? '#2a7a8a' : '#4fd1c5'}
              strokeWidth={isUnused ? 1 : 1.5}
              strokeOpacity={isUnused ? 0.22 : 0.55}
              strokeDasharray={isUnused ? '5 5' : undefined}
            />
            {isUnused && (
              <text x={leftW + railAreaW / 2} y={cy - 5} textAnchor="middle" fontSize="7.5" fill="#2a7a8a" fillOpacity="0.55" fontWeight="bold" letterSpacing="1">
                неиспользуемый рельс
              </text>
            )}
          </g>
        );
      })}

      {/* Panels on their rails */}
      {Array.from({ length: panels }, (_, pi) => {
        const ri = panelRailMap[pi];
        const cy = topPad + ri * rowH + rowH / 2;
        const px = leftW + pi * panelW;
        const panelNum = firstPanelInside === 'Справа' ? panels - pi : pi + 1;
        // Overlap: extend into neighbours except at frame edges
        const rx = px + (pi === 0 ? 5 : -6);
        const rRight = px + panelW + (pi === panels - 1 ? -5 : 6);
        const rw = rRight - rx;
        const cx = px + panelW / 2;
        return (
          <g key={pi}>
            <rect x={rx} y={cy - 9} width={rw} height={18} rx="2"
              fill="#4fd1c5" fillOpacity="0.13" stroke="#4fd1c5" strokeWidth="1.4" strokeOpacity="0.75" />
            {glassW && glassH ? (
              <>
                <text x={cx} y={cy + 1} textAnchor="middle" fontSize="8" fill="#4fd1c5" fillOpacity="0.9" fontWeight="bold">{glassW}×{glassH}</text>
                <text x={cx} y={cy + 11} textAnchor="middle" fontSize="6.5" fill="#4fd1c5" fillOpacity="0.55">№{panelNum}</text>
              </>
            ) : (
              <text x={cx} y={cy + 5} textAnchor="middle" fontSize="9" fill="#4fd1c5" fillOpacity="0.9" fontWeight="bold">{panelNum}</text>
            )}
          </g>
        );
      })}

      {/* Inter-glass profile RS1061 — thin vertical bar between panels in top-view */}
      {interGlassProfile && Array.from({ length: panels - 1 }, (_, pi) => (
        <rect key={pi}
          x={leftW + (pi + 1) * panelW - 2} y={topPad}
          width={4} height={railCount * rowH}
          fill="#4fd1c5" fillOpacity="0.15" stroke="#4fd1c5" strokeWidth="1" strokeOpacity="0.55" />
      ))}

      {/* Left profiles — full construction height */}
      <g>{drawLeftProfiles()}</g>

      {/* Right profiles — full construction height */}
      <g>{drawRightProfiles()}</g>

      {/* Slide direction arrow */}
      {(() => {
        const ay = svgH - botPad / 2 - 2;
        const ax = leftW + railAreaW / 2;
        const aLen = 100;
        return (
          <g>
            <line x1={ax - aLen / 2} y1={ay} x2={ax + aLen / 2} y2={ay} stroke="#4fd1c5" strokeWidth="1.5" strokeOpacity="0.5" />
            {slideLeft ? (
              <>
                <polyline points={`${ax - aLen / 2 + 12},${ay - 6} ${ax - aLen / 2},${ay} ${ax - aLen / 2 + 12},${ay + 6}`} stroke="#4fd1c5" strokeWidth="1.5" fill="none" strokeOpacity="0.5" />
                <text x={ax + aLen / 2 + 6} y={ay + 4} fontSize="9" fill="#4fd1c5" fillOpacity="0.55" fontWeight="bold">сдвиг</text>
              </>
            ) : (
              <>
                <polyline points={`${ax + aLen / 2 - 12},${ay - 6} ${ax + aLen / 2},${ay} ${ax + aLen / 2 - 12},${ay + 6}`} stroke="#4fd1c5" strokeWidth="1.5" fill="none" strokeOpacity="0.5" />
                <text x={ax - aLen / 2 - 6} y={ay + 4} fontSize="9" fill="#4fd1c5" fillOpacity="0.55" fontWeight="bold" textAnchor="end">сдвиг</text>
              </>
            )}
          </g>
        );
      })()}
    </svg>
  );
}

// ── SVG: Вид из помещения ─────────────────────────────────────────────────────

function SlideRoomViewSVG({ section }: { section: Section }) {
  const panels  = section.panels;
  const firstRight = (section.firstPanelInside ?? 'Справа') === 'Справа';
  const W  = section.width;
  const Hh = section.height;

  // SVG canvas
  const vbW = 540, vbH = 330;
  // Frame position
  const fX = 50, fY = 35, fW = 400, fH = 210;
  const pt = 10; // profile (frame border) thickness

  // Inner glass area
  const iX = fX + pt, iY = fY + pt;
  const iW = fW - 2 * pt, iH = fH - 2 * pt;
  const pW = iW / panels; // panel draw-width per panel

  const panelWmm = Math.round(W / panels);
  const arrowLeft = firstRight; // true = all arrows ←, false = all →

  return (
    <svg viewBox={`0 0 ${vbW} ${vbH}`} className="w-full" style={{ maxWidth: 540, maxHeight: 330 }}>

      {/* ── Outer frame ── */}
      {/* Top rail */}
      <rect x={fX} y={fY} width={fW} height={pt} fill="#1a4b54" stroke="#4fd1c5" strokeWidth="0.6" strokeOpacity="0.4" />
      {/* Bottom rail */}
      <rect x={fX} y={fY + fH - pt} width={fW} height={pt} fill="#1a4b54" stroke="#4fd1c5" strokeWidth="0.6" strokeOpacity="0.4" />
      {/* Left jamb */}
      <rect x={fX} y={fY} width={pt} height={fH} fill="#1a4b54" stroke="#4fd1c5" strokeWidth="0.6" strokeOpacity="0.4" />
      {/* Right jamb */}
      <rect x={fX + fW - pt} y={fY} width={pt} height={fH} fill="#1a4b54" stroke="#4fd1c5" strokeWidth="0.6" strokeOpacity="0.4" />
      {/* Outer border */}
      <rect x={fX} y={fY} width={fW} height={fH} fill="none" stroke="#4fd1c5" strokeWidth="1.5" strokeOpacity="0.5" />

      {/* ── Panels ── */}
      {Array.from({ length: panels }).map((_, i) => {
        const px = iX + i * pW;
        const cx = px + pW / 2;
        const cy = iY + iH / 2;
        const num = firstRight ? panels - i : i + 1;
        const aLen = Math.min(22, pW * 0.45);

        return (
          <g key={i}>
            {/* Glass fill */}
            <rect x={px} y={iY} width={pW} height={iH}
              fill="#4fd1c5" fillOpacity="0.07" />
            {/* Glass highlight */}
            <rect x={px + 3} y={iY + 3} width={pW * 0.28} height={iH - 6}
              fill="white" fillOpacity="0.025" rx="1" />

            {/* Inter-panel profile (not after last panel) */}
            {i < panels - 1 && (
              <rect x={px + pW - 2} y={iY} width={4} height={iH}
                fill="#0d1e2d" stroke="#4fd1c5" strokeWidth="0.4" strokeOpacity="0.25" />
            )}

            {/* Panel number */}
            <text x={cx} y={cy - 12} textAnchor="middle" fontSize="14"
              fill="#4fd1c5" fillOpacity="0.85" fontWeight="bold" fontFamily="monospace">
              {num}
            </text>

            {/* Slide arrow */}
            <line
              x1={arrowLeft ? cx + aLen / 2 : cx - aLen / 2}
              y1={cy + 5}
              x2={arrowLeft ? cx - aLen / 2 : cx + aLen / 2}
              y2={cy + 5}
              stroke="#4fd1c5" strokeWidth="1.3" strokeOpacity="0.55"
            />
            {arrowLeft ? (
              <polyline
                points={`${cx - aLen / 2 + 6},${cy + 1} ${cx - aLen / 2},${cy + 5} ${cx - aLen / 2 + 6},${cy + 9}`}
                stroke="#4fd1c5" strokeWidth="1.3" fill="none" strokeOpacity="0.55"
              />
            ) : (
              <polyline
                points={`${cx + aLen / 2 - 6},${cy + 1} ${cx + aLen / 2},${cy + 5} ${cx + aLen / 2 - 6},${cy + 9}`}
                stroke="#4fd1c5" strokeWidth="1.3" fill="none" strokeOpacity="0.55"
              />
            )}
          </g>
        );
      })}

      {/* ── Dimension lines ── */}

      {/* Per-panel widths */}
      {Array.from({ length: panels }).map((_, i) => {
        const dx1 = iX + i * pW;
        const dx2 = iX + (i + 1) * pW;
        const dy  = fY + fH + 18;
        const cx  = (dx1 + dx2) / 2;
        return (
          <g key={i}>
            <line x1={dx1 + 3} y1={dy} x2={dx2 - 3} y2={dy} stroke="#4fd1c5" strokeWidth="0.8" strokeOpacity="0.35" />
            <line x1={dx1 + 3} y1={dy - 4} x2={dx1 + 3} y2={dy + 4} stroke="#4fd1c5" strokeWidth="0.8" strokeOpacity="0.35" />
            <line x1={dx2 - 3} y1={dy - 4} x2={dx2 - 3} y2={dy + 4} stroke="#4fd1c5" strokeWidth="0.8" strokeOpacity="0.35" />
            <text x={cx} y={dy + 12} textAnchor="middle" fontSize="9" fill="#4fd1c5" fillOpacity="0.45">{panelWmm}</text>
          </g>
        );
      })}

      {/* Total width */}
      <line x1={iX} y1={fY + fH + 38} x2={iX + iW} y2={fY + fH + 38} stroke="#4fd1c5" strokeWidth="0.8" strokeOpacity="0.3" />
      <line x1={iX}        y1={fY + fH + 32} x2={iX}        y2={fY + fH + 44} stroke="#4fd1c5" strokeWidth="0.8" strokeOpacity="0.3" />
      <line x1={iX + iW}   y1={fY + fH + 32} x2={iX + iW}   y2={fY + fH + 44} stroke="#4fd1c5" strokeWidth="0.8" strokeOpacity="0.3" />
      <text x={iX + iW / 2} y={fY + fH + 52} textAnchor="middle" fontSize="10" fill="#4fd1c5" fillOpacity="0.5">{W}</text>

      {/* Height on right */}
      <line x1={fX + fW + 18} y1={fY} x2={fX + fW + 18} y2={fY + fH} stroke="#4fd1c5" strokeWidth="0.8" strokeOpacity="0.3" />
      <line x1={fX + fW + 12} y1={fY}      x2={fX + fW + 24} y2={fY}      stroke="#4fd1c5" strokeWidth="0.8" strokeOpacity="0.3" />
      <line x1={fX + fW + 12} y1={fY + fH} x2={fX + fW + 24} y2={fY + fH} stroke="#4fd1c5" strokeWidth="0.8" strokeOpacity="0.3" />
      <text
        x={fX + fW + 34} y={fY + fH / 2}
        textAnchor="middle" fontSize="10" fill="#4fd1c5" fillOpacity="0.5"
        transform={`rotate(90,${fX + fW + 34},${fY + fH / 2})`}
      >{Hh}</text>
    </svg>
  );
}

// ── ProjectEditor ─────────────────────────────────────────────────────────────

export const ProjectEditor: React.FC<ProjectEditorProps> = ({ projectId, onBack }) => {
  const [project, setProject] = useState<{ id: number; number: string; customer: string } | null>(null);
  const [sections, setSections] = useState<Section[]>([]);
  const [loadingProject, setLoadingProject] = useState(true);

  useEffect(() => {
    getProject(projectId).then(p => {
      setProject({ id: p.id, number: p.number, customer: p.customer });
      setProjectExtraParts(p.extra_parts || '');
      setProjectComments(p.comments || '');
      setProductionStages((p.production_stages as 1 | 2) || 1);
      setCurrentStage((p.current_stage as 1 | 2) || 1);
      setProjectStatus(p.status || '');
      setGlassStatus(p.glass_status || '');
      setGlassInvoice(p.glass_invoice || '');
      setGlassReadyDate(p.glass_ready_date || '');
      setPaintStatus(p.paint_status || '');
      setPaintShipDate(p.paint_ship_date || '');
      setPaintReceivedDate(p.paint_received_date || '');
      try { setOrderItems(p.order_items ? JSON.parse(p.order_items) : []); } catch { setOrderItems([]); }
      setSections(p.sections.map(s => apiToLocal(s)));
      setLoadingProject(false);
    }).catch(() => { setLoadingProject(false); onBack(); });
  }, [projectId]);

  const [activeSectionId, setActiveSectionId] = useState<string | null>(null);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [sectionToDelete, setSectionToDelete] = useState<Section | null>(null);
  const [isPreviewModalOpen, setIsPreviewModalOpen] = useState(false);
  const [previewDocName, setPreviewDocName] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [isDirty, setIsDirty] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(true);
  const [projectExtraParts, setProjectExtraParts] = useState('');
  const [projectComments, setProjectComments] = useState('');
  const [productionStages, setProductionStages] = useState<1 | 2>(1);
  const [currentStage, setCurrentStage] = useState<1 | 2>(1);
  const [projectStatus, setProjectStatus] = useState('');
  const [glassStatus, setGlassStatus] = useState('');
  const [glassInvoice, setGlassInvoice] = useState('');
  const [glassReadyDate, setGlassReadyDate] = useState('');
  const [paintStatus, setPaintStatus] = useState('');
  const [paintShipDate, setPaintShipDate] = useState('');
  const [paintReceivedDate, setPaintReceivedDate] = useState('');
  const [orderItems, setOrderItems] = useState<OrderItem[]>([]);
  const [notesOpen, setNotesOpen] = useState(false);
  const [showSystemPicker, setShowSystemPicker] = useState(false);
  const [slideSubVisible, setSlideSubVisible] = useState(false);
  const [bookSubVisible, setBookSubVisible] = useState(false);
  const [liftSubVisible, setLiftSubVisible] = useState(false);
  const [csSubVisible, setCsSubVisible] = useState(false);
  const [unsavedModalOpen, setUnsavedModalOpen] = useState(false);
  const [pendingNavTarget, setPendingNavTarget] = useState<string | null>(null);
  const handleSaveSectionRef = useRef<() => Promise<void>>(async () => {});

  const activeSection = useMemo(() =>
    sections.find(s => s.id === activeSectionId) || null,
    [sections, activeSectionId]
  );

  // Reset dirty flag when switching sections; auto-close sidebar on mobile
  useEffect(() => {
    setIsDirty(false);
    setShowSystemPicker(false);
    if (activeSectionId) setMobileSidebarOpen(false);
  }, [activeSectionId]);

  // Ctrl+S → сохранить секцию
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        handleSaveSectionRef.current();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  // Предупреждение при закрытии вкладки с несохранёнными изменениями
  useEffect(() => {
    if (!isDirty) return;
    const onBeforeUnload = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue = ''; };
    window.addEventListener('beforeunload', onBeforeUnload);
    return () => window.removeEventListener('beforeunload', onBeforeUnload);
  }, [isDirty]);

  const defaultsForSystem = (system: SystemType, opts?: { bookSubtype?: string; liftPanels?: number; csShape?: string }): Partial<Section> => {
    switch (system) {
      case 'СЛАЙД':  return { rails: 3, firstPanelInside: 'Справа', panels: 3 };
      case 'КНИЖКА': {
        const sub = opts?.bookSubtype || 'doors';
        const hasDoors = sub === 'doors' || sub === 'doors_and_angle';
        return {
          bookSubtype: sub,
          doors: hasDoors ? 1 : undefined,
          doorSide: hasDoors ? 'Правая' : undefined,
          panels: 3,
        };
      }
      case 'ЛИФТ':   return { panels: opts?.liftPanels || 2 };
      case 'ЦС':     return { csShape: opts?.csShape || 'Прямоугольник', panels: 1 };
      case 'КОМПЛЕКТАЦИЯ': return { panels: 1, doorSystem: 'Одностворчатая', doorOpening: 'Внутрь' };
    }
  };

  const handleAddSection = async (system: SystemType, opts?: { slideRails?: 3 | 5; bookSubtype?: string; liftPanels?: number; csShape?: string }) => {
    if (!project) return;
    setShowSystemPicker(false);
    setSlideSubVisible(false);
    setBookSubVisible(false);
    setLiftSubVisible(false);
    setCsSubVisible(false);
    const extra: Partial<Section> = {};
    if (system === 'СЛАЙД' && opts?.slideRails) extra.rails = opts.slideRails;
    if (system === 'КНИЖКА' && opts?.bookSubtype) extra.bookSubtype = opts.bookSubtype;
    if (system === 'ЛИФТ' && opts?.liftPanels) extra.panels = opts.liftPanels;
    if (system === 'ЦС' && opts?.csShape) extra.csShape = opts.csShape;
    const maxNum = sections.reduce((m, sec) => Math.max(m, parseInt(sec.name.replace(/\D/g, '')) || 0), 0);
    const newSection: Section = {
      id: `tmp-${Date.now()}`,
      name: `Секция ${maxNum + 1}`,
      system,
      width: 2000, height: 2400, panels: 3, quantity: 1,
      glassType: '10ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ',
      paintingType: 'RAL стандарт', ralColor: '9016',
      cornerLeft: false, cornerRight: false,
      floorLatchesLeft: false, floorLatchesRight: false,
      profileLeftWall: false, profileLeftLockBar: false, profileLeftPBar: false,
      profileLeftHandleBar: false, profileLeftBubble: false,
      profileRightWall: false, profileRightLockBar: false, profileRightPBar: false,
      profileRightHandleBar: false, profileRightBubble: false,
      ...defaultsForSystem(system, opts),
      ...extra,
    };
    try {
      const created = await createSection(project.id, localToApi(newSection, sections.length));
      const local = apiToLocal(created);
      setSections(prev => [...prev, local]);
      setActiveSectionId(local.id);
    } catch (e: any) {
      toast.error(e.response?.data?.detail || 'Не удалось создать секцию');
    }
  };

  const updateActiveSection = (updates: Partial<Section>) => {
    if (!activeSectionId) return;
    setIsDirty(true);
    setSections(sections.map(s => s.id === activeSectionId ? { ...s, ...updates } : s));
  };

  const handleSaveSection = async () => {
    if (!activeSection || !project || isSaving) return;
    const sectionId = parseInt(activeSection.id);
    if (isNaN(sectionId)) return;
    setIsSaving(true);
    const idx = sections.findIndex(s => s.id === activeSectionId);
    try {
      await updateSection(project.id, sectionId, localToApi(activeSection, idx));
      setIsDirty(false);
      toast.success('Секция сохранена');
    } catch (e: any) {
      toast.error(e.response?.data?.detail || 'Не удалось сохранить секцию');
    } finally {
      setIsSaving(false);
    }
  };

  handleSaveSectionRef.current = handleSaveSection;

  const requestNavigate = (targetId: string | null) => {
    if (isDirty) {
      setPendingNavTarget(targetId);
      setUnsavedModalOpen(true);
    } else {
      setActiveSectionId(targetId);
    }
  };

  const confirmUnsavedSave = async () => {
    await handleSaveSection();
    setUnsavedModalOpen(false);
    setActiveSectionId(pendingNavTarget);
    setPendingNavTarget(null);
  };

  const confirmUnsavedDiscard = () => {
    setIsDirty(false);
    setUnsavedModalOpen(false);
    setActiveSectionId(pendingNavTarget);
    setPendingNavTarget(null);
  };

  const handleDeleteSection = async () => {
    if (!sectionToDelete || !project) return;
    try {
      const sectionId = parseInt(sectionToDelete.id);
      if (!isNaN(sectionId)) await deleteSection(project.id, sectionId);
      setSections(sections.filter(s => s.id !== sectionToDelete.id));
      if (activeSectionId === sectionToDelete.id) setActiveSectionId(null);
    } catch (e: any) {
      toast.error(e.response?.data?.detail || 'Не удалось удалить секцию');
    } finally {
      setIsDeleteModalOpen(false);
      setSectionToDelete(null);
    }
  };

  const openPreview = (name: string) => { setPreviewDocName(name); setIsPreviewModalOpen(true); };

  const handleSaveProjectNotes = async () => {
    if (!project) return;
    try {
      await updateProject(project.id, {
        extra_parts: projectExtraParts,
        comments: projectComments,
        production_stages: productionStages,
        current_stage: currentStage,
        status: projectStatus || undefined,
        glass_status: glassStatus || undefined,
        glass_invoice: glassInvoice || undefined,
        glass_ready_date: glassReadyDate || undefined,
        paint_status: paintStatus || undefined,
        paint_ship_date: paintShipDate || undefined,
        paint_received_date: paintReceivedDate || undefined,
        order_items: orderItems.length ? JSON.stringify(orderItems) : undefined,
      });
    } catch {
      toast.error('Не удалось сохранить данные проекта');
    }
  };

  const saveStatus = async (updates: Partial<{ status: string; glass_status: string; glass_invoice: string; glass_ready_date: string; paint_status: string; paint_ship_date: string; paint_received_date: string; current_stage: number; order_items: string; production_stages: number; }>) => {
    if (!project) return;
    try { await updateProject(project.id, updates); }
    catch { toast.error('Не удалось сохранить'); }
  };

  const addOrderItem = () => {
    const newItem: OrderItem = { id: `oi-${Date.now()}`, name: '', invoice: '', paidDate: '', deliveredDate: '' };
    const next = [...orderItems, newItem];
    setOrderItems(next);
    saveStatus({ order_items: JSON.stringify(next) });
  };

  const removeOrderItem = (id: string) => {
    const next = orderItems.filter(oi => oi.id !== id);
    setOrderItems(next);
    saveStatus({ order_items: next.length > 0 ? JSON.stringify(next) : undefined });
  };

  const updateOrderItem = (id: string, field: keyof OrderItem, value: string) => {
    const next = orderItems.map(oi => oi.id === id ? { ...oi, [field]: value } : oi);
    setOrderItems(next);
  };

  const saveOrderItems = () => {
    saveStatus({ order_items: orderItems.length > 0 ? JSON.stringify(orderItems) : undefined });
  };

  // Рендер всего содержимого секции на одной странице
  const renderSectionContent = () => {
    if (!activeSection) return null;
    return (
      <div className="space-y-5">
        <div>
          <SectionDivider label="Основное" />
          <div className="mt-3">
            <MainTab s={activeSection} update={updateActiveSection} />
          </div>
        </div>

        {activeSection.system === 'СЛАЙД' && (
          <div>
            <SectionDivider label="Система · Профили · Фурнитура" />
            <div className="mt-3">
              <SlideSystemTab s={activeSection} update={updateActiveSection} />
            </div>
          </div>
        )}

        {activeSection.system === 'КНИЖКА' && (
          <div>
            <SectionDivider label="Система" />
            <div className="mt-3">
              <BookSystemTab s={activeSection} update={updateActiveSection} />
            </div>
          </div>
        )}

        {activeSection.system === 'ЛИФТ' && (
          <div>
            <SectionDivider label="Система" />
            <div className="mt-3">
              <LiftSystemTab s={activeSection} update={updateActiveSection} />
            </div>
          </div>
        )}

        {activeSection.system === 'ЦС' && (
          <div>
            <SectionDivider label="Форма" />
            <div className="mt-3">
              <CsShapeTab s={activeSection} update={updateActiveSection} />
            </div>
          </div>
        )}

        {activeSection.system === 'КОМПЛЕКТАЦИЯ' && (
          <div>
            <SectionDivider label="Система" />
            <div className="mt-3">
              <DoorSystemTab s={activeSection} update={updateActiveSection} />
            </div>
          </div>
        )}

        {/* Примечания к секции — для всех систем */}
        <div>
          <SectionDivider label="Примечания к секции" />
          <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label className={LBL}>Доп. комплектующие</label>
              <textarea
                value={activeSection.extraParts || ''}
                onChange={e => updateActiveSection({ extraParts: e.target.value || undefined })}
                rows={2}
                placeholder="Дополнительные комплектующие..."
                className="w-full bg-white/8 border border-[#2a7a8a]/30 rounded-xl px-3 py-2 outline-none focus:border-[#4fd1c5]/50 transition-all text-white resize-y placeholder-white/20 text-sm"
              />
            </div>
            <div className="space-y-1.5">
              <label className={LBL}>Комментарии</label>
              <textarea
                value={activeSection.comments || ''}
                onChange={e => updateActiveSection({ comments: e.target.value || undefined })}
                rows={2}
                placeholder="Дополнительные комментарии..."
                className="w-full bg-white/8 border border-[#2a7a8a]/30 rounded-xl px-3 py-2 outline-none focus:border-[#4fd1c5]/50 transition-all text-white resize-y placeholder-white/20 text-sm"
              />
            </div>
          </div>
        </div>
      </div>
    );
  };

  if (loadingProject) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-[#0c1d2d]">
        <Loader2 className="w-10 h-10 text-[#4fd1c5] animate-spin" />
      </div>
    );
  }

  if (!project) return null;

  return (
    <div className="min-h-screen flex flex-col bg-[#0c1d2d]">

      {/* Header */}
      <div className="bg-[#1a4b54]/40 border-b border-[#2a7a8a]/30 px-4 sm:px-8 py-3 sm:py-4 flex items-center justify-between z-20 flex-shrink-0 gap-3">
        {/* Left: back + title */}
        <div className="flex items-center gap-3 min-w-0 flex-shrink-0">
          <button onClick={onBack} className="flex items-center gap-2 text-white/40 hover:text-[#4fd1c5] transition-colors group flex-shrink-0">
            <ArrowLeft className="w-4 h-4 group-hover:-translate-x-1 transition-transform" />
            <span className="hidden sm:inline text-sm font-bold uppercase tracking-wider">Проекты</span>
          </button>
          <div className="hidden sm:block h-6 w-px bg-[#2a7a8a]/20 flex-shrink-0" />
          <div className="flex items-center gap-2 min-w-0 overflow-hidden">
            <span className="text-sm sm:text-xl font-bold whitespace-nowrap">№ {project.number}</span>
            <div className="hidden lg:flex items-center gap-2 flex-shrink-0">
              <span className="text-white/20">·</span>
              <span className="text-white/60 truncate max-w-[200px]">{project.customer}</span>
            </div>
          </div>
        </div>

        {/* Right: actions */}
        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            className="sm:hidden p-2.5 rounded-xl bg-[#2a7a8a]/15 border border-[#2a7a8a]/30 text-[#4fd1c5] hover:bg-[#2a7a8a]/30 transition-colors"
            onClick={() => setMobileSidebarOpen(v => !v)}
            aria-label="Секции"
          >
            <ClipboardList className="w-4 h-4" />
          </button>
          <button onClick={async () => { await handleSaveSection(); onBack(); }}
            className={`flex items-center gap-2 px-3 sm:px-6 py-2 sm:py-2.5 text-white font-bold rounded-xl transition-all shadow-lg ${
              isDirty
                ? 'bg-amber-500 hover:bg-amber-400 shadow-amber-500/20'
                : 'bg-[#00b894] hover:bg-[#00d1a7] shadow-[#00b894]/20'
            }`}>
            {isSaving ? (
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <Save className="w-4 h-4" />
            )}
            <span className="hidden sm:inline">{isDirty ? 'Сохранить и выйти' : 'Выйти'}</span>
          </button>
        </div>
      </div>

      {/* Document buttons sub-bar */}
      <div className="hidden sm:flex items-center gap-1 px-4 sm:px-8 py-2 border-b border-[#2a7a8a]/20 bg-[#1a4b54]/20 flex-shrink-0">
        {[
          { name: 'Спецификация', icon: FileText },
          { name: 'Накладная', icon: ClipboardList },
          { name: 'Заказ стекла', icon: WindowIcon },
          { name: 'Заявка покр.', icon: Palette },
        ].map(doc => (
          <button key={doc.name} onClick={() => openPreview(doc.name)}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/[0.03] border border-white/[0.06] hover:bg-[#2a7a8a]/20 hover:border-[#2a7a8a]/40 transition-all group">
            <doc.icon className="w-3 h-3 text-[#4fd1c5]/50 group-hover:text-[#4fd1c5] transition-colors flex-shrink-0" />
            <span className="text-[10px] font-bold text-white/40 group-hover:text-white transition-colors whitespace-nowrap">{doc.name}</span>
          </button>
        ))}
      </div>

      {/* Body */}
      <div className="flex-1 flex flex-col sm:flex-row min-h-0 overflow-hidden">

        {/* Left: sections list */}
        <aside className={`border-r border-[#2a7a8a]/30 flex-col bg-[#0c1d2d]/80 backdrop-blur-sm z-10 flex-shrink-0 w-full sm:w-[300px] ${mobileSidebarOpen ? 'flex' : 'hidden sm:flex'}`}>
          <div className="p-5 flex-1 overflow-y-auto">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#4fd1c5]/40">Секции</h3>
              <button
                onClick={() => setShowSystemPicker(v => !v)}
                className={`p-1.5 rounded-lg border transition-colors ${
                  showSystemPicker
                    ? 'bg-[#4fd1c5]/20 border-[#4fd1c5]/40 text-[#4fd1c5]'
                    : 'bg-[#2a7a8a]/20 border-[#2a7a8a]/30 text-[#4fd1c5] hover:bg-[#2a7a8a]/40'
                }`}
              >
                <Plus className="w-4 h-4" />
              </button>
            </div>

            {/* System picker */}
            <AnimatePresence>
              {showSystemPicker && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="overflow-hidden mb-4"
                >
                  <div className="flex flex-col gap-1.5 pt-1 pb-3">
                    {/* СЛАЙД */}
                    <div className={`rounded-xl border overflow-hidden transition-all ${slideSubVisible ? 'border-[#2a7a8a]/50' : 'border-[#2a7a8a]/25'}`}>
                      <button onClick={() => setSlideSubVisible(v => !v)}
                        className={`w-full py-2.5 px-3 font-bold text-[11px] transition-all flex items-center justify-between ${SYSTEM_PICKER_COLORS['СЛАЙД']}`}>
                        <span>СЛАЙД</span>
                        <ChevronRight className={`w-3.5 h-3.5 transition-transform ${slideSubVisible ? 'rotate-90' : ''}`} />
                      </button>
                      {slideSubVisible && (
                        <div className="grid grid-cols-2 border-t border-[#2a7a8a]/25">
                          <button onClick={() => handleAddSection('СЛАЙД', { slideRails: 3 })}
                            className={`py-2 font-bold text-[11px] transition-all border-r border-[#2a7a8a]/25 ${SYSTEM_PICKER_COLORS['СЛАЙД']}`}>
                            Стандарт 1 ряд
                          </button>
                          <button onClick={() => handleAddSection('СЛАЙД', { slideRails: 5 })}
                            className={`py-2 font-bold text-[11px] transition-all ${SYSTEM_PICKER_COLORS['СЛАЙД']}`}>
                            2 ряда от центра
                          </button>
                        </div>
                      )}
                    </div>
                    {/* КНИЖКА */}
                    <div className={`rounded-xl border overflow-hidden transition-all ${bookSubVisible ? 'border-[#7a4a2a]/50' : 'border-[#7a4a2a]/25'}`}>
                      <button onClick={() => setBookSubVisible(v => !v)}
                        className={`w-full py-2.5 px-3 font-bold text-[11px] transition-all flex items-center justify-between ${SYSTEM_PICKER_COLORS['КНИЖКА']}`}>
                        <span>КНИЖКА</span>
                        <ChevronRight className={`w-3.5 h-3.5 transition-transform ${bookSubVisible ? 'rotate-90' : ''}`} />
                      </button>
                      {bookSubVisible && (
                        <div className="border-t border-[#7a4a2a]/25">
                          <div className="grid grid-cols-2">
                            <button onClick={() => handleAddSection('КНИЖКА', { bookSubtype: 'doors' })}
                              className={`py-2 font-bold text-[11px] transition-all border-r border-b border-[#7a4a2a]/25 ${SYSTEM_PICKER_COLORS['КНИЖКА']}`}>
                              С дверями
                            </button>
                            <button onClick={() => handleAddSection('КНИЖКА', { bookSubtype: 'angle' })}
                              className={`py-2 font-bold text-[11px] transition-all border-b border-[#7a4a2a]/25 ${SYSTEM_PICKER_COLORS['КНИЖКА']}`}>
                              С углом
                            </button>
                          </div>
                          <button onClick={() => handleAddSection('КНИЖКА', { bookSubtype: 'doors_and_angle' })}
                            className={`w-full py-2 font-bold text-[11px] transition-all ${SYSTEM_PICKER_COLORS['КНИЖКА']}`}>
                            С дверями и углом
                          </button>
                        </div>
                      )}
                    </div>
                    {/* ЛИФТ */}
                    <div className={`rounded-xl border overflow-hidden transition-all ${liftSubVisible ? 'border-[#4a2a7a]/50' : 'border-[#4a2a7a]/25'}`}>
                      <button onClick={() => setLiftSubVisible(v => !v)}
                        className={`w-full py-2.5 px-3 font-bold text-[11px] transition-all flex items-center justify-between ${SYSTEM_PICKER_COLORS['ЛИФТ']}`}>
                        <span>ЛИФТ</span>
                        <ChevronRight className={`w-3.5 h-3.5 transition-transform ${liftSubVisible ? 'rotate-90' : ''}`} />
                      </button>
                      {liftSubVisible && (
                        <div className="grid grid-cols-3 border-t border-[#4a2a7a]/25">
                          {[2, 3, 4].map((n, i) => (
                            <button key={n} onClick={() => handleAddSection('ЛИФТ', { liftPanels: n })}
                              className={`py-2 font-bold text-[11px] transition-all ${i < 2 ? 'border-r border-[#4a2a7a]/25' : ''} ${SYSTEM_PICKER_COLORS['ЛИФТ']}`}>
                              {n} пан.
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                    {/* ЦС */}
                    <div className={`rounded-xl border overflow-hidden transition-all ${csSubVisible ? 'border-[#2a4a7a]/50' : 'border-[#2a4a7a]/25'}`}>
                      <button onClick={() => setCsSubVisible(v => !v)}
                        className={`w-full py-2.5 px-3 font-bold text-[11px] transition-all flex items-center justify-between ${SYSTEM_PICKER_COLORS['ЦС']}`}>
                        <span>ЦС</span>
                        <ChevronRight className={`w-3.5 h-3.5 transition-transform ${csSubVisible ? 'rotate-90' : ''}`} />
                      </button>
                      {csSubVisible && (
                        <div className="grid grid-cols-2 border-t border-[#2a4a7a]/25">
                          {['Треугольник', 'Прямоугольник', 'Трапеция', 'Сложная форма'].map((shape, i) => (
                            <button key={shape} onClick={() => handleAddSection('ЦС', { csShape: shape })}
                              className={`py-2 font-bold text-[11px] transition-all
                                ${i % 2 === 0 ? 'border-r border-[#2a4a7a]/25' : ''}
                                ${i < 2 ? 'border-b border-[#2a4a7a]/25' : ''}
                                ${SYSTEM_PICKER_COLORS['ЦС']}`}>
                              {shape}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                    {/* КОМПЛЕКТАЦИЯ */}
                    <button onClick={() => handleAddSection('КОМПЛЕКТАЦИЯ')}
                      className={`py-2.5 rounded-xl border font-bold text-[11px] transition-all ${SYSTEM_PICKER_COLORS['КОМПЛЕКТАЦИЯ']}`}>
                      КОМПЛЕКТАЦИЯ
                    </button>
                  </div>
                  <div className="h-px bg-[#2a7a8a]/20" />
                </motion.div>
              )}
            </AnimatePresence>

            <div className="space-y-2">
              {sections.map(section => (
                <motion.div key={section.id} layoutId={section.id}
                  onClick={() => requestNavigate(section.id)}
                  className={`relative group p-4 rounded-2xl border transition-all cursor-pointer ${
                    activeSectionId === section.id
                      ? 'bg-[#2a7a8a]/20 border-[#4fd1c5]/50 shadow-lg shadow-[#4fd1c5]/5'
                      : 'bg-white/[0.02] border-[#2a7a8a]/10 hover:border-[#2a7a8a]/40'
                  }`}
                >
                  <div className="flex justify-between items-start mb-2">
                    <span className={`text-sm font-bold leading-snug ${activeSectionId === section.id ? 'text-[#4fd1c5]' : 'text-white/80'}`}>
                      {section.name}
                    </span>
                    <button onClick={e => { e.stopPropagation(); setSectionToDelete(section); setIsDeleteModalOpen(true); }}
                      className="p-1 rounded-lg hover:bg-red-500/20 text-red-400 opacity-0 group-hover:opacity-100 transition-all flex-shrink-0 ml-1">
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                  {/* Тип */}
                  <div className="flex items-center gap-1.5 mb-1.5 flex-wrap">
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold border ${SYSTEM_COLORS[section.system]}`}>
                      {section.system}
                    </span>
                    {getSectionTypeLabel(section) && (
                      <span className="text-[11px] text-white/40 font-medium">{getSectionTypeLabel(section)}</span>
                    )}
                  </div>
                  {/* Размеры + цвет */}
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-[11px] font-mono text-white/35">{section.width} × {section.height} мм</span>
                    {getSectionColorLabel(section) && (
                      <span className="text-[11px] text-white/35">{getSectionColorLabel(section)}</span>
                    )}
                  </div>
                </motion.div>
              ))}
              {sections.length === 0 && !showSystemPicker && (
                <div className="text-center py-8 text-white/20 text-xs">Нажмите + чтобы добавить секцию</div>
              )}
            </div>

            {/* Sidebar project notes — collapsible */}
            <div className="mt-5 pt-4 border-t border-[#2a7a8a]/20">
              <button
                onClick={() => setNotesOpen(v => !v)}
                className="flex items-center justify-between w-full group mb-0"
              >
                <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#4fd1c5]/40 group-hover:text-[#4fd1c5]/70 transition-colors">
                  Примечания
                </span>
                <span className={`text-[#4fd1c5]/30 group-hover:text-[#4fd1c5]/60 transition-all ${notesOpen ? 'rotate-180' : ''} duration-200`}>
                  <ChevronRight className="w-3.5 h-3.5 rotate-90" />
                </span>
              </button>
              <AnimatePresence initial={false}>
                {notesOpen && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.2, ease: 'easeInOut' }}
                    className="overflow-hidden"
                  >
                    <div className="space-y-2.5 pt-3">
                      <div>
                        <label className="text-[10px] text-white/25 uppercase tracking-wider block mb-1.5">Доп. комплектующие</label>
                        <textarea
                          value={projectExtraParts}
                          onChange={e => setProjectExtraParts(e.target.value)}
                          onBlur={handleSaveProjectNotes}
                          rows={2}
                          placeholder="..."
                          className="w-full bg-white/[0.02] border border-[#2a7a8a]/20 rounded-xl px-3 py-2 text-[11px] text-white/60 placeholder-white/15 resize-none focus:outline-none focus:border-[#4fd1c5]/40 transition-colors"
                        />
                      </div>
                      <div>
                        <label className="text-[10px] text-white/25 uppercase tracking-wider block mb-1.5">Комментарии</label>
                        <textarea
                          value={projectComments}
                          onChange={e => setProjectComments(e.target.value)}
                          onBlur={handleSaveProjectNotes}
                          rows={2}
                          placeholder="..."
                          className="w-full bg-white/[0.02] border border-[#2a7a8a]/20 rounded-xl px-3 py-2 text-[11px] text-white/60 placeholder-white/15 resize-none focus:outline-none focus:border-[#4fd1c5]/40 transition-colors"
                        />
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>

          {/* Mobile: go to editor button */}
          {activeSectionId && (
            <div className="sm:hidden p-3 border-t border-[#2a7a8a]/20 flex-shrink-0">
              <button onClick={() => setMobileSidebarOpen(false)}
                className="w-full py-3 rounded-xl bg-[#2a7a8a]/20 border border-[#2a7a8a]/40 text-[#4fd1c5] font-bold text-sm flex items-center justify-center gap-2">
                <ChevronRight className="w-4 h-4" /> Редактировать
              </button>
            </div>
          )}

        </aside>

        {/* Right: editor */}
        <main className={`flex-1 overflow-y-auto bg-[#0c1d2d]/50 ${mobileSidebarOpen ? 'hidden sm:block' : 'block'}`}>
          <AnimatePresence mode="wait">
            {!activeSection ? (
              <motion.div key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                className="p-4 sm:p-8 max-w-3xl mx-auto w-full">

                {/* Production stages badge + Stage selector */}
                {productionStages === 2 && (
                  <div className="flex items-center gap-3 mb-6">
                    <span className="text-xs font-bold text-amber-300/70 border border-amber-500/20 bg-amber-500/5 rounded-xl px-3 py-1.5">
                      Производство в 2 этапа
                    </span>
                    <div className="flex gap-2">
                      {([1, 2] as const).map(n => (
                        <button key={n} onClick={() => { setCurrentStage(n); saveStatus({ current_stage: n }); }}
                          className={`px-4 py-1.5 rounded-xl border font-bold text-sm transition-all ${
                            currentStage === n
                              ? 'bg-[#4fd1c5]/15 border-[#4fd1c5]/40 text-[#4fd1c5]'
                              : 'bg-black/10 border-[#2a7a8a]/20 text-white/40 hover:border-[#2a7a8a]/40'
                          }`}>
                          Этап {n}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Status */}
                <div className="bg-[#1a4b54]/40 border border-[#2a7a8a]/30 rounded-2xl p-5 sm:p-6 mb-4">
                  <div className="flex items-center gap-3 mb-4">
                    <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#4fd1c5]/40">Статус</span>
                  </div>
                  <select value={projectStatus} onChange={e => { setProjectStatus(e.target.value); saveStatus({ status: e.target.value }); }} className={SEL}>
                    <option>РАСЧЕТ</option>
                    <option>В работе</option>
                    <option>Запущен в производство</option>
                    <option>Готов</option>
                    <option>Отгружен полностью</option>
                    <option>Отгружен частично</option>
                    <option>Отгружен 1 этап</option>
                    <option>Рекламация</option>
                    <option>Архив</option>
                  </select>
                </div>

                {/* Glass — hidden for 2-stage stage 1 */}
                {!(productionStages === 2 && currentStage === 1) && (
                  <div className="bg-[#1a4b54]/40 border border-[#2a7a8a]/30 rounded-2xl p-5 sm:p-6 mb-4">
                    <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#4fd1c5]/40 block mb-4">Стекла</span>
                    <div className="mb-4">
                      <select value={glassStatus} onChange={e => { setGlassStatus(e.target.value); saveStatus({ glass_status: e.target.value }); }} className={SEL}>
                        <option>Без стекла</option>
                        <option>Стекла заказаны</option>
                        <option>Стекла в цеху</option>
                      </select>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <div className="space-y-1">
                        <label className={LBL}>Счёт №</label>
                        <input value={glassInvoice} onChange={e => setGlassInvoice(e.target.value)}
                          onBlur={() => saveStatus({ glass_invoice: glassInvoice || undefined })}
                          className={INP} placeholder="Номер счёта" />
                      </div>
                      <div className="space-y-1">
                        <label className={LBL}>Ориентир готовности</label>
                        <input type="date" value={glassReadyDate} onChange={e => { setGlassReadyDate(e.target.value); saveStatus({ glass_ready_date: e.target.value || undefined }); }}
                          className={INP} />
                      </div>
                    </div>
                  </div>
                )}

                {/* Paint */}
                <div className="bg-[#1a4b54]/40 border border-[#2a7a8a]/30 rounded-2xl p-5 sm:p-6 mb-4">
                  <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#4fd1c5]/40 block mb-4">Покраска</span>
                  <div className="mb-4">
                    <select value={paintStatus} onChange={e => { setPaintStatus(e.target.value); saveStatus({ paint_status: e.target.value }); }} className={SEL}>
                      <option>Без покраски</option>
                      <option>Задание на покраску в цеху</option>
                      <option>Отгружен на покраску</option>
                      <option>Получен с покраски</option>
                    </select>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <label className={LBL}>Отгружен на покраску</label>
                      <input type="date" value={paintShipDate} onChange={e => { setPaintShipDate(e.target.value); saveStatus({ paint_ship_date: e.target.value || undefined }); }}
                        className={INP} />
                    </div>
                    <div className="space-y-1">
                      <label className={LBL}>Получен с покраски</label>
                      <input type="date" value={paintReceivedDate} onChange={e => { setPaintReceivedDate(e.target.value); saveStatus({ paint_received_date: e.target.value || undefined }); }}
                        className={INP} />
                    </div>
                  </div>
                </div>

                {/* Order items */}
                <div className="bg-[#1a4b54]/40 border border-[#2a7a8a]/30 rounded-2xl p-5 sm:p-6 mb-4">
                  <div className="flex items-center justify-between mb-4">
                    <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#4fd1c5]/40">Заказ доп. комплектующих</span>
                    <button onClick={addOrderItem}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-[#2a7a8a]/20 border border-[#2a7a8a]/40 text-[#4fd1c5] text-xs font-bold hover:bg-[#2a7a8a]/40 transition-colors">
                      <Plus className="w-3.5 h-3.5" /> Добавить
                    </button>
                  </div>
                  {orderItems.length > 0 && (
                    <div className="space-y-2">
                      <div className="hidden sm:grid grid-cols-[1fr_1fr_120px_120px_32px] gap-2 mb-1">
                        {['Название','Счёт','Оплачен','Доставлен в цех',''].map((h, i) => (
                          <span key={i} className="text-[9px] font-bold uppercase tracking-widest text-white/25">{h}</span>
                        ))}
                      </div>
                      {orderItems.map(item => (
                        <div key={item.id} className="grid grid-cols-1 sm:grid-cols-[1fr_1fr_120px_120px_32px] gap-2 items-center">
                          <input value={item.name} onChange={e => updateOrderItem(item.id,'name',e.target.value)}
                            onBlur={saveOrderItems} placeholder="Название"
                            className="bg-white/[0.04] border border-[#2a7a8a]/20 rounded-xl px-3 py-2 text-xs text-white/70 outline-none focus:border-[#4fd1c5]/40 transition-colors" />
                          <input value={item.invoice} onChange={e => updateOrderItem(item.id,'invoice',e.target.value)}
                            onBlur={saveOrderItems} placeholder="Счёт"
                            className="bg-white/[0.04] border border-[#2a7a8a]/20 rounded-xl px-3 py-2 text-xs text-white/70 outline-none focus:border-[#4fd1c5]/40 transition-colors" />
                          <input type="date" value={item.paidDate} onChange={e => { updateOrderItem(item.id,'paidDate',e.target.value); saveOrderItems(); }}
                            className="bg-white/[0.04] border border-[#2a7a8a]/20 rounded-xl px-3 py-2 text-xs text-white/70 outline-none focus:border-[#4fd1c5]/40 transition-colors" />
                          <input type="date" value={item.deliveredDate} onChange={e => { updateOrderItem(item.id,'deliveredDate',e.target.value); saveOrderItems(); }}
                            className="bg-white/[0.04] border border-[#2a7a8a]/20 rounded-xl px-3 py-2 text-xs text-white/70 outline-none focus:border-[#4fd1c5]/40 transition-colors" />
                          <button onClick={() => removeOrderItem(item.id)}
                            className="flex items-center justify-center w-8 h-8 rounded-lg hover:bg-red-500/20 text-red-400/60 hover:text-red-400 transition-colors">
                            <X className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                  {orderItems.length === 0 && (
                    <p className="text-xs text-white/20 text-center py-4">Нажмите «Добавить» для добавления позиции</p>
                  )}
                </div>

                {/* Notes */}
                <div className="bg-[#1a4b54]/40 border border-[#2a7a8a]/30 rounded-2xl p-5 sm:p-6 mb-4">
                  <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#4fd1c5]/40 mb-5">Примечания к проекту</p>
                  <div className="space-y-4">
                    <div>
                      <label className="text-[11px] text-white/35 uppercase tracking-wider block mb-2">Доп. комплектующие</label>
                      <textarea value={projectExtraParts} onChange={e => setProjectExtraParts(e.target.value)}
                        onBlur={handleSaveProjectNotes} rows={3} placeholder="Перечислите дополнительные комплектующие..."
                        className="w-full bg-white/[0.03] border border-[#2a7a8a]/25 rounded-2xl px-4 py-3 text-sm text-white/70 placeholder-white/20 resize-none focus:outline-none focus:border-[#4fd1c5]/40 transition-colors" />
                    </div>
                    <div>
                      <label className="text-[11px] text-white/35 uppercase tracking-wider block mb-2">Комментарии</label>
                      <textarea value={projectComments} onChange={e => setProjectComments(e.target.value)}
                        onBlur={handleSaveProjectNotes} rows={3} placeholder="Любые дополнительные комментарии..."
                        className="w-full bg-white/[0.03] border border-[#2a7a8a]/25 rounded-2xl px-4 py-3 text-sm text-white/70 placeholder-white/20 resize-none focus:outline-none focus:border-[#4fd1c5]/40 transition-colors" />
                    </div>
                  </div>
                </div>

                <button onClick={() => setMobileSidebarOpen(true)}
                  className="sm:hidden mt-4 w-full flex items-center justify-center gap-2 px-6 py-3 bg-white/[0.03] border border-[#2a7a8a]/20 hover:bg-[#2a7a8a]/20 text-white/40 hover:text-[#4fd1c5] text-sm font-bold rounded-xl transition-all">
                  <ClipboardList className="w-4 h-4" /> Список секций
                </button>
              </motion.div>
            ) : (
              <motion.div key={activeSection.id} initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }}
                className="p-4 sm:p-8 max-w-4xl mx-auto w-full">

                {/* Section title + system badge */}
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-4 sm:mb-5 gap-3">
                  <div>
                    <button onClick={() => requestNavigate(null)}
                      className="flex items-center gap-1.5 text-white/30 hover:text-[#4fd1c5] transition-colors group mb-3 text-xs font-bold uppercase tracking-wider">
                      <ArrowLeft className="w-3.5 h-3.5 group-hover:-translate-x-0.5 transition-transform" />
                      К проекту
                    </button>
                    <h2 className="text-xl sm:text-2xl font-bold mb-1.5">{activeSection.name}</h2>
                    <span className={`px-3 py-1 rounded-lg text-[11px] font-bold border ${SYSTEM_COLORS[activeSection.system]}`}>
                      {activeSection.system === 'СЛАЙД'
                        ? `СЛАЙД стандарт ${activeSection.rails === 5 ? '2 ряда от центра' : '1 ряд'}`
                        : activeSection.system === 'КНИЖКА' && activeSection.bookSubtype
                          ? `КНИЖКА ${activeSection.bookSubtype === 'doors' ? 'с дверями' : activeSection.bookSubtype === 'angle' ? 'с углом' : 'с дверями и углом'}`
                          : activeSection.system === 'ЛИФТ'
                            ? `ЛИФТ · ${activeSection.panels ?? 2} пан.`
                            : activeSection.system === 'ЦС' && activeSection.csShape
                              ? `ЦС · ${activeSection.csShape}`
                              : activeSection.system}
                    </span>
                  </div>
                </div>

                {/* All section content on one page */}
                <div className="bg-[#1a4b54]/40 border border-[#2a7a8a]/35 rounded-2xl sm:rounded-[2rem] p-4 sm:p-6 mb-4">
                  {renderSectionContent()}
                </div>

                {/* SVG schemes (only for СЛАЙД) */}
                {activeSection.system === 'СЛАЙД' && (
                  <>
                    {/* Вид сверху */}
                    <div className="bg-[#1a4b54]/25 border border-[#2a7a8a]/30 rounded-2xl sm:rounded-[2rem] p-4 sm:p-7 mb-4 overflow-x-auto">
                      <div className="flex items-center justify-between mb-5 min-w-[360px]">
                        <h4 className="text-[10px] font-bold uppercase tracking-widest text-[#4fd1c5]/40">Схема · Вид сверху</h4>
                        <span className="text-[10px] text-white/20 font-bold uppercase tracking-widest">
                          {activeSection.rails ?? 3}-рельсовая · {activeSection.panels} пан.
                        </span>
                      </div>
                      <div className="flex justify-center py-4">
                        <SlideSchemeSVG section={activeSection} />
                      </div>
                    </div>

                    {/* Вид из помещения */}
                    <div className="bg-[#1a4b54]/25 border border-[#2a7a8a]/30 rounded-2xl sm:rounded-[2rem] p-4 sm:p-7 mb-6 overflow-x-auto">
                      <div className="flex items-center justify-between mb-4 min-w-[360px]">
                        <h4 className="text-[10px] font-bold uppercase tracking-widest text-[#4fd1c5]/40">Вид из помещения</h4>
                        <span className="text-[10px] text-white/20 font-bold uppercase tracking-widest">
                          {activeSection.panels} пан. · {activeSection.width} × {activeSection.height} мм
                        </span>
                      </div>
                      <div className="flex justify-center py-2">
                        <SlideRoomViewSVG section={activeSection} />
                      </div>
                    </div>
                  </>
                )}

                {/* Actions */}
                <div className="flex gap-4">
                  <button onClick={handleSaveSection} disabled={isSaving}
                    className={`flex-1 py-4 rounded-2xl text-white font-bold transition-all flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed ${
                      isDirty
                        ? 'bg-amber-500 hover:bg-amber-400 shadow-lg shadow-amber-500/20'
                        : 'bg-[#00b894] hover:bg-[#00d1a7] shadow-lg shadow-[#00b894]/20'
                    }`}>
                    {isSaving ? (
                      <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    ) : isDirty ? (
                      <><Save className="w-4 h-4" /> Сохранить изменения</>
                    ) : 'Сохранить секцию'}
                  </button>
                  <button onClick={() => openPreview('Спецификация')}
                    className="flex-1 py-4 rounded-2xl bg-[#2a7a8a]/20 border border-[#2a7a8a]/40 hover:bg-[#2a7a8a]/40 text-[#4fd1c5] font-bold transition-all">
                    СПЕЦИФИКАЦИЯ
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </main>
      </div>

      {/* Delete Section Modal */}
      <AnimatePresence>
        {isDeleteModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => setIsDeleteModalOpen(false)} className="absolute inset-0 bg-black/80 backdrop-blur-sm" />
            <motion.div initial={{ scale: 0.9, opacity: 0, y: 20 }} animate={{ scale: 1, opacity: 1, y: 0 }} exit={{ scale: 0.9, opacity: 0, y: 20 }}
              className="relative w-full max-w-md bg-[#122433] border border-red-500/30 rounded-[2rem] p-6 sm:p-8 shadow-2xl z-10">
              <button onClick={() => setIsDeleteModalOpen(false)} className="absolute right-6 top-6 text-white/20 hover:text-white transition-colors">
                <X className="w-6 h-6" />
              </button>
              <div className="w-16 h-16 rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center mb-6">
                <Trash2 className="w-8 h-8 text-red-400" />
              </div>
              <h2 className="text-2xl font-bold mb-2">Удалить секцию?</h2>
              <p className="text-white/60 leading-relaxed mb-8">
                Секция <span className="text-white font-bold">{sectionToDelete?.name}</span> будет удалена безвозвратно.
              </p>
              <div className="flex gap-4">
                <button onClick={() => setIsDeleteModalOpen(false)} className="flex-1 py-4 rounded-2xl bg-white/5 hover:bg-white/10 font-bold transition-all">Отмена</button>
                <button onClick={handleDeleteSection} className="flex-1 py-4 rounded-2xl bg-red-500 hover:bg-red-400 text-white font-bold transition-all">Удалить</button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Unsaved Changes Modal */}
      <AnimatePresence>
        {unsavedModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => { setUnsavedModalOpen(false); setPendingNavTarget(null); }}
              className="absolute inset-0 bg-black/80 backdrop-blur-sm" />
            <motion.div initial={{ scale: 0.9, opacity: 0, y: 20 }} animate={{ scale: 1, opacity: 1, y: 0 }} exit={{ scale: 0.9, opacity: 0, y: 20 }}
              className="relative w-full max-w-md bg-[#122433] border border-amber-500/30 rounded-[2rem] p-6 sm:p-8 shadow-2xl z-10">
              <div className="w-16 h-16 rounded-2xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center mb-6">
                <Save className="w-8 h-8 text-amber-400" />
              </div>
              <h2 className="text-2xl font-bold mb-2">Несохранённые изменения</h2>
              <p className="text-white/60 leading-relaxed mb-8">
                Секция <span className="text-white font-bold">{activeSection?.name}</span> содержит несохранённые изменения.
              </p>
              <div className="flex gap-3 flex-col sm:flex-row">
                <button onClick={() => { setUnsavedModalOpen(false); setPendingNavTarget(null); }}
                  className="flex-1 py-3 rounded-2xl bg-white/5 hover:bg-white/10 font-bold transition-all text-sm">
                  Остаться
                </button>
                <button onClick={confirmUnsavedDiscard}
                  className="flex-1 py-3 rounded-2xl bg-white/5 hover:bg-white/10 font-bold transition-all text-sm text-white/50">
                  Не сохранять
                </button>
                <button onClick={confirmUnsavedSave} disabled={isSaving}
                  className="flex-1 py-3 rounded-2xl bg-amber-500 hover:bg-amber-400 text-white font-bold transition-all text-sm disabled:opacity-60 flex items-center justify-center gap-2">
                  {isSaving
                    ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    : <><Save className="w-4 h-4" /> Сохранить</>
                  }
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Document Preview Modal */}
      <AnimatePresence>
        {isPreviewModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => setIsPreviewModalOpen(false)} className="absolute inset-0 bg-black/80 backdrop-blur-sm" />
            <motion.div initial={{ scale: 0.9, opacity: 0, y: 20 }} animate={{ scale: 1, opacity: 1, y: 0 }} exit={{ scale: 0.9, opacity: 0, y: 20 }}
              className="relative w-full max-w-4xl bg-[#1a4b54] border border-[#2a7a8a]/30 rounded-2xl sm:rounded-[2.5rem] shadow-2xl overflow-hidden flex flex-col max-h-[95vh] z-10">
              <div className="px-5 py-5 sm:px-10 sm:py-7 border-b border-[#2a7a8a]/20 flex items-center justify-between flex-shrink-0">
                <h2 className="text-2xl font-bold">{previewDocName}</h2>
                <button onClick={() => setIsPreviewModalOpen(false)} className="text-white/20 hover:text-white transition-colors">
                  <X className="w-6 h-6" />
                </button>
              </div>
              <div className="flex-1 p-4 sm:p-10 overflow-y-auto bg-black/20">
                <div className="aspect-[1/1.414] w-full bg-white rounded-lg shadow-inner p-5 sm:p-12 text-black flex flex-col">
                  <div className="flex justify-between items-start border-b-2 border-black pb-8 mb-8">
                    <div>
                      <h1 className="text-4xl font-black uppercase tracking-tighter">Ралюма</h1>
                      <p className="text-xs font-bold uppercase tracking-widest text-black/40">
                        {previewDocName} · {activeSection?.system ?? '—'}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-bold">Проект № {project.number}</p>
                      <p className="text-xs text-black/60">{project.customer}</p>
                      <p className="text-xs text-black/40">{new Date().toLocaleDateString('ru-RU')}</p>
                    </div>
                  </div>
                  <div className="flex-1 border-2 border-dashed border-black/10 rounded-xl flex items-center justify-center">
                    <div className="text-center">
                      <FileText className="w-16 h-16 text-black/10 mx-auto mb-4" />
                      <p className="text-sm font-medium text-black/40">Визуализация в разработке</p>
                      <p className="text-xs text-black/20 mt-1">{sections.length} секц. · {activeSection ? activeSection.name : '—'}</p>
                    </div>
                  </div>
                </div>
              </div>
              <div className="px-5 py-4 sm:px-10 sm:py-6 bg-black/40 border-t border-[#2a7a8a]/20 flex justify-end gap-4 flex-shrink-0">
                <button onClick={() => setIsPreviewModalOpen(false)} className="px-8 py-3 rounded-xl bg-white/5 hover:bg-white/10 font-bold transition-all">Закрыть</button>
                <button className="px-8 py-3 rounded-xl bg-[#00b894] hover:bg-[#00d1a7] text-white font-bold transition-all">
                  <ArrowRight className="w-4 h-4 inline mr-2" />Скачать PDF
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
};
