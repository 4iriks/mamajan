import { createServer } from 'vite';
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const { chromium } = await import(pathToFileURL(path.join(process.env.QA_NODE_MODULES, 'playwright/index.mjs')).href);
const fixture = process.argv[2] || 'economics';
if (!['economics', 'editor-layout', 'cs-editor', 'extra-components'].includes(fixture)) throw new Error('Unknown fixture');
const executablePath = [path.join(process.env.LOCALAPPDATA || '', 'ms-playwright/chromium_headless_shell-1208/chrome-headless-shell-win64/chrome-headless-shell.exe'), 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', 'C:/Program Files/Google/Chrome/Application/chrome.exe', '/usr/bin/chromium'].find(file => fs.existsSync(file));
const vite = await createServer({
  optimizeDeps: { entries: [`scripts/browser-fixtures/${fixture}.html`] },
  server: { host: '127.0.0.1', port: 4194, strictPort: true, watch: { ignored: ['**/tmp/**', '**/office-qa-*/**', '**/outputs/**'] } },
});
await vite.listen();
let browser;
try {
  const url = `http://127.0.0.1:4194/scripts/browser-fixtures/${fixture}.html`;
  for (let retry = 0; retry < 100; retry++) {
    try { if ((await fetch(url)).ok) break; } catch { /* startup */ }
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  console.log('Fixture ready; launching browser');
  browser = await chromium.launch({ executablePath, headless: true, timeout: 15000, args: ['--no-proxy-server'] });
  console.log('Browser ready');
  for (const [width, height] of [[1366, 768], [1280, 720]]) {
    const page = await browser.newPage({ viewport: { width, height }, acceptDownloads: true });
    page.on('console', message => { if (message.type() === 'error' || message.text().startsWith('QA')) console.log(message.text()); });
    page.on('pageerror', error => console.error(error.message));
    page.on('requestfailed', request => console.error('Request failed', request.url(), request.failure()));
    page.on('response', response => { if (response.url().includes('economics') || response.status() >= 400) console.log(response.status(), response.url()); });
    await page.route(/\/api\/(projects|pricing|catalog|calculate)\//, route => route.fulfill({ status: 200, contentType: 'text/html', body: '<html><body>Локальный предпросмотр</body></html>' }));
    await page.goto(url, { waitUntil: 'commit', timeout: 45000 });
    console.log('Fixture loaded');
    try {
      await page.waitForFunction(() => ['passed', 'failed'].includes(document.body.dataset.smoke), undefined, { timeout: 120000 });
    } finally {
      fs.mkdirSync('tmp/oct12-qa/browser', { recursive: true });
      await page.screenshot({ path: `tmp/oct12-qa/browser/${fixture}-${width}.png`, fullPage: true }).catch(error => console.error('Diagnostic screenshot failed:', error.message));
    }
    const state = await page.locator('body').getAttribute('data-smoke');
    const result = await page.locator('#result').textContent();
    if (state !== 'passed') throw new Error(result);
    if (fixture === 'editor-layout') {
      await page.locator('#cs').click();
      const canvas = page.locator('.cs-canvas svg');
      await canvas.waitFor();
      const before = await canvas.evaluate(svg => ({ viewBox: svg.getAttribute('viewBox'), points: [...svg.querySelectorAll('circle')].map(p => [p.getAttribute('cx'), p.getAttribute('cy')]) }));
      const point = await canvas.locator('circle').first().boundingBox();
      await page.mouse.move(point.x + point.width / 2, point.y + point.height / 2);
      await page.mouse.down();
      await page.mouse.move(point.x + point.width / 2 + 12, point.y + point.height / 2 - 12, { steps: 6 });
      await page.mouse.up();
      const after = await canvas.evaluate(svg => ({ viewBox: svg.getAttribute('viewBox'), points: [...svg.querySelectorAll('circle')].map(p => [p.getAttribute('cx'), p.getAttribute('cy')]) }));
      if (after.viewBox !== before.viewBox || JSON.stringify(after.points.slice(1)) !== JSON.stringify(before.points.slice(1)) || JSON.stringify(after.points[0]) === JSON.stringify(before.points[0])) throw new Error('Pointer drag changed other vertices or scale');
      await page.locator('.cs-dimension-editor input').first().waitFor({ state: 'visible' });
      await page.screenshot({ path: `tmp/oct12-qa/browser/cs-pointer-${width}.png`, fullPage: true });
    }
    console.log(`${fixture} ${width}x${height}: ${result}`);
    await page.close();
  }
} finally {
  await browser?.close();
  await vite.close();
}
