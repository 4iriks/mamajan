import { execFileSync, spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const appUrl = process.env.SMOKE_APP_URL ?? 'http://localhost:3000';
const apiUrl = process.env.SMOKE_API_URL ?? 'http://localhost:8000';
const keepData = process.env.SMOKE_KEEP_DATA === '1';

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
  if (!response.ok) {
    throw new Error(`CDP request failed ${response.status}: ${url}`);
  }
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
    async command(method, params) {
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
    async close() {
      ws.close();
    },
    runtimeErrors,
  };
}

async function waitForExpression(cdp, expression, label, timeoutMs = 10000) {
  const started = Date.now();
  let lastValue;
  while (Date.now() - started < timeoutMs) {
    lastValue = await cdp.evaluate(`Boolean(${expression})`);
    if (lastValue) return;
    await sleep(150);
  }
  const bodyText = await cdp.evaluate('document.body?.innerText?.slice(0, 1200) ?? ""');
  const iframeDebug = await cdp.evaluate(`(() => JSON.stringify([...document.querySelectorAll('iframe')].map(frame => {
    try {
      return {
        titleAttr: frame.getAttribute('title'),
        src: frame.getAttribute('src'),
        srcDocLength: frame.getAttribute('srcdoc')?.length ?? 0,
        docTitle: frame.contentDocument?.title ?? '',
        bodyText: frame.contentDocument?.body?.innerText?.slice(0, 500) ?? '',
      };
    } catch (error) {
      return { titleAttr: frame.getAttribute('title'), error: String(error) };
    }
  })))()`);
  throw new Error(`Timeout waiting for ${label}. Last body text:\n${bodyText}\nIframes:\n${iframeDebug}`);
}

