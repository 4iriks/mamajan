import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { csAngleEnd, csBounds, csChangeDimensionMode, csContourFrames, csContourError, csDimensionUpdates, csSide, csSideEnd, csSplitPositions, csVertexAngle, parseCsPositions } from '../src/components/editor/csGeometry';
import type { CsConfig, CsSplitConfig, Section } from '../src/components/editor/types';
import { apiToLocal, localToApi } from '../src/components/editor/converters';

const config: CsConfig = {
  version: 1,
  vertices: [{ x: 0, y: 0 }, { x: 3000, y: 0 }, { x: 3000, y: 3000 }, { x: 0, y: 3000 }],
  vertical: { count: 2, mode: 'equal' }, horizontal: { count: 0, mode: 'equal' },
  profiledEdges: [1, 2, 3],
};
const original = {
  id: 'cs', name: 'CS', system: 'ЦС', width: 3000, height: 3000, quantity: 1,
  panels: 3, glassType: '', paintingType: 'RAL стандарт', cornerLeft: false, cornerRight: false,
  floorLatchesLeft: false, floorLatchesRight: false,
  profileLeftWall: false, profileLeftLockBar: false, profileLeftPBar: false,
  profileLeftHandleBar: false, profileLeftBubble: false,
  profileRightWall: false, profileRightLockBar: false, profileRightPBar: false,
  profileRightHandleBar: false, profileRightBubble: false,
  csConfig: config,
} satisfies Section;
const near = (actual: number, expected: number) => assert.ok(Math.abs(actual - expected) < 0.000001, `${actual} ≠ ${expected}`);
for (const vertices of [config.vertices, [...config.vertices].reverse()]) {
  vertices.forEach((_, index) => near(csVertexAngle(vertices, index), 90));
  const moved = [...vertices];
  moved[1] = csAngleEnd(vertices, 0, 60);
  near(csVertexAngle(moved, 0), 60);
  near(csSide(moved, 0).length, 3000);
}
assert.deepEqual(csSide(config.vertices, 0), { length: 3000, angle: 0 });
near(csSideEnd(config.vertices, 0, 2000, 90).y, 2000);
near(csSideEnd(config.vertices, 0, 2000, 90).x, 0);
const concave = [{ x: 0, y: 0 }, { x: 3000, y: 0 }, { x: 1500, y: 1500 }, { x: 3000, y: 3000 }, { x: 0, y: 3000 }];
near(csVertexAngle(concave, 2), 270);
near(csVertexAngle([...concave].reverse(), 2), 270);
assert.equal(csContourError(concave), undefined);
assert.ok(csContourError([{ x: 0, y: 0 }, { x: 3000, y: 3000 }, { x: 3000, y: 0 }, { x: 0, y: 3000 }]));
assert.ok(csContourError([{ x: 0, y: 0 }, { x: 0, y: 0 }, { x: 0, y: 3000 }]));
assert.ok(csContourError([{ x: 0, y: 0 }, { x: 1000, y: 0 }, { x: 3000, y: 0 }]));
function change(section: Section, updates: Partial<Section>): Section {
  return { ...section, ...csDimensionUpdates(section, updates) };
}

const wide = change(original, { width: 4000 });
assert.equal(csBounds(wide.csConfig!.vertices).maxX, 4000);
assert.equal(csBounds(wide.csConfig!.vertices).maxY, 3000);
const tall = change(wide, { height: 4500 });
assert.equal(csBounds(tall.csConfig!.vertices).maxY, 4500);
const small = change(original, { width: 1500, height: 1500 });
assert.deepEqual(small.csConfig!.vertices[2], { x: 1500, y: 1500 });
assert.equal(original.csConfig.vertices[2].x, 3000, 'resize must not mutate a saved snapshot');
assert.deepEqual(tall.csConfig!.profiledEdges, [1, 2, 3]);

// Emptying the number field and typing a replacement must not lose the reference frame.
let typed: Section = original;
for (const width of [0, 4, 40, 400, 4000]) typed = change(typed, { width });
assert.equal(csBounds(typed.csConfig!.vertices).maxX, 4000);
const restored = apiToLocal(JSON.parse(JSON.stringify({ ...localToApi(typed, 0), id: 1, project_id: 1 })));
assert.deepEqual(restored.csConfig, typed.csConfig, 'API save/load must retain geometry and its reference dimensions');
assert.equal(restored.width, typed.width);
assert.equal(restored.height, typed.height);
const inactive = { ...original, system: 'СЛАЙД' as const };
assert.deepEqual(csDimensionUpdates(inactive, { width: 4000 }), { width: 4000 });
assert.equal(csDimensionUpdates(original, { width: 4000, csConfig: config }).csConfig, config);

