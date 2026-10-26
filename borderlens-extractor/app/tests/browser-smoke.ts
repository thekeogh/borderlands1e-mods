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
  const native = gameView
    .locator(".game-data-panel")
    .filter({
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
