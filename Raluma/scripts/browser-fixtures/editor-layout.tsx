import { useState } from 'react';
import { createRoot } from 'react-dom/client';
import client from '../../src/api/client';
import { SectionFormWrapper } from '../../src/components/editor/SectionFormWrapper';
import { csPreset } from '../../src/components/editor/csPresets';
import { csDimensionUpdates } from '../../src/components/editor/csGeometry';
import type { Section } from '../../src/components/editor/types';
import '../../src/index.css';

client.defaults.adapter = async config => ({ data: config.url?.includes('calculate') ? { profiles: [], hardware: [], glass: [] } : [], status: 200, statusText: 'OK', headers: {}, config });
const initial: Section = {
  id: 'qa', name: 'Секция 1', system: 'ЦС', width: 3000, height: 2500, panels: 3, quantity: 1,
  paintingType: 'RAL стандарт', glassType: '10ММ ЗАКАЛЕННОЕ ПРОЗРАЧНОЕ', cornerLeft: false, cornerRight: false,
  floorLatchesLeft: false, floorLatchesRight: false, profileLeftWall: true, profileLeftLockBar: true,
  profileLeftHandleBar: true, profileLeftPBar: false, profileLeftBubble: false,
  profileRightWall: false, profileRightLockBar: false, profileRightHandleBar: false, profileRightPBar: false, profileRightBubble: true,
  csShape: 'Трапеция', rails: 3, slideRows: 1,
};
initial.csConfig = csPreset(initial);
let current = initial;
function App() {
  const [section, setSection] = useState(initial); current = section;
  return <div className="h-screen flex flex-col overflow-hidden">
    <header className="h-16 flex-none border-b p-4">Контроль размеров редактора <button id="slide" onClick={() => setSection(s => ({ ...s, system: 'СЛАЙД' }))}>SLIDE</button> · <button id="cs" onClick={() => setSection(s => ({ ...s, system: 'ЦС' }))}>ЦС</button></header>
    <div className="flex min-h-0 flex-1"><aside className="w-[240px] flex-none bg-surface/20 p-4">Секции</aside>
      <main className="min-w-0 flex-1 p-4 overflow-y-auto"><SectionFormWrapper section={section} onUpdate={updates => setSection(s => ({ ...s, ...csDimensionUpdates(s, updates) }))} onSave={async () => {}} onBack={() => {}} isSaving={false} isDirty={false} /></main>
    </div>
  </div>;
}
createRoot(document.getElementById('root')!).render(<App />);
const pause = (ms = 200) => new Promise(resolve => setTimeout(resolve, ms));
function assert(value: unknown, message: string) { if (!value) throw new Error(message); }
async function run() {
  await pause(1200);
  const canvas = document.querySelector<SVGSVGElement>('.cs-canvas svg')!;
  assert(document.querySelectorAll('.cs-canvas svg').length === 1, 'Only one CS drawing');
  const left = document.querySelector<HTMLElement>('.section-editor-diagram')!, fields = document.querySelector<HTMLElement>('.section-editor-fields')!;
  assert(left.getBoundingClientRect().right <= fields.getBoundingClientRect().left + 1, 'Drawing and parameters side by side');
  assert(left.getBoundingClientRect().bottom <= innerHeight, 'Drawing fits laptop height');
  const viewBox = canvas.getAttribute('viewBox'), top = canvas.getBoundingClientRect().top;
  const old = structuredClone(current.csConfig!.vertices);
  const coordinate = [...fields.querySelectorAll('label')].find(label => label.querySelector('span')?.textContent === 'Ш, мм')!.querySelector('input')!;
  coordinate.closest('details')!.open = true;
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(coordinate, '200');
  coordinate.dispatchEvent(new Event('input', { bubbles: true })); await pause(); coordinate.focus(); coordinate.blur(); await pause();
  assert(current.csConfig!.vertices[0].x === 200, 'Selected vertex moves');
  assert(JSON.stringify(current.csConfig!.vertices.slice(1)) === JSON.stringify(old.slice(1)), 'Other vertices stay fixed');
  assert(canvas.getAttribute('viewBox') === viewBox, 'Stable scale during edits');
  fields.scrollTop = fields.scrollHeight; await pause();
  assert(Math.abs(canvas.getBoundingClientRect().top - top) < 1, 'Parameters scroll independently');
  document.getElementById('slide')!.click(); await pause(600);
  const svgs = [...left.querySelectorAll('svg')].filter(svg => svg.getAttribute('viewBox'));
  assert(svgs.length === 2, 'Both SLIDE views present');
  assert(svgs.every(svg => svg.getBoundingClientRect().height > 50 && svg.getBoundingClientRect().bottom <= innerHeight), 'Both SLIDE views visible together');
  fields.scrollTop = fields.scrollHeight; await pause();
  assert(svgs.every(svg => svg.getBoundingClientRect().top > 0), 'SLIDE views stay visible when settings scroll');
  fields.scrollTop = 0;
  document.getElementById('result')!.textContent = 'Laptop layout and stable vertices passed'; document.body.dataset.smoke = 'passed';
}
run().catch(error => { document.getElementById('result')!.textContent = String(error.stack || error); document.body.dataset.smoke = 'failed'; });
