import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import type { SlideCalcPreview } from '../src/api/projects';
import { SlideRoomViewSVG, SlideSchemeSVG } from '../src/components/editor/SlideDiagrams';
import type { Section } from '../src/components/editor/types';
import {
  GLASS_FILL_COLORS,
  diagramGlassFillColor,
  glassFillColor,
  isMatteGlass,
} from '../src/constants/glass';
import { buildCustomerOptions } from '../src/utils/customers';

function relativeLuminance(hex: string): number {
  const channels = hex
    .slice(1)
    .match(/.{2}/g)!
    .map(value => Number.parseInt(value, 16) / 255)
    .map(value => value <= 0.03928
      ? value / 12.92
      : ((value + 0.055) / 1.055) ** 2.4);
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
}

function contrastRatio(first: string, second: string): number {
  const [lighter, darker] = [relativeLuminance(first), relativeLuminance(second)]
    .sort((a, b) => b - a);
  return (lighter + 0.05) / (darker + 0.05);
}

const themeCss = readFileSync(new URL('../src/index.css', import.meta.url), 'utf8');
const darkThemeBlock = themeCss.match(/:root\s*\{([\s\S]*?)\}/)?.[1] ?? '';
const cssColor = (name: string) => {
  const match = darkThemeBlock.match(new RegExp(`${name}:\\s*(#[0-9a-fA-F]{6})`));
  assert.ok(match, `${name} must be a concrete color in the dark theme`);
  return match[1];
};
const diagramSymbolColor = cssColor('--diagram-symbol');
for (const glassVariable of [
  '--diagram-glass-clear',
  '--diagram-glass-bronze',
  '--diagram-glass-gray',
  '--diagram-glass-matte',
  '--diagram-glass-clarified',
  '--diagram-glass-triplex',
]) {
  assert.ok(
    contrastRatio(diagramSymbolColor, cssColor(glassVariable)) >= 4.5,
    `${glassVariable} must keep diagram symbols readable in the dark theme`,
  );
}

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
  profileLeftLockBar: true,
  profileLeftPBar: false,
  profileLeftHandleBar: true,
  profileLeftBubble: false,
  profileRightWall: true,
  profileRightLockBar: false,
  profileRightPBar: true,
  profileRightHandleBar: false,
  profileRightBubble: true,
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

assert.equal(glassFillColor('10ММ БРОНЗА В МАССЕ'), GLASS_FILL_COLORS.bronze);
assert.equal(glassFillColor('10ММ СЕРОЕ В МАССЕ'), GLASS_FILL_COLORS.gray);
assert.equal(glassFillColor('10ММ МАТОВОЕ'), GLASS_FILL_COLORS.matte);
assert.equal(glassFillColor('10ММ ПРОСВЕТЛЕННОЕ'), GLASS_FILL_COLORS.clarified);
assert.equal(glassFillColor('ТРИПЛЕКС 4.1.4'), GLASS_FILL_COLORS.triplex);
assert.equal(isMatteGlass('10ММ МАТОВОЕ'), true);
assert.ok(
  roomMarkup.includes(`data-glass-fill="${diagramGlassFillColor(section.glassType)}"`),
  'room view must use the selected glass appearance',
);
assert.ok(
  schemeMarkup.includes(`data-glass-fill="${diagramGlassFillColor(section.glassType)}"`),
  'top scheme must use the selected glass appearance',
);

const bronzeRoomMarkup = renderToStaticMarkup(
  <SlideRoomViewSVG section={{ ...section, glassType: '10ММ БРОНЗА В МАССЕ' }} calc={calc} />,
);
const bronzeSchemeMarkup = renderToStaticMarkup(
  <SlideSchemeSVG section={{ ...section, glassType: '10ММ БРОНЗА В МАССЕ' }} calc={calc} />,
);
assert.ok(
  bronzeRoomMarkup.includes(`data-glass-fill="${diagramGlassFillColor('10ММ БРОНЗА В МАССЕ')}"`),
  'room view must recolor bronze glass',
);
assert.ok(
  bronzeSchemeMarkup.includes(`data-glass-fill="${diagramGlassFillColor('10ММ БРОНЗА В МАССЕ')}"`),
  'top scheme must recolor bronze glass',
);