const shifted = {
  ...original,
  csConfig: { ...config, vertices: config.vertices.map(point => ({ x: point.x || 600, y: point.y || 300 })) },
};
const bounds = csBounds(shifted.csConfig.vertices);
assert.deepEqual(csSplitPositions(config.vertical, bounds.minX, bounds.maxX), [1399.5, 2200.5]);
const trapezoid = {
  ...original,
  csConfig: { ...config, vertices: [{ x: 0, y: 0 }, { x: 3000, y: 0 }, { x: 2500, y: 3000 }, { x: 500, y: 3000 }] },
};
const resizedTrapezoid = change(trapezoid, { width: 6000, height: 1500 });
assert.deepEqual(resizedTrapezoid.csConfig!.vertices[2], { x: 5000, y: 1500 });

const manual: CsSplitConfig = { count: 2, mode: 'manual', positions: [1000, 2000] };
const resizedManual = change({ ...original, csConfig: { ...config, vertical: manual } }, { width: 6000 });
assert.deepEqual(resizedManual.csConfig!.vertical.positions, [2000, 4000]);
const stepped = change({ ...original, csConfig: { ...config, vertical: { count: 2, mode: 'from-left', step: 750 } } }, { width: 6000 });
assert.equal(stepped.csConfig!.vertical.step, 750, 'explicit mm step stays fixed');

assert.deepEqual(parseCsPositions('1000,', 0, 3000), { positions: [1000] });
assert.deepEqual(parseCsPositions('1000, 2000', 0, 3000), { positions: [1000, 2000] });
assert.deepEqual(parseCsPositions('2000; 1000 1000', 0, 3000), { positions: [1000, 2000] });
assert.deepEqual(parseCsPositions('', 0, 3000), { positions: [] });
assert.ok(parseCsPositions('1000, abc', 0, 3000).error);
assert.ok(parseCsPositions('1000, 3000', 0, 3000).error);
assert.ok(parseCsPositions('500', 600, 3000).error);
assert.deepEqual(parseCsPositions('1400, 2200', 600, 3000), { positions: [1400, 2200] });

// Cross-check frontend geometry against the actual Python engine, not a second test formula.
const sections = [original, wide, tall, small, typed, shifted, resizedTrapezoid, resizedManual, stepped];
const modes: CsSplitConfig[] = [
  { count: 2, mode: 'equal' }, { count: 2, mode: 'from-left', step: 700 },
  { count: 2, mode: 'from-right', step: 700 }, { count: 20, mode: 'from-left', step: 800 },
  { count: 2, mode: 'from-right', step: 0 }, { count: 2, mode: 'from-left' },
  { count: 3, mode: 'manual', positions: [1400, 1400, 2200] },
];
for (const split of modes) sections.push({ ...shifted, csConfig: { ...shifted.csConfig, vertical: split, horizontal: split } });
const payload = sections.map(section => ({ width: section.width, height: section.height, quantity: 1, cs_config: section.csConfig }));
const engine = spawnSync(process.env.CS_PYTHON || 'python', ['-c', `
import json, sys
from types import SimpleNamespace
from engine.cs_calc import calculate_cs
print(json.dumps([calculate_cs(SimpleNamespace(**row)) for row in json.load(sys.stdin)]))
`], { cwd: fileURLToPath(new URL('../backend', import.meta.url)), input: JSON.stringify(payload), encoding: 'utf8' });
assert.equal(engine.status, 0, engine.error?.message || engine.stderr);
const results = JSON.parse(engine.stdout);
sections.forEach((section, index) => {
  const config = section.csConfig!;
  const frames = csContourFrames(config);
  const bounds = csBounds(frames.clear);
  const actual = results[index].normalized_config;
  for (const axis of ['vertical', 'horizontal'] as const) {
    const expected = csSplitPositions(config[axis], axis === 'vertical' ? bounds.minX : bounds.minY, axis === 'vertical' ? bounds.maxX : bounds.maxY);
    assert.equal(actual[axis].positions.length, expected.length);
    expected.forEach((value, i) => near(actual[axis].positions[i], value));
  }
  frames.glass.forEach((point, i) => { near(point.x, results[index].glass_polygon[i].x); near(point.y, results[index].glass_polygon[i].y); });
  const light = csChangeDimensionMode(config, 'clear');
  const restored = csChangeDimensionMode(light.csConfig!, 'installation');
  const originalBounds = csBounds(frames.installation);
  restored.csConfig!.vertices.forEach((p, i) => {
    near(p.x, frames.installation[i].x - originalBounds.minX);
    near(p.y, frames.installation[i].y - originalBounds.minY);
  });
});
near(results[1].glass_area_m2, (4000 - 52 - 6) * (3000 - 26) / 1e6);
near(results[2].glass_area_m2, (4000 - 52 - 6) * (4500 - 26) / 1e6);
near(results[3].glass_area_m2, (1500 - 52 - 6) * (1500 - 26) / 1e6);
console.log(`CS geometry: resize, draft parsing and ${sections.length} frontend/backend comparisons passed.`);
