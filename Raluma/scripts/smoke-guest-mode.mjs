import { execFileSync, spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const appUrl = process.env.SMOKE_APP_URL ?? 'http://localhost:3000';
const apiUrl = process.env.SMOKE_API_URL ?? 'http://localhost:8000';

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

async function waitForExpression(cdp, expression, label, timeoutMs = 30000) {
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
  const navigation = await cdp.command('Page.navigate', { url });
  assert(!navigation.errorText, `Cannot navigate to ${url}: ${navigation.errorText}`);
  await waitForExpression(
    cdp,
    `location.href.startsWith(${JSON.stringify(origin)}) && document.readyState === "complete"`,
    `page load ${url}`,
    15000,
  );
}

// This smoke is read-only and can also verify the deployed site.
async function runScenario(cdp) {
  await cdp.command('Page.enable');
  await cdp.command('Runtime.enable');
  const routes = ['/', '/projects/-1', '/admin', '/admin/catalog/hardware', '/admin/pricing'];
  for (const route of routes) {
    await navigate(cdp, `${appUrl}${route}`);
    await waitForExpression(cdp, `location.pathname === "/login" && Boolean(document.querySelector('input[placeholder="Ваш логин"]'))`, `login required for ${route}`);
    assert(await cdp.evaluate('!document.body.innerText.includes("Продолжить без входа")'), 'Guest entry is still shown');
    assert(await cdp.evaluate('!document.body.innerText.includes("Новый проект")'), 'Projects visible without login');
  }

  const endpoints = [
    ['GET', '/api/projects'],
    ['GET', '/api/catalog/hardware/options'],
    ['GET', '/api/catalog/cs-systems'],
    ['POST', '/api/calculate/local/book'],
    ['POST', '/api/calculate/local/cs'],
    ...['calc', 'preview', 'pdf', 'docx', 'xlsx'].map(kind => ['POST', `/api/projects/local/sections/${kind}`]),
    ...['preview', 'pdf', 'docx', 'xlsx'].map(kind => ['POST', `/api/projects/local/documents/sketch/${kind}`]),
  ];
  for (const [method, route] of endpoints) {
    for (const invalidToken of [false, true]) {
      const response = await fetch(`${apiUrl}${route}`, {
        method,
        headers: { 'Content-Type': 'application/json', ...(invalidToken ? { Authorization: 'Bearer invalid.token' } : {}) },
        ...(method === 'POST' ? { body: '{}' } : {}),
      });
      const expected = invalidToken ? 401 : 403;
      assert(response.status === expected, `${method} ${route}: expected ${expected}, received ${response.status}`);
    }
  }

  // A stale or forged browser session must also return to login.
  await cdp.evaluate('localStorage.setItem("access_token", "invalid.token"); location.href = "/projects/-1"');
  await waitForExpression(cdp, `location.pathname === "/login" && !localStorage.getItem("access_token") && Boolean(document.querySelector('input[placeholder="Ваш логин"]'))`, 'invalid session rejected');

  let authenticatedChecked = false;
  if (process.env.SMOKE_USERNAME && process.env.SMOKE_PASSWORD) {
    await fillBySelector(cdp, 'input[placeholder="Ваш логин"]', process.env.SMOKE_USERNAME);
    await fillBySelector(cdp, 'input[type="password"]', process.env.SMOKE_PASSWORD);
    await clickText(cdp, 'Войти');
    await waitForExpression(cdp, 'location.pathname === "/" && document.body.innerText.includes("Новый проект")', 'authenticated projects');
    await clickText(cdp, 'Выйти');
    await waitForExpression(cdp, 'location.pathname === "/login" && !localStorage.getItem("access_token")', 'logout requires login');
    authenticatedChecked = true;
  }
  return { protectedRoutes: routes.length, protectedEndpoints: endpoints.length, authenticatedChecked };
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
