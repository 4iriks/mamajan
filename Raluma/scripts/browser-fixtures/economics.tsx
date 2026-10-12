import { useState } from 'react';
import { createRoot } from 'react-dom/client';
import client from '../../src/api/client';
import { ProjectEconomics } from '../../src/components/editor/ProjectEconomics';
import ProjectDocumentModal from '../../src/components/ProjectDocumentModal';
import { useProjectEconomics } from '../../src/hooks/useProjectEconomics';
import { useAuthStore } from '../../src/store/authStore';
import type { QuoteConfig } from '../../src/api/quotes';
import '../../src/index.css';

useAuthStore.getState().setAuth('local-fixture-only', { id: 1, username: 'qa', role: 'superadmin', display_name: 'QA', is_active: true } as never);
let config: QuoteConfig = { validity_days: 30, manufacturing_term: '', payment_terms: '70/30', services: [], overrides: [], margin_override_comment: '', discounts: [
  { id: 'existing', name: 'Особое правило', scope: 'service', mode: 'percent', value: '5' },
  { id: 'first', name: 'Ранее заданная', scope: 'construction', mode: 'percent', value: '10' },
  { id: 'extra', name: 'Дополнительная', scope: 'construction', mode: 'percent', value: '2' },
] };
const original = JSON.stringify(config.discounts.filter(rule => rule.id !== 'first'));
let failSave = false, exportedValue = '', fixed = false, refreshes = 0;
const pause = (ms = 80) => new Promise(resolve => setTimeout(resolve, ms));
const quote = () => ({ revision: 1, status: fixed ? 'fixed' : 'draft', stale: fixed, totals: { before_discount: '1000', discount: '100', grand_total: '900' }, export_allowed: true, discounts: config.discounts });
client.defaults.adapter = async request => {
  let data: unknown;
  if (request.url?.endsWith('/config')) {
    await pause(180);
    if (failSave) throw new Error('Сохранение временно недоступно');
    config = { ...config, ...JSON.parse(request.data) }; data = quote();
  } else if (request.url?.includes('/documents/')) {
    exportedValue = config.discounts.find(rule => rule.id === 'first')!.value;
    data = new Blob(['local QA document']);
  } else if (request.url?.endsWith('/refresh')) { refreshes += 1; data = quote(); }
  else if (request.url?.includes('/pricing/projects/')) data = { config: structuredClone(config) };
  else data = quote();
  return { data, status: 200, statusText: 'OK', headers: {}, config: request };
};
new MutationObserver(() => {
  document.querySelectorAll('iframe:not([data-qa-preview])').forEach(frame => {
    frame.setAttribute('data-qa-preview', 'true');
    (frame as HTMLIFrameElement).srcdoc = '<html><body>Локальный предпросмотр КП</body></html>';
    frame.removeAttribute('src');
  });
}).observe(document.body, { childList: true, subtree: true });
function App() {
  const state = useProjectEconomics(1, true, true);
  const [open, setOpen] = useState(false);
  return <main className="p-4 max-w-4xl mx-auto">
    <ProjectEconomics state={state} />
    <button id="open" onClick={async () => { if (await state.save()) setOpen(true); }}>Открыть КП</button>
    <ProjectDocumentModal isOpen={open} onClose={() => setOpen(false)} projectId={1} projectNumber="QA" docType="commercial" title="КП" />
  </main>;
}
createRoot(document.getElementById('root')!).render(<App />);
function assert(value: unknown, message: string) { if (!value) throw new Error(message); }
async function set(value: string) {
  const input = document.querySelector<HTMLInputElement>('[aria-label="На изделия, %"]')!;
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, value);
  input.dispatchEvent(new Event('input', { bubbles: true })); await pause();
}
async function run() {
  console.log("QA started");
  await pause(700);
  console.log("QA editing");
  await set('21'); document.getElementById('open')!.click();
  await pause(500);
  console.log("QA saved");
  assert(config.discounts.find(rule => rule.id === 'first')!.value === '21', 'Save before preview');
  assert(JSON.stringify(config.discounts.filter(rule => rule.id !== 'first')) === original, 'Additional rules and order unchanged');
  assert(document.querySelectorAll('[aria-label="На изделия, %"]').length === 1, 'No financial editor in quote modal');
  [...document.querySelectorAll('button')].find(button => button.textContent?.trim() === 'PDF')!.click();
  await pause(400); assert(exportedValue === '21', 'Immediate export uses saved discount');
  document.querySelector<HTMLButtonElement>('[aria-label="Полноэкранный просмотр"]')!.click();
  await pause(); assert(document.querySelector('[aria-label="Выйти из полноэкранного просмотра"]'), 'Full screen toggle');
  const close = [...document.querySelectorAll('button')].find(button => button.querySelector('.lucide-x'))!;
  close.click(); await pause(350);
  failSave = true; await set('22'); document.getElementById('open')!.click(); await pause(500);
  assert(!document.querySelector('iframe'), 'Failed save must block preview/export');
  assert(document.querySelector<HTMLInputElement>('[aria-label="На изделия, %"]')!.value === '22', 'Failed save preserves input');
  failSave = false; fixed = true; document.getElementById('open')!.click(); await pause(500);
  assert(refreshes === 0, 'Fixed quote cannot be silently revised');
  assert(config.discounts.find(rule => rule.id === 'first')!.value === '22', 'Retry succeeds');
  document.getElementById('result')!.textContent = 'Economics browser tests passed';
  document.body.dataset.smoke = 'passed';
}
run().catch(error => { document.getElementById('result')!.textContent = String(error.stack || error); document.body.dataset.smoke = 'failed'; });
