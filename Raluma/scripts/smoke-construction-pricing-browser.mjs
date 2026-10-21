// Run against the isolated DB created by seed-construction-pricing-qa.py.
// Start Vite with VITE_API_URL and the backend with DATABASE_URL pointing to that copy.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
const modulePath = process.env.PLAYWRIGHT_MODULE || path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs');
const { chromium } = await import(pathToFileURL(modulePath));
const api = process.env.QA_API_URL || 'http://127.0.0.1:8813';
const origin = process.env.QA_FRONTEND_URL || 'http://localhost:8833';
let token;
async function request(url, body, method = body ? 'POST' : 'GET') {
  const response = await fetch(`${api}${url}`, { method, headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) }, body: body ? JSON.stringify(body) : undefined });
  assert.equal(response.ok, true, `${url}: ${response.status} ${await response.clone().text()}`);
  return response.json();
}
token = (await request('/api/auth/login', { username: 'admin', password: process.env.QA_ADMIN_PASSWORD || 'admin123' })).access_token;
const initial = await request('/api/construction-pricing/systems/SLIDE_1');
await request('/api/construction-pricing/systems/SLIDE_1', { token: initial.token, general: { markup_percent: '0', discount_percent: '0' } }, 'PUT');
const browser = await chromium.launch({ channel: process.env.QA_BROWSER_CHANNEL || 'msedge', headless: true });
const page = await browser.newPage({ viewport: { width: 1540, height: 1080 } });
const output = path.resolve('tmp/construction-pricing-qa'); fs.mkdirSync(output, { recursive: true });
const errors = [];
page.on('pageerror', error => errors.push(error.message));
await page.addInitScript(value => localStorage.setItem('access_token', value), token);
async function settled() {
  await page.waitForFunction(() => !document.body.textContent.includes('Загружаем настройки системы'));
  await page.waitForFunction(() => document.querySelector('[aria-label="Проверка на конструкции"]')?.getAttribute('aria-busy') === 'false');
  await page.waitForFunction(() => document.querySelector('[data-testid="sample-total"]')?.textContent?.includes('₽'));
}
async function previewAfter(action) {
  const response = page.waitForResponse(response => response.url().includes('/preview') && response.request().method() === 'POST' && response.status() === 200);
  await action(); return (await response).json();
}
try {
  const firstPreview = page.waitForResponse(response => response.url().endsWith('/SLIDE_1/preview') && response.status() === 200);
  await page.goto(`${origin}/admin/pricing`);
  let result = await (await firstPreview).json();
  assert.equal(result.samples[0].draft.complete, true, JSON.stringify(result.samples[0].draft.issues));
  await settled();
  const key = result.samples[0].draft.bom.find(row => row.sku === 'RS112')?.component_key || result.samples[0].draft.bom[0].component_key;
  const component = page.locator(`[data-component-key="${key}"]`);
  const markup = component.getByRole('textbox', { name: /: наценка$/ });
  const before = result.samples[0].draft.total;
  result = await previewAfter(() => markup.fill('67.89'));
  assert.notEqual(result.samples[0].draft.total, before);
  await settled();
  assert.match(await component.innerText(), /Было/);
  result = await previewAfter(() => page.getByLabel('Общее для системы: наценка', { exact: true }).fill('12'));
  assert.equal(result.samples[0].draft.stages.markup_percent, '12');
  await previewAfter(() => page.getByRole('button', { name: 'Добавить пример', exact: true }).click());
  await previewAfter(() => page.getByLabel('Выбранная конструкция', { exact: true }).selectOption('4'));
  await settled();
  await previewAfter(() => page.getByRole('button', { name: /Слайд 2 ряда/ }).click());
  await previewAfter(() => page.getByRole('button', { name: /Слайд 1 ряд/ }).click());
  assert.equal(await markup.inputValue(), '67.89');
  assert.equal(await page.getByLabel('Общее для системы: наценка', { exact: true }).inputValue(), '12');
  // Network errors leave the typed value intact and retry uses the same draft.
  await page.route('**/SLIDE_1/preview', route => route.abort());
  await markup.fill('68.12');
  await page.getByRole('button', { name: 'Повторить расчёт' }).waitFor();
  assert.equal(await markup.inputValue(), '68.12');
  await page.unroute('**/SLIDE_1/preview');
  result = await previewAfter(() => page.getByRole('button', { name: 'Повторить расчёт' }).click());
  await settled();
  // A genuine concurrent save causes an optimistic conflict; edits survive.
  const config = await request('/api/construction-pricing/systems/SLIDE_1');
  await request('/api/construction-pricing/systems/SLIDE_1', { token: config.token, general: { markup_percent: '1', discount_percent: '2' } }, 'PUT');
  const conflict = page.waitForResponse(response => response.url().endsWith('/SLIDE_1') && response.request().method() === 'PUT');
  await page.getByRole('button', { name: 'Сохранить систему' }).click();
  assert.equal((await conflict).status(), 409);
  assert.equal(await markup.inputValue(), '68.12');
  await previewAfter(() => page.getByRole('button', { name: 'Обновить исходные цены' }).click());
  assert.equal(await page.getByLabel('Общее для системы: скидка', { exact: true }).inputValue(), '2', 'untouched global field adopts latest saved value');
  assert.equal(await markup.inputValue(), '68.12');
  await settled();
  const saved = page.waitForResponse(response => response.url().endsWith('/SLIDE_1') && response.request().method() === 'PUT' && response.status() === 200);
  await page.getByRole('button', { name: 'Сохранить систему' }).click(); await saved;
  await settled();
  const actual = await request('/api/construction-pricing/systems/SLIDE_1/preview', { section_ids: [4] });
  const quote = await request('/api/pricing/projects/4');
  assert.equal(quote.calculation.sections[0].internal_total, actual.samples[0].draft.total);
  await page.screenshot({ path: path.join(output, 'pricing-desktop.png'), fullPage: true });
  await previewAfter(() => page.getByRole('button', { name: 'Удалить пример 2', exact: true }).click());
  await previewAfter(() => page.getByLabel('Заменить пример 1', { exact: true }).selectOption('2'));
  await previewAfter(() => page.getByRole('button', { name: 'Добавить пример', exact: true }).click());
  await page.setViewportSize({ width: 390, height: 844 });
  await settled();
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true, 'page must fit a phone');
  await page.screenshot({ path: path.join(output, 'pricing-mobile.png'), fullPage: true });
  await page.setViewportSize({ width: 1540, height: 1080 });
  result = await previewAfter(() => page.getByRole('button', { name: /^ЦС/ }).click());
  assert.equal(result.samples[0].draft.complete, true, JSON.stringify(result.samples[0].draft.issues));
  await settled();
  assert.ok(await page.locator('svg').count());
  await page.screenshot({ path: path.join(output, 'pricing-cs.png'), fullPage: true });
  const csComponentKey = result.samples[0].draft.bom.find(row => row.role === 'outer').component_key;
  const catalogRows = await request('/api/catalog/hardware');
  const csItem = catalogRows.find(row => row.id === Number(csComponentKey.split(':')[0]));
  const csFinish = csItem.finishVariants.find(row => row.id === Number(csComponentKey.split(':')[1]));
  csFinish.costIsSet = false;
  await request(`/api/catalog/hardware/${csItem.id}`, csItem, 'PUT');
  result = await previewAfter(() => page.getByRole('button', { name: 'Обновить исходные цены' }).click());
  assert.equal(result.samples[0].draft.complete, false);
  const unknown = page.locator(`[data-component-key="${csComponentKey}"]`);
  assert.match(await unknown.innerText(), /Не заполнена/);
  assert.doesNotMatch(await unknown.innerText(), /Расход в образце\s+—/);
  csFinish.costIsSet = true; csFinish.cost = '0';
  await request(`/api/catalog/hardware/${csItem.id}`, csItem, 'PUT');
  result = await previewAfter(() => page.getByRole('button', { name: 'Обновить исходные цены' }).click());
  assert.equal(result.samples[0].draft.complete, true, 'explicit zero remains a valid cost');
  await previewAfter(() => page.getByLabel('Общее для системы: наценка', { exact: true }).fill('9.5'));
  page.once('dialog', dialog => dialog.accept());
  const restored = page.waitForResponse(response => response.url().endsWith('/SLIDE_1/preview') && response.status() === 200);
  await page.reload(); await restored;
  await previewAfter(() => page.getByRole('button', { name: /^ЦС/ }).click());
  assert.equal(await page.getByLabel('Общее для системы: наценка', { exact: true }).inputValue(), '9.5');
  await previewAfter(() => page.getByRole('button', { name: 'Сбросить', exact: true }).click());
  // Catalogue contains only standalone sale; mass changes retain the kit editor.
  await page.goto(`${origin}/admin/catalog/hardware`);
  await page.getByRole('button', { name: /Массовые изменения/ }).click();
  await page.getByText('Системы ЦС', { exact: true }).waitFor();
  assert.doesNotMatch(await page.locator('body').innerText(), /Готовые правила|Вернуть правило|Массовая наценка|Применить ко всем/);
  await page.screenshot({ path: path.join(output, 'catalog-mass-cs.png'), fullPage: true });
  await page.goto(`${origin}/admin/catalog/hardware?item=${Number(key.split(':')[0])}`);
  await page.getByText('Позиция каталога', { exact: true }).waitFor();
  assert.doesNotMatch(await page.locator('body').innerText(), /В готовой конструкции|Отходы|Вернуть правило/);
  assert.match(await page.locator('body').innerText(), /Продажа детали/i);
  await page.screenshot({ path: path.join(output, 'catalog-sale.png'), fullPage: true });
  assert.deepEqual(errors, []);
  console.log('Browser QA passed: real API parity, drafts, switching, examples, network recovery, conflict, save, mobile, CS and catalogue.');
} finally { await browser.close(); }
