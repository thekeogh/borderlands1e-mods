import { chromium } from "@playwright/test";
import assert from "node:assert/strict";
import path from "node:path";
import { mkdirSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { spawn } from "node:child_process";
const dir = mkdtempSync(path.join(tmpdir(), "borderlens-browser-"));
const server = spawn(
  process.execPath,
  ["--import", "tsx", "tests/browser-server.ts"],
  {
    env: { ...process.env, BORDERLENS_DATA_DIR: dir },
    stdio: ["ignore", "pipe", "inherit"],
  },
);
await new Promise<void>((resolve, reject) => {
  const timeout = setTimeout(
    () => reject(new Error("Browser server startup timed out")),
    15000,
  );
  server.stdout.on("data", (b) => {
    if (b.toString().includes("READY")) {
      clearTimeout(timeout);
      resolve();
    }
  });
  server.once("error", reject);
});
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({
    baseURL: "http://127.0.0.1:4321",
    viewport: { width: 1440, height: 1000 },
  });
  page.setDefaultTimeout(15000);
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("http://127.0.0.1:4321");
  await page.getByRole("heading", { name: /Build a clearer/ }).waitFor();
  mkdirSync(".test-data/screenshots", { recursive: true });
  await page.screenshot({ path: ".test-data/screenshots/empty.png" });
  await page
    .locator("input[type=file]")
    .setInputFiles(
      path.resolve("../temp/imports/borderlens-20261023-153827-931444.zip"),
    );
  await page
    .getByRole("heading", { name: /Hellfire/i })
    .waitFor({ timeout: 60000 });
  const before = await page.request.get("/api/state").then((r) => r.json());
  assert.equal(before.families.length, 255);
  await page.getByRole("button", { name: "Sources & evidence" }).click();
  await page.getByRole("heading", { name: "Help it move forward" }).waitFor();
  await page.getByRole("button", { name: "Final JSON" }).click();
  await page
    .getByRole("textbox", { name: "Edit final item JSON" })
    .fill('{"unfinished":"keep this edit"}');
  await page.request.post("/api/items/" + before.families[0].id + "/action", {
    data: { action: "exclude", notes: "Browser checkpoint test" },
  });
  await page.waitForTimeout(500);
  assert.equal(
    await page
      .getByRole("textbox", { name: "Edit final item JSON" })
      .inputValue(),
    '{"unfinished":"keep this edit"}',
  );
  await page.getByRole("button", { name: "Rebuild this item" }).click();
  await page.getByRole("button", { name: "Pause", exact: true }).waitFor();
  await page.getByRole("textbox", { name: "Find an item" }).fill("Thunder");
  await page
    .locator(".item-row")
    .filter({ hasText: "Thunder" })
    .first()
    .click();
  await page.getByRole("heading", { name: /Thunder/ }).waitFor();
  assert.match(
    (await page.request.get("/api/state").then((r) => r.json())).run.currentId,
    /hellfire/,
  );
  await page.getByRole("button", { name: "Pause", exact: true }).click();
  await page.getByRole("button", { name: "Resume", exact: true }).waitFor();
  await page.getByRole("button", { name: "Resume", exact: true }).click();
  await page.getByText("This run is complete", { exact: true }).waitFor();
  await page.getByRole("textbox", { name: "Find an item" }).fill("Hellfire");
  await page.locator(".item-row").first().click();
  await page.getByRole("heading", { name: /Hellfire/i }).waitFor();
  await page.getByRole("button", { name: "Final JSON" }).click();
  await page.waitForTimeout(250);
  assert.match(
    await page
      .getByRole("textbox", { name: "Edit final item JSON" })
      .inputValue(),
    /browser test description/,
  );
  await page.getByRole("button", { name: "Preview", exact: true }).click();
  await page.screenshot({ path: ".test-data/screenshots/catalogue.png" });
  const top = await page.locator(".runbar").boundingBox();
  await page.locator("main").evaluate((el) => {
    el.scrollTop = 5000;
  });
  const after = await page.locator(".runbar").boundingBox();
  assert.equal(top?.y, after?.y);
  await page.getByRole("button", { name: /Coverage/ }).click();
  await page.getByRole("heading", { name: "Catalogue coverage" }).waitFor();
  await page.screenshot({ path: ".test-data/screenshots/coverage.png" });
  await page.getByTitle("Settings", { exact: true }).first().click();
  await page.getByRole("dialog").waitFor();
  await page
    .getByRole("dialog")
    .screenshot({ path: ".test-data/screenshots/settings.png" });
  await page.locator(".close-modal").click();
  const ajax = before.families.find((f: any) => f.name === "Ajax's Spear");
  await page
    .getByRole("textbox", { name: "Find an item" })
    .fill("Ajax's Spear");
  await page.locator(".item-row").first().click();
  await page.getByRole("heading", { name: /Ajax's Spear/ }).waitFor();
  await page.getByRole("button", { name: "Sources & evidence" }).click();
  await page.request.post("/api/items/" + ajax.id + "/action", {
    data: {
      action: "resolve",
      url: "https://www.lootlemon.com/weapon/browser-test-fixture-bl1",
      html: "<main><h1>Test fixture only</h1><p>Ajax's Spear is a combat rifle in Borderlands. This is synthetic browser-test evidence only.</p><table><caption>Saved fixture table</caption><tr><td>Fixture key</td><td>Fixture value</td></tr></table><script>globalThis.__sourceViewerExecuted=true</script></main>",
      gameOnly: true,
    },
  });
  await page.getByRole("button", { name: "Rebuild this item" }).click();
  await page
    .locator(".group-toggle")
    .filter({ hasText: "Combat rifles" })
    .waitFor();
  assert.equal(
    await page.locator(".item-row.selected").textContent(),
    "Ajax's Spear",
  );
  await page.getByText("This run is complete", { exact: true }).waitFor();
  const detail = await page.request
    .get("/api/items/" + ajax.id)
    .then((r) => r.json());
  assert.equal(detail.output.weaponType, "Combat rifles");
  await page
    .getByRole("combobox", { name: "Weapon classification" })
    .selectOption("Shotguns");
  await page.locator(".group-toggle").filter({ hasText: "Shotguns" }).waitFor();
  await page
    .getByRole("combobox", { name: "Weapon classification" })
    .selectOption("");
  await page
    .locator(".group-toggle")
    .filter({ hasText: "Combat rifles" })
    .waitFor();
  await page.reload();
  await page
    .locator(".group-toggle")
    .filter({ hasText: "Combat rifles" })
    .waitFor();
  assert.equal(
    await page.locator(".item-row.selected").textContent(),
    "Ajax's Spear",
  );
  await page.getByRole("button", { name: "Sources & evidence" }).click();
  const sourceDetail = await page.request
    .get("/api/items/" + ajax.id)
    .then((r) => r.json());
  const savedSource = sourceDetail.sources[0];
  await page
    .getByRole("button", { name: "Show more: " + savedSource.title })
    .click();
  const viewer = page.getByRole("dialog", { name: savedSource.title });
  await viewer.waitFor();
  assert.equal(
    await viewer.locator(".stored-source-text").textContent(),
    savedSource.text,
  );
  await viewer.getByRole("tab", { name: "Source record", exact: true }).click();
  assert.deepEqual(
    JSON.parse(
      (await viewer.locator(".stored-source-record").textContent()) || "",
    ),
    savedSource,
  );
  await viewer
    .getByRole("tab", { name: "Sections & tables", exact: true })
    .click();
  await viewer.getByRole("heading", { name: "Saved fixture table" }).waitFor();
  await viewer.getByRole("tab", { name: "Stored HTML", exact: true }).click();
  await viewer.locator(".stored-source-html").waitFor();
  const cached = await page.request
    .get("/api/sources/" + encodeURIComponent(savedSource.id) + "/html")
    .then((r) => r.text());
  assert.equal(
    await viewer.locator(".stored-source-html").textContent(),
    cached,
  );
  assert.equal(
    await page.evaluate(() => "__sourceViewerExecuted" in globalThis),
    false,
  );
  await page.screenshot({ path: ".test-data/screenshots/source-viewer.png" });
  await page.keyboard.press("Escape");
  await viewer.waitFor({ state: "hidden" });
  assert.equal(
    await page.evaluate(() =>
      document.activeElement?.getAttribute("aria-label"),
    ),
    "Show more: " + savedSource.title,
  );
  assert.deepEqual(errors, []);
  console.log(
    "Browser: import, background selection, pause/resume, editor persistence, coverage, settings and fixed progress passed. 255 real capture candidates.",
  );
} finally {
  await browser.close();
  server.kill("SIGTERM");
  await new Promise((r) => server.once("exit", r));
  rmSync(dir, { recursive: true, force: true });
}
