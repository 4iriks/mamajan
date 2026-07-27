import { execFileSync, spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const host = '127.0.0.1';
const vitePort = 4187;
const cdpPort = 9387;
const fixtureUrl = `http://${host}:${vitePort}/scripts/browser-fixtures/lift-remote-input.html`;
const browserCandidates = [
  process.env.SMOKE_BROWSER_PATH,
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
  '/usr/bin/google-chrome',
  '/usr/bin/google-chrome-stable',
  '/usr/bin/chromium',
].filter(Boolean);

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const assert = (value, message) => {
  if (!value) throw new Error(message);
};

async function waitForHttp(url) {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {
      // Vite is still starting.
    }
    await sleep(100);
  }
  throw new Error(`Vite did not start: ${url}`);
}

async function waitForPageTarget() {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    try {
      const response = await fetch(`http://${host}:${cdpPort}/json/list`);
      const targets = await response.json();
      const page = targets.find(target => target.type === 'page' && target.webSocketDebuggerUrl);
      if (page) return page.webSocketDebuggerUrl;
    } catch {
      // Browser is still starting.
    }
    await sleep(100);
  }
  throw new Error('Could not connect to the browser through CDP');
}

async function connectCdp(wsUrl) {
  const ws = new WebSocket(wsUrl);
  const pending = new Map();
  let nextId = 1;

  ws.addEventListener('message', event => {
    const message = JSON.parse(event.data);
    if (!message.id || !pending.has(message.id)) return;
    const { resolve, reject } = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) reject(new Error(message.error.message));
    else resolve(message.result);
  });

  await new Promise((resolve, reject) => {
    ws.addEventListener('open', resolve, { once: true });
    ws.addEventListener('error', reject, { once: true });
  });

  const command = (method, params = {}) => new Promise((resolve, reject) => {
    const id = nextId++;
    pending.set(id, { resolve, reject });
    ws.send(JSON.stringify({ id, method, params }));
  });

  return {
    command,
    async evaluate(expression) {
      const response = await command('Runtime.evaluate', {
        expression,
        awaitPromise: true,
        returnByValue: true,
      });
      if (response.exceptionDetails) {
        throw new Error(response.exceptionDetails.exception?.description ?? response.exceptionDetails.text);
      }
      return response.result?.value;
    },
    close() {
      ws.close();
    },
  };
}

async function waitFor(cdp, expression, label) {
  for (let attempt = 0; attempt < 80; attempt += 1) {
    if (await cdp.evaluate(`Boolean(${expression})`)) return;
    await sleep(100);
  }
  throw new Error(`Timeout: ${label}`);
}

function stopProcess(child) {
  if (!child?.pid) return;
  if (process.platform === 'win32') {
    try {
      execFileSync('taskkill', ['/pid', String(child.pid), '/t', '/f'], { stdio: 'ignore' });
    } catch {
      // Process already stopped.
    }
  } else {
    try {
      process.kill(-child.pid, 'SIGTERM');
    } catch {
      // Process already stopped.
    }
  }
}

const browserPath = browserCandidates.find(candidate => fs.existsSync(candidate));
assert(browserPath, 'Chrome or Edge was not found');
const profileDir = fs.mkdtempSync(path.join(os.tmpdir(), 'raluma-lift-input-'));
const vite = spawn(process.execPath, [
  path.resolve('node_modules/vite/bin/vite.js'),
  '--host',
  host,
  '--port',
  String(vitePort),
], {
  cwd: process.cwd(),
  detached: process.platform !== 'win32',
  stdio: 'ignore',
});
let browser;
let cdp;

