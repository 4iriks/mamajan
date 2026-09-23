import { useState } from 'react';
import { createRoot } from 'react-dom/client';
import client from '../../src/api/client';
import { CsEditor } from '../../src/components/editor/CsEditor';
import type { Section } from '../../src/components/editor/types';
import '../../src/index.css';

// No backend or production data is used by this browser fixture.
client.defaults.adapter = async config => ({ data: [], status: 200, statusText: 'OK', headers: {}, config });
const initial: Section = {
  id: 'cs-fixture', name: 'CS', system: 'ЦС', width: 3000, height: 3000, quantity: 1,
  panels: 1, glassType: '', paintingType: 'RAL стандарт', cornerLeft: false, cornerRight: false,
  floorLatchesLeft: false, floorLatchesRight: false,
  profileLeftWall: false, profileLeftLockBar: false, profileLeftPBar: false,
  profileLeftHandleBar: false, profileLeftBubble: false,
  profileRightWall: false, profileRightLockBar: false, profileRightPBar: false,
  profileRightHandleBar: false, profileRightBubble: false,
  csConfig: {
    version: 1, vertices: [{ x: 0, y: 0 }, { x: 3000, y: 0 }, { x: 3000, y: 3000 }, { x: 0, y: 3000 }],
    vertical: { count: 0, mode: 'equal' }, horizontal: { count: 0, mode: 'equal' }, profiledEdges: [1, 2, 3],
  },
};
let current = initial;
function App() {
  const [section, setSection] = useState(initial);
  current = section;
  return <main className="mx-auto max-w-[1250px] p-5">
    <div id="price" className="mb-4 rounded-xl border border-emerald-500/20 bg-emerald-500/[0.06] p-3 font-bold text-[var(--catalog-price)]">2 059 ₽</div>
    <CsEditor section={section} update={updates => setSection(previous => ({ ...previous, ...updates }))} />
  </main>;
}
createRoot(document.getElementById('root')!).render(<App />);
const pause = () => new Promise(resolve => setTimeout(resolve, 60));
const assert = (condition: unknown, message: string) => { if (!condition) throw new Error(message); };
function input(label: string, index = 0): HTMLInputElement {
  const labels = [...document.querySelectorAll('label')].filter(el => el.querySelector('span')?.textContent === label);
  const field = labels[index]?.querySelector('input');
  if (!field) throw new Error(`Missing input ${label}`);
  return field;
}
function select(label: string): HTMLSelectElement {
  const field = [...document.querySelectorAll('label')].find(el => el.querySelector('span')?.textContent === label)?.querySelector('select');
  if (!field) throw new Error(`Missing select ${label}`);
  return field;
}
async function set(field: HTMLInputElement | HTMLSelectElement, value: string, commit = false) {
  field.focus();
  const prototype = field instanceof HTMLInputElement ? HTMLInputElement.prototype : HTMLSelectElement.prototype;
  Object.getOwnPropertyDescriptor(prototype, 'value')!.set!.call(field, value);
  field.dispatchEvent(new Event(field instanceof HTMLInputElement ? 'input' : 'change', { bubbles: true }));
  await pause();
  if (commit) { field.blur(); await pause(); }
}
async function click(text: string) {
  const button = [...document.querySelectorAll('button')].find(el => el.textContent?.trim() === text);
  if (!button) throw new Error(`Missing button ${text}`);
  button.click(); await pause();
}
async function run() {
  await pause();
  assert(document.querySelector('svg[aria-label]')?.textContent?.includes('У4'), 'Vertex labels');
  assert(select('Выбранная сторона').options[3].text === 'С4: У4 → У1', 'Closing side mapping');
  for (const index of [0, 1]) {
    await set(input('Количество стёкол', index), '');
    assert(input('Количество стёкол', index).value === '', 'Count must remain erasable');
    await set(input('Количество стёкол', index), '3', true);
    assert(input('Количество стёкол', index).value === '3', 'Three panes');
    assert(current.csConfig![index === 0 ? 'vertical' : 'horizontal'].count === 2, 'Three panes produce two cuts');
    await set(input('Количество стёкол', index), '1.5', true);
    assert(input('Количество стёкол', index).value === '3', 'Fractional counts must not apply');
  }
  await set(input('X, мм'), '');
  assert(input('X, мм').value === '', 'Empty coordinate draft');
  await set(input('X, мм'), '500', true);
  assert(current.csConfig!.vertices[0].x === 500, 'Coordinate committed');
  await set(input('X, мм'), '0', true);
  await set(input('Внутренний угол, °'), '60', true);
  assert(Math.abs(current.csConfig!.vertices[1].y - 1500) < 0.001, 'Angle moves following vertex');
  await set(input('Внутренний угол, °'), '90', true);
  await set(input('Длина, мм'), '2000', true);
  assert(Math.abs(current.csConfig!.vertices[1].x - 2000) < 0.001, 'Side length moves endpoint');
  assert(current.csConfig!.vertices[0].x === 0, 'Side start stays fixed');
  await set(input('Наклон, °'), '30', true);
  assert(Math.abs(current.csConfig!.vertices[1].y - 1000) < 0.001, 'Side inclination');
  const before = JSON.stringify(current.csConfig);
  await set(input('Длина, мм'), '10000', true);
  assert(JSON.stringify(current.csConfig) === before && document.querySelector('[role=alert]'), 'Out-of-bounds edits rejected visibly');
  await set(select('Выбранная сторона'), '2');
  await click('Добавить угол на С3');
  assert(current.csConfig!.vertices.length === 5 && current.csConfig!.vertices[3].x === 1500, 'Insert on chosen side');
  assert(select('Выбранный угол').value === '3', 'New vertex selected');
  assert(current.csConfig!.profiledEdges.includes(2) && current.csConfig!.profiledEdges.includes(3), 'Profile inherited by both halves');
  await click('Удалить У4');
  assert(current.csConfig!.vertices.length === 4, 'Delete chosen vertex');
  assert(current.csConfig!.profiledEdges.join(',') === '1,2,3', 'Profile mapping restored');
  const price = document.getElementById('price')!;
  assert(getComputedStyle(price).color === 'rgb(6, 95, 70)', 'Dark green in light theme');
  document.documentElement.classList.remove('light'); await pause();
  assert(getComputedStyle(price).color === 'rgb(167, 243, 208)', 'Readable green in dark theme');
  document.documentElement.classList.add('light');
  await click('Прямоугольник');
  assert(current.csConfig!.edgeTreatments!.every(kind => kind === 'clamp'), 'New contour has profiles on every side');
  await set(select('Тип введённых размеров'), 'clear');
  assert(current.width === 2920 && current.height === 2920, 'Switch to light opening subtracts 80 mm');
  await set(select('Тип введённых размеров'), 'installation');
  assert(current.width === 3000 && current.height === 3000, 'Switch back preserves physical geometry');
  await set(document.querySelector<HTMLSelectElement>('[aria-label="Комплектация С4"]')!, 'bubble');
  assert(current.csConfig!.edgeTreatments![3] === 'bubble' && !current.csConfig!.profiledEdges.includes(3), 'Bubble excludes clamp on selected side');
  await click('Многоугольник');
  await set(input('Углов в новой заготовке'), '7', true);
  assert(current.csConfig!.vertices.length === 7, 'Seven-sided preset');
  await click('Прямоугольник');
  // Make the final screenshot representative of the requested six-corner contour.
  await set(select('Выбранная сторона'), '2'); await click('Добавить угол на С3');
  await set(input('Y, мм'), '1950', true);
  await set(select('Выбранная сторона'), '4'); await click('Добавить угол на С5');
  document.getElementById('result')!.textContent = 'CS browser tests passed';
  document.body.dataset.smoke = 'passed';
}
run().catch(error => {
  document.getElementById('result')!.textContent = String(error?.stack || error);
  document.body.dataset.smoke = 'failed';
});
