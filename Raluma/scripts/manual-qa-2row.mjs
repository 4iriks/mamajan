import { execFileSync, spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const appUrl = process.argv[2] ?? process.env.QA_APP_URL ?? 'https://raluma.tech';
const outputDir = process.env.QA_OUTPUT_DIR ?? 'C:\\tmp\\raluma-qa-2row';

const browserCandidates = [
  process.env.SMOKE_BROWSER_PATH,
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
  '/usr/bin/google-chrome',
  '/usr/bin/google-chrome-stable',
  '/usr/bin/chromium',
  '/usr/bin/chromium-browser',
].filter(Boolean);

const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

function assert(value, message) {
  if (!value) throw new Error(message);
}

function findBrowser() {
  const browserPath = browserCandidates.find(candidate => fs.existsSync(candidate));
  if (!browserPath) {
    throw new Error('Chrome/Edge не найден. Укажите путь через SMOKE_BROWSER_PATH.');
  }
  return browserPath;
}

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`CDP request failed ${response.status}: ${url}`);
  return response.json();
}

async function waitForPageTarget(port) {
  const listUrl = `http://127.0.0.1:${port}/json/list`;
  for (let attempt = 0; attempt < 80; attempt += 1) {
    try {
      const targets = await fetchJson(listUrl);
      const page = targets.find(target => target.type === 'page' && target.webSocketDebuggerUrl);
      if (page) return page.webSocketDebuggerUrl;
    } catch {
      // Browser is still starting.
    }
    await sleep(100);
  }
  throw new Error('Не удалось подключиться к headless browser по CDP.');
}

async function connectCdp(wsUrl) {
  const ws = new WebSocket(wsUrl);
  const pending = new Map();
  const runtimeErrors = [];
  let nextId = 1;

  ws.addEventListener('message', event => {
    const message = JSON.parse(event.data);
    if (message.id && pending.has(message.id)) {
      const { resolve, reject } = pending.get(message.id);
      pending.delete(message.id);
      if (message.error) reject(new Error(`${message.error.message}: ${message.error.data ?? ''}`));
      else resolve(message.result);
      return;
    }
    if (message.method === 'Runtime.exceptionThrown') {
      runtimeErrors.push(message.params.exceptionDetails?.text ?? 'Runtime exception');
    }
  });

  await new Promise((resolve, reject) => {
    ws.addEventListener('open', resolve, { once: true });
    ws.addEventListener('error', reject, { once: true });
  });

  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const id = nextId;
    nextId += 1;
    pending.set(id, { resolve, reject });
    ws.send(JSON.stringify({ id, method, params }));
  });

  return {
    command(method, params = {}) {
      return send(method, params);
    },
    async evaluate(expression) {
      const result = await send('Runtime.evaluate', {
        expression,
        awaitPromise: true,
        returnByValue: true,
        userGesture: true,
      });
      if (result.exceptionDetails) {
        throw new Error(result.exceptionDetails.exception?.description ?? result.exceptionDetails.text);
      }
      return result.result?.value;
    },
    close() {
      ws.close();
    },
    runtimeErrors,
  };
}

async function waitForExpression(cdp, expression, label, timeoutMs = 10000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    if (await cdp.evaluate(`Boolean(${expression})`)) return;
    await sleep(150);
  }
  const bodyText = await cdp.evaluate('document.body?.innerText?.slice(0, 2000) ?? ""');
  throw new Error(`Timeout waiting for ${label}. Body:\n${bodyText}`);
}

async function clickText(cdp, text) {
  const result = await cdp.evaluate(`(() => {
    const normalize = value => (value || '').replace(/\\s+/g, ' ').trim();
    const candidates = [...document.querySelectorAll('button, a, [role="button"]')];
    const element = candidates.find(item => normalize(item.textContent).includes(${JSON.stringify(text)}));
    if (!element) return { ok: false, body: document.body.innerText.slice(0, 1400) };
    element.scrollIntoView({ block: 'center', inline: 'center' });
    element.click();
    return { ok: true };
  })()`);
  assert(result?.ok, `Не найдена кликабельная надпись "${text}".\n${result?.body ?? ''}`);
}

