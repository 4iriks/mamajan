import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import type { SlideCalcPreview } from '../src/api/projects';
import { SlideRoomViewSVG, SlideSchemeSVG } from '../src/components/editor/SlideDiagrams';
import type { Section } from '../src/components/editor/types';

const section: Section = {
  id: 'diagram-smoke',
  name: 'Секция',
  system: 'СЛАЙД',
  width: 2000,
  height: 2400,
  panels: 4,
  quantity: 1,
  glassType: 'Стекло 10мм',
  paintingType: 'Анодированный',
  cornerLeft: false,
  cornerRight: false,
  rails: 3,
  threshold: 'Стандартный анод',
  firstPanelInside: 'Справа',
  interGlassProfile: 'Алюминиевый RS2061',
  floorLatchesLeft: false,
  floorLatchesRight: false,
  profileLeftWall: true,
  profileLeftLockBar: false,
  profileLeftPBar: false,
  profileLeftHandleBar: true,
  profileLeftBubble: false,
  profileRightWall: true,
  profileRightLockBar: true,
  profileRightPBar: false,
  profileRightHandleBar: false,
  profileRightBubble: false,
  handleLeft: 'Без',
  handleRight: 'Без',
  lockLeft: 'Без',
  lockRight: 'Без',
};

const calc: SlideCalcPreview = {
  glass: [
    { position: 'Крайние', width_mm: 520, height_mm: 2294, qty: 2, glass_profile_length: 2244 },
    { position: 'Промежуточные', width_mm: 470, height_mm: 2294, qty: 2, glass_profile_length: 2244 },
  ],
  profiles: [
    { article: 'RS1313', name: 'Верхний направляющий профиль 3-рельсовый', length_mm: 2000, qty: 1, painted: true, section_width_mm: 72, section_height_mm: 53, paint_mode: 'Красится', color_variants: ['Анод'], paint_note: '' },
    { article: 'RS2323', name: 'Порог 3-рельсовый', length_mm: 2000, qty: 1, painted: false, section_width_mm: 76, section_height_mm: 23, paint_mode: 'Частично', color_variants: ['Анод'], paint_note: 'НЕ КРАСИТЬ!!!' },
    { article: 'RS2333', name: 'Пристеночный профиль 3-рельсовый', length_mm: 2400, qty: 2, painted: true, section_width_mm: 76, section_height_mm: 16, paint_mode: 'Красится', color_variants: ['Анод'], paint_note: '' },
    { article: 'RS112', name: 'Профиль-ручка', length_mm: 2250, qty: 1, painted: true, section_width_mm: 52, section_height_mm: 40, paint_mode: 'Красится', color_variants: ['Анод'], paint_note: '' },
    { article: 'RS2081', name: 'Боковой П-образный профиль-замок', length_mm: 2250, qty: 1, painted: true, section_width_mm: 57, section_height_mm: 25, paint_mode: 'Красится', color_variants: ['Анод'], paint_note: 'КРАСИТЬ ВЕСЬ ПЕРИМЕТР' },
    { article: 'RS2061', name: 'Межстекольный профиль', length_mm: 2250, qty: 3, painted: true, section_width_mm: 20, section_height_mm: 12, paint_mode: 'Красится', color_variants: ['Анод'], paint_note: '' },
  ],
  panel_rails: [0, 1, 2, 0],
};

const roomMarkup = renderToStaticMarkup(<SlideRoomViewSVG section={section} calc={calc} />);
const schemeMarkup = renderToStaticMarkup(<SlideSchemeSVG section={section} calc={calc} />);

const renderedWidths = [...roomMarkup.matchAll(/width="([^"]+)"/g)]
  .map(match => Number(match[1]))
  .filter(Number.isFinite);

assert(renderedWidths.some(width => width === 175), 'room view must keep 2000x2400 proportions');
assert(!renderedWidths.some(width => width === 400), 'room view must not use the old fixed 400px frame width');
assert.match(roomMarkup, />53</, 'room view must render top profile size from catalog metadata');
assert.match(roomMarkup, />23</, 'room view must render threshold size from catalog metadata');
assert.match(schemeMarkup, />16</, 'top scheme must show wall profile thickness');
assert.doesNotMatch(schemeMarkup, /RS112|RS2081/, 'top scheme must not render old side profile stack');
assert.match(schemeMarkup, /stroke-linecap="round"/, 'top scheme must render the mirrored inter-glass profile path');

const sectionTwoRows: Section = {
  ...section,
  id: 'diagram-smoke-2row',
  panels: 4,
  slideRows: 2,
  firstPanelInside: undefined,
  unusedTrack: 'Внешний',
  centerHandle: 'Ручка-кноб RS3014',
  centerLock: 'Замок стекло-стекло RS30301',
  centerFloorLatchesLeft: true,
  centerFloorLatchesRight: true,
};

const calcTwoRows: SlideCalcPreview = {
  glass: [
    { position: 'Левое', width_mm: 520, height_mm: 2294, qty: 1, glass_profile_length: 520 },
    { position: 'Центральные', width_mm: 500.1, height_mm: 2294, qty: 2, glass_profile_length: 497 },
    { position: 'Правое', width_mm: 530, height_mm: 2294, qty: 1, glass_profile_length: 530 },
  ],
  profiles: calc.profiles,
  panel_rails: [1, 2, 2, 1],
};

const roomMarkupTwoRows = renderToStaticMarkup(<SlideRoomViewSVG section={sectionTwoRows} calc={calcTwoRows} />);
const schemeMarkupTwoRows = renderToStaticMarkup(<SlideSchemeSVG section={sectionTwoRows} calc={calcTwoRows} />);

assert.match(roomMarkupTwoRows, />501</, '2-row room view must render central glass widths rounded up');
assert.match(schemeMarkupTwoRows, /501 · №2/, '2-row top scheme must render left central panel with calculated width rounded up');
assert.match(schemeMarkupTwoRows, /501 · №3/, '2-row top scheme must render right central panel with calculated width rounded up');
assert.match(schemeMarkupTwoRows, /data-dir="1"/, '2-row top scheme must mirror left-side inter-glass profile');
assert.match(schemeMarkupTwoRows, /data-dir="-1"/, '2-row top scheme must mirror right-side inter-glass profile');
assert.match(schemeMarkupTwoRows, />сдвиг</, '2-row top scheme must render bidirectional shift label');

console.log('slide diagram smoke passed');