const matteRoomMarkup = renderToStaticMarkup(
  <SlideRoomViewSVG section={{ ...section, glassType: '10ММ МАТОВОЕ' }} calc={calc} />,
);
const matteSchemeMarkup = renderToStaticMarkup(
  <SlideSchemeSVG section={{ ...section, glassType: '10ММ МАТОВОЕ' }} calc={calc} />,
);
assert.match(matteRoomMarkup, /data-glass-pattern="matte"/, 'room view must render matte glass as visible dots');
assert.match(matteSchemeMarkup, /data-glass-pattern="matte"/, 'top scheme must render matte glass as visible dots');
assert.match(roomMarkup, /margin:0 auto/, 'room view must be centered in its card');
assert.match(schemeMarkup, /margin:0 auto/, 'top scheme must be centered in its card');

const schemeOuterBounds = schemeMarkup.match(
  /data-diagram-outer-left="([^"]+)" data-diagram-outer-right="([^"]+)"/,
);
assert.ok(schemeOuterBounds, 'top scheme must expose its visible outer bounds');
const schemeOuterLeft = Number(schemeOuterBounds[1]);
const schemeOuterRight = Number(schemeOuterBounds[2]);
assert.ok(schemeOuterLeft >= 0, 'left wall profile must stay inside the top scheme SVG');
assert.ok(schemeOuterRight <= 760, 'right wall profile must stay inside the top scheme SVG');
assert.ok(
  Math.abs((schemeOuterLeft + schemeOuterRight) / 2 - 380) < 0.01,
  'top scheme including asymmetric side assemblies must be visually centered',
);

const renderedWidths = [...roomMarkup.matchAll(/width="([^"]+)"/g)]
  .map(match => Number(match[1]))
  .filter(Number.isFinite);

assert(
  renderedWidths.some(width => width > 204 && width < 205),
  'enlarged room view must keep 2000x2400 proportions',
);
assert(!renderedWidths.some(width => width === 400), 'room view must not use the old fixed 400px frame width');
assert.doesNotMatch(roomMarkup, />53</, 'room view must not render the top profile service size');
assert.doesNotMatch(roomMarkup, />23</, 'room view must not render the threshold service size');
assert.doesNotMatch(schemeMarkup, />16</, 'top scheme must not render a separate wall profile marker');
assert.match(schemeMarkup, /data-profile-image="RS2333-left"/, 'top scheme must render the left wall profile image');
assert.match(schemeMarkup, /data-profile-image="RS2333-right"/, 'top scheme must render the right wall profile image');
assert.match(schemeMarkup, /data-side-assembly="lock-handle"/, 'top scheme must render the left side assembly');
assert.match(schemeMarkup, /data-side-assembly="p-bubble"/, 'top scheme must render the right side assembly');
assert.match(schemeMarkup, /data-side-assembly-image="SIDE_RS2081_RS112.png"/, 'left side assembly must use the technical PNG');
assert.match(schemeMarkup, /data-side-assembly-image="SIDE_RS1082_RS1002.png"/, 'right side assembly must use the technical PNG');
assert.ok(
  schemeMarkup.indexOf('data-side-assembly-image=') > schemeMarkup.lastIndexOf('data-scheme-panel='),
  'side assembly images must render above the glass panels',
);
assert.doesNotMatch(schemeMarkup, />RS(?:112|2081)</, 'top scheme must not render old side profile labels');
assert.match(schemeMarkup, /stroke-linecap="round"/, 'top scheme must render the mirrored inter-glass profile path');
assert.match(schemeMarkup, /data-dir="1"/, 'inter-glass profile prongs must enter the glass edge');

const bubbleOnlyMarkup = renderToStaticMarkup(
  <SlideSchemeSVG
    section={{
      ...section,
      profileLeftLockBar: false,
      profileLeftPBar: false,
      profileLeftHandleBar: false,
      profileLeftBubble: true,
    }}
    calc={calc}
  />,
);
assert.match(bubbleOnlyMarkup, /data-side-assembly="bubble"/, 'standalone RS1002 must render as a side assembly');
assert.match(bubbleOnlyMarkup, /data-side-assembly-image="SIDE_RS1002.png"/, 'standalone RS1002 must use its PNG');

const pHandleMarkup = renderToStaticMarkup(
  <SlideSchemeSVG
    section={{
      ...section,
      profileLeftLockBar: false,
      profileLeftPBar: true,
      profileLeftHandleBar: true,
      profileLeftBubble: false,
    }}
    calc={calc}
  />,
);
assert.match(pHandleMarkup, /data-side-assembly="p-handle"/, 'RS1082 with RS112 must render as a side assembly');
assert.match(pHandleMarkup, /data-side-assembly-image="SIDE_RS1082_RS112.png"/, 'RS1082 with RS112 must use its PNG');

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
  panel_glass: [
    { panel: 1, position: 'Левое', width_mm: 520, height_mm: 2294, glass_profile_length: 520 },
    { panel: 2, position: 'Центральное левое', width_mm: 500.1, height_mm: 2294, glass_profile_length: 497 },
    { panel: 3, position: 'Центральное правое', width_mm: 501.1, height_mm: 2294, glass_profile_length: 498 },
    { panel: 4, position: 'Правое', width_mm: 530, height_mm: 2294, glass_profile_length: 530 },
  ],
  profiles: calc.profiles,
  panel_rails: [1, 2, 2, 1],
  panel_numbers: [2, 1, 1, 2],
};

