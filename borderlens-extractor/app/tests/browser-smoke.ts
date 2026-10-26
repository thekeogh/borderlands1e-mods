import { chromium, expect } from "@playwright/test";
import assert from "node:assert/strict";
import path from "node:path";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
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
  const waitForState = async (predicate: (state: any) => boolean) => {
    await expect
      .poll(
        async () =>
          predicate(await page.request.get("/api/state").then((r) => r.json())),
        { timeout: 15000 },
      )
      .toBe(true);
  };
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("http://127.0.0.1:4321");
  await page.getByRole("heading", { name: /Build a clearer/ }).waitFor();
  const agentSelect = page.getByRole("combobox", { name: "Default agent" });
  assert.equal(await agentSelect.inputValue(), "grok");
  assert.deepEqual(
    await agentSelect
      .locator("option")
      .evaluateAll((options) =>
        options.map((option) => (option as HTMLOptionElement).value),
      ),
    ["grok", "codex"],
  );
  await agentSelect.selectOption("codex");
  await waitForState((s) => s.settings.agent === "codex");
  await page.reload();
  assert.equal(await agentSelect.inputValue(), "codex");
  await agentSelect.selectOption("grok");
  await waitForState((s) => s.settings.agent === "grok");
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
  assert.equal(before.families.length, 299);
  assert.equal(
    before.families.filter((f: any) => f.category === "Class mods").length,
    44,
  );
  assert.equal(
    before.families.filter((f: any) => f.category === "Artifacts").length,
    16,
  );
  for (const category of ["Artifacts", "Class mods"]) {
    const group = page.locator(".tree-group").filter({
      has: page.locator(":scope > .group-toggle").filter({ hasText: category }),
    });
    assert.equal(await group.locator(".character-group").count(), 4);
    assert.equal(
      await group
        .locator(".character-group")
        .filter({ hasText: "Lilith" })
        .count(),
      1,
    );
  }
  assert.equal(
    await page
      .getByRole("button", { name: "Start from saved sources", exact: true })
      .isEnabled(),
    true,
  );
  await page.getByLabel("Rebuild options", { exact: true }).click();
  assert.equal(
    await page
      .locator(".rebuild-options-panel")
      .getByRole("button", { name: /^Rebuild from saved sources/ })
      .isDisabled(),
    true,
  );
  assert.equal(
    await page
      .locator(".rebuild-options-panel")
      .getByRole("button", { name: /^Rebuild from fresh sources/ })
      .isEnabled(),
    true,
  );
  await page.getByLabel("Rebuild options", { exact: true }).click();

  const hellfireRawFamily = before.families.find((family: any) =>
    /^hellfire$/i.test(family.name),
  );
  const rawBeforeBuild = await page.request
    .get(`/api/items/${hellfireRawFamily.id}/game-data`)
    .then((r) => r.json());
  assert.equal(
    (
      await page.request
        .get(`/api/items/${hellfireRawFamily.id}`)
        .then((r) => r.json())
    ).output,
    null,
  );
  await page.getByRole("button", { name: "Game data", exact: true }).click();
  const gameView = page.getByRole("region", {
    name: "Imported game data",
    exact: true,
  });
  await expect(
    gameView.getByRole("heading", { name: "HellFire", exact: true }),
  ).toBeVisible();
  await expect(
    gameView.getByText("We don't need no water...", { exact: true }),
  ).toBeVisible();
  const native = gameView.locator(".game-data-panel").filter({
    has: page.getByRole("heading", {
      name: "Native values & defining parts",
      exact: true,
    }),
  });
  await native
    .locator(".game-data-record")
    .filter({ hasText: "Incendiary" })
    .first()
    .locator(":scope > summary")
    .click();
  await expect(
    native.getByText("Tech Level Increase", { exact: true }),
  ).toBeVisible();
  await expect(native.getByText("14", { exact: true })).toBeVisible();
  await page
    .getByRole("textbox", { name: "Search game definitions" })
    .fill("TitleM_Maliwan1_HellFire");
  await page
    .getByRole("combobox", { name: "Filter game definitions" })
    .selectOption("root");
  await expect(
    gameView.locator(".game-data-panel").last().locator(".game-data-record"),
  ).toHaveCount(
    rawBeforeBuild.definitions.filter(
      (definition: any) => definition.role === "root",
    ).length,
  );
  await page.screenshot({
    path: ".test-data/screenshots/game-data-before-build.png",
  });
  await page.getByRole("button", { name: "Preview", exact: true }).click();
  await page
    .getByRole("heading", {
      name: "A good entry starts with evidence.",
      exact: true,
    })
    .waitFor();
  const hero = page.getByRole("img", { name: /Hellfire/i });
  await hero.waitFor();
  await page.waitForFunction(
    () =>
      !!document.querySelector<HTMLImageElement>(".item-image-stage img")
        ?.naturalWidth,
  );
  await page.locator(".image-picker summary").click();
  await page
    .getByRole("combobox", { name: "Item image file" })
    .selectOption("weapons/bessie.png");
  await page.waitForFunction(() =>
    document
      .querySelector<HTMLImageElement>(".item-image-stage img")
      ?.src.includes("weapons/bessie.png"),
  );
  assert.equal(
    (await page.request.get("/api/state").then((r) => r.json())).run.status,
    before.run.status,
  );
  await page.getByRole("button", { name: "Use automatic matching" }).click();
  await page.waitForFunction(() =>
    document
      .querySelector<HTMLImageElement>(".item-image-stage img")
      ?.src.includes("weapons/hellfire.png"),
  );
  await page.screenshot({ path: ".test-data/screenshots/item-image.png" });

  await page.getByRole("button", { name: "Sources & evidence" }).click();
  await page.getByRole("heading", { name: "Help it move forward" }).waitFor();
  const rawAfterBuild = await page.request
    .get(`/api/items/${hellfireRawFamily.id}/game-data`)
    .then((r) => r.json());
  assert.deepEqual(rawAfterBuild, rawBeforeBuild);
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
  await page
    .getByRole("button", { name: "Rebuild from fresh sources", exact: true })
    .click();
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
  await page.getByText("Final JSON checked", { exact: true }).waitFor();
  await page.screenshot({ path: ".test-data/screenshots/catalogue.png" });
  const top = await page.locator(".runbar").boundingBox();
  await page.locator("main").evaluate((el) => {
    el.scrollTop = 5000;
  });
  const after = await page.locator(".runbar").boundingBox();
  assert.equal(top?.y, after?.y);
  await page.getByRole("button", { name: /Coverage/ }).click();
  await page.getByRole("heading", { name: "Catalogue coverage" }).waitFor();
  await page
    .getByRole("heading", { name: "Image coverage", exact: true })
    .waitFor();
  assert.equal(
    await page
      .getByRole("combobox", { name: "Image coverage filter" })
      .inputValue(),
    "missing",
  );
  assert.ok((await page.locator(".image-missing-label").count()) > 0);
  await page
    .getByRole("textbox", { name: "Find image candidate" })
    .fill("Bessie");
  await page
    .getByRole("combobox", { name: "Image coverage filter" })
    .selectOption("matched");
  await page
    .locator(".image-coverage-table")
    .getByRole("button", { name: "Bessie", exact: true })
    .click();
  await page.getByRole("heading", { name: /Bessie/ }).waitFor();
  await expect(page.locator(".inspector")).toContainText(
    "The Secret Armory of General Knoxx",
  );
  await expect(
    page.locator(".inspector").getByText("Borderlands", { exact: true }),
  ).toBeVisible();
  await expect(page.locator(".inspector")).not.toContainText(
    "Borderlands GOTY Enhanced",
  );
  await page.screenshot({
    path: ".test-data/screenshots/item-dlc-preview.png",
  });
  await page.getByRole("img", { name: "Bessie", exact: true }).waitFor();
  await page.getByRole("button", { name: /Coverage/ }).click();

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
  await page
    .getByRole("button", { name: "Rebuild from saved sources", exact: true })
    .click();
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
  assert.equal(detail.output.dlc, "The Secret Armory of General Knoxx");
  assert.equal(detail.websiteOutput.dlc, "The Secret Armory of General Knoxx");
  assert(!("game" in detail.websiteOutput));
  assert(!("game" in detail.output));
  await page
    .getByRole("combobox", { name: "Item type" })
    .selectOption("Shotguns");
  await page.locator(".group-toggle").filter({ hasText: "Shotguns" }).waitFor();
  await page.getByRole("combobox", { name: "Item type" }).selectOption("");
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

  await page.getByLabel("Batch source options", { exact: true }).click();
  await page
    .locator(".batch-options .rebuild-options-panel")
    .screenshot({ path: ".test-data/screenshots/batch-source-options.png" });
  await page
    .locator(".batch-options")
    .getByRole("button", { name: /^Start from fresh sources/ })
    .click();
  await page.getByRole("button", { name: "Pause", exact: true }).waitFor();
  await page.getByRole("button", { name: "Pause", exact: true }).click();
  await waitForState((s) => s.run.status === "paused");
  assert.equal(
    (await page.request.get("/api/state").then((r) => r.json())).run.sourceMode,
    "fresh",
  );
  await page.reload();
  await page.getByRole("button", { name: "Resume", exact: true }).waitFor();

  await page.getByRole("button", { name: "Final JSON", exact: true }).click();
  await page
    .getByRole("textbox", { name: "Edit final item JSON" })
    .fill('{"unsaved":"keep during folder refresh"}');
  await page.getByRole("button", { name: "Preview", exact: true }).click();
  await page.locator(".image-picker summary").click();
  await page.getByRole("button", { name: "Resume", exact: true }).click();
  await page.getByRole("button", { name: "Pause", exact: true }).waitFor();
  const runningBefore = await page.request
    .get("/api/state")
    .then((r) => r.json());
  const folder = path.join(dir, "image-library", "new-images");
  mkdirSync(folder, { recursive: true });
  writeFileSync(
    path.join(folder, "added.png"),
    Buffer.from(
      "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jq1sAAAAASUVORK5CYII=",
      "base64",
    ),
  );
  const [folderResponse] = await Promise.all([
    page.waitForResponse(
      (r) => r.url().endsWith("/api/images") && r.status() === 200,
    ),
    page.getByRole("button", { name: "Refresh folder", exact: true }).click(),
  ]);
  assert.ok(
    (await folderResponse.json()).files.includes("new-images/added.png"),
  );
  await page
    .getByRole("combobox", { name: "Item image file" })
    .locator('option[value="new-images/added.png"]')
    .waitFor({ state: "attached" });
  await page.getByText("Folder refreshed.", { exact: true }).waitFor();
  const runningAfter = await page.request
    .get("/api/state")
    .then((r) => r.json());
  assert.equal(runningAfter.run.status, "running");
  assert.equal(runningAfter.run.startedAt, runningBefore.run.startedAt);
  assert.deepEqual(runningAfter.run.queue, runningBefore.run.queue);
  assert.equal(runningAfter.run.pauseRequested, false);
  await page.getByRole("button", { name: "Final JSON", exact: true }).click();
  assert.equal(
    await page
      .getByRole("textbox", { name: "Edit final item JSON" })
      .inputValue(),
    '{"unsaved":"keep during folder refresh"}',
  );
  await page.getByRole("button", { name: "Pause", exact: true }).click();
  await waitForState((s) => s.run.status === "paused");
  await page.getByRole("button", { name: "All", exact: true }).click();
  await page.getByRole("textbox", { name: "Find an item" }).fill("Hellfire");
  await page
    .locator(".item-row")
    .filter({ hasText: /Hellfire/i })
    .first()
    .click();
  await page.getByRole("button", { name: "Preview", exact: true }).click();
  await page
    .getByRole("button", { name: "Remove from catalogue", exact: true })
    .click();
  await waitForState(
    (s) =>
      s.families.find((f: any) => /hellfire/i.test(f.name)).status ===
      "excluded",
  );
  await page
    .locator(".item-row")
    .filter({ hasText: /Hellfire/i })
    .waitFor({ state: "detached" });
  await page.getByRole("button", { name: /^Removed items/ }).click();
  await page
    .locator(".item-row")
    .filter({ hasText: /Hellfire/i })
    .first()
    .click();
  await page
    .getByRole("button", { name: "Restore to catalogue", exact: true })
    .click();
  await waitForState(
    (s) =>
      s.families.find((f: any) => /hellfire/i.test(f.name)).status !==
      "excluded",
  );
  await page.getByRole("button", { name: "All", exact: true }).click();
  await page
    .locator(".item-row")
    .filter({ hasText: /Hellfire/i })
    .first()
    .waitFor();
  const shield = before.families.find((f: any) => f.name === "Ironclad");
  assert.ok(shield);
  await page.getByRole("textbox", { name: "Find an item" }).fill("Ironclad");
  await page
    .locator(".item-row")
    .filter({ hasText: "Ironclad" })
    .first()
    .click();
  await page.request.post("/api/run", { data: { action: "pause" } });
  await waitForState((s) => s.run.status === "paused" && !s.run.pauseRequested);
  const savedShield = await page.request.post(
    `/api/items/${shield.id}/action`,
    {
      data: {
        action: "resolve",
        url: "https://www.lootlemon.com/shield/ironclad-bl1",
        html: "<h1>Ironclad • BL1 – Pearlescent Shield | Lootlemon</h1><p>Synthetic fixture article identifies Ironclad as a Borderlands 1 shield for browser testing.</p>",
      },
    },
  );
  assert.equal(savedShield.status(), 200, await savedShield.text());
  assert.equal(
    (
      await page.request.post(`/api/items/${shield.id}/action`, {
        data: { action: "rebuild-saved" },
      })
    ).status(),
    200,
  );
  await waitForState((s) => {
    const f = s.families.find((f: any) => f.id === shield.id);
    return f.category === "Shields" && f.status === "done";
  });
  await page
    .locator(".tree-group")
    .filter({
      has: page
        .locator(":scope > .group-toggle")
        .filter({ hasText: "Shields" }),
    })
    .locator(".item-row")
    .filter({ hasText: "Ironclad" })
    .waitFor();
  const shieldDetail = await page.request
    .get(`/api/items/${shield.id}`)
    .then((r) => r.json());
  assert.equal(shieldDetail.family.id, shield.id);
  assert.equal(shieldDetail.websiteOutput.category, "Shields");
  await page.getByRole("button", { name: /^Sources & evidence/ }).click();
  const removeSource = page.getByRole("button", {
    name: "Remove source: Ironclad • BL1 – Pearlescent Shield | Lootlemon",
    exact: true,
  });
  await removeSource.click();
  await waitForState(
    (s) => s.families.find((f: any) => f.id === shield.id).status === "queued",
  );
  await page
    .locator(".source-card")
    .filter({ hasText: "Synthetic fixture article" })
    .waitFor({ state: "detached" });
  const removedSources = page.locator(".removed-sources");
  await removedSources.locator("summary").click();
  await removedSources
    .getByRole("button", {
      name: "Restore source: Ironclad • BL1 – Pearlescent Shield | Lootlemon",
      exact: true,
    })
    .click();
  await page
    .locator(".source-card")
    .filter({ hasText: "Synthetic fixture article" })
    .waitFor();
  // Shared evidence is managed without touching the individual item's form.
  const sharedCategory = (
    await page.request.get(`/api/items/${shield.id}`).then((r) => r.json())
  ).family.category;
  await page
    .getByRole("button", {
      name: "Shared evidence for " + sharedCategory,
      exact: true,
    })
    .click();
  const shared = page.getByRole("dialog", {
    name: "Shared evidence",
    exact: true,
  });
  await expect(
    shared.getByRole("combobox", { name: "Evidence group" }),
  ).toHaveValue(sharedCategory);
  const sharedUrl = "https://borderlands.fandom.com/wiki/Shield_(Borderlands)";
  await shared
    .getByRole("textbox", { name: "Shared evidence URL" })
    .fill(sharedUrl);
  await shared.getByRole("button", { name: "Add source", exact: true }).click();
  await shared
    .getByRole("button", { name: "Open in Chrome", exact: true })
    .waitFor();
  await expect(
    shared.getByText(
      "Not captured yet · URL only. Open in Chrome to capture the article.",
    ),
  ).toBeVisible();
  await shared
    .getByLabel("Import shared HTML: " + sharedUrl, { exact: true })
    .setInputFiles({
      name: "shield-overview.html",
      mimeType: "text/html",
      buffer: Buffer.from(
        "<h1>Shield overview fixture</h1><p>Stored shared shield mechanics and capacity evidence for this synthetic browser workflow. These original words are not copied from any external source.</p>",
      ),
    });
  await expect(
    shared.getByText(/Imported HTML · .*characters saved/),
  ).toBeVisible();
  const savedShared = await page.request
    .get("/api/shared-sources")
    .then((r) => r.json());
  const storedArticle = savedShared
    .find((row: any) => row.family.evidenceScope.category === sharedCategory)
    .sources.find((source: any) => source.url === sharedUrl);
  await expect(shared.locator(".shared-captured-text")).toHaveText(
    storedArticle.text.slice(0, 550),
  );
  await page.screenshot({ path: ".test-data/screenshots/shared-evidence.png" });
  await shared.getByRole("button", { name: "Close shared evidence" }).click();
  await page
    .getByRole("region", { name: "Inherited evidence", exact: true })
    .getByRole("link", { name: "Shield overview fixture" })
    .waitFor();
  await expect(
    page
      .locator("article.source-card")
      .filter({ hasText: "Shield overview fixture" }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "Shared evidence", exact: true })
    .click();
  const globalDialog = page.getByRole("dialog", {
    name: "Shared evidence",
    exact: true,
  });
  await expect(
    globalDialog.getByRole("combobox", { name: "Evidence group" }),
  ).toHaveValue("Everything");
  const globalUrl = "https://borderlands.fandom.com/wiki/Elemental_fixture";
  await globalDialog
    .getByRole("textbox", { name: "Shared evidence URL" })
    .fill(globalUrl);
  await globalDialog
    .getByRole("button", { name: "Add source", exact: true })
    .click();
  await globalDialog
    .getByLabel("Import shared HTML: " + globalUrl, { exact: true })
    .setInputFiles({
      name: "global.html",
      mimeType: "text/html",
      buffer: Buffer.from(
        "<h1>Universal elemental fixture</h1><p>Original global evidence fixture available to every category, weapon type and character in this synthetic catalogue.</p>",
      ),
    });
  await expect(
    globalDialog.getByText(/Imported HTML · .*characters saved/),
  ).toBeVisible();
  await expect(globalDialog.locator(".source-site").first()).toHaveText(
    "borderlands.fandom.com",
  );
  const pendingGlobalUrl =
    "https://borderlands.fandom.com/wiki/Pending_elemental_fixture";
  await globalDialog
    .getByRole("textbox", { name: "Shared evidence URL" })
    .fill(pendingGlobalUrl);
  await globalDialog
    .getByRole("button", { name: "Add source", exact: true })
    .click();
  await globalDialog
    .getByText(
      "Not captured yet · URL only. Open in Chrome to capture the article.",
    )
    .waitFor();
  await page.screenshot({ path: ".test-data/screenshots/global-evidence.png" });
  await globalDialog
    .getByRole("button", { name: "Close shared evidence" })
    .click();
  const allState = await page.request.get("/api/state").then((r) => r.json());
  for (const sample of [
    allState.families.find((f: any) => f.category === "Weapons"),
    allState.families.find((f: any) => f.category === "Artifacts"),
    allState.families.find((f: any) => f.category === "Class mods"),
  ]) {
    const sampleDetail = await page.request
      .get(`/api/items/${sample.id}`)
      .then((r) => r.json());
    assert(
      sampleDetail.sources.some(
        (source: any) =>
          source.url === globalUrl &&
          source.inheritedFrom.name === "Everything",
      ),
    );
  }
  const inheritedList = page.getByRole("region", {
    name: "Inherited evidence",
    exact: true,
  });
  await expect(
    inheritedList.getByText("Universal elemental fixture", { exact: true }),
  ).toBeVisible();
  await expect(
    inheritedList.getByText("Pending elemental fixture", { exact: true }),
  ).toBeVisible();
  await expect(
    inheritedList.getByText("Awaiting capture", { exact: true }),
  ).toBeVisible();
  await expect(
    page
      .locator("article.source-card")
      .filter({ hasText: "Universal elemental fixture" }),
  ).toHaveCount(0);
  await expect(
    page
      .locator("article.source-card")
      .filter({ hasText: "Ironclad • BL1 – Pearlescent Shield | Lootlemon" }),
  ).toHaveCount(1);
  await page.getByLabel("Rebuild options", { exact: true }).click();
  await page.getByRole("button", { name: /Fetch evidence URLs only/ }).click();
  await waitForState(
    (s) =>
      s.run.mode === "discover" &&
      s.run.status === "complete" &&
      s.run.queue.length === 1 &&
      s.run.queue[0] === shield.id,
  );
  const itemDiscovery = await page.request
    .get(`/api/items/${shield.id}`)
    .then((r) => r.json());
  assert(
    itemDiscovery.family.sourceUrls.includes(
      "https://borderlands.fandom.com/wiki/Fixture_article",
    ),
  );
  assert(!itemDiscovery.family.sourceUrls.includes(globalUrl));
  assert(!itemDiscovery.family.sourceUrls.includes(pendingGlobalUrl));
  const pendingItemUrl = "https://borderlands.fandom.com/wiki/Fixture_article";
  await page
    .getByRole("button", {
      name: "Remove evidence URL: " + pendingItemUrl,
      exact: true,
    })
    .click();
  await waitForState(
    (s) =>
      !s.families
        .find((family: any) => family.id === shield.id)
        .sourceUrls.includes(pendingItemUrl),
  );
  await expect(
    page.getByRole("button", {
      name: "Remove evidence URL: " + pendingItemUrl,
      exact: true,
    }),
  ).toHaveCount(0);
  const pendingRemoved = page.locator(".removed-sources");
  if ((await pendingRemoved.getAttribute("open")) === null)
    await pendingRemoved.locator("summary").click();
  await pendingRemoved
    .getByRole("button", {
      name: "Restore source: Fixture article",
      exact: true,
    })
    .click();
  await page
    .getByRole("button", {
      name: "Remove evidence URL: " + pendingItemUrl,
      exact: true,
    })
    .waitFor();

  await page.screenshot({
    path: ".test-data/screenshots/item-discovery-inheritance.png",
  });
  const beforeDiscovery = await page.request
    .get("/api/state")
    .then((r) => r.json());
  await page.request.patch("/api/settings", { data: { maxItems: 2 } });
  await page.getByLabel("Batch source options", { exact: true }).click();
  await page.getByRole("button", { name: /Find evidence URLs only/ }).click();
  await waitForState(
    (s) =>
      s.run.mode === "discover" &&
      s.run.status === "complete" &&
      s.run.queue.length === 2 &&
      s.run.index === 2,
  );
  const afterDiscovery = await page.request
    .get("/api/state")
    .then((r) => r.json());
  assert.deepEqual(
    afterDiscovery.families.map((f: any) => [
      f.id,
      f.status,
      f.stage,
      f.revision,
    ]),
    beforeDiscovery.families.map((f: any) => [
      f.id,
      f.status,
      f.stage,
      f.revision,
    ]),
  );
  assert.equal(afterDiscovery.run.index, 2);
  assert(
    afterDiscovery.run.queue.every(
      (id: string) =>
        afterDiscovery.families.find((family: any) => family.id === id)
          .urlDiscovery?.status === "complete",
    ),
  );
  // Group actions use all active descendants, regardless of the filtered tree.
  const groupSnapshot = await page.request
    .get("/api/state")
    .then((r) => r.json());
  const artifactIds = groupSnapshot.families
    .filter(
      (f: any) =>
        f.category === "Artifacts" &&
        f.status !== "excluded" &&
        !f.supersededBy,
    )
    .map((f: any) => f.id);
  const expectedBrickIds = groupSnapshot.families
    .filter((f: any) => artifactIds.includes(f.id) && f.character === "Brick")
    .map((f: any) => f.id);
  await page.request.patch("/api/settings", { data: { maxItems: 10000 } });
  await page
    .getByRole("textbox", { name: "Find an item" })
    .fill("Corrosive Artifact");
  await page
    .getByRole("button", { name: "Batch actions for Artifacts", exact: true })
    .click();
  const categoryMenu = page.getByRole("menu", {
    name: "Batch actions for Artifacts",
    exact: true,
  });
  await expect(
    categoryMenu.getByText(`${artifactIds.length} items`, { exact: true }),
  ).toBeVisible();
  await categoryMenu
    .getByRole("menuitem", { name: /Fetch evidence URLs only/ })
    .click();
  await waitForState(
    (s) =>
      s.run.scope?.category === "Artifacts" &&
      !s.run.scope.character &&
      s.run.status === "complete" &&
      s.run.queue.length === artifactIds.length,
  );
  let scoped = await page.request.get("/api/state").then((r) => r.json());
  assert(
    scoped.run.queue.every(
      (id: string) =>
        scoped.families.find((f: any) => f.id === id).category === "Artifacts",
    ),
  );
  await page.getByRole("textbox", { name: "Find an item" }).fill("Artifact");
  const artifactGroup = page.locator(".tree-group").filter({
    has: page
      .locator(":scope > .group-toggle")
      .filter({ hasText: "Artifacts" }),
  });
  const artifactToggle = artifactGroup.locator(":scope > .group-toggle");
  if ((await artifactToggle.getAttribute("aria-expanded")) === "false")
    await artifactToggle.click();
  await page
    .getByRole("button", {
      name: "Batch actions for Artifacts → Brick",
      exact: true,
    })
    .click();
  const characterMenu = page.getByRole("menu", {
    name: "Batch actions for Artifacts → Brick",
    exact: true,
  });
  await expect(
    characterMenu.getByText(`${expectedBrickIds.length} items`, {
      exact: true,
    }),
  ).toBeVisible();
  await page.screenshot({ path: ".test-data/screenshots/group-actions.png" });
  await characterMenu
    .getByRole("menuitem", { name: /Fetch evidence URLs only/ })
    .click();
  await waitForState(
    (s) =>
      s.run.scope?.character === "Brick" &&
      s.run.status === "complete" &&
      s.run.queue.length === expectedBrickIds.length,
  );
  scoped = await page.request.get("/api/state").then((r) => r.json());
  const brickIds = scoped.run.queue;
  for (const action of [
    "Rebuild from saved sources",
    "Rebuild from fresh sources",
  ]) {
    await page
      .getByRole("button", {
        name: "Batch actions for Artifacts → Brick",
        exact: true,
      })
      .click();
    await page
      .getByRole("menu", {
        name: "Batch actions for Artifacts → Brick",
        exact: true,
      })
      .getByRole("menuitem", { name: new RegExp("^" + action) })
      .click();
    await waitForState(
      (s) =>
        s.run.mode === "build" &&
        s.run.scope?.character === "Brick" &&
        s.run.status === "complete" &&
        s.run.queue.length === expectedBrickIds.length &&
        s.run.queue.every(
          (id: string) =>
            s.families.find((f: any) => f.id === id).status === "done",
        ),
    );
    scoped = await page.request.get("/api/state").then((r) => r.json());
    assert.deepEqual(scoped.run.queue, brickIds);
  }
  await expect(page.getByLabel("Batch group", { exact: true })).toHaveText(
    "Artifacts → Brick",
  );
  await page.locator(`.item-row[data-family-id="${brickIds[1]}"]`).click();
  await page.getByRole("button", { name: /^Sources & evidence/ }).click();
  const sharedSummary = page.locator(".shared-research-summary");
  await expect(sharedSummary).toBeVisible();
  await sharedSummary.locator("summary").click();
  await expect(sharedSummary).toContainText(
    "General and uncertain facts stay included",
  );
  const sharedDetail = await page.request
    .get(`/api/items/${brickIds[1]}`)
    .then((r) => r.json());
  assert(sharedDetail.sharedSourceSelection.cachedChunks > 0);
  await page.screenshot({
    path: ".test-data/screenshots/shared-source-analysis.png",
  });
  // Existing captures are reused across item references without another build.
  const cacheUrl =
    "https://borderlands.fandom.com/wiki/Catalogue_Cache_Fixture";
  const cacheAlias =
    "https://borderlands.fandom.com/wiki/Catalogue%20Cache%20Fixture#Notes";
  for (const [id, body] of [
    [
      brickIds[0],
      {
        url: cacheUrl,
        html: "<main><h1>Saved catalogue article fixture</h1><p>This is the original saved content for a catalogue-wide article, reused only by items explicitly referencing the same page.</p></main>",
      },
    ],
    [brickIds[1], { url: cacheAlias }],
  ] as const) {
    const response = await page.request.post(`/api/items/${id}/action`, {
      data: { action: "resolve", ...body },
    });
    assert.equal(response.ok(), true, await response.text());
  }
  await page.locator(`.item-row[data-family-id="${brickIds[1]}"]`).click();
  await page.getByRole("button", { name: /^Sources & evidence/ }).click();
  await expect(
    page.getByText("Saved catalogue article fixture", { exact: true }),
  ).toBeVisible();
  await expect(
    page
      .locator(".source-card")
      .filter({ hasText: "Saved catalogue article fixture" })
      .locator(".source-site"),
  ).toHaveText("borderlands.fandom.com");
  await expect(page.locator(".source-reused")).toContainText(
    "Reused saved article",
  );
  await expect(
    page.getByText("This is the original saved content", { exact: false }),
  ).toBeVisible();
  await page.screenshot({
    path: ".test-data/screenshots/catalogue-cache-reuse.png",
    fullPage: true,
  });
  const beforePromotion = await page.request
    .get("/api/state")
    .then((r) => r.json());
  const cacheCard = page
    .locator(".source-card")
    .filter({ hasText: "Saved catalogue article fixture" });
  await cacheCard
    .getByRole("button", {
      name: "Move evidence to Artifacts → Brick",
      exact: true,
    })
    .click();
  await expect(cacheCard).toHaveCount(0);
  await expect(
    page
      .locator(".inherited-evidence-list")
      .getByText("Saved catalogue article fixture", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Shared evidence", exact: true })
    .click();
  const promoteDialog = page.getByRole("dialog", {
    name: "Shared evidence",
    exact: true,
  });
  await promoteDialog
    .getByRole("combobox", { name: "Evidence group" })
    .selectOption({ label: "Artifacts → Brick" });
  const sharedCacheCard = promoteDialog
    .locator(".source-card")
    .filter({ hasText: "Saved catalogue article fixture" });
  await expect(sharedCacheCard).toBeVisible();
  await page.screenshot({
    path: ".test-data/screenshots/promote-evidence.png",
  });
  await sharedCacheCard
    .getByRole("button", { name: "Move evidence to Artifacts", exact: true })
    .click();
  await expect(sharedCacheCard).toHaveCount(0);
  await promoteDialog
    .getByRole("combobox", { name: "Evidence group" })
    .selectOption({ label: "Artifacts" });
  await expect(sharedCacheCard).toBeVisible();
  await sharedCacheCard
    .getByRole("button", { name: "Move evidence to Everything", exact: true })
    .click();
  await promoteDialog
    .getByRole("combobox", { name: "Evidence group" })
    .selectOption({ label: "Everything" });
  await expect(sharedCacheCard).toBeVisible();
  await expect(sharedCacheCard.locator(".source-promote-button")).toHaveCount(
    0,
  );
  await promoteDialog
    .getByRole("button", { name: "Close shared evidence" })
    .click();
  const afterPromotion = await page.request
    .get("/api/state")
    .then((r) => r.json());
  assert.deepEqual(afterPromotion.run, beforePromotion.run);
  assert.deepEqual(
    afterPromotion.buildCheckpoint,
    beforePromotion.buildCheckpoint,
  );
  const inclusionRegion = page.getByRole("region", {
    name: "Inherited evidence",
  });
  const inclusion = inclusionRegion.getByRole("combobox", {
    name: "Evidence mode: Saved catalogue article fixture",
    exact: true,
  });
  await expect(inclusion).toHaveValue("auto");
  await inclusion.selectOption("always");
  await expect(inclusion).toHaveValue("always");
  await expect(inclusion).toBeEnabled();

  const inclusionDetail = await page.request
    .get(`/api/items/${brickIds[1]}`)
    .then((r) => r.json());
  assert(
    inclusionDetail.inheritedEvidence.find(
      (row: any) => row.title === "Saved catalogue article fixture",
    ).alwaysInclude,
  );
  const otherInclusion = await page.request
    .get(`/api/items/${brickIds[0]}`)
    .then((r) => r.json());
  assert(
    !otherInclusion.inheritedEvidence.find(
      (row: any) => row.title === "Saved catalogue article fixture",
    ).alwaysInclude,
  );
  await page.screenshot({
    path: ".test-data/screenshots/inherited-inclusion.png",
  });
  await inclusion.selectOption("never");
  await expect(inclusion).toBeEnabled();
  await expect(inclusion).toHaveValue("never");
  const neverDetail = await page.request
    .get(`/api/items/${brickIds[1]}`)
    .then((r) => r.json());
  assert.equal(
    neverDetail.inheritedEvidence.find(
      (row: any) => row.title === "Saved catalogue article fixture",
    ).inclusionMode,
    "never",
  );
  assert(
    !neverDetail.sources.some(
      (row: any) => row.title === "Saved catalogue article fixture",
    ),
  );
  await page.screenshot({ path: ".test-data/screenshots/inherited-never.png" });
  await inclusion.selectOption("auto");
  await expect(inclusion).toBeEnabled();
  await expect(inclusion).toHaveValue("auto");
  const afterInclusion = await page.request
    .get("/api/state")
    .then((r) => r.json());
  assert.deepEqual(afterInclusion.run, afterPromotion.run);
  assert.deepEqual(
    afterInclusion.buildCheckpoint,
    afterPromotion.buildCheckpoint,
  );
  await page.request.post(`/api/items/${brickIds[1]}/action`, {
    data: { action: "resolve", notes: "browser-followup-fixture" },
  });
  await page
    .getByRole("button", { name: "Rebuild from saved sources", exact: true })
    .click();
  await waitForState(
    (state) =>
      state.run.status === "complete" &&
      state.families.find((item: any) => item.id === brickIds[1]).status ===
        "done",
  );
  const followupSummary = page.locator(".evidence-followup-summary");
  await expect(followupSummary).toBeVisible();
  await followupSummary.locator("summary").click();
  await expect(followupSummary).toContainText("Original catalogue context");
  await expect(followupSummary).toContainText("One optional request round");
  await expect(followupSummary.locator(".source-site").first()).toHaveText(
    "borderlands.fandom.com",
  );
  const followed = await page.request
    .get(`/api/items/${brickIds[1]}`)
    .then((r) => r.json());
  assert.equal(followed.evidenceFollowup.status, "supplied");
  assert(followed.evidenceFollowup.matches.length > 0);
  assert(!("evidenceRequests" in followed.websiteOutput));
  await page.screenshot({
    path: ".test-data/screenshots/saved-evidence-followup.png",
  });
  const reviewFixture = await page.request
    .post("/__test/review-tools")
    .then((r) => r.json());
  await page
    .getByRole("textbox", { name: "Find an item" })
    .fill("Browser Cyclone");
  await page.locator('.item-row[data-family-id="browser-review"]').click();
  await page.getByRole("button", { name: "Preview", exact: true }).click();
  await page
    .getByRole("button", { name: "Find duplicates", exact: true })
    .click();
  await expect(page.locator(".duplicate-finder")).toContainText(
    "1 possible match",
  );
  await page.getByRole("button", { name: "Inspect Browser Cyclone" }).click();
  const duplicateDialog = page.getByRole("dialog", {
    name: "Possible match: Browser Cyclone",
  });
  await expect(duplicateDialog).toContainText("Read-only inspection");
  await expect(
    duplicateDialog.getByText("ZIP only", { exact: true }),
  ).toBeVisible();
  await expect(
    duplicateDialog.getByRole("heading", { name: "Identity", exact: true }),
  ).toBeVisible();
  await expect(
    duplicateDialog.getByRole("button", { name: /Remove/ }),
  ).toHaveCount(0);
  await page.screenshot({
    path: ".test-data/screenshots/duplicate-inspection.png",
  });
  await page
    .getByRole("button", { name: "Close duplicate inspection" })
    .click();
  await page.screenshot({
    path: ".test-data/screenshots/duplicate-finder.png",
  });
  await page
    .getByRole("button", { name: "Remove this Needs review item" })
    .click();
  await waitForState(
    (state) =>
      state.families.find((f: any) => f.id === "browser-review").status ===
      "excluded",
  );
  assert.notEqual(
    (
      await page.request
        .get(`/api/items/${reviewFixture.properId}`)
        .then((r) => r.json())
    ).family.status,
    "excluded",
  );
  await page.request.post("/api/items/browser-review/action", {
    data: { action: "restore" },
  });
  await page.reload();
  await page
    .getByRole("textbox", { name: "Find an item" })
    .fill("Browser Cyclone");
  await page.locator('.item-row[data-family-id="browser-review"]').click();
  await page.getByLabel("Rebuild options", { exact: true }).click();
  await page.getByRole("button", { name: /Fetch evidence URLs only/ }).click();
  await waitForState(
    (state) =>
      state.run.status === "complete" &&
      state.families.find((f: any) => f.id === "browser-review").classification
        ?.weaponType === "SMGs",
  );
  const discoveredReview = await page.request
    .get("/api/items/browser-review")
    .then((r) => r.json());
  assert(!discoveredReview.output);
  assert(
    discoveredReview.family.history.some((h: any) =>
      h.message.includes("Verified during URL discovery"),
    ),
  );
  await expect(page.locator(".duplicate-finder")).toHaveCount(0);
  await page.screenshot({
    path: ".test-data/screenshots/discovery-classification.png",
  });
  const naming = await page.request
    .post("/__test/name-tools")
    .then((r) => r.json());
  await page.getByRole("textbox", { name: "Find an item" }).fill("Rifle");
  await page.locator(`.item-row[data-family-id="${naming.id}"]`).click();
  await page.getByRole("button", { name: "Preview", exact: true }).click();
  await page
    .getByRole("button", { name: "Rebuild from saved sources", exact: true })
    .click();
  await waitForState(
    (state) =>
      state.run.status === "complete" &&
      state.families.find((f: any) => f.id === naming.id).status === "done",
  );
  await expect(
    page.getByRole("heading", { name: /^Eridian Rifle/, level: 1 }),
  ).toBeVisible();
  await expect(
    page.locator(`.item-row[data-family-id="${naming.id}"]`),
  ).toContainText("Eridian Rifle");
  await expect(page.locator(".inspector")).toContainText("Extracted name");
  const renamed = await page.request
    .get(`/api/items/${naming.id}`)
    .then((r) => r.json());
  assert.equal(renamed.family.rawName, "Rifle");
  assert.equal(renamed.websiteOutput.name, "Eridian Rifle");
  assert.equal(renamed.websiteOutput.slug, "eridian-rifle");
  assert(!("nameDecision" in renamed.websiteOutput));
  const namedState = await page.request.get("/api/state").then((r) => r.json());
  assert.equal(
    namedState.families.find(
      (f: any) =>
        f.id !== naming.id &&
        f.subtype === "Combat rifles" &&
        f.name === "Rifle",
    ).name,
    "Rifle",
  );
  await page.screenshot({ path: ".test-data/screenshots/verified-name.png" });
  const syncType = await page.request
    .post("/__test/sync-type-tools")
    .then((r) => r.json());
  await page.getByRole("textbox", { name: "Find an item" }).fill("Ironclad");
  await page.locator(`.item-row[data-family-id="${syncType.id}"]`).click();
  await page.getByRole("button", { name: "Preview", exact: true }).click();
  const syncRun = (await page.request.get("/api/state").then((r) => r.json()))
    .run;
  await page.getByRole("button", { name: "Sync type", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Sync type", exact: true }),
  ).toBeDisabled();
  await waitForState(
    (state) =>
      state.identitySync === null &&
      state.families.find((f: any) => f.id === syncType.id).category ===
        "Shields",
  );
  await expect(page.locator(".inspector")).toContainText("Shields");
  const syncedShield = await page.request
    .get(`/api/items/${syncType.id}`)
    .then((r) => r.json());
  assert.equal(Boolean(syncedShield.output), syncType.hadOutput);
  if (syncType.hadOutput) {
    assert.equal(syncedShield.output.category, "Shields");
    assert.deepEqual(syncedShield.output.description, syncType.description);
  }
  assert.deepEqual(
    (await page.request.get("/api/state").then((r) => r.json())).run,
    syncRun,
  );
  await page.screenshot({ path: ".test-data/screenshots/sync-type.png" });
  const syncName = await page.request
    .post("/__test/sync-name-tools")
    .then((r) => r.json());
  await page.getByRole("textbox", { name: "Find an item" }).fill("Rifle");
  await page.locator(`.item-row[data-family-id="${syncName.id}"]`).click();
  await page.getByRole("button", { name: "Sync name", exact: true }).click();
  await waitForState(
    (state) =>
      state.identitySync === null &&
      state.families.find((f: any) => f.id === syncName.id).name ===
        "Eridian Rifle",
  );
  await expect(
    page.getByRole("heading", { name: /^Eridian Rifle/, level: 1 }),
  ).toBeVisible();
  const syncedName = await page.request
    .get(`/api/items/${syncName.id}`)
    .then((r) => r.json());
  assert.equal(syncedName.websiteOutput.name, "Eridian Rifle");
  assert.deepEqual(syncedName.output.description, syncName.description);
  assert(syncedName.family.manualOutput);
  await page.screenshot({ path: ".test-data/screenshots/sync-name.png" });
  const manualCalls = await page.request
    .get("/__test/ai-count")
    .then((r) => r.json());
  await page.getByRole("textbox", { name: "Find an item" }).fill("Ironclad");
  await page.locator(`.item-row[data-family-id="${syncType.id}"]`).click();
  const manualPicker = page.getByRole("combobox", {
    name: "Item type",
    exact: true,
  });
  await expect(manualPicker).toBeVisible();
  const choices = await manualPicker
    .locator("option")
    .evaluateAll((options) =>
      options.map((o) => (o as HTMLOptionElement).value),
    );
  for (const type of [
    "Shields",
    "Class mods",
    "Grenade mods",
    "Artifacts",
    "SMGs",
  ])
    assert(choices.includes(type));
  for (const type of ["Artifacts", "Class mods", "Grenade mods", "SMGs"]) {
    await manualPicker.selectOption(type);
    await waitForState(
      (state) =>
        state.families.find((f: any) => f.id === syncType.id).classification
          ?.origin === "manual" &&
        (type === "SMGs"
          ? state.families.find((f: any) => f.id === syncType.id).classification
              .weaponType === type
          : state.families.find((f: any) => f.id === syncType.id).category ===
            type),
    );
    await expect(manualPicker).toHaveValue(type);
  }
  await page.screenshot({ path: ".test-data/screenshots/manual-type.png" });
  await manualPicker.selectOption("");
  await waitForState(
    (state) =>
      state.families.find((f: any) => f.id === syncType.id).classification
        ?.origin === "research" &&
      state.families.find((f: any) => f.id === syncType.id).category ===
        "Shields",
  );
  assert.deepEqual(
    await page.request.get("/__test/ai-count").then((r) => r.json()),
    manualCalls,
  );
  await expect(
    page.getByRole("button", { name: "Sync type", exact: true }),
  ).toBeVisible();
  const nameCalls = await page.request
    .get("/__test/ai-count")
    .then((r) => r.json());
  await page
    .getByRole("button", { name: "Edit item name", exact: true })
    .click();
  const manualNameInput = page.getByRole("textbox", {
    name: "Item name",
    exact: true,
  });
  await expect(manualNameInput).toHaveValue("Ironclad");
  await manualNameInput.fill("Discard this edit");
  await page
    .locator(".manual-name-form")
    .getByRole("button", { name: "Cancel", exact: true })
    .click();
  await expect(manualNameInput).toHaveCount(0);
  await page
    .getByRole("button", { name: "Edit item name", exact: true })
    .click();
  await manualNameInput.fill('My "keeper" shield');
  await page.getByRole("button", { name: "Save name", exact: true }).click();
  await waitForState(
    (state) =>
      state.families.find((f: any) => f.id === syncType.id).name ===
      'My "keeper" shield',
  );
  await expect(page.locator(".manual-name-form")).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: /My "keeper" shield/, level: 1 }),
  ).toBeVisible();
  await expect(
    page.locator(`.item-row[data-family-id="${syncType.id}"]`),
  ).toContainText('My "keeper" shield');
  await expect(page.locator(".inspector")).toContainText(
    "Your manual override (locked)",
  );
  await page.getByRole("button", { name: "Sync name", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Sync name", exact: true }),
  ).toBeEnabled();
  assert.deepEqual(
    await page.request.get("/__test/ai-count").then((r) => r.json()),
    nameCalls,
  );
  const manuallyNamed = await page.request
    .get(`/api/items/${syncType.id}`)
    .then((r) => r.json());
  assert.equal(manuallyNamed.family.nameOverride.origin, "manual");
  if (manuallyNamed.websiteOutput) {
    assert.equal(manuallyNamed.websiteOutput.name, 'My "keeper" shield');
    assert.equal(manuallyNamed.websiteOutput.slug, "my-keeper-shield");
  }
  await page.screenshot({ path: ".test-data/screenshots/manual-name.png" });
  assert.deepEqual(errors, []);
  console.log(
    "Browser: import, background selection, pause/resume, editor persistence, coverage, settings and fixed progress passed. 299 real capture candidates; character equipment grouped.",
  );
} finally {
  await browser.close();
  server.kill("SIGTERM");
  await new Promise((r) => server.once("exit", r));
  rmSync(dir, { recursive: true, force: true });
}
