// Runs a real MV3 extension against an isolated workshop and synthetic wiki page.
// The temporary test copy grants the fixture host so automated popup navigation
// doesn't need a physical toolbar gesture. Shipped manifest uses activeTab only.
import { chromium } from "@playwright/test";
import assert from "node:assert/strict";
import {
  mkdtempSync,
  cpSync,
  readFileSync,
  writeFileSync,
  rmSync,
  mkdirSync,
} from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { spawn } from "node:child_process";
const dir = mkdtempSync(path.join(tmpdir(), "borderlens-extension-")),
  extension = path.join(dir, "extension");
cpSync("chrome-extension", extension, { recursive: true });
const manifest = JSON.parse(
  readFileSync(path.join(extension, "manifest.json"), "utf8"),
);
manifest.host_permissions.push("https://borderlands.fandom.com/*");
writeFileSync(path.join(extension, "manifest.json"), JSON.stringify(manifest));
const server = spawn(
  process.execPath,
  ["--import", "tsx", "tests/browser-server.ts"],
  {
    env: { ...process.env, BORDERLENS_DATA_DIR: path.join(dir, "project") },
    stdio: ["ignore", "pipe", "inherit"],
  },
);
await new Promise<void>((resolve, reject) => {
  const timer = setTimeout(
    () => reject(new Error("Test server startup timed out")),
    15000,
  );
  server.stdout.on("data", (chunk) => {
    if (chunk.toString().includes("READY")) {
      clearTimeout(timer);
      resolve();
    }
  });
  server.once("error", reject);
});
const context = await chromium.launchPersistentContext(
  path.join(dir, "profile"),
  {
    channel: "chromium",
    headless: true,
    args: [
      `--disable-extensions-except=${extension}`,
      `--load-extension=${extension}`,
    ],
    viewport: { width: 1440, height: 1000 },
  },
);
try {
  const worker =
    context.serviceWorkers()[0] ||
    (await context.waitForEvent("serviceworker"));
  const id = new URL(worker.url()).hostname;
  await context.route("https://borderlands.fandom.com/wiki/**", (route) =>
    route.fulfill({
      contentType: "text/html",
      body: '<!doctype html><html><head><title>Hellfire – fixture only</title></head><body><h1 id="firstHeading">Hellfire</h1><div class="mw-parser-output"><h2>Unique ability</h2><p>This synthetic wiki article exists only to verify browser capture. It is not real game evidence.</p><table><tr><td>Fixture field</td><td>Fixture value</td></tr></table><form><input value="private-test-secret"></form><script>globalThis.fixtureScript=true</script></div></body></html>',
    }),
  );
  const app = await context.newPage();
  app.setDefaultTimeout(20000);
  const errors: string[] = [];
  app.on("pageerror", (e) => errors.push(e.message));
  await app.goto("http://127.0.0.1:4321");
  await app.getByTitle("Chrome helper connected", { exact: true }).waitFor();
  await app
    .locator("input[type=file]")
    .setInputFiles(
      path.resolve("../temp/imports/borderlens-20261023-153827-931444.zip"),
    );
  await app
    .getByRole("heading", { name: /Hellfire/i })
    .waitFor({ timeout: 60000 });
  const state = await app.request
      .get("http://127.0.0.1:4321/api/state")
      .then((r) => r.json()),
    family = state.families.find((f: any) => /hellfire/i.test(f.name));
  const url = "https://borderlands.fandom.com/wiki/Hellfire_(Borderlands)";
  await app.request.post(
    "http://127.0.0.1:4321/api/items/" + family.id + "/action",
    { data: { action: "resolve", url, gameOnly: true } },
  );
  await app.getByRole("button", { name: "Sources & evidence" }).click();
  const articlePromise = context.waitForEvent("page");
  await app
    .getByRole("button", { name: "Open wiki in Chrome", exact: true })
    .click();
  const article = await articlePromise;
  // Chrome-created tabs can issue their first navigation before Playwright attaches.
  // Repeat navigation under the installed route to serve the local article fixture.
  await article.goto(url);
  await article.locator(".mw-parser-output").waitFor();
  const popup = await context.newPage();
  await popup.goto(`chrome-extension://${id}/popup.html`);
  await popup
    .getByRole("button", { name: "Send page to Borderlens", exact: true })
    .click();
  await popup
    .getByRole("heading", { name: "Article saved", exact: true })
    .waitFor();
  await app.getByText("Wiki · 1 saved", { exact: true }).waitFor();
  const detail = await app.request
    .get("http://127.0.0.1:4321/api/items/" + family.id)
    .then((r) => r.json());
  assert.equal(detail.sources[0].captureMethod, "chrome");
  assert.match(detail.sources[0].text, /synthetic wiki article/);
  assert.ok(detail.sources[0].tables.length);
  assert.ok(!detail.sources[0].text.includes("private-test-secret"));
  assert.ok(!detail.sources[0].text.includes("fixtureScript"));
  assert.deepEqual(errors, []);
  await app.getByTitle("Chrome helper connected", { exact: true }).click();
  await app.getByRole("dialog", { name: "Chrome helper setup" }).waitFor();
  mkdirSync(".test-data/screenshots", { recursive: true });
  await app.screenshot({
    path: ".test-data/screenshots/chrome-helper-setup.png",
  });
  await app.getByRole("button", { name: "Close Chrome helper setup" }).click();
  await app.screenshot({
    path: ".test-data/screenshots/chrome-source-saved.png",
  });
  console.log(
    "MV3 Chrome fixture: automatic connection, open article, popup capture, local relay, cached HTML/tables and live saved status passed.",
  );
} finally {
  await context.close();
  server.kill("SIGTERM");
  await new Promise((r) => server.once("exit", r));
  rmSync(dir, { recursive: true, force: true });
}