const roomMarkupTwoRows = renderToStaticMarkup(<SlideRoomViewSVG section={sectionTwoRows} calc={calcTwoRows} />);
const schemeMarkupTwoRows = renderToStaticMarkup(<SlideSchemeSVG section={sectionTwoRows} calc={calcTwoRows} />);

assert.match(roomMarkupTwoRows, />500</, '2-row room view must round the left central glass to the nearest millimeter');
assert.match(schemeMarkupTwoRows, /500 · №1/, 'center-first numbering must label the left central panel as 1');
assert.match(schemeMarkupTwoRows, /501 · №1/, 'center-first numbering must label the right central panel as 1');
assert.match(schemeMarkupTwoRows, /data-dir="1"/, '2-row top scheme must mirror left-side inter-glass profile');
assert.match(schemeMarkupTwoRows, /data-dir="-1"/, '2-row top scheme must mirror right-side inter-glass profile');
assert.equal((schemeMarkupTwoRows.match(/data-profile="inter-glass"/g) ?? []).length, 2, '2-row top scheme must not draw an inter-glass profile in the central joint');
assert.match(schemeMarkupTwoRows, />сдвиг</, '2-row top scheme must render bidirectional shift label');

function schemePanelRect(markup: string, panel: number) {
  const match = markup.match(new RegExp(`data-scheme-panel="${panel}" x="([^"]+)" y="[^"]+" width="([^"]+)"`));
  assert.ok(match, `top scheme must expose geometry for panel ${panel}`);
  return { x: Number(match[1]), width: Number(match[2]) };
}

const centerLeft = schemePanelRect(schemeMarkupTwoRows, 2);
const centerRight = schemePanelRect(schemeMarkupTwoRows, 3);
const centerGap = centerRight.x - (centerLeft.x + centerLeft.width);
assert.ok(centerGap > 0 && centerGap <= 2, '2-row central panels must have a visible scaled 3 mm gap without overlap');

const centerHandleAnchors = [...roomMarkupTwoRows.matchAll(/data-center-handle="(left|right)" data-anchor-x="([^"]+)"/g)]
  .map(match => ({ side: match[1], x: Number(match[2]) }));
assert.equal(centerHandleAnchors.length, 2, '2-row room view must render both center handle anchors');
assert.ok(centerHandleAnchors[0].x < centerHandleAnchors[1].x, 'center handles must stay on their physical sides of the joint');
assert.ok(
  centerHandleAnchors[1].x - centerHandleAnchors[0].x >= 16,
  'center handles must remain visually separated around the joint',
);
assert.match(roomMarkupTwoRows, /data-center-lock="center" data-center-lock-position="below-handles"/, 'center lock must stay below the central handles');

const movableTwoRowsMarkup = renderToStaticMarkup(
  <SlideRoomViewSVG
    section={{
      ...sectionTwoRows,
      profileLeftHandleBar: false,
      profileLeftLockBar: false,
      profileRightPBar: false,
      profileRightBubble: false,
      handleLeft: 'Ручка-кноб RS3014',
      handleRight: 'Ручка-кноб RS3014',
    }}
    calc={calcTwoRows}
  />,
);
assert.equal(
  (movableTwoRowsMarkup.match(/data-panel-direction="both"/g) ?? []).length,
  4,
  'each 2-row half must show bidirectional arrows when its outer panel is movable',
);