try {
  await waitForHttp(fixtureUrl);
  browser = spawn(browserPath, [
    '--headless=new',
    '--disable-gpu',
    '--no-first-run',
    '--no-default-browser-check',
    `--remote-debugging-port=${cdpPort}`,
    `--user-data-dir=${profileDir}`,
    fixtureUrl,
  ], {
    detached: process.platform !== 'win32',
    stdio: 'ignore',
  });

  cdp = await connectCdp(await waitForPageTarget());
  await cdp.command('Runtime.enable');
  await waitFor(
    cdp,
    'document.querySelectorAll("[data-lift-remote-count]").length === 2',
    'remote inputs',
  );

  const setInput = async value => cdp.evaluate(`(() => {
    const input = document.querySelector('[data-lift-remote-count="1"]');
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    setter.call(input, ${JSON.stringify(value)});
    input.dispatchEvent(new Event('input', { bubbles: true }));
  })()`);

  await setInput('');
  await waitFor(cdp, 'document.querySelector(\'[data-lift-remote-count="1"]\').value === ""', 'empty draft');
  assert(
    await cdp.evaluate('document.querySelector("[data-shared-count]").textContent === "3"'),
    'empty draft must not immediately overwrite the shared value',
  );

  await setInput('5');
  await waitFor(
    cdp,
    '[...document.querySelectorAll("[data-lift-remote-count]")].every(input => input.value === "5")',
    'shared value 5',
  );
  assert(
    await cdp.evaluate('document.querySelector("[data-button-section-count]").textContent === "9"'),
    'a button-controlled section must remain unchanged',
  );

  await setInput('');
  await cdp.evaluate(`(() => {
    const input = document.querySelector('[data-lift-remote-count="1"]');
    input.focus();
    input.blur();
  })()`);
  await waitFor(
    cdp,
    '[...document.querySelectorAll("[data-lift-remote-count]")].every(input => input.value === "0")',
    'blank blur normalization',
  );

  await cdp.evaluate('document.querySelector("[data-external-update]").click()');
  await waitFor(
    cdp,
    '[...document.querySelectorAll("[data-lift-remote-count]")].every(input => input.value === "7")',
    'external synchronized update',
  );

  await setInput('-1');
  assert(
    await cdp.evaluate('document.querySelector("[data-shared-count]").textContent === "7"'),
    'negative input must be rejected',
  );
  assert(
    await cdp.evaluate('document.querySelector(\'[data-lift-remote-count="1"]\').value === "7"'),
    'negative input must not remain visible',
  );
  await setInput('1.5');
  assert(
    await cdp.evaluate('document.querySelector("[data-shared-count]").textContent === "7"'),
    'fractional input must be rejected',
  );
  assert(
    await cdp.evaluate('document.querySelector(\'[data-lift-remote-count="1"]\').value === "7"'),
    'fractional input must not remain visible',
  );

  await cdp.command('Emulation.setDeviceMetricsOverride', {
    width: 1400,
    height: 1000,
    deviceScaleFactor: 1,
    mobile: false,
  });
  await cdp.evaluate('document.documentElement.classList.remove("light")');
  await sleep(100);
  const darkScreenshot = await cdp.command('Page.captureScreenshot', {
    format: 'png',
    captureBeyondViewport: true,
  });
  fs.writeFileSync(
    'C:\\tmp\\raluma-slide-dark-theme.png',
    Buffer.from(darkScreenshot.data, 'base64'),
  );
  await cdp.evaluate('document.documentElement.classList.add("light")');
  await sleep(100);
  const lightScreenshot = await cdp.command('Page.captureScreenshot', {
    format: 'png',
    captureBeyondViewport: true,
  });
  fs.writeFileSync(
    'C:\\tmp\\raluma-slide-light-theme.png',
    Buffer.from(lightScreenshot.data, 'base64'),
  );

  console.log('LIFT remote input browser smoke passed');
} finally {
  if (cdp) {
    try {
      await cdp.command('Browser.close');
    } catch {
      // Browser may already be closed.
    }
    cdp.close();
  }
  await sleep(500);
  stopProcess(browser);
  stopProcess(vite);
  await sleep(500);
  try {
    fs.rmSync(profileDir, {
      recursive: true,
      force: true,
      maxRetries: 10,
      retryDelay: 100,
    });
  } catch {
    console.warn(`Browser profile cleanup deferred: ${profileDir}`);
  }
}
