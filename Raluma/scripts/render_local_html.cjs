const { spawn } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function waitForPageTarget(port) {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/json/list`);
      const targets = await response.json();
      const page = targets.find(
        (target) => target.type === "page" && target.webSocketDebuggerUrl,
      );
      if (page) return page.webSocketDebuggerUrl;
    } catch {
      // Chrome is still starting.
    }
    await sleep(100);
  }
  throw new Error("Could not connect to Chrome through CDP");
}

async function connectCdp(wsUrl) {
  const ws = new WebSocket(wsUrl);
  const pending = new Map();
  let nextId = 1;

  ws.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (!message.id || !pending.has(message.id)) return;
    const { resolve, reject } = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) reject(new Error(message.error.message));
    else resolve(message.result);
  });
  ws.addEventListener("close", () => {
    for (const { reject } of pending.values()) {
      reject(new Error("Chrome closed the CDP connection"));
    }
    pending.clear();
  });
  await new Promise((resolve, reject) => {
    ws.addEventListener("open", resolve, { once: true });
    ws.addEventListener("error", reject, { once: true });
  });

  return {
    command(method, params = {}) {
      return new Promise((resolve, reject) => {
        const id = nextId++;
        pending.set(id, { resolve, reject });
        ws.send(JSON.stringify({ id, method, params }));
      });
    },
    close() {
      ws.close();
    },
  };
}

function stopProcess(child) {
  if (!child?.pid) return;
  try {
    child.kill();
  } catch {
    // Chrome already stopped.
  }
}

async function main() {
  const input = process.argv[2];
  const output = process.argv[3];
  if (!input || !output) {
    throw new Error("Usage: node render_local_html.cjs <input.html> <output.png>");
  }

  const browserPath =
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
  const profileDir = fs.mkdtempSync(path.join(os.tmpdir(), "raluma-render-"));
  const cdpPort = 9400 + Math.floor(Math.random() * 400);
  const browser = spawn(
    browserPath,
    [
      "--headless=new",
      "--disable-gpu",
      "--no-sandbox",
      "--hide-scrollbars",
      "--no-first-run",
      "--no-default-browser-check",
      `--remote-debugging-port=${cdpPort}`,
      `--user-data-dir=${profileDir}`,
      pathToFileURL(path.resolve(input)).href,
    ],
    { stdio: ["ignore", "pipe", "pipe"] },
  );
  let chromeLog = "";
  browser.stdout.on("data", (chunk) => {
    chromeLog += chunk.toString();
  });
  browser.stderr.on("data", (chunk) => {
    chromeLog += chunk.toString();
  });
  let cdp;
  try {
    cdp = await connectCdp(await waitForPageTarget(cdpPort));
    await cdp.command("Page.enable");
    await cdp.command("Runtime.enable");
    await sleep(500);
    const metrics = await cdp.command("Page.getLayoutMetrics");
    const width = Math.ceil(metrics.cssContentSize.width);
    const height = Math.ceil(metrics.cssContentSize.height);
    await cdp.command("Emulation.setDeviceMetricsOverride", {
      width: Math.max(1200, width),
      height: Math.max(900, height),
      deviceScaleFactor: 1,
      mobile: false,
    });
    const screenshot = await cdp.command("Page.captureScreenshot", {
      format: "png",
      captureBeyondViewport: true,
    });
    fs.writeFileSync(path.resolve(output), Buffer.from(screenshot.data, "base64"));
    const result = await cdp.command("Runtime.evaluate", {
      expression: `JSON.stringify([...document.querySelectorAll(".page")].map((element, index) => {
        const rect = element.getBoundingClientRect();
        return {
          index: index + 1,
          top: Math.round(rect.top),
          width: Math.round(rect.width),
          height: Math.round(rect.height),
          scrollHeight: element.scrollHeight,
        };
      }))`,
      returnByValue: true,
    });
    const pages = JSON.parse(result.result.value);
    process.stdout.write(`${JSON.stringify(pages)}\n`);
  } finally {
    if (chromeLog) fs.writeFileSync(`${output}.chrome.log`, chromeLog, "utf8");
    cdp?.close();
    stopProcess(browser);
    try {
      fs.rmSync(profileDir, { recursive: true, force: true });
    } catch {
      // Chrome can briefly retain profile files after the process exits.
    }
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
