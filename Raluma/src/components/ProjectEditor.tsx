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
import { getProject, createSection, updateSection, deleteSection, SectionOut } from '../api/projects';
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
  paintingType: 'RAL стандарт' | 'RAL нестандарт' | 'Анодированный' | 'Без окрашивания';
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
}

interface ProjectEditorProps {
  projectId: number;
  onBack: () => void;
}

// ── Style constants ───────────────────────────────────────────────────────────

const LBL = 'text-[10px] font-bold uppercase tracking-widest text-[#4fd1c5]/40 ml-1';
const INP = 'w-full bg-white/8 border border-[#2a7a8a]/30 rounded-xl px-4 py-3 outline-none focus:border-[#4fd1c5]/50 transition-all font-mono text-white';
const SEL = 'w-full bg-white/8 border border-[#2a7a8a]/30 rounded-xl px-4 py-3 outline-none focus:border-[#4fd1c5]/50 transition-all appearance-none text-white';

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
    doors: s.doors, door_side: s.doorSide, door_type: s.doorType,
    door_opening: s.doorOpening, compensator: s.compensator,
    angle_left: s.angleLeft, angle_right: s.angleRight, book_system: s.bookSystem,
    door_system: s.doorSystem, cs_shape: s.csShape, cs_width2: s.csWidth2,
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
          className={`flex-1 py-2.5 rounded-xl border font-bold text-xs transition-all min-w-0 ${
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
            className={`w-full text-left px-4 py-2.5 rounded-xl border transition-all text-xs ${
              active ? 'bg-[#4fd1c5]/10 border-[#4fd1c5]/50 text-[#4fd1c5]' : 'border-[#2a7a8a]/20 bg-black/10 text-white/40 hover:border-[#4fd1c5]/30'
            }`}
          >{opt}</button>
        );
      })}
    </div>
  );
}

// ── Section divider ───────────────────────────────────────────────────────────

function SectionDivider({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3 pt-2">
      <span className="text-[10px] font-bold uppercase tracking-widest text-[#4fd1c5]/40 whitespace-nowrap">{label}</span>
      <div className="flex-1 h-px bg-[#2a7a8a]/20" />
    </div>
  );
}

// ── Tab: Основное (общая для всех систем) ────────────────────────────────────

function MainTab({ s, update }: { s: Section; update: (u: Partial<Section>) => void }) {
  return (
    <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 sm:gap-8">
      <div className="space-y-5">
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className={LBL}>Название</label>
            <input value={s.name} onChange={e => update({ name: e.target.value })} className={INP} />
          </div>
          <div className="space-y-2">
            <label className={LBL}>Кол-во, шт</label>
            <input type="number" min="1" value={s.quantity} onChange={e => update({ quantity: parseInt(e.target.value) || 1 })} className={INP} />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className={LBL}>Ширина, мм</label>
            <input type="number" value={s.width} onChange={e => update({ width: parseInt(e.target.value) || 0 })} className={INP} />
          </div>
          <div className="space-y-2">
            <label className={LBL}>Высота, мм</label>
            <input type="number" value={s.height} onChange={e => update({ height: parseInt(e.target.value) || 0 })} className={INP} />
          </div>
        </div>
        <div className="space-y-2">
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
      </div>
      <div className="space-y-5">
        <div className="space-y-2">
          <label className={LBL}>Окрашивание</label>
          <div className="space-y-1.5">
            {(['RAL стандарт', 'RAL нестандарт', 'Анодированный', 'Без окрашивания'] as const).map(type => (
              <button key={type} onClick={() => update({ paintingType: type })}
                className={`flex items-center gap-3 w-full px-4 py-2.5 rounded-xl border transition-all text-left ${
                  s.paintingType === type ? 'bg-[#4fd1c5]/10 border-[#4fd1c5]/50 text-[#4fd1c5]' : 'bg-black/10 border-[#2a7a8a]/20 text-white/40 hover:border-[#2a7a8a]/50'
                }`}
              >
                <div className={`w-4 h-4 rounded-full border flex items-center justify-center flex-shrink-0 ${s.paintingType === type ? 'border-[#4fd1c5]' : 'border-white/10'}`}>
                  {s.paintingType === type && <div className="w-2 h-2 rounded-full bg-[#4fd1c5]" />}
                </div>
                <span className="text-xs font-medium">{type}</span>
              </button>
            ))}
          </div>
        </div>
        {s.paintingType.includes('RAL') && (
          <div className="space-y-2">
            <label className={LBL}>Цвет RAL</label>
            <input type="text" value={s.ralColor || ''} onChange={e => update({ ralColor: e.target.value })} className={INP} placeholder="Напр. 9016" />
          </div>
        )}
      </div>
    </div>
  );
}

// ── Tab: СЛАЙД — Система ─────────────────────────────────────────────────────

function SlideSystemTab({ s, update }: { s: Section; update: (u: Partial<Section>) => void }) {
  return (
    <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 sm:gap-8">
      <div className="space-y-5">
        <div className="space-y-2">
          <label className={LBL}>Рельсы</label>
          <ToggleGroup value={s.rails?.toString()} options={['3', '5']}
            onChange={v => update({ rails: parseInt(v) as 3 | 5 })} />
        </div>
        <div className="space-y-2">
          <label className={LBL}>Кол-во панелей</label>
          <select value={s.panels} onChange={e => update({ panels: parseInt(e.target.value) })} className={SEL}>
            {[1, 2, 3, 4, 5].map(n => <option key={n} value={n}>{n}</option>)}
          </select>
        </div>
        <div className="space-y-2">
          <label className={LBL}>1-я панель внутри</label>
          <ToggleGroup value={s.firstPanelInside} options={['Слева', 'Справа']}
            onChange={v => update({ firstPanelInside: v })} />
        </div>
        <div className="space-y-2">
          <label className={LBL}>Свободная нить</label>
          <ToggleGroup value={s.unusedTrack ?? 'Нет'} options={['Внешняя', 'Внутренняя', 'Нет']}
            onChange={v => update({ unusedTrack: v === 'Нет' ? undefined : v })} />
        </div>
        <div className="space-y-2">
          <label className={LBL}>Порог</label>
          <select value={s.threshold || ''} onChange={e => update({ threshold: e.target.value || undefined })} className={SEL}>
            <option value="">— Без порога —</option>
            <option>Стандартный анод</option>
            <option>Стандартный окраш</option>
            <option>Накладной анод</option>
            <option>Накладной окраш</option>
          </select>
        </div>
      </div>
      <div className="space-y-5">
        <div className="space-y-2">
          <label className={LBL}>Межстекольный профиль</label>
          <select value={s.interGlassProfile || ''} onChange={e => update({ interGlassProfile: e.target.value || undefined })} className={SEL}>
            <option value="">— Нет —</option>
            <option>Алюминиевый RS1061</option>
            <option>Прозрачный</option>
            <option>h-профиль RS1004</option>
          </select>
        </div>
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
          <label className={LBL}>Угловое соединение</label>
          <div className="flex gap-6 mt-1">
            <Checkbox checked={s.cornerLeft} onChange={() => update({ cornerLeft: !s.cornerLeft })} label="Левое" />
            <Checkbox checked={s.cornerRight} onChange={() => update({ cornerRight: !s.cornerRight })} label="Правое" />
          </div>
        </div>
        {(s.cornerLeft || s.cornerRight) && (
          <div className="space-y-2">
            <label className={LBL}>Внешняя ширина, мм</label>
            <input type="number" value={s.externalWidth || ''} onChange={e => update({ externalWidth: parseFloat(e.target.value) || undefined })} className={INP} placeholder="мм" />
          </div>
        )}
      </div>
    </div>
  );
}

// ── Tab: СЛАЙД — Фурнитура ───────────────────────────────────────────────────

function SlideHardwareTab({ s, update }: { s: Section; update: (u: Partial<Section>) => void }) {
  return (
    <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 sm:gap-8">
      <div className="space-y-5">
        <div className="space-y-2">
          <label className={LBL}>Замок</label>
          <RadioList value={s.lock} noneLabel="Без замка"
            options={['RS3018 Замок-защёлка 1-ст.', 'RS3019 Замок-защёлка 2-ст. с ключом']}
            onChange={v => update({ lock: v })} />
        </div>
        <div className="space-y-2">
          <label className={LBL}>Ручка</label>
          <RadioList value={s.handle} noneLabel="Без ручки"
            options={['RS3014 Ручка-кноб', 'RS3017 Стеклянная ручка', 'Ручка-скоба']}
            onChange={v => update({ handle: v })} />
        </div>
      </div>
      <div className="space-y-5">
        <div className="space-y-2">
          <label className={LBL}>Напольные защёлки</label>
          <div className="flex gap-6 mt-1">
            <Checkbox checked={s.floorLatchesLeft} onChange={() => update({ floorLatchesLeft: !s.floorLatchesLeft })} label="Левая" />
            <Checkbox checked={s.floorLatchesRight} onChange={() => update({ floorLatchesRight: !s.floorLatchesRight })} label="Правая" />
          </div>
        </div>
        {s.lock && (
          <div className="space-y-2">
            <label className={LBL}>Отступ ручки, мм</label>
            <input type="number" value={s.handleOffset || ''} onChange={e => update({ handleOffset: parseInt(e.target.value) || undefined })} className={INP} placeholder="мм от края" />
          </div>
        )}
      </div>
    </div>
  );
}

// ── Tab: КНИЖКА — Система ────────────────────────────────────────────────────

function BookSystemTab({ s, update }: { s: Section; update: (u: Partial<Section>) => void }) {
  return (
    <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 sm:gap-8">
      <div className="space-y-5">
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
      </div>
      <div className="space-y-5">
        <div className="space-y-2">
          <label className={LBL}>Кол-во панелей</label>
          <select value={s.panels} onChange={e => update({ panels: parseInt(e.target.value) })} className={SEL}>
            {[2, 3, 4, 5, 6].map(n => <option key={n} value={n}>{n}</option>)}
          </select>
        </div>
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
  const { panels, rails = 3, firstPanelInside = 'Справа' } = section;
  const railCount = rails as number;
  const H = 20 + railCount * 22 + 20;
  const trackYs = Array.from({ length: railCount }, (_, i) => 30 + i * 22);
  const panelW = 330 / panels;

  return (
    <svg width="400" height={H} viewBox={`0 0 400 ${H}`} className="drop-shadow-[0_0_15px_rgba(79,209,197,0.1)]">
      {trackYs.map((y, i) => (
        <line key={i} x1="20" y1={y} x2="380" y2={y} stroke="#2a7a8a" strokeWidth="1.5" strokeDasharray="6 4" opacity="0.7" />
      ))}
      <rect x="14" y={trackYs[0] - 8} width="6" height={trackYs[trackYs.length - 1] - trackYs[0] + 16} rx="2" fill="#2a7a8a" opacity="0.5" />
      <rect x="380" y={trackYs[0] - 8} width="6" height={trackYs[trackYs.length - 1] - trackYs[0] + 16} rx="2" fill="#2a7a8a" opacity="0.5" />
      {Array.from({ length: panels }).map((_, i) => {
        const trackIdx = i % railCount;
        const y = trackYs[trackIdx];
        const x = 25 + i * panelW;
        const num = firstPanelInside === 'Слева' ? i + 1 : panels - i;
        return (
          <g key={i}>
            <rect x={x} y={y - 7} width={panelW - 6} height="14" rx="3"
              fill="#4fd1c5" fillOpacity="0.15" stroke="#4fd1c5" strokeWidth="1.5" />
            <text x={x + (panelW - 6) / 2} y={y + 4} textAnchor="middle" fontSize="9" fill="#4fd1c5" fontWeight="bold">
              {num}
            </text>
          </g>
        );
      })}
      <g transform={`translate(${firstPanelInside === 'Справа' ? 340 : 40}, ${trackYs[Math.floor(railCount / 2)] + 14})`}>
        <text fontSize="8" fill="#4fd1c5" opacity="0.5" textAnchor={firstPanelInside === 'Справа' ? 'end' : 'start'}>
          {firstPanelInside === 'Справа' ? '◀ сдвиг' : 'сдвиг ▶'}
        </text>
      </g>
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
  const [showSystemPicker, setShowSystemPicker] = useState(false);
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

  const defaultsForSystem = (system: SystemType): Partial<Section> => {
    switch (system) {
      case 'СЛАЙД':  return { rails: 3, firstPanelInside: 'Справа', panels: 3 };
      case 'КНИЖКА': return { doors: 1, doorSide: 'Правая', panels: 3 };
      case 'ЛИФТ':   return { panels: 2 };
      case 'ЦС':     return { csShape: 'Прямоугольник', panels: 1 };
      case 'КОМПЛЕКТАЦИЯ': return { panels: 1, doorSystem: 'Одностворчатая', doorOpening: 'Внутрь' };
    }
  };

  const handleAddSection = async (system: SystemType) => {
    if (!project) return;
    setShowSystemPicker(false);
    const newSection: Section = {
      id: `tmp-${Date.now()}`,
      name: `Секция ${sections.length + 1}`,
      system,
      width: 2000, height: 2400, panels: 3, quantity: 1,
      glassType: '10ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ',
      paintingType: 'RAL стандарт', ralColor: '9016',
      cornerLeft: false, cornerRight: false,
      floorLatchesLeft: false, floorLatchesRight: false,
      ...defaultsForSystem(system),
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

  const handleDeleteSection = async () => {
    if (!sectionToDelete || !project) return;
    try {
      const sectionId = parseInt(sectionToDelete.id);
      if (!isNaN(sectionId)) await deleteSection(project.id, sectionId);
    } catch (e: any) {
      toast.error(e.response?.data?.detail || 'Не удалось удалить секцию');
    }
    setSections(sections.filter(s => s.id !== sectionToDelete.id));
    if (activeSectionId === sectionToDelete.id) setActiveSectionId(null);
    setIsDeleteModalOpen(false);
    setSectionToDelete(null);
  };

  const openPreview = (name: string) => { setPreviewDocName(name); setIsPreviewModalOpen(true); };

  // Рендер всего содержимого секции на одной странице
  const renderSectionContent = () => {
    if (!activeSection) return null;
    return (
      <div className="space-y-8">
        <div>
          <SectionDivider label="Основное" />
          <div className="mt-5">
            <MainTab s={activeSection} update={updateActiveSection} />
          </div>
        </div>

        {activeSection.system === 'СЛАЙД' && (
          <>
            <div>
              <SectionDivider label="Система" />
              <div className="mt-5">
                <SlideSystemTab s={activeSection} update={updateActiveSection} />
              </div>
            </div>
            <div>
              <SectionDivider label="Фурнитура" />
              <div className="mt-5">
                <SlideHardwareTab s={activeSection} update={updateActiveSection} />
              </div>
            </div>
          </>
        )}

        {activeSection.system === 'КНИЖКА' && (
          <div>
            <SectionDivider label="Система" />
            <div className="mt-5">
              <BookSystemTab s={activeSection} update={updateActiveSection} />
            </div>
          </div>
        )}

        {activeSection.system === 'ЛИФТ' && (
          <div>
            <SectionDivider label="Система" />
            <div className="mt-5">
              <LiftSystemTab s={activeSection} update={updateActiveSection} />
            </div>
          </div>
        )}

        {activeSection.system === 'ЦС' && (
          <div>
            <SectionDivider label="Форма" />
            <div className="mt-5">
              <CsShapeTab s={activeSection} update={updateActiveSection} />
            </div>
          </div>
        )}

        {activeSection.system === 'КОМПЛЕКТАЦИЯ' && (
          <div>
            <SectionDivider label="Система" />
            <div className="mt-5">
              <DoorSystemTab s={activeSection} update={updateActiveSection} />
            </div>
          </div>
        )}
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

        {/* Center: document buttons */}
        <div className="hidden md:flex items-center gap-1 flex-1 justify-center">
          {[
            { name: 'Произв. лист', icon: FileText },
            { name: 'Накладная', icon: ClipboardList },
            { name: 'Заказ стекла', icon: WindowIcon },
            { name: 'Заявка покр.', icon: Palette },
          ].map(doc => (
            <button key={doc.name} onClick={() => openPreview(doc.name)}
              className="flex items-center gap-2 px-3 py-2 rounded-xl bg-white/[0.03] border border-white/[0.06] hover:bg-[#2a7a8a]/20 hover:border-[#2a7a8a]/40 transition-all group">
              <doc.icon className="w-3.5 h-3.5 text-[#4fd1c5]/50 group-hover:text-[#4fd1c5] transition-colors flex-shrink-0" />
              <span className="text-[11px] font-bold text-white/40 group-hover:text-white transition-colors whitespace-nowrap">{doc.name}</span>
            </button>
          ))}
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
                  <div className="grid grid-cols-2 gap-2 pt-1 pb-3">
                    {(['СЛАЙД', 'КНИЖКА', 'ЛИФТ', 'ЦС', 'КОМПЛЕКТАЦИЯ'] as SystemType[]).map(sys => (
                      <button
                        key={sys}
                        onClick={() => handleAddSection(sys)}
                        className={`py-2.5 rounded-xl border font-bold text-[11px] transition-all ${SYSTEM_PICKER_COLORS[sys]}`}
                      >
                        {sys}
                      </button>
                    ))}
                  </div>
                  <div className="h-px bg-[#2a7a8a]/20" />
                </motion.div>
              )}
            </AnimatePresence>

            <div className="space-y-2">
              {sections.map(section => (
                <motion.div key={section.id} layoutId={section.id}
                  onClick={() => setActiveSectionId(section.id)}
                  className={`relative group p-4 rounded-2xl border transition-all cursor-pointer ${
                    activeSectionId === section.id
                      ? 'bg-[#2a7a8a]/20 border-[#4fd1c5]/50 shadow-lg shadow-[#4fd1c5]/5'
                      : 'bg-white/[0.02] border-[#2a7a8a]/10 hover:border-[#2a7a8a]/40'
                  }`}
                >
                  <div className="flex justify-between items-start mb-2">
                    <span className={`text-sm font-bold ${activeSectionId === section.id ? 'text-[#4fd1c5]' : 'text-white/80'}`}>
                      {section.name}
                    </span>
                    <button onClick={e => { e.stopPropagation(); setSectionToDelete(section); setIsDeleteModalOpen(true); }}
                      className="p-1 rounded-lg hover:bg-red-500/20 text-red-400 opacity-0 group-hover:opacity-100 transition-all flex-shrink-0">
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className={`px-2 py-0.5 rounded-md text-[10px] font-bold border ${SYSTEM_COLORS[section.system]}`}>
                      {section.system}
                    </span>
                    <span className="text-xs font-mono text-white/40">{section.width} × {section.height}</span>
                  </div>
                </motion.div>
              ))}
              {sections.length === 0 && !showSystemPicker && (
                <div className="text-center py-8 text-white/20 text-xs">Нажмите + чтобы добавить секцию</div>
              )}
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
                className="h-full flex flex-col items-center justify-center p-8 sm:p-12 min-h-[60vh]">
                <div className="w-full max-w-sm">
                  <div className="text-center mb-8">
                    <div className="w-16 h-16 rounded-2xl bg-[#2a7a8a]/15 border border-[#2a7a8a]/25 flex items-center justify-center mx-auto mb-5">
                      <Plus className="w-7 h-7 text-[#4fd1c5]/60" />
                    </div>
                    <h3 className="text-xl font-bold mb-1.5">Создать секцию</h3>
                    <p className="text-white/30 text-sm">Выберите систему</p>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    {(['СЛАЙД', 'КНИЖКА', 'ЛИФТ', 'ЦС', 'КОМПЛЕКТАЦИЯ'] as SystemType[]).map(sys => (
                      <button key={sys} onClick={() => handleAddSection(sys)}
                        className={`py-5 rounded-2xl border font-bold text-sm transition-all ${SYSTEM_PICKER_COLORS[sys]} ${sys === 'КОМПЛЕКТАЦИЯ' ? 'col-span-2' : ''}`}>
                        {sys}
                      </button>
                    ))}
                  </div>
                  <button onClick={() => setMobileSidebarOpen(true)}
                    className="sm:hidden mt-4 w-full flex items-center justify-center gap-2 px-6 py-3 bg-white/[0.03] border border-[#2a7a8a]/20 hover:bg-[#2a7a8a]/20 text-white/40 hover:text-[#4fd1c5] text-sm font-bold rounded-xl transition-all">
                    <ClipboardList className="w-4 h-4" /> Список секций
                  </button>
                </div>
              </motion.div>
            ) : (
              <motion.div key={activeSection.id} initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }}
                className="p-4 sm:p-8 max-w-4xl mx-auto w-full">

                {/* Section title + system badge */}
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-5 sm:mb-7 gap-3">
                  <div>
                    <h2 className="text-xl sm:text-2xl font-bold mb-1.5">{activeSection.name}</h2>
                    <span className={`px-3 py-1 rounded-lg text-[11px] font-bold border ${SYSTEM_COLORS[activeSection.system]}`}>
                      {activeSection.system}
                    </span>
                  </div>
                </div>

                {/* All section content on one page */}
                <div className="bg-[#1a4b54]/40 border border-[#2a7a8a]/35 rounded-2xl sm:rounded-[2rem] p-4 sm:p-8 mb-6">
                  {renderSectionContent()}
                </div>

                {/* SVG scheme (only for СЛАЙД) */}
                {activeSection.system === 'СЛАЙД' && (
                  <div className="bg-[#1a4b54]/25 border border-[#2a7a8a]/30 rounded-2xl sm:rounded-[2rem] p-4 sm:p-7 mb-6 overflow-x-auto">
                    <div className="flex items-center justify-between mb-5 min-w-[360px]">
                      <h4 className="text-[10px] font-bold uppercase tracking-widest text-[#4fd1c5]/40">Схема (Вид сверху)</h4>
                      <span className="text-[10px] text-white/20 font-bold uppercase tracking-widest">
                        {activeSection.rails ?? 3}-рельсовая · {activeSection.panels} пан.
                      </span>
                    </div>
                    <div className="flex justify-center py-4">
                      <SlideSchemeSVG section={activeSection} />
                    </div>
                  </div>
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
                  <button onClick={() => openPreview('Производственный лист')}
                    className="flex-1 py-4 rounded-2xl bg-[#2a7a8a]/20 border border-[#2a7a8a]/40 hover:bg-[#2a7a8a]/40 text-[#4fd1c5] font-bold transition-all">
                    Производственный лист
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