async function fillBySelector(cdp, selector, value) {
  const result = await cdp.evaluate(`(() => {
    const element = document.querySelector(${JSON.stringify(selector)});
    if (!element) return false;
    const setter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(element), 'value')?.set;
    setter?.call(element, ${JSON.stringify(value)});
    element.dispatchEvent(new Event('input', { bubbles: true }));
    element.dispatchEvent(new Event('change', { bubbles: true }));
    return true;
  })()`);
  assert(result, `Поле не найдено: ${selector}`);
}

async function navigate(cdp, url) {
  await cdp.command('Page.navigate', { url });
  await waitForExpression(cdp, 'document.readyState === "complete"', `page load ${url}`, 15000);
}

async function screenshot(cdp, name) {
  const result = await cdp.command('Page.captureScreenshot', {
    format: 'png',
    captureBeyondViewport: true,
    fromSurface: true,
  });
  const file = path.join(outputDir, `${name}.png`);
  fs.writeFileSync(file, Buffer.from(result.data, 'base64'));
  return file;
}

async function openSystemPicker(cdp) {
  await cdp.evaluate(`(() => {
    const button = document.querySelector('aside .flex.items-center.justify-between button');
    button?.click();
    return Boolean(button);
  })()`);
  await waitForExpression(cdp, 'document.body.innerText.includes("СЛАЙД")', 'system picker');
}

async function iframeText(cdp, title) {
  return cdp.evaluate(`(() => {
    const frame = document.querySelector(${JSON.stringify(`iframe[title="${title}"]`)});
    const doc = frame?.contentDocument;
    return doc?.body?.innerText ?? '';
  })()`);
}

async function closeTopModal(cdp) {
  const point = await cdp.evaluate(`(() => {
    window.confirm = () => true;
    const closeButton = [...document.querySelectorAll('.fixed button')]
      .find(button => button.querySelector('svg.lucide-x'));
    const target = closeButton || document.querySelector('.fixed .absolute.inset-0');
    if (!target) return null;
    const rect = target.getBoundingClientRect();
    return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
  })()`);
  assert(point, 'Не найдена кнопка/область закрытия модалки.');
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', x: point.x, y: point.y });
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', x: point.x, y: point.y, button: 'left', clickCount: 1 });
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', x: point.x, y: point.y, button: 'left', clickCount: 1 });
}

