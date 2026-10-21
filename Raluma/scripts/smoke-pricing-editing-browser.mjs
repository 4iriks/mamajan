// Uses only the local isolated database prepared by seed-construction-pricing-qa.py.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
const { chromium } = await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE || path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs')));
const api = process.env.QA_API_URL || 'http://127.0.0.1:8813';
const origin = process.env.QA_FRONTEND_URL || 'http://localhost:8833';
assert(['localhost', '127.0.0.1'].includes(new URL(api).hostname), 'Mutating checks require an isolated local API');
let token;
async function request(url, body, method = body ? 'POST' : 'GET') {
  const response = await fetch(api + url, { method, headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) }, body: body ? JSON.stringify(body) : undefined });
  assert(response.ok, `${method} ${url}: ${response.status}`);
  return response.json();
}
token = (await request('/api/auth/login', { username: 'admin', password: process.env.QA_ADMIN_PASSWORD || 'admin123' })).access_token;
const browser = await chromium.launch({ channel: 'msedge', headless: true });
const page = await browser.newPage({ viewport: { width: 1540, height: 1080 } });
const output = path.resolve('tmp/construction-pricing-qa'); fs.mkdirSync(output, { recursive: true });
const errors = [];
page.on('pageerror', error => errors.push(error.message));
await page.addInitScript(value => localStorage.setItem('access_token', value), token);
async function settled() {
  await page.waitForFunction(() => document.querySelector('[aria-label="Проверка на конструкции"]')?.getAttribute('aria-busy') === 'false');
}
async function previewAfter(action) {
  const response = page.waitForResponse(response => response.url().endsWith('/SLIDE_1/preview') && response.status() === 200);
  await action(); const result = await (await response).json(); await settled(); return result;
}
try {
  const result = await previewAfter(() => page.goto(origin + '/admin/pricing'));
  const key = (result.samples[0].draft.bom.find(row => row.sku === 'RS112') || result.samples[0].draft.bom[0]).component_key;
  const card = page.locator(`[data-component-key="${key}"]`);
  const panel = page.getByRole('region', { name: 'Проверка на конструкции', exact: true });
  await page.getByLabel('Используются в образце', { exact: true }).check();
  const count = await page.locator('[data-component-key]').count();
  const diagram = await panel.locator('svg').first().elementHandle();
  const fields = [
    card.getByRole('textbox', { name: /: отходы$/ }),
    card.getByRole('textbox', { name: /: наценка$/ }),
    card.getByRole('textbox', { name: /: скидка$/ }),
    page.getByLabel('Общее для системы: наценка', { exact: true }),
    page.getByLabel('Общее для системы: скидка', { exact: true }),
  ];
  for (const field of fields) {
    const original = await field.inputValue();
    await field.fill(''); await page.waitForTimeout(300);
    assert.equal(await field.inputValue(), '', 'Clearing must not reinsert zero');
    assert.equal(await field.evaluate(el => el === document.activeElement), true, 'Clearing must retain focus');
    assert.equal(await page.locator('[data-component-key]').count(), count, 'Used-components filter must retain cards while input is blank');
    assert(await diagram.evaluate(el => el.isConnected), 'The same drawing node must remain mounted');
    assert(await panel.locator('[data-testid="sample-total"]').isVisible());
    assert(await page.getByRole('button', { name: 'Сохранить систему' }).isDisabled());
    assert.match(await panel.innerText(), /Пока показан предыдущий расчёт/);
    await previewAfter(() => field.fill(original));
  }
  // Keep the entire panel and physical consumption while a valid request is pending.
  const markup = fields[1];
  const originalMarkup = await markup.inputValue();
  const oldTotal = await page.getByTestId('sample-total').innerText();
  const oldQuantity = await card.innerText();
  await page.route('**/SLIDE_1/preview', async route => { await new Promise(resolve => setTimeout(resolve, 600)); await route.continue(); });
  const delayed = page.waitForResponse(response => response.url().endsWith('/SLIDE_1/preview') && response.status() === 200);
  await markup.fill(String(Number(originalMarkup) + 7.5));
  await page.waitForTimeout(350);
  assert(await diagram.evaluate(el => el.isConnected));
  assert.equal(await page.getByTestId('sample-total').innerText(), oldTotal);
  assert.equal(await page.locator('[data-component-key]').count(), count);
  assert.equal((await card.innerText()).match(/Расход в образце[^\n]*/)?.[0], oldQuantity.match(/Расход в образце[^\n]*/)?.[0]);
  await delayed; await settled(); await page.unroute('**/SLIDE_1/preview');
  // Another editor changes untouched fields on this same component.
  const config = await request('/api/construction-pricing/systems/SLIDE_1');
  const old = config.components.find(row => row.key === key).settings;
  const updated = { ...old, waste_percent: String(Number(old.waste_percent) + 3), discount_percent: old.discount_percent === '8' ? '9' : '8' };
  await request('/api/construction-pricing/systems/SLIDE_1', { token: config.token, components: { [key]: updated } }, 'PUT');
  await previewAfter(() => page.getByRole('button', { name: 'Обновить исходные цены' }).click());
  assert.equal(await fields[0].inputValue(), updated.waste_percent);
  assert.equal(await fields[2].inputValue(), updated.discount_percent);
  assert.equal(await markup.inputValue(), String(Number(originalMarkup) + 7.5), 'Refresh must keep only the field actually edited');
  await previewAfter(() => page.getByRole('button', { name: 'Сбросить', exact: true }).click());
  const current = await request('/api/construction-pricing/systems/SLIDE_1');
  const updatedGeneral = { ...current.general, markup_percent: String(Number(current.general.markup_percent) + 2) };
  await request('/api/construction-pricing/systems/SLIDE_1', { token: current.token, general: updatedGeneral }, 'PUT');
  await previewAfter(() => page.reload());
  assert.equal(await fields[3].inputValue(), updatedGeneral.markup_percent, 'A clean restored tab must use current server settings');
  // Even a draft reloaded while a field is blank still has a drawing and sample usage.
  await fields[3].fill(''); page.once('dialog', dialog => dialog.accept());
  const reloadPreview = page.waitForResponse(response => response.url().endsWith('/SLIDE_1/preview') && response.status() === 200);
  await page.reload(); await reloadPreview;
  await panel.locator('svg').first().waitFor();
  assert.equal(await fields[3].inputValue(), '');
  await page.getByLabel('Используются в образце', { exact: true }).check();
  assert(await page.locator('[data-component-key]').count() > 0);
  await previewAfter(() => fields[3].fill(updatedGeneral.markup_percent));
  await page.getByLabel('Используются в образце', { exact: true }).uncheck();
  for (const width of [1920, 1540, 1366, 1024, 768, 390, 320]) {
    await page.setViewportSize({ width, height: 1080 });
    await page.waitForTimeout(80);
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `No overflow at ${width}px`);
    const boxes = await page.locator('[data-component-key]').evaluateAll(cards => cards.slice(0, 2).map(card => { const box = card.getBoundingClientRect(); return { x: box.x, y: box.y, width: box.width }; }));
    if (width >= 1366) assert(Math.abs(boxes[0].y - boxes[1].y) < 1 && boxes[1].x > boxes[0].x, `Two readable cards across at ${width}px`);
    for (const element of await page.locator('[data-component-key]').first().locator('input, .pricing-price-output > div').all()) {
      assert(await element.evaluate(el => el.scrollWidth <= el.clientWidth + 1), `Complete field value fits at ${width}px`);
    }
    if ([1540, 390].includes(width)) await page.screenshot({ path: path.join(output, `pricing-compact-${width}.png`), fullPage: true });
  }
  assert.deepEqual(errors, []);
  console.log('Pricing editing checks passed: all five empty percentage fields, preserved focus/cards/drawing, delayed replies, per-field conflict refresh, clean and incomplete draft reload, two-column cards and seven viewport sizes.');
} finally { await browser.close(); }
