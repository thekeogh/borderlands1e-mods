import { chromium, expect } from "@playwright/test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { spawn } from "node:child_process";
import AdmZip from "adm-zip";
const dir = mkdtempSync(path.join(tmpdir(), "backup-browser-"));
const server = spawn(
  process.execPath,
  ["--import", "tsx", "tests/browser-server.ts"],
  {
    env: { ...process.env, BORDERLENS_DATA_DIR: path.join(dir, ".data") },
    stdio: ["ignore", "pipe", "inherit"],
  },
);
await new Promise<void>((resolve, reject) => {
  const timer = setTimeout(
    () => reject(Error("Fixture startup timed out")),
    15000,
  );
  server.stdout.on("data", (data) => {
    if (data.toString().includes("READY")) {
      clearTimeout(timer);
      resolve();
    }
  });
});
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({
    baseURL: "http://127.0.0.1:4321",
    viewport: { width: 1440, height: 1000 },
    acceptDownloads: true,
  });
  page.setDefaultTimeout(60000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("http://127.0.0.1:4321");
  await page
    .locator("input[type=file]")
    .setInputFiles(
      path.resolve("../temp/imports/borderlens-20261023-153827-931444.zip"),
    );
  await page
    .getByRole("heading", { name: /Hellfire/i, level: 1 })
    .waitFor({ timeout: 60000 });
  const state = await page.request.get("/api/state").then((r) => r.json()),
    family = state.families.find((f: any) => /hellfire/i.test(f.name));
  await page.request.post(`/api/items/${family.id}/name`, {
    data: { name: "Backed up Hellfire" },
  });
  await page.request.post(`/api/items/${family.id}/text-evidence`, {
    data: {
      label: "Backup evidence",
      text: "Chosen facts saved before exporting the project.",
    },
  });
  await page.getByRole("button", { name: /Sources & evidence/ }).click();
  await page.getByTitle("Settings", { exact: true }).first().click();
  const backup = page.getByRole("region", { name: "Project backup" });
  await expect(
    backup.getByRole("button", { name: "Export Data", exact: true }),
  ).toBeEnabled();
  // Verify native Save As receives the timestamped default; cancellation is harmless.
  await page.evaluate(() => {
    (window as any).showSaveFilePicker = async (options: any) => {
      (window as any).__backupSuggestedName = options.suggestedName;
      throw new DOMException("Cancelled", "AbortError");
    };
  });
  await backup
    .getByRole("button", { name: "Export Data", exact: true })
    .click();
  await expect(
    backup.getByRole("button", { name: "Export Data", exact: true }),
  ).toBeEnabled();
  assert.match(
    await page.evaluate(() => (window as any).__backupSuggestedName),
    /^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}\.zip$/,
  );
  await expect(backup.getByRole("alert")).toHaveCount(0);
  // Exercise the successful native writable-stream branch without an OS dialog.
  await page.evaluate(`
    window.__nativeBackup={bytes:0,first:[],closed:false};
    window.showSaveFilePicker=async function(){return {createWritable:async function(){return new WritableStream({
      write:function(chunk){const state=window.__nativeBackup;if(!state.bytes)state.first=Array.from(chunk.slice(0,4));state.bytes+=chunk.byteLength;},
      close:function(){window.__nativeBackup.closed=true;}
    });}};};
  `);
  await backup
    .getByRole("button", { name: "Export Data", exact: true })
    .click();
  await expect
    .poll(
      async () =>
        await backup
          .locator('[role="status"],[role="alert"]')
          .allTextContents(),
      { timeout: 60000 },
    )
    .not.toEqual([]);
  await expect(
    backup.getByText("Project backup exported.", { exact: true }),
  ).toBeVisible();
  const native = await page.evaluate(() => (window as any).__nativeBackup);
  assert.ok(native.bytes > 1000);
  assert.equal(native.closed, true);
  assert.deepEqual(native.first.slice(0, 2), [0x50, 0x4b]);
  // Exercise browser-download fallback using the real complete ZIP endpoint.
  await page.evaluate(() => {
    (window as any).showSaveFilePicker = undefined;
  });
  const downloaded = page.waitForEvent("download");
  await backup
    .getByRole("button", { name: "Export Data", exact: true })
    .click();
  const download = await downloaded,
    file = (await download.path())!;
  assert.match(
    download.suggestedFilename(),
    /^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}\.zip$/,
  );
  const zip = new AdmZip(readFileSync(file)),
    manifest = JSON.parse(zip.readAsText("backup.json"));
  assert.equal(manifest.ui.tab, "sources");
  assert.equal(manifest.ui.selection, family.id);
  assert.ok(zip.getEntry("data/workshop.sqlite"));
  assert.ok(zip.getEntries().some((e) => e.entryName.startsWith("images/")));
  await expect(
    backup.getByText("Project backup exported.", { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: ".test-data/screenshots/project-backup-settings.png",
  });
  await page.request.post(`/api/items/${family.id}/name`, {
    data: { name: "Changed after backup" },
  });
  await page.request.post(`/api/items/${family.id}/text-evidence`, {
    data: {
      label: "Not in backup",
      text: "This later source must be replaced by restore.",
    },
  });
  const chooser = page.waitForEvent("filechooser");
  await backup
    .getByRole("button", { name: "Import Data", exact: true })
    .click();
  const ready = page.waitForEvent("load");
  await (await chooser).setFiles(file);
  await ready;
  await page
    .getByRole("heading", { name: "Backed up Hellfire", level: 1 })
    .waitFor();
  await expect(page.locator(".tabs > button.active")).toContainText(
    "Sources & evidence",
  );
  await expect(
    page.getByText("Backup evidence", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Not in backup", { exact: true })).toHaveCount(0);
  const restored = await page.request
    .get(`/api/items/${family.id}`)
    .then((r) => r.json());
  assert.equal(restored.family.name, "Backed up Hellfire");
  await page.getByRole("button", { name: "Preview", exact: true }).click();
  const restoredImage = page.locator(".item-image-stage img");
  await expect(restoredImage).toBeVisible();
  await expect
    .poll(() =>
      restoredImage.evaluate(
        (image: HTMLImageElement) => image.complete && image.naturalWidth > 0,
      ),
    )
    .toBe(true);
  await page.screenshot({ path: ".test-data/screenshots/restored-image.png" });
  assert.equal(restored.sources.length, 1);
  assert.equal(
    restored.sources[0].text,
    "Chosen facts saved before exporting the project.",
  );
  assert.deepEqual(
    await page.request.get("/__test/ai-count").then((r) => r.json()),
    { calls: 0 },
  );
  // Full reset must clear browser project state as well as server data.
  await page.getByTitle("Settings", { exact: true }).first().click();
  await page
    .locator("select")
    .filter({
      has: page.locator('option[value="all"]', {
        hasText: "Clear the entire project",
      }),
    })
    .selectOption("all");
  await page.getByLabel("Type RESET to confirm").fill("RESET");
  const resetLoaded = page.waitForEvent("load");
  await page
    .getByRole("button", { name: "Reset selected scope", exact: true })
    .click();
  await resetLoaded;
  const empty = await page.request.get("/api/state").then((r) => r.json());
  assert.deepEqual(empty.families, []);
  assert.deepEqual(empty.captures, []);
  assert.deepEqual(empty.sharedScopes, []);
  assert.equal(empty.run.status, "idle");
  assert.ok(
    !JSON.stringify(await page.evaluate(() => ({ ...localStorage }))).includes(
      family.id,
    ),
  );
  assert.ok(readFileSync(file).length > 1000);
  assert.deepEqual(errors, []);
  console.log(
    "Backup UI: timestamped native Save As/cancel, ZIP export/download, file picker restore, images/evidence/name/layout round-trip, full reset clears project/browser state and preserves downloaded ZIP; no AI.",
  );
} finally {
  await browser.close();
  server.kill("SIGTERM");
  await new Promise((resolve) => server.once("exit", resolve));
  rmSync(dir, { recursive: true, force: true });
}