async function runScenario(cdp) {
  fs.mkdirSync(outputDir, { recursive: true });
  const seed = Date.now().toString().slice(-6);
  const projectNumber = `QA2-${seed}`;
  const checks = [];
  const shot = {};

  const check = async (name, expression, statusText) => {
    let ok = false;
    const started = Date.now();
    while (Date.now() - started < 3000) {
      ok = await cdp.evaluate(`Boolean(${expression})`);
      if (ok) break;
      await sleep(100);
    }
    checks.push({ name, ok, statusText });
    if (!ok) {
      const body = await cdp.evaluate('document.body?.innerText?.slice(0, 2000) ?? ""');
      throw new Error(`QA check failed: ${name}\n${body}`);
    }
  };

  await cdp.command('Page.enable');
  await cdp.command('Runtime.enable');
  await cdp.command('Emulation.setDeviceMetricsOverride', {
    width: 1440,
    height: 1000,
    deviceScaleFactor: 1,
    mobile: false,
  });

  await navigate(cdp, appUrl);
  await cdp.evaluate('try { window.localStorage?.clear(); } catch {} location.href = new URL("/", location.href).href');
  await waitForExpression(cdp, 'location.pathname === "/" && document.body.innerText.includes("Новый проект")', 'guest projects page');
  await check('guest_mode_visible', 'document.body.innerText.includes("Гостевой режим") && document.body.innerText.includes("Войти")', 'гостевой режим и вход видны');
  shot.projects = await screenshot(cdp, '01-projects-guest');

  await clickText(cdp, 'Новый проект');
  await fillBySelector(cdp, 'input[placeholder="Х00-0-0000"]', projectNumber);
  await fillBySelector(cdp, 'input[placeholder="Введите или выберите заказчика"]', 'QA Client');
  await clickText(cdp, 'Создать');
  await waitForExpression(cdp, 'location.pathname.startsWith("/projects/")', 'guest project editor');
  await check('project_level_docs_initial', '(() => { const labels = [...document.querySelectorAll("button")].map(button => button.textContent || ""); return labels.some(text => text.includes("Коммерческое")) && labels.some(text => text.includes("Заказ стекла")) && labels.some(text => text.includes("Заявка покр")); })()', 'project docs visible on empty project view');
  await check('project_level_no_old_buttons_initial', '!document.body.innerText.includes("Схема") && !document.body.innerText.includes("Производственный лист")', 'old project-level section docs absent before active section');
  shot.emptyProject = await screenshot(cdp, '02-empty-project-docs');

  await openSystemPicker(cdp);
  await clickText(cdp, 'СЛАЙД');
  await waitForExpression(cdp, 'document.body.innerText.includes("Стандарт 1 ряд")', 'slide subtype picker');
  await clickText(cdp, 'Стандарт 1 ряд');
  await waitForExpression(cdp, 'document.body.innerText.includes("СЛАЙД стандарт 1 ряд") && document.body.innerText.toLowerCase().includes("1-я панель внутри помещения")', 'one row form');
  await check('one_row_no_row_switch', `(() => {
    return ![...document.querySelectorAll('label')].some(label => {
      const text = (label.textContent || '').replace(/\\s+/g, ' ').trim();
      const block = label.parentElement?.innerText || '';
      return text === 'Система' && block.includes('1 ряд') && block.includes('2 ряда');
    });
  })()`, 'row switch hidden in 1-row edit form');
  shot.oneRowForm = await screenshot(cdp, '03-one-row-form');
  await clickText(cdp, 'Производственный лист');
  await waitForExpression(cdp, 'document.querySelector("iframe[title=\\"Производственный лист\\"]")', 'one row production modal');
  await waitForExpression(cdp, `(async () => {
    const text = await new Promise(resolve => setTimeout(() => resolve(document.querySelector('iframe[title="Производственный лист"]')?.contentDocument?.body?.innerText ?? ''), 300));
    return text.includes('SLIDE-стандарт 1 ряд') && text.includes('Крайние');
  })()`, 'one row production sheet', 15000);
  shot.oneRowSheet = await screenshot(cdp, '04-one-row-production-sheet');
  await closeTopModal(cdp);
  await waitForExpression(cdp, '!document.querySelector("iframe[title=\\"Производственный лист\\"]")', 'close one row modal');

  await clickText(cdp, 'К проекту');
  await waitForExpression(cdp, 'document.body.innerText.includes("Коммерческое предложение") && document.body.innerText.includes("Заказ стекла") && document.body.innerText.includes("СТАТУС") && !document.body.innerText.includes("СЛАЙД стандарт 1 ряд")', 'project docs after back');
  await check('project_level_no_old_buttons_after_section', '!document.body.innerText.includes("Схема") && !document.body.innerText.includes("Производственный лист")', 'old project-level docs absent after returning from section');

  await openSystemPicker(cdp);
  await clickText(cdp, 'СЛАЙД');
  await clickText(cdp, '2 ряда от центра');
  await waitForExpression(cdp, 'document.body.innerText.includes("СЛАЙД стандарт 2 ряда")', 'two row form title');
  await check('two_row_no_row_switch', `(() => {
    return ![...document.querySelectorAll('label')].some(label => {
      const text = (label.textContent || '').replace(/\\s+/g, ' ').trim();
      const block = label.parentElement?.innerText || '';
      return text === 'Система' && block.includes('1 ряд') && block.includes('2 ряда');
    });
  })()`, 'row switch hidden in 2-row edit form');
  await check('two_row_default', '(() => { const text = document.body.innerText.toLowerCase(); return text.includes("3х рельсовая") && text.includes("4") && text.includes("первые панели"); })()', '2 row default 3 rails, 4 panels, first panels control');
  await check('two_row_sidebar_label', 'document.body.innerText.includes("2 ряда · 4 пан.")', 'sidebar card labels 2-row sections correctly');
  await check('two_row_no_first_panel_control', '!document.body.innerText.toLowerCase().includes("1-я панель внутри помещения")', 'old first panel control hidden for 2 rows');
  shot.twoRowForm = await screenshot(cdp, '05-two-row-form-default');

  await clickText(cdp, 'Ручки-профиль RS112');
  await clickText(cdp, 'Накидная защёлка RS206');
  await waitForExpression(cdp, 'document.body.innerText.includes("Ручки-профиль RS112") && document.body.innerText.includes("Накидная защёлка RS206")', 'center rs112 selected');
  shot.twoRowCenter = await screenshot(cdp, '06-two-row-center-rs112');
  await clickText(cdp, 'Сохранить изменения');
  await waitForExpression(cdp, '!document.body.innerText.includes("Сохранение")', 'save two row section');

  await clickText(cdp, 'Производственный лист');
  await waitForExpression(cdp, 'document.querySelector("iframe[title=\\"Производственный лист\\"]")', 'two row production modal');
  await waitForExpression(cdp, `(async () => {
    const text = await new Promise(resolve => setTimeout(() => resolve(document.querySelector('iframe[title="Производственный лист"]')?.contentDocument?.body?.innerText ?? ''), 500));
    return text.includes('SLIDE-стандарт 2 ряда') && text.includes('Центральные') && text.includes('RS112') && text.includes('RS1083') && text.includes('RU010') && text.includes('RS206');
  })()`, 'two row production sheet contains center hardware', 15000);
  const twoRowSheetText = await iframeText(cdp, 'Производственный лист');
  shot.twoRowSheet = await screenshot(cdp, '07-two-row-production-sheet');
  await closeTopModal(cdp);

  await clickText(cdp, 'К проекту');
  await waitForExpression(cdp, 'document.body.innerText.includes("Коммерческое предложение") && document.body.innerText.includes("СТАТУС") && !document.body.innerText.includes("СЛАЙД стандарт 2 ряда")', 'project docs visible before opening project docs');
  await sleep(300);
  shot.projectDocs = await screenshot(cdp, '08-project-doc-buttons');

  await clickText(cdp, 'Заказ стекла');
  await waitForExpression(cdp, 'document.querySelector("iframe")', 'project glass document modal');
  await waitForExpression(cdp, `(async () => {
    const text = await new Promise(resolve => setTimeout(() => resolve(document.querySelector('iframe')?.contentDocument?.body?.innerText ?? ''), 500));
    return text.includes('ЗАКАЗ СТЕКЛА') || text.includes('Заказ стекла');
  })()`, 'glass document iframe', 15000);
  const glassDocText = await cdp.evaluate(`document.querySelector('iframe')?.contentDocument?.body?.innerText ?? ''`);
  shot.glassDoc = await screenshot(cdp, '09-glass-document');
  await closeTopModal(cdp);

  await cdp.evaluate('localStorage.clear()');

  return {
    projectNumber,
    outputDir,
    screenshots: shot,
    checks,
    twoRowSheetText: twoRowSheetText.slice(0, 1800),
    glassDocText: glassDocText.slice(0, 1800),
    runtimeErrors: cdp.runtimeErrors,
  };
}

