import { spawn, execFile, execFileSync } from 'node:child_process';
import { promisify } from 'node:util';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const browser = [process.env.SMOKE_BROWSER_PATH, 'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', '/usr/bin/chromium', '/usr/bin/google-chrome'].find(value => value && fs.existsSync(value));
if (!browser) throw new Error('Headless Chrome/Edge is required for this regression test');
const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'raluma-cs-test-'));
const screenshot = path.resolve('tmp/cs-editor-regression.png');
fs.mkdirSync(path.dirname(screenshot), { recursive: true });
const vite = spawn(process.execPath, ['node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', '4191', '--strictPort'], { stdio: 'ignore' });
const url = 'http://127.0.0.1:4191/scripts/browser-fixtures/cs-editor.html';
try {
  let ready = false;
  for (let attempt = 0; attempt < 100; attempt++) {
    try { if ((await fetch(url)).ok) { ready = true; break; } } catch { /* starting */ }
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  if (!ready) throw new Error('Fixture server failed to start');
  const { stdout } = await promisify(execFile)(browser, ['--headless=new', '--disable-gpu', '--no-first-run',
    '--no-default-browser-check', `--user-data-dir=${profile}`, '--window-size=1400,1700',
    '--virtual-time-budget=15000', '--dump-dom', `--screenshot=${screenshot}`, url], { timeout: 60000, maxBuffer: 4 * 1024 * 1024 });
  if (!stdout.includes('data-smoke="passed"')) throw new Error(stdout.match(/<pre id="result">([\s\S]*?)<\/pre>/)?.[1] || 'Browser fixture did not finish');
  console.log('CS browser tests passed: empty drafts, coordinates, angles, sides, insertion/removal, light/dark price contrast.');
  console.log(`Screenshot: ${screenshot}`);
} finally {
  if (process.platform === 'win32') {
    try { execFileSync('taskkill', ['/pid', String(vite.pid), '/t', '/f'], { stdio: 'ignore' }); } catch { /* stopped */ }
  } else vite.kill();
  // Only remove this test's newly created, resolved temporary browser profile.
  if (path.dirname(path.resolve(profile)) !== path.resolve(os.tmpdir()) || !path.basename(profile).startsWith('raluma-cs-test-')) throw new Error('Unsafe profile cleanup path');
  fs.rmSync(profile, { recursive: true, force: true, maxRetries: 10, retryDelay: 100 });
}