const leftDeafTwoRowsMarkup = renderToStaticMarkup(
  <SlideRoomViewSVG
    section={{
      ...sectionTwoRows,
      profileLeftHandleBar: false,
      profileLeftLockBar: false,
      profileRightPBar: false,
      profileRightBubble: false,
      handleLeft: 'Без ручки (глухая)',
      handleRight: 'Ручка-кноб RS3014',
    }}
    calc={calcTwoRows}
  />,
);
assert.equal(
  (leftDeafTwoRowsMarkup.match(/data-panel-direction="both"/g) ?? []).length,
  2,
  'a deaf outer panel must keep only its half one-directional',
);
assert.equal(
  (leftDeafTwoRowsMarkup.match(/data-panel-direction="left"/g) ?? []).length,
  1,
  'the remaining moving panel in a deaf left half must point toward the edge',
);

const centerRs112Section: Section = {
  ...sectionTwoRows,
  centerHandle: 'Ручки-профиль RS112 (2шт)',
  centerLock: 'Без',
};
const centerRs112RoomMarkup = renderToStaticMarkup(<SlideRoomViewSVG section={centerRs112Section} calc={calcTwoRows} />);
const centerRs112TopMarkup = renderToStaticMarkup(<SlideSchemeSVG section={centerRs112Section} calc={calcTwoRows} />);
assert.equal(
  (centerRs112RoomMarkup.match(/data-center-rs112-room="(left|right)"/g) ?? []).length,
  2,
  'room view must render a 40 mm RS112 strip on both central panels',
);
assert.doesNotMatch(
  centerRs112RoomMarkup,
  /data-center-rs112-room="(?:left|right)"[^>]*fill="var\(--theme-accent\)"/,
  'central RS112 profiles must keep their contour without a blue fill',
);

const outsideFirstCalc: SlideCalcPreview = {
  ...calcTwoRows,
  panel_numbers: [1, 2, 2, 1],
};
const outsideFirstMarkup = renderToStaticMarkup(
  <SlideSchemeSVG
    section={{ ...sectionTwoRows, unusedTrack: 'Внутренний' }}
    calc={outsideFirstCalc}
  />,
);
assert.match(outsideFirstMarkup, /520 · №1/);
assert.match(outsideFirstMarkup, /500 · №2/);
assert.match(outsideFirstMarkup, /501 · №2/);
assert.match(outsideFirstMarkup, /530 · №1/);
assert.equal(
  (centerRs112TopMarkup.match(/data-center-rs112-top="(left|right)"/g) ?? []).length,
  2,
  'top view must render both central RS112 profiles',
);

const roomMarkupRs206 = renderToStaticMarkup(
  <SlideRoomViewSVG section={{ ...sectionTwoRows, centerLock: 'Накидная защёлка RS206' }} calc={calcTwoRows} />,
);
assert.match(roomMarkupRs206, /data-center-lock="RS206" data-center-lock-position="bottom"/, 'RS206 must be rendered at the bottom edge');

const bidirectionalSection: Section = {
  ...section,
  panels: 2,
  profileLeftHandleBar: false,
  profileLeftLockBar: false,
  profileRightPBar: false,
  profileRightBubble: false,
  handleLeft: 'Ручка-кноб RS3014',
  handleRight: 'Ручка-кноб RS3014',
};
const bidirectionalMarkup = renderToStaticMarkup(<SlideRoomViewSVG section={bidirectionalSection} calc={calc} />);
assert.equal(
  (bidirectionalMarkup.match(/data-panel-direction="both"/g) ?? []).length,
  2,
  'one-row moving panels on both sides must show bidirectional arrows',
);

assert.deepEqual(
  buildCustomerOptions(
    [{ customer: 'ООО СТУДИЯ СПК' }, { customer: 'ООО КРОКНА ИНЖИНИРИНГ' }],
    'ООО СПК',
    'СТУДИЯ СПК',
  ),
  ['ООО ПРОЗРАЧНЫЕ РЕШЕНИЯ', 'ООО КРОКНА ИНЖИНИРИНГ'],
  'retired customer must not return through saved projects or legacy aliases',
);

console.log('slide diagram smoke passed');