async function main() {
  const browserPath = findBrowser();
  const port = 9700 + Math.floor(Math.random() * 300);
  const profileDir = fs.mkdtempSync(path.join(os.tmpdir(), 'raluma-qa-'));
  const browser = spawn(browserPath, [
    '--headless=new',
    '--disable-gpu',
    '--disable-extensions',
    '--no-first-run',
    '--no-default-browser-check',
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${profileDir}`,
    'about:blank',
  ], { stdio: ['ignore', 'ignore', 'pipe'] });

  let stderr = '';
  browser.stderr.on('data', chunk => {
    stderr += chunk.toString();
    stderr = stderr.slice(-4000);
  });

  let cdp;
  try {
    const wsUrl = await waitForPageTarget(port);
    cdp = await connectCdp(wsUrl);
    const result = await runScenario(cdp);
    assert(result.runtimeErrors.length === 0, `Runtime errors:\n${result.runtimeErrors.join('\n')}`);
    console.log(JSON.stringify({ ok: true, ...result }, null, 2));
  } catch (error) {
    console.error(error);
    if (stderr) console.error(stderr);
    process.exitCode = 1;
  } finally {
    cdp?.close();
    const exited = new Promise(resolve => {
      if (browser.exitCode !== null) resolve();
      else browser.once('exit', resolve);
    });
    if (browser.exitCode === null) {
      if (process.platform === 'win32' && browser.pid) {
        try {
          execFileSync('taskkill', ['/PID', String(browser.pid), '/T', '/F'], { stdio: 'ignore' });
        } catch {
          browser.kill();
        }
      } else {
        browser.kill('SIGKILL');
      }
    }
    await Promise.race([exited, sleep(1500)]);
    try {
      fs.rmSync(profileDir, { recursive: true, force: true, maxRetries: 8, retryDelay: 250 });
    } catch (error) {
      console.warn(`Warning: не удалось удалить временный профиль ${profileDir}: ${error.message}`);
    }
  }
}

main();
