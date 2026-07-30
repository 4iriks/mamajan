import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

import type { BookCalcPanel, BookCalcPreview } from '../src/api/projects';
import { BookCalcResults } from '../src/components/editor/BookCalcResults';
import { BookRoomViewSVG, BookTopViewSVG } from '../src/components/editor/BookDiagrams';
import { BookSystemTab } from '../src/components/editor/BookForm';
import { apiToLocal, applyTemplateDataToSection, localToApi, localToTemplateData } from '../src/components/editor/converters';
import { EditorVisualizer } from '../src/components/editor/EditorVisualizer';
import type { Section } from '../src/components/editor/types';


const section: Section = {
  id: 'book-smoke',
  name: 'Секция 1',
  system: 'КНИЖКА',
  width: 3000,
  height: 2500,
  panels: 4,
  quantity: 1,
  glassType: '10ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ',
  paintingType: 'RAL стандарт',
  ralColor: '9016 МАТОВЫЙ',
  cornerLeft: false,
  cornerRight: false,
  floorLatchesLeft: false,
  floorLatchesRight: false,
  profileLeftWall: false,
  profileLeftLockBar: false,
  profileLeftPBar: false,
  profileLeftHandleBar: false,
  profileLeftBubble: false,
  profileRightWall: false,
  profileRightLockBar: false,
  profileRightPBar: false,
  profileRightHandleBar: false,
  profileRightBubble: false,
  doors: 2,
  doorSide: 'both',
  compensator: 'both',
  bookLeftDoorHardware: 'handle',
  bookRightDoorHardware: 'lock',
  bookLeftDoorOpening: 'inside_in',
  bookRightDoorOpening: 'outside_out',
  bookObstacleDistance: 500,
  bookLeftStackPanels: 2,
  bookHandleHeight: 1000,
  bookExtraFixedEnabled: false,
  bookExtraDoorEnabled: false,
};

function panel(
  number: number,
  role: BookCalcPanel['role'],
  movement: BookCalcPanel['movement_direction'],
  width: number,
): BookCalcPanel {
  const side = role === 'door' ? (number === 1 ? 'left' : 'right') : null;
  return {
    number,
    position: number === 1 ? 'left' : number === 4 ? 'right' : 'middle',
    role,
    movement_direction: movement,
    door_side: side,
    door_hardware: role === 'door' ? (number === 1 ? 'handle' : 'lock') : null,
    door_opening: role === 'door' ? (number === 1 ? 'inside_in' : 'outside_out') : null,
    door_opening_label: role === 'door' ? (number === 1 ? 'изнутри внутрь' : 'снаружи наружу') : null,
    glass_type: section.glassType,
    glass_width_mm: width - 3,
    glass_height_mm: 2365,
    glass_profile_article: 'RBP002',
    glass_profile_width_mm: width,
    panel_width_mm: width,
    panel_height_mm: 2398,
    qty: 1,
    hardware_articles: [],
    source: 'tz',
    status: 'confirmed',
    dimension_sources: {
      glass_width_mm: { source: 'tz', status: 'confirmed' },
    },
  };
}

const calc: BookCalcPreview = {
  panels: [
    panel(1, 'door', 'left', 600),
    panel(2, 'standard', 'left', 700),
    panel(3, 'standard', 'right', 800),
    panel(4, 'door', 'right', 900),
  ],
  profiles: [
    {
      article: 'RBP001',
      name: 'Направляющий профиль',
      length_mm: 3000,
      qty: 2,
      unit: 'шт.',
      position: 'Верх и низ',
      panel_number: null,
      source: 'excel',
      status: 'confirmed',
      formula: 'W × 2',
    },
  ],
  hardware: [
    {
      article: 'RBA0009',
      name: 'Компенсирующие болт и гайка',
      qty: 4,
      unit: 'шт.',
      shipment_stage: 1,
      formula: 'P',
      note: '',
      source: 'tz',
      status: 'confirmed',
      included: true,
    },
  ],
  formulas: [
    {
      key: 'glass_width',
      name: 'Ширина стекла',
      value: 742,
      unit: 'мм',
      expression: '(W − 11,5 − 11,5 − 3 × (P − 1)) / P',
      scope: 'Прямая секция',
      source: 'tz',
      status: 'confirmed',
      source_reference: 'ТЗ, стр. 9',
    },
  ],
  warnings: ['Документы — следующий пакет.'],
  normalized_config: {
    width_mm: 3000,
    height_mm: 2500,
    base_panel_count: 4,
    physical_panel_count: 4,
    quantity: 1,
    door_layout: 'both',
    compensator: 'both',
    obstacle_distance_mm: 500,
    left_stack_panels: 2,
  },
  source_priority: ['tz', 'excel', 'legacy'],
  configuration_status: 'confirmed',
  calculation_status: 'preliminary',
  documents_allowed: true,
  documents_implemented: false,
  document_block_reasons: [],
};

