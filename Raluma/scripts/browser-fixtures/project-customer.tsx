import { useState } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import { ProjectEditor } from '../../src/components/ProjectEditor';
import client from '../../src/api/client';
import { useAuthStore } from '../../src/store/authStore';
import '../../src/index.css';

const names = ['ООО КРОКНА ИНЖИНИРИНГ', 'ООО ПРОЗРАЧНЫЕ РЕШЕНИЯ'];
const project = { id: 91, number: 'QA', invoice_number: '00000091', customer: names[0], sections: [], extra_components: '[]' };
let requests: object[] = [];
let failNext = false;
useAuthStore.setState({ token: 'fixture-only' });
localStorage.setItem('access_token', 'fixture-only');
client.defaults.adapter = async config => {
  if (config.url?.includes('/quote')) throw new Error('No pricing data needed for this UI fixture');
  if (config.url === '/api/projects/91' && config.method === 'put') {
    const update = JSON.parse(config.data);
    requests.push(update);
    await new Promise(resolve => setTimeout(resolve, 100));
    if (failNext) { failNext = false; throw new Error('Test connection failure'); }
    Object.assign(project, update);
  }
  const data = config.url === '/api/customers'
    ? names.map((name, id) => ({ id, name, is_active: true })) : structuredClone(project);
  return { data, config, headers: {}, status: 200, statusText: 'OK' };
};
function App() {
  const [version, setVersion] = useState(0);
  return <MemoryRouter><button id="reload-project" onClick={() => setVersion(value => value + 1)}>Reload fixture</button>
    <ProjectEditor key={version} projectId={91} onBack={() => {}} />
  </MemoryRouter>;
}
createRoot(document.getElementById('root')!).render(<App />);
const pause = (ms = 200) => new Promise(resolve => setTimeout(resolve, ms));
function assert(value: unknown, message: string) { if (!value) throw new Error(message); }
function select(name: string) {
  const field = document.querySelector<HTMLSelectElement>('#project-customer')!;
  Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value')!.set!.call(field, name);
  field.dispatchEvent(new Event('change', { bubbles: true }));
}
function button(text: string) {
  return [...document.querySelectorAll<HTMLButtonElement>('[data-project-customer] button')].find(item => item.textContent === text)!;
}
async function run() {
  await pause(1200);
  assert(document.querySelector<HTMLSelectElement>('#project-customer')!.value === names[0], 'Existing customer can be edited');
  select(names[1]); await pause();
  assert(requests.length === 0 && project.customer === names[0], 'Selection alone does not save');
  button('Отмена').click(); await pause();
  assert(document.querySelector<HTMLSelectElement>('#project-customer')!.value === names[0], 'Cancel restores saved customer');
  select(names[1]); await pause();
  failNext = true;
  button('Сохранить заказчика').click(); await pause(20);
  assert(document.querySelector<HTMLSelectElement>('#project-customer')!.disabled, 'No competing change during save');
  await pause();
  assert(document.querySelector('[data-project-customer] [role=alert]'), 'Save error is visible');
  assert(document.querySelector<HTMLSelectElement>('#project-customer')!.value === names[1], 'Failed save keeps the draft');
  assert(project.customer === names[0], 'Failed save does not change persisted customer');
  button('Сохранить заказчика').click(); await pause(300);
  assert(project.customer === names[1] && !button('Сохранить заказчика'), 'Retry saves and clears the dirty state');
  assert(requests.every(payload => JSON.stringify(payload) === JSON.stringify({ customer: names[1] })), 'Only customer is sent');
  assert(document.querySelector('.text-fg\\/60.truncate')?.textContent === names[1], 'Page header reflects saved customer');
  document.getElementById('reload-project')!.click(); await pause(500);
  assert(document.querySelector<HTMLSelectElement>('#project-customer')!.value === names[1], 'Change survives reload');
  project.customer = 'Старое название';
  requests = [];
  document.getElementById('reload-project')!.click(); await pause(500);
  assert(document.querySelector<HTMLSelectElement>('#project-customer')!.value === 'Старое название', 'Legacy name is preserved on opening');
  assert(requests.length === 0, 'Opening an old project never writes customer data');
  select(names[0]); await pause(); button('Сохранить заказчика').click(); await pause(300);
  assert(project.customer === names[0], 'Legacy customer can be replaced with an active entry');
  document.getElementById('result')!.textContent = 'Customer change, explicit save, cancel, failure/retry, reload, header and legacy value passed';
  document.body.dataset.smoke = 'passed';
}
run().catch(error => { document.getElementById('result')!.textContent = String(error.stack || error); document.body.dataset.smoke = 'failed'; });