async function clickText(cdp, text) {
  const result = await cdp.evaluate(`(() => {
    const normalize = value => (value || '').replace(/\\s+/g, ' ').trim();
    const candidates = [...document.querySelectorAll('button, a, [role="button"]')];
    const element = candidates.find(item => normalize(item.textContent).includes(${JSON.stringify(text)}));
    if (!element) return { ok: false, body: document.body.innerText.slice(0, 1000) };
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
  const origin = new URL(url).origin;
  await cdp.command('Page.navigate', { url });
  await waitForExpression(
    cdp,
    `location.href.startsWith(${JSON.stringify(origin)}) && document.readyState === "complete"`,
    `page load ${url}`,
    15000,
  );
}

async function cleanupProject(cdp, projectNumber) {
  if (keepData) return { deletedProjects: 0, kept: true };
  return cdp.evaluate(`(async () => {
    const token = localStorage.getItem('access_token');
    if (!token) return { deletedProjects: 0, skipped: 'no token' };
    const headers = { Authorization: 'Bearer ' + token };
    const response = await fetch(${JSON.stringify(`${apiUrl}/api/projects`)}, { headers });
    if (!response.ok) return { deletedProjects: 0, skipped: 'projects list ' + response.status };
    const projects = await response.json();
    const matches = projects.filter(project => project.number === ${JSON.stringify(projectNumber)});
    for (const project of matches) {
      await fetch(${JSON.stringify(`${apiUrl}/api/projects`) } + '/' + project.id, { method: 'DELETE', headers });
    }
    localStorage.clear();
    return { deletedProjects: matches.length };
  })()`);
}

async function runScenario(cdp) {
  const seed = Date.now().toString().slice(-6);
  const rawProjectNumber = `SMK${seed.slice(-5)}`;
  const username = `smoke_${seed}_${Math.random().toString(36).slice(2, 7)}`;
  const password = 'SmokePass123!';

  await cdp.command('Page.enable');
  await cdp.command('Runtime.enable');

  await navigate(cdp, appUrl);
  await cdp.evaluate('localStorage.clear(); location.href = "/"');
  await waitForExpression(cdp, 'location.pathname === "/" && document.body.innerText.includes("Новый проект")', 'guest projects page');
  await waitForExpression(cdp, 'document.body.innerText.includes("Гостевой режим") && document.body.innerText.includes("Войти")', 'guest header');

  await clickText(cdp, 'Новый проект');
  await waitForExpression(cdp, 'document.body.innerText.toLowerCase().includes("номер проекта")', 'create project modal');
  await fillBySelector(cdp, 'input[placeholder="Х00-0-0000"]', rawProjectNumber);
  await fillBySelector(cdp, 'input[placeholder="Введите или выберите заказчика"]', 'Smoke Client');
  await clickText(cdp, 'Создать');
  await waitForExpression(cdp, 'location.pathname.startsWith("/projects/")', 'guest project editor');

  await waitForExpression(cdp, 'document.body.innerText.includes("Нажмите + чтобы добавить секцию")', 'empty sections hint');
  await cdp.evaluate(`(() => {
    const button = document.querySelector('aside .flex.items-center.justify-between button');
    button?.click();
    return Boolean(button);
  })()`);
  await waitForExpression(cdp, 'document.body.innerText.includes("СЛАЙД")', 'system picker');
  await clickText(cdp, 'СЛАЙД');
  await waitForExpression(cdp, 'document.body.innerText.includes("Стандарт 1 ряд")', 'slide subtype picker');
  await clickText(cdp, 'Стандарт 1 ряд');
  await waitForExpression(
    cdp,
    'document.body.innerText.includes("Секция 1") && [...document.querySelectorAll("button")].some(button => button.textContent.includes("Производственный лист"))',
    'created guest section',
  );

  await clickText(cdp, 'Производственный лист');
  await waitForExpression(cdp, 'document.querySelector(".fixed iframe[title=\\"Производственный лист\\"]")', 'production sheet modal');
  await waitForExpression(cdp, `(() => {
    const frame = document.querySelector('iframe[title="Производственный лист"]');
    const doc = frame?.contentDocument;
    const bodyText = doc?.body?.innerText ?? '';
    return doc?.title === 'Производственный лист' || bodyText.includes('ПРОЕКТ');
  })()`, 'guest production sheet iframe', 15000);
  await cdp.evaluate(`document.querySelector('.fixed .relative button')?.click()`);

  const projectNumber = await cdp.evaluate(`(() => {
    const raw = localStorage.getItem('raluma-local-projects-v1');
    const projects = raw ? JSON.parse(raw) : [];
    return projects[0]?.number ?? '';
  })()`);
  assert(projectNumber, 'Локальный проект не найден в localStorage после создания.');

  await navigate(cdp, `${appUrl}/login`);
  await waitForExpression(cdp, 'document.body.innerText.toLowerCase().includes("регистрация")', 'login/register page');
  await clickText(cdp, 'Регистрация');
  await fillBySelector(cdp, 'input[placeholder="Ваш логин"]', username);
  await fillBySelector(cdp, 'input[placeholder="Как вас показывать в системе"]', 'Smoke User');
  await fillBySelector(cdp, 'input[type="password"]', password);
  await clickText(cdp, 'Зарегистрироваться');

  await waitForExpression(cdp, 'location.pathname === "/" && document.body.innerText.includes("Перенести локальные проекты?")', 'local import modal', 15000);
  await clickText(cdp, 'Перенести');
  await waitForExpression(cdp, `!document.body.innerText.includes("Перенести локальные проекты?") && document.body.innerText.includes(${JSON.stringify(projectNumber)})`, 'imported server project', 20000);

  const localCleared = await cdp.evaluate(`(() => {
    const raw = localStorage.getItem('raluma-local-projects-v1');
    return !raw || JSON.parse(raw).length === 0;
  })()`);
  assert(localCleared, 'Локальные проекты не были очищены после переноса.');

  const cleanup = await cleanupProject(cdp, projectNumber);
  return { username, projectNumber, cleanup };
}

async function main() {
  const browserPath = findBrowser();
  const port = 9300 + Math.floor(Math.random() * 400);
  const profileDir = fs.mkdtempSync(path.join(os.tmpdir(), 'raluma-smoke-'));
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
    assert(cdp.runtimeErrors.length === 0, `Runtime errors:\n${cdp.runtimeErrors.join('\n')}`);
    console.log(JSON.stringify({ ok: true, ...result }, null, 2));
  } catch (error) {
    console.error(error);
    if (stderr) console.error(stderr);
    process.exitCode = 1;
  } finally {
    await cdp?.close();
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