const roomMarkup = renderToStaticMarkup(<BookRoomViewSVG section={section} calc={calc} />);
const topMarkup = renderToStaticMarkup(<BookTopViewSVG section={section} calc={calc} />);
const visualizerMarkup = renderToStaticMarkup(
  <EditorVisualizer section={section} variant="desktop" calc={calc} />,
);
const formMarkup = renderToStaticMarkup(<BookSystemTab s={section} update={() => undefined} />);
const resultsMarkup = renderToStaticMarkup(<BookCalcResults calc={calc} />);

assert.match(roomMarkup, /data-book-room-view="true"/);
assert.match(topMarkup, /data-book-top-view="true"/);
assert.equal((roomMarkup.match(/data-book-panel-number=/g) ?? []).length, 4);
assert.equal((topMarkup.match(/data-book-top-panel=/g) ?? []).length, 4);
assert.equal((roomMarkup.match(/data-book-door-swing=/g) ?? []).length, 2);
assert.equal((topMarkup.match(/data-book-top-door-swing=/g) ?? []).length, 2);
assert.match(roomMarkup, /data-book-panel-movement="left"/);
assert.match(roomMarkup, /data-book-panel-movement="right"/);
assert.match(topMarkup, /data-book-stack-split="true"/);
assert.match(topMarkup, /data-book-obstacle="true"/);
assert.match(visualizerMarkup, /Вид из помещения/);
assert.match(visualizerMarkup, /Вид сверху/);

const roomPanelWidths = [...roomMarkup.matchAll(/<rect x="[^"]+" y="36" width="([^"]+)"/g)]
  .map(match => Number(match[1]));
assert.equal(roomPanelWidths.length, 4);
assert.ok(roomPanelWidths[0] < roomPanelWidths[1]);
assert.ok(roomPanelWidths[1] < roomPanelWidths[2]);
assert.ok(roomPanelWidths[2] < roomPanelWidths[3]);

assert.match(formMarkup, /data-book-form="true"/);
assert.equal((formMarkup.match(/data-book-form-block=/g) ?? []).length, 4);
assert.equal((formMarkup.match(/data-book-opening=/g) ?? []).length, 2);
for (const label of ['Изнутри внутрь', 'Изнутри наружу', 'Снаружи наружу', 'Снаружи внутрь']) {
  assert.match(formMarkup, new RegExp(label));
}
assert.match(resultsMarkup, /data-book-calc-results="true"/);
assert.equal((resultsMarkup.match(/data-book-result-panel=/g) ?? []).length, 4);
assert.match(resultsMarkup, /TZ → EXCEL → LEGACY/i);

const api = localToApi(section, 2);
assert.equal(api.book_left_door_hardware, 'handle');
assert.equal(api.book_right_door_hardware, 'lock');
assert.equal(api.book_left_door_opening, 'inside_in');
assert.equal(api.book_right_door_opening, 'outside_out');
assert.equal(api.book_left_stack_panels, 2);
assert.equal(api.book_obstacle_distance, 500);

const roundTrip = apiToLocal({ ...api, id: 1, project_id: 2 });
assert.equal(roundTrip.doorSide, 'both');
assert.equal(roundTrip.bookLeftDoorHardware, 'handle');
assert.equal(roundTrip.bookRightDoorOpening, 'outside_out');

const legacy = apiToLocal({
  ...api,
  id: 3,
  project_id: 4,
  doors: 1,
  door_side: 'Левая',
  door_type: 'Тип 4',
  door_opening: 'Наружу',
  book_left_door_hardware: undefined,
  book_right_door_hardware: undefined,
  book_left_door_opening: undefined,
  book_right_door_opening: undefined,
});
assert.equal(legacy.doorSide, 'left');
assert.equal(legacy.bookLeftDoorHardware, 'lock');
assert.equal(legacy.bookLeftDoorOpening, 'inside_out');

const template = localToTemplateData(section);
const applied = applyTemplateDataToSection(
  {
    ...section,
    doorSide: 'right',
    doors: 1,
    bookLeftDoorHardware: undefined,
    bookRightDoorHardware: 'handle',
  },
  template,
);
assert.equal(applied.doorSide, 'both');
assert.equal(applied.bookLeftDoorHardware, 'handle');
assert.equal(applied.bookRightDoorHardware, 'lock');

console.log('Book calculator diagrams and compatibility smoke passed.');
