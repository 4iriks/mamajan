import { useState } from 'react';
import { createRoot } from 'react-dom/client';
import client from '../../src/api/client';
import { ExtraComponentsEditor } from '../../src/components/editor/ExtraComponentsEditor';
import type { ExtraComponent } from '../../src/components/editor/types';
import '../../src/index.css';

client.defaults.adapter = async config => ({ data: [], status: 200, statusText: 'OK', headers: {}, config });
const original: ExtraComponent = { id: 'original', sku: 'RS112', name: 'Профиль-ручка', category: 'profile', color: '9005', finishName: 'RAL муар', requiresPaint: true, size: '1234', qty: '5', unit: 'шт', unitPrice: '420', imageFile: 'RS112.png', deliveryStage: '2' };
let current = [original];
function App() {
  const [items, setItems] = useState(current);
  current = items;
  return <main className="mx-auto max-w-[1100px] p-5"><ExtraComponentsEditor items={items} onChange={setItems} /></main>;
}
createRoot(document.getElementById('root')!).render(<App />);
const pause = () => new Promise(resolve => setTimeout(resolve, 120));
const assert = (value: unknown, message: string) => { if (!value) throw new Error(message); };
async function run() {
  await pause();
  document.querySelector<HTMLButtonElement>('[aria-label="Копировать RS112"]')!.click();
  await pause();
  assert(current.length === 2, 'Copy added');
  assert(current[1].id !== original.id, 'Fresh row id');
  assert(current[1].size === '' && current[1].qty === '', 'Length and quantity are empty');
  for (const key of ['sku', 'name', 'category', 'color', 'finishName', 'requiresPaint', 'unit', 'unitPrice', 'imageFile', 'deliveryStage'] as const) {
    assert(current[1][key] === original[key], `Preserved ${key}`);
  }
  assert(document.activeElement?.hasAttribute('data-length'), 'Length gets focus');
  assert(document.activeElement?.closest('article')?.dataset.rowId === current[1].id, 'Focus belongs to new row');
  assert(current[0].size === '1234' && current[0].qty === '5', 'Source unchanged');
  const add = [...document.querySelectorAll<HTMLButtonElement>('button')].find(button => button.textContent === 'Добавить комплектующий')!;
  add.click(); await pause();
  assert(document.activeElement?.getAttribute('aria-label') === 'Поиск комплектующих', 'Bottom button opens catalogue search');
  document.body.dataset.smoke = 'passed';
  document.getElementById('result')!.textContent = 'Extra-component browser tests passed';
}
run().catch(error => { document.body.dataset.smoke = 'failed'; document.getElementById('result')!.textContent = String(error.stack || error); });
