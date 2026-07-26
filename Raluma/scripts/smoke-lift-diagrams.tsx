import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { apiToLocal, applyTemplateDataToSection, localToApi, localToTemplateData } from '../src/components/editor/converters';
import { EditorVisualizer } from '../src/components/editor/EditorVisualizer';
import { LiftRoomViewSVG } from '../src/components/editor/LiftDiagrams';
import {
  LIFT_SPLIT_OPENING,
  liftOpeningOptions,
} from '../src/components/editor/liftConfig';
import type { Section } from '../src/components/editor/types';

const baseSection: Section = {
  id: 'lift-smoke',
  name: 'Секция 1',
  system: 'ЛИФТ',
  width: 3043,
  height: 3300,
  panels: 2,
  quantity: 1,
  glassType: '8ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ',
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
  liftFillingType: 'ДРУГОЕ 20мм',
  liftFillingCustom: 'Панель по ТЗ',
  liftControlType: 'Пульт ДУ',
  liftCableSide: 'Слева',
  liftOpeningType: 'Сдвиг вниз',
};

const cases = [
  { panels: 2, opening: 'Сдвиг вниз', fixed: [2], moving: [1] },
  { panels: 2, opening: 'Сдвиг вверх', fixed: [1], moving: [2] },
  { panels: 3, opening: 'Сдвиг вниз', fixed: [3], moving: [1, 2] },
  { panels: 3, opening: 'Сдвиг вверх', fixed: [1], moving: [2, 3] },
  { panels: 4, opening: 'Сдвиг вниз', fixed: [4], moving: [1, 2, 3] },
  { panels: 4, opening: 'Сдвиг вверх', fixed: [1], moving: [2, 3, 4] },
  { panels: 4, opening: LIFT_SPLIT_OPENING, fixed: [1, 4], moving: [2, 3] },
] as const;

for (const scenario of cases) {
  const markup = renderToStaticMarkup(
    <LiftRoomViewSVG
      section={{
        ...baseSection,
        panels: scenario.panels,
        liftOpeningType: scenario.opening,
      }}
    />,
  );

  assert.match(markup, new RegExp(`data-lift-panels="${scenario.panels}"`));
  assert.match(markup, new RegExp(`data-lift-opening="${scenario.opening}"`));
  for (const panel of scenario.fixed) {
    assert.match(markup, new RegExp(`data-lift-fixed-panel="${panel}"`));
  }
  for (const panel of scenario.moving) {
    assert.match(markup, new RegExp(`data-lift-moving-panel="${panel}"`));
  }
  assert.equal(
    (markup.match(/data-lift-fixed-panel=/g) ?? []).length,
    scenario.fixed.length,
  );
  assert.equal(
    (markup.match(/data-lift-moving-panel=/g) ?? []).length,
    scenario.moving.length,
  );
}

const proportionalMarkup = renderToStaticMarkup(<LiftRoomViewSVG section={baseSection} />);
const frame = proportionalMarkup.match(
  /data-frame-width="([^"]+)" data-frame-height="([^"]+)"/,
);
assert.ok(frame, 'lift diagram must expose proportional frame geometry');
const renderedRatio = Number(frame[1]) / Number(frame[2]);
assert.ok(
  Math.abs(renderedRatio - baseSection.width / baseSection.height) < 0.001,
  'lift frame must keep the construction width/height ratio',
);
assert.match(proportionalMarkup, /data-cable-side="Слева"/);
assert.match(proportionalMarkup, /ВВОД КАБЕЛЯ СЛЕВА/);
assert.match(proportionalMarkup, /data-lift-profile="top"[^>]*stroke-width="8"/);
assert.match(proportionalMarkup, /data-lift-profile="bottom"[^>]*stroke-width="4"/);
assert.match(
  renderToStaticMarkup(
    <LiftRoomViewSVG section={{ ...baseSection, liftCableSide: 'Справа' }} />,
  ),
  /ВВОД КАБЕЛЯ СПРАВА/,
);

assert.deepEqual(liftOpeningOptions(2), ['Сдвиг вниз', 'Сдвиг вверх']);
assert.deepEqual(liftOpeningOptions(3), ['Сдвиг вниз', 'Сдвиг вверх']);
assert.deepEqual(liftOpeningOptions(4), [
  'Сдвиг вниз',
  'Сдвиг вверх',
  LIFT_SPLIT_OPENING,
]);

const apiSection = localToApi(baseSection, 3);
assert.equal(apiSection.lift_filling_type, 'ДРУГОЕ 20мм');
assert.equal(apiSection.lift_filling_custom, 'Панель по ТЗ');
assert.equal('lift_remote_channels' in apiSection, false);
assert.equal(apiSection.lift_cable_side, 'Слева');
assert.equal(apiSection.lift_opening_type, 'Сдвиг вниз');

const roundTrip = apiToLocal({
  ...apiSection,
  id: 10,
  project_id: 20,
});
assert.equal(roundTrip.liftFillingType, baseSection.liftFillingType);
assert.equal(roundTrip.liftFillingCustom, baseSection.liftFillingCustom);
assert.equal(roundTrip.liftControlType, baseSection.liftControlType);
assert.equal(roundTrip.liftCableSide, baseSection.liftCableSide);
assert.equal(roundTrip.liftOpeningType, baseSection.liftOpeningType);

const templateData = localToTemplateData(baseSection);
const fromTemplate = applyTemplateDataToSection(
  { ...baseSection, liftFillingCustom: undefined },
  templateData,
);
assert.equal(fromTemplate.liftFillingCustom, 'Панель по ТЗ');
assert.equal(fromTemplate.liftOpeningType, 'Сдвиг вниз');

const visualizerMarkup = renderToStaticMarkup(
  <EditorVisualizer section={baseSection} variant="desktop" />,
);
assert.match(visualizerMarkup, /data-lift-view-caption/);
assert.match(visualizerMarkup, /Вид из помещения/);

console.log('Lift diagrams smoke passed: 7 variants, persistence, proportions and caption');
