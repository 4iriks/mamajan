import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

import { SlideRoomViewSVG } from '../src/components/editor/SlideDiagrams';
import { SlideSystemTab } from '../src/components/editor/FormTabs';
import {
  SLIDE_HARDWARE_PRESETS,
  SLIDE_ONE_ROW_LAYOUTS,
  SLIDE_TWO_ROW_LAYOUTS,
  slideLayoutUpdates,
} from '../src/components/editor/slidePresets';
import { SlidePresetsPanel } from '../src/components/editor/SlidePresetsPanel';
import type { Section } from '../src/components/editor/types';

const section: Section = {
  id: 'preset-smoke',
  name: 'Секция 1',
  system: 'СЛАЙД',
  width: 2000,
  height: 3000,
  panels: 2,
  quantity: 3,
  glassType: '10ММ БРОНЗА В МАССЕ',
  paintingType: 'RAL стандарт',
  ralColor: '9016 МАТОВЫЙ',
  cornerLeft: false,
  cornerRight: false,
  rails: 3,
  slideRows: 1,
  threshold: 'Стандартный окраш',
  firstPanelInside: 'Справа',
  interGlassProfile: 'Алюминиевый RS2061',
  floorLatchesLeft: false,
  floorLatchesRight: false,
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
  comments: 'Не менять при выборе пресета',
};

assert.equal(SLIDE_ONE_ROW_LAYOUTS.length, 4);
assert.deepEqual(
  SLIDE_ONE_ROW_LAYOUTS.map(item => [item.updates.width, item.updates.panels, item.updates.rails]),
  [[2000, 2, 3], [3000, 3, 3], [4000, 4, 5], [5000, 5, 5]],
);
assert.deepEqual(
  SLIDE_TWO_ROW_LAYOUTS.map(item => [item.updates.width, item.updates.panels, item.updates.rails]),
  [[3500, 4, 3], [5000, 6, 3], [5000, 8, 5], [7000, 10, 5]],
);
assert.equal(SLIDE_HARDWARE_PRESETS.length, 3);

const oneRowMarkup = renderToStaticMarkup(
  <SlidePresetsPanel section={section} onApply={() => undefined} />,
);
assert.equal((oneRowMarkup.match(/data-slide-layout-preset=/g) ?? []).length, 4);
assert.equal((oneRowMarkup.match(/data-slide-hardware-preset=/g) ?? []).length, 0);
assert.equal((oneRowMarkup.match(/data-room-view-mode="compact"/g) ?? []).length, 4);
assert.match(oneRowMarkup, /data-glass-panel="1"/);
assert.doesNotMatch(oneRowMarkup, /data-room-panel-dimension/);
assert.doesNotMatch(oneRowMarkup, /data-room-overall-dimensions/);
assert.doesNotMatch(oneRowMarkup, /Добавить|0\/10|Переименовать|Удалить/);
assert.doesNotMatch(oneRowMarkup, /Быстрый выбор|СЛАЙД · 1 ряд|>Схема</);
assert.doesNotMatch(oneRowMarkup, /2000 × 3000 мм/);

const brace = SLIDE_HARDWARE_PRESETS[1];
const twoRowSection: Section = {
  ...section,
  ...SLIDE_TWO_ROW_LAYOUTS[0].updates,
  ...brace.updates,
};
const twoRowMarkup = renderToStaticMarkup(
  <SlidePresetsPanel section={twoRowSection} onApply={() => undefined} />,
);
assert.equal((twoRowMarkup.match(/data-slide-layout-preset=/g) ?? []).length, 4);
assert.equal((twoRowMarkup.match(/data-slide-hardware-preset=/g) ?? []).length, 3);
assert.equal((twoRowMarkup.match(/data-room-view-mode="compact"/g) ?? []).length, 4);
assert.match(twoRowMarkup, /data-glass-panel="1"/);
assert.doesNotMatch(twoRowMarkup, /data-room-panel-dimension/);
assert.doesNotMatch(twoRowMarkup, /data-room-overall-dimensions/);
assert.doesNotMatch(twoRowMarkup, /Быстрый выбор|СЛАЙД · 2 ряда|>Схема<|>Фурнитура</);
assert.doesNotMatch(twoRowMarkup, /3500 × 3000 мм/);

const layoutUpdates = slideLayoutUpdates(twoRowSection, SLIDE_TWO_ROW_LAYOUTS[2]);
const applied = { ...twoRowSection, ...layoutUpdates };
assert.equal(applied.width, 5000);
assert.equal(applied.panels, 8);
assert.equal(applied.rails, 5);
assert.equal(applied.centerHandle, 'Ручка-скоба 600мм RS30201');
assert.equal(applied.centerLock, 'Замок стекло-стекло RS30301');
assert.equal(applied.glassType, section.glassType);
assert.equal(applied.quantity, section.quantity);
assert.equal(applied.ralColor, section.ralColor);
assert.equal(applied.comments, section.comments);

const fiveRailEightPanelMarkup = renderToStaticMarkup(
  <SlideSystemTab
    s={{
      ...twoRowSection,
      rails: 5,
      panels: 8,
      unusedTrack: 'Внешний',
    }}
    update={() => undefined}
  />,
);
assert.match(fiveRailEightPanelMarkup, /Неиспользуемая полоса/);
assert.match(fiveRailEightPanelMarkup, />Внутренняя</);
assert.match(fiveRailEightPanelMarkup, />Внешняя</);
assert.doesNotMatch(fiveRailEightPanelMarkup, /Первые панели/);

const rs112 = SLIDE_HARDWARE_PRESETS[2];
assert.equal(rs112.updates.centerLock, undefined);
assert.equal(rs112.updates.centerFloorLatchesLeft, true);
assert.equal(rs112.updates.centerFloorLatchesRight, true);
const staleRs112Markup = renderToStaticMarkup(
  <SlideRoomViewSVG
    section={{
      ...twoRowSection,
      ...rs112.updates,
      centerLock: 'Замок стекло-стекло RS30301',
    }}
  />,
);
assert.equal((staleRs112Markup.match(/data-center-rs112-room=/g) ?? []).length, 2);
assert.doesNotMatch(staleRs112Markup, /data-center-lock=/);

console.log('SLIDE fixed presets and RS112 compatibility smoke passed.');
