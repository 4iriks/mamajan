// Run against an isolated local backend database and Vite server; never production.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const app = process.env.SERVICES_QA_APP || 'http://127.0.0.1:8848';
const api = process.env.SERVICES_QA_API || 'http://127.0.0.1:8838';
for (const url of [app, api]) assert.equal(new URL(url).hostname, '127.0.0.1', 'Local fixture servers required');
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
const output = path.resolve('tmp/services-sidebar-qa');
fs.mkdirSync(output, { recursive: true });
const login = await fetch(`${api}/api/auth/login`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username: 'admin', password: 'admin123' }) }).then(r => r.json());
assert.ok(login.access_token);
async function request(route, method = 'GET', body) {
  const response = await fetch(`${api}${route}`, { method, headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${login.access_token}` }, ...(body ? { body: JSON.stringify(body) } : {}) });
  const data = await response.json();
  assert.ok(response.ok, `${method} ${route}: ${JSON.stringify(data)}`);
  return data;
}
const customers = await request('/api/customers');
const customer = customers[0] || await request('/api/customers', 'POST', { name: 'Проверка услуг' });
const project = await request('/api/projects', 'POST', { customer: customer.name, number: `SERVICES-QA-${Date.now()}`, extra_components: JSON.stringify([{ id: 'qa-part', name: 'Крепёж', qty: '3', unit_price: '100', unit: 'шт', category: 'component' }]) });
// Initialize the quote before development StrictMode issues duplicate initial GETs.
await request(`/api/projects/${project.id}/quote`);
const browser = await chromium.launch({ headless: true, ...(process.env.SMOKE_BROWSER_PATH ? { executablePath: process.env.SMOKE_BROWSER_PATH } : { channel: 'msedge' }) });
const page = await browser.newPage({ viewport: { width: 1366, height: 768 } });
const errors = [];
page.on('pageerror', error => errors.push(error.message));
page.on('dialog', dialog => dialog.accept());
await page.route('**/*', route => ['127.0.0.1', 'localhost'].includes(new URL(route.request().url()).hostname) ? route.continue() : route.abort());
await page.addInitScript(token => localStorage.setItem('access_token', token), login.access_token);
const dialog = page.getByRole('dialog', { name: 'Услуги проекта' });
const footer = page.locator('[data-sidebar-project-actions]');
const servicesButton = footer.getByRole('button', { name: /^Услуги/ });
const save = () => dialog.getByRole('button', { name: 'Сохранить и пересчитать', exact: true }).click();
try {
  await page.goto(`${app}/projects/${project.id}`, { waitUntil: 'domcontentloaded' });
  await servicesButton.waitFor();
  await servicesButton.click();
  assert.equal(await page.locator('summary').filter({ hasText: /^Услуги/ }).count(), 0);
  assert.equal(await page.locator('[data-sections-below]').count(), 0);
  await dialog.getByRole('button', { name: 'Добавить услугу' }).click();
  const first = dialog.getByRole('article', { name: 'Услуга 1', exact: true });
  await first.getByLabel('Название', { exact: true }).fill('Монтаж');
  await first.getByLabel('Количество', { exact: true }).fill('2,5');
  await first.getByLabel('Цена продажи, ₽/ед.', { exact: true }).fill('1200');
  await first.getByLabel('Себестоимость, ₽/ед.', { exact: true }).fill('400');
  await dialog.getByRole('button', { name: 'Добавить услугу' }).click();
  const second = dialog.getByRole('article', { name: 'Услуга 2', exact: true });
  await second.getByLabel('Название', { exact: true }).fill('Доставка');
  await second.getByLabel('Цена продажи, ₽/ед.', { exact: true }).fill('700');
  await dialog.getByRole('button', { name: 'Копировать услугу 2', exact: true }).click();
  const third = dialog.getByRole('article', { name: 'Услуга 3', exact: true });
  await third.getByLabel('Название', { exact: true }).fill('Подъём');
  await third.getByLabel('Количество', { exact: true }).fill('2');
  await third.getByLabel('Цена продажи, ₽/ед.', { exact: true }).fill('150');
  await dialog.getByRole('button', { name: 'Копировать услугу 1', exact: true }).click();
  await dialog.getByRole('button', { name: 'Удалить услугу 4', exact: true }).click();
  const ids = await dialog.locator('[data-service-id]').evaluateAll(rows => rows.map(row => row.dataset.serviceId));
  assert.equal(new Set(ids).size, 3);
  // Validation and failed requests must preserve every entered row.
  await second.getByLabel('Количество', { exact: true }).fill('0');
  await save();
  await dialog.getByRole('alert').waitFor();
  assert.equal((await request(`/api/pricing/projects/${project.id}`)).config.services.length, 0);
  await second.getByLabel('Количество', { exact: true }).fill('1');
  await page.route(`**/api/projects/${project.id}/quote/config`, route => route.fulfill({ status: 503, contentType: 'application/json', body: '{"detail":"QA simulated failure"}' }));
  await save();
  await dialog.getByText('Не удалось сохранить стоимость и скидки. Ввод сохранён на экране.', { exact: true }).waitFor();
  assert.equal(await first.getByLabel('Название', { exact: true }).inputValue(), 'Монтаж');
  await page.unroute(`**/api/projects/${project.id}/quote/config`);
  await dialog.getByRole('button', { name: 'Закрыть', exact: true }).click();
  await dialog.waitFor({ state: 'hidden' });
  await servicesButton.click();
  assert.equal(await dialog.locator('[data-service-id]').count(), 3, 'Closing must retain the project draft');
  await save();
  await dialog.waitFor({ state: 'hidden' });
  let quote = await request(`/api/projects/${project.id}/quote`);
  assert.equal(quote.lines.filter(row => row.category === 'service').length, 3);
  assert.equal(Number(quote.totals.grand_total), 4300, '300 parts + 3000 installation + 700 delivery + 300 lifting');
  await page.getByLabel('Общая, %', { exact: true }).fill('10');
  await page.getByRole('button', { name: 'Сохранить и пересчитать', exact: true }).click();
  await page.getByRole('button', { name: 'Обновить расчёт', exact: true }).waitFor();
  quote = await request(`/api/projects/${project.id}/quote`);
  assert.equal(Number(quote.totals.grand_total), 3870);
  await page.reload({ waitUntil: 'domcontentloaded' });
  await servicesButton.click();
  assert.equal(await first.getByLabel('Количество', { exact: true }).inputValue(), '2.5');
  assert.equal(await first.getByLabel('Себестоимость, ₽/ед.', { exact: true }).inputValue(), '400');
  assert.match(await servicesButton.innerText(), /3/);
  await page.waitForFunction(() => getComputedStyle(document.querySelector('[role="dialog"]')).opacity === '1');
  await page.screenshot({ path: path.join(output, 'services-desktop.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: path.join(output, 'services-mobile.png'), fullPage: true });
  assert.ok(await dialog.evaluate(el => el.scrollWidth <= el.clientWidth));
  await dialog.getByRole('button', { name: 'Закрыть', exact: true }).click();
  // Long real section list, ordinary wheel scrolling, persistent footer and passive hint.
  for (let i = 1; i <= 24; i++) await request(`/api/projects/${project.id}/sections`, 'POST', { name: `Секция ${i}`, system: 'ЦС', width: 1200, height: 2000 });
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => {
    const button = document.querySelector('[data-sidebar-project-actions] button:nth-child(2)');
    return button && !button.disabled;
  });
  const viewport = page.locator('[data-sidebar-sections]');
  const hint = page.locator('[data-sections-below]');
  await hint.waitFor();
  assert.equal(await hint.getAttribute('role'), null);
  assert.equal(await hint.evaluate(el => getComputedStyle(el).pointerEvents), 'none');
  assert.equal(await viewport.evaluate(el => el.scrollTop), 0, 'Hint must not scroll automatically');
  const initial = await footer.boundingBox();
  await page.screenshot({ path: path.join(output, 'sections-desktop.png'), fullPage: true });
  await viewport.hover();
  await page.mouse.wheel(0, 10000);
  await hint.waitFor({ state: 'hidden' });
  const after = await footer.boundingBox();
  assert.ok(Math.abs(initial.y - after.y) < 1 && Math.abs(initial.height - after.height) < 1, 'Footer must not move with the list');
  await viewport.getByText('Секция 24', { exact: true }).waitFor();
  await page.mouse.wheel(0, -10000);
  await hint.waitFor();
  await footer.getByRole('button', { name: 'Примечания' }).click();
  for (const size of [{ width: 1366, height: 768 }, { width: 768, height: 600 }, { width: 390, height: 844 }, { width: 320, height: 568 }]) {
    await page.setViewportSize(size);
    await hint.waitFor();
    const box = await footer.boundingBox();
    assert.ok(box.y >= 0 && box.y + box.height <= size.height + 1, `Footer visible at ${size.width}×${size.height}`);
    assert.ok(await viewport.evaluate(el => el.clientHeight > 60), 'Section list remains usable');
    await page.screenshot({ path: path.join(output, `sections-${size.width}.png`), fullPage: true });
  }
  assert.deepEqual(errors, [], 'No browser runtime errors');
  console.log(JSON.stringify({ passed: true, project_id: project.id, total_before_discount: 4300, total_after_discount: 3870, screenshots: output, scenarios: ['multiple services', 'copy/delete', 'validation', 'failed save retains draft', 'save/reload', 'shared order discount', 'private cost', 'mobile modal', '24 sections', 'fixed footer', 'passive overflow hint', 'bottom hides hint', 'resize and notes'] }, null, 2));
} catch (error) {
  await page.screenshot({ path: path.join(output, 'failure.png'), fullPage: true });
  console.error((await page.locator('body').innerText()).slice(-10000));
  throw error;
} finally { await browser.close(); }
