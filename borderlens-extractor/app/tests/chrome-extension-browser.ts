// Runs a real MV3 extension against an isolated workshop and synthetic wiki page.
// The temporary test copy grants the fixture host so automated popup navigation
// doesn't need a physical toolbar gesture. Shipped manifest uses activeTab only.
import { chromium, expect } from "@playwright/test";
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
manifest.host_permissions.push(
  "https://borderlands.fandom.com/*",
  "https://www.lootlemon.com/*",
);
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
      body: '<!doctype html><html><head><title>Hellfire – fixture only</title><style>body{padding:40px;min-height:1600px;font:18px/1.6 system-ui}.mw-parser-output{width:650px}p{margin:25px 0}table{border-collapse:collapse;margin-top:40px;width:500px}td,th{border:1px solid;padding:12px}</style></head><body><h1 id="firstHeading">Hellfire</h1><div class="mw-parser-output"><h2>Unique ability</h2><p id="wanted">This synthetic wiki article exists only to verify browser capture. It is not real game evidence.</p><table><thead><tr><th>Field</th><th>Value</th></tr></thead><tbody><tr><td>Fixture field</td><td>Fixture value</td></tr></tbody></table><p id="unwanted">Unselected boilerplate must never reach the saved source.</p><form><input value="private-test-secret"></form><script>globalThis.fixtureScript=true</script></div></body></html>',
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
  const sourceUrlInput = app.getByRole("textbox", {
    name: "Source page URL",
    exact: true,
  });
  const captureLink = app.getByRole("button", {
    name: "Open URL in Chrome for capture",
    exact: true,
  });
  await sourceUrlInput.fill("");
  await expect(captureLink).toBeVisible();
  await expect(captureLink).toBeDisabled();
  await sourceUrlInput.fill(url);
  await expect(captureLink).toBeEnabled();
  const articlePromise = context.waitForEvent("page");
  await captureLink.click();
  const article = await articlePromise;
  // Chrome-created tabs can issue their first navigation before Playwright attaches.
  // Repeat navigation under the installed route to serve the local article fixture.
  await article.goto(url);
  await article.locator(".mw-parser-output").waitFor();
  const popup = await context.newPage();
  await popup.goto(`chrome-extension://${id}/popup.html`);
  await expect(
    popup.getByRole("button", {
      name: "Send selections to Borderlens",
      exact: true,
    }),
  ).toBeDisabled();
  await popup
    .getByRole("button", { name: "Select content on page", exact: true })
    .click();
  await article.bringToFront();
  const panel = article
    .locator("#borderlens-selection-overlay")
    .getByRole("region", { name: "Borderlens content selection" });
  await expect(panel).toBeVisible();
  const sendSelection = panel.getByRole("button", {
    name: "Send to Borderlens",
    exact: true,
  });
  await expect(sendSelection).toBeDisabled();
  const draw = async (
    r: { x: number; y: number; width: number; height: number },
    fraction = 1,
    releaseControlFirst = false,
  ) => {
    await article.keyboard.down("Control");
    await article.mouse.move(r.x - 3, r.y - 3);
    await article.mouse.down();
    await article.mouse.move(r.x + r.width * fraction + 3, r.y + r.height + 3, {
      steps: 6,
    });
    if (releaseControlFirst) await article.keyboard.up("Control");
    await article.mouse.up();
    if (!releaseControlFirst) await article.keyboard.up("Control");
  };
  const boxes = article.locator("#borderlens-selection-overlay .box");
  // Form fields are excluded even if a box covers them.
  await draw(
    (await article.locator("input[value=private-test-secret]").boundingBox())!,
  );
  await expect(boxes.first()).toHaveClass(/bad/);
  await panel.locator("#partial input").check();
  await expect(sendSelection).toBeDisabled();
  await boxes
    .first()
    .getByRole("button", { name: "Remove selection", exact: true })
    .click();
  await expect(boxes).toHaveCount(0);
  const wanted = (await article.locator("#wanted").boundingBox())!;
  await draw(wanted, 0.5);
  await expect(boxes).toHaveCount(1);
  await expect(boxes.first()).toHaveClass(/bad/);
  await expect(sendSelection).toBeDisabled();
  mkdirSync(".test-data/screenshots", { recursive: true });
  await article.screenshot({
    path: ".test-data/screenshots/chrome-partial-selection.png",
  });
  await panel.locator("#partial input").check();
  await expect(sendSelection).toBeEnabled();
  await panel.locator("#partial input").uncheck();
  // Resize the first box to the complete paragraph.
  const handle = (await boxes.first().locator(".se").boundingBox())!;
  await article.mouse.move(handle.x + 5, handle.y + 5);
  await article.mouse.down();
  await article.mouse.move(
    wanted.x + wanted.width + 4,
    wanted.y + wanted.height + 4,
    { steps: 5 },
  );
  await article.mouse.up();
  await expect(boxes.first()).not.toHaveClass(/bad/);
  await expect(sendSelection).toBeEnabled();
  await expect(panel.locator("#partial")).toBeHidden();
  const shiftBox = async (dx: number) => {
    const label = (await boxes.first().locator(".caption").boundingBox())!;
    await article.mouse.move(
      label.x + label.width / 2,
      label.y + label.height / 2,
    );
    await article.mouse.down();
    await article.mouse.move(
      label.x + label.width / 2 + dx,
      label.y + label.height / 2,
      { steps: 4 },
    );
    await article.mouse.up();
  };
  const beforeMove = (await boxes.first().boundingBox())!;
  await shiftBox(20);
  assert.equal(
    Math.round((await boxes.first().boundingBox())!.x),
    Math.round(beforeMove.x + 20),
  );
  await shiftBox(-20);
  await expect(boxes.first()).not.toHaveClass(/bad/);
  const table = (await article
    .locator(".mw-parser-output table")
    .boundingBox())!;
  await draw(table, 0.5);
  await expect(boxes.nth(1)).toHaveClass(/bad/);
  await expect(panel.locator("#hint")).toContainText("partial");
  await boxes
    .nth(1)
    .getByRole("button", { name: "Fit content", exact: true })
    .click();
  await expect(boxes.nth(1)).not.toHaveClass(/bad/);
  await draw(wanted, 1, true);
  await expect(boxes).toHaveCount(3);
  assert.equal(
    (await panel.locator("#preview").textContent())!.split(
      "synthetic wiki article",
    ).length - 1,
    1,
  );
  await boxes
    .nth(2)
    .getByRole("button", { name: "Remove selection", exact: true })
    .click();
  await expect(boxes).toHaveCount(2);
  // Boxes stay anchored in document space after scrolling.
  const beforeScroll = (await boxes.first().boundingBox())!;
  await article.evaluate(() => window.scrollBy(0, 80));
  await expect
    .poll(async () => Math.round((await boxes.first().boundingBox())!.y))
    .toBe(Math.round(beforeScroll.y - 80));
  await article.evaluate(() => window.scrollTo(0, 0));
  await panel.locator("summary").click();
  mkdirSync(".test-data/screenshots", { recursive: true });
  await article.screenshot({
    path: ".test-data/screenshots/chrome-selected-boxes.png",
  });
  await sendSelection.click();
  await expect(
    panel.getByRole("button", { name: "Saved to Borderlens", exact: true }),
  ).toBeDisabled();
  await app.getByText("Wiki · 1 saved", { exact: true }).waitFor();
  const detail = await app.request
    .get("http://127.0.0.1:4321/api/items/" + family.id)
    .then((r) => r.json());
  assert.equal(detail.sources[0].captureMethod, "chrome");
  assert.match(detail.sources[0].text, /synthetic wiki article/);
  assert.ok(detail.sources[0].tables.length);
  assert.deepEqual(detail.sources[0].selectedContent, {
    boxes: 2,
    warnings: 0,
  });
  assert.ok(!detail.sources[0].text.includes("Unselected boilerplate"));
  await expect(
    app.locator(".source-card .selected-content-badge"),
  ).toContainText("Selected page content");
  assert.equal(detail.sources[0].tables[0].rows[1][1], "Fixture value");
  assert.ok(!detail.sources[0].text.includes("private-test-secret"));
  assert.ok(!detail.sources[0].text.includes("fixtureScript"));
  // Return with the default preference keeps the article and anchors its evidence.
  const closeAfter = panel.getByRole("checkbox", {
    name: "Close source tab when returning after capture",
  });
  await expect(closeAfter).toBeEnabled();
  await expect(closeAfter).not.toBeChecked();
  await app.getByRole("button", { name: "Preview", exact: true }).click();
  await panel
    .getByRole("button", { name: "Back to workshop", exact: true })
    .click();
  await expect(app.locator(".tabs > button.active")).toContainText(
    "Sources & evidence",
  );
  await expect(
    app.locator(".source-card.source-return-highlight"),
  ).toBeInViewport();
  assert.equal(article.isClosed(), false);
  await closeAfter.check();
  await expect
    .poll(
      async () =>
        await worker.evaluate(
          async () =>
            (
              await (globalThis as any).chrome.storage.local.get(
                "closeSourceTab",
              )
            ).closeSourceTab,
        ),
    )
    .toBe(true);
  const runBeforeRecapture = (
    await app.request
      .get("http://127.0.0.1:4321/api/state")
      .then((r) => r.json())
  ).run;
  const callsBeforeRecapture = await app.request
    .get("http://127.0.0.1:4321/__test/ai-count")
    .then((r) => r.json());
  const recaptureAndSend = async (button: any, shared = false) => {
    const nextPage = context.waitForEvent("page");
    await button.click();
    const nextArticle = await nextPage;
    await nextArticle.goto(url);
    assert.equal(nextArticle.url(), url);
    const helper = await context.newPage();
    await helper.goto(`chrome-extension://${id}/popup.html`);
    await expect(
      helper.getByRole("checkbox", {
        name: "Close source tab when returning after capture",
      }),
    ).toBeChecked();
    await helper
      .getByRole("button", { name: "Select content on page", exact: true })
      .click();
    await nextArticle.bringToFront();
    const selectionPanel = nextArticle.locator(
      "#borderlens-selection-overlay .panel",
    );
    const text = (await nextArticle.locator("#wanted").boundingBox())!;
    await nextArticle.keyboard.down("Control");
    await nextArticle.mouse.move(text.x - 3, text.y - 3);
    await nextArticle.mouse.down();
    await nextArticle.mouse.move(
      text.x + text.width + 3,
      text.y + text.height + 3,
      { steps: 5 },
    );
    await nextArticle.mouse.up();
    await nextArticle.keyboard.up("Control");
    await selectionPanel
      .getByRole("button", { name: "Send to Borderlens", exact: true })
      .click();
    await expect(
      selectionPanel.getByRole("button", {
        name: "Saved to Borderlens",
        exact: true,
      }),
    ).toBeDisabled();
    await expect(
      selectionPanel.getByRole("checkbox", {
        name: "Close source tab when returning after capture",
      }),
    ).toBeChecked();
    await app.getByRole("button", { name: "Preview", exact: true }).click();
    const closed = nextArticle.waitForEvent("close");
    await selectionPanel
      .getByRole("button", { name: "Back to workshop", exact: true })
      .click();
    await closed;
    await expect(app.locator(".tabs > button.active")).toContainText(
      "Sources & evidence",
    );
    const anchor = shared
      ? app.locator(".shared-source-modal .source-return-highlight")
      : app.locator(".source-card.source-return-highlight");
    await expect(anchor).toBeInViewport();
  };
  const recapture = app
    .locator(".source-card")
    .getByRole("button", { name: "Recapture: Hellfire", exact: true });
  await expect(recapture).toBeVisible();
  await recaptureAndSend(recapture);
  const replaced = await app.request
    .get(`http://127.0.0.1:4321/api/items/${family.id}`)
    .then((r) => r.json());
  assert.equal(replaced.sources.length, 1);
  assert.notEqual(replaced.sources[0].id, detail.sources[0].id);
  assert.deepEqual(replaced.sources[0].selectedContent, {
    boxes: 1,
    warnings: 0,
  });
  assert.equal(replaced.sources[0].tables.length, 0);
  assert.ok(!replaced.sources[0].text.includes("Fixture value"));
  await app.request.post(
    `http://127.0.0.1:4321/api/items/${family.id}/text-evidence`,
    {
      data: {
        label: "Manual recapture fixture",
        text: "Manually selected useful facts.",
      },
    },
  );
  const manual = app
    .locator(".source-card")
    .filter({ hasText: "Manual recapture fixture" });
  await expect(manual).toBeVisible();
  await expect(manual.getByRole("button", { name: /Recapture:/ })).toHaveCount(
    0,
  );
  await app.request.post("http://127.0.0.1:4321/api/evidence/promote", {
    data: { ownerId: family.id, url },
  });
  const inherited = app
    .locator(".inherited-evidence-row")
    .filter({ hasText: "Hellfire" });
  await expect(inherited).toBeVisible();
  await recaptureAndSend(
    inherited.getByRole("button", { name: "Recapture: Hellfire", exact: true }),
    true,
  );
  const groups = await app.request
    .get("http://127.0.0.1:4321/api/shared-sources")
    .then((r) => r.json());
  const owner = groups.find((g: any) => g.family.sourceUrls.includes(url));
  assert.ok(owner);
  assert.equal(owner.sources.length, 1);
  assert.equal(owner.sources[0].familyId, owner.family.id);
  assert.deepEqual(owner.sources[0].selectedContent, { boxes: 1, warnings: 0 });
  assert.deepEqual(
    (
      await app.request
        .get("http://127.0.0.1:4321/api/state")
        .then((r) => r.json())
    ).run,
    runBeforeRecapture,
  );
  assert.deepEqual(
    await app.request
      .get("http://127.0.0.1:4321/__test/ai-count")
      .then((r) => r.json()),
    callsBeforeRecapture,
  );
  await app
    .getByRole("button", { name: "Close shared evidence", exact: true })
    .click();
  // The same persistent setting must not close a newly opened, unsent article.
  const pendingPage = context.waitForEvent("page");
  await inherited
    .getByRole("button", { name: "Recapture: Hellfire", exact: true })
    .click();
  const unsent = await pendingPage;
  await unsent.goto(url);
  const pendingPopup = await context.newPage();
  await pendingPopup.goto(`chrome-extension://${id}/popup.html`);
  await expect(
    pendingPopup.getByRole("checkbox", {
      name: "Close source tab when returning after capture",
    }),
  ).toBeChecked();
  await pendingPopup
    .getByRole("button", { name: "Back to workshop", exact: true })
    .click();
  await expect(
    app.locator(".shared-source-modal .source-return-highlight"),
  ).toBeInViewport();
  assert.equal(unsent.isClosed(), false);
  await app
    .getByRole("button", { name: "Close shared evidence", exact: true })
    .click();

  // Whole-page capture from the on-page panel requires no boxes and replaces an excerpt.
  const fullWikiPopup = await context.newPage();
  await fullWikiPopup.goto(`chrome-extension://${id}/popup.html`);
  await expect(
    fullWikiPopup.getByRole("button", {
      name: "Capture whole page",
      exact: true,
    }),
  ).toBeEnabled();
  await fullWikiPopup
    .getByRole("button", { name: "Select content on page", exact: true })
    .click();
  const wholePanel = unsent.locator("#borderlens-selection-overlay .panel");
  await expect(wholePanel.locator("#count")).toContainText("Saved 0 boxes");
  await wholePanel
    .getByRole("button", { name: "Capture whole page", exact: true })
    .click();
  await expect(
    wholePanel.getByRole("button", { name: "Whole page saved", exact: true }),
  ).toBeDisabled();
  const fullGroups = await app.request
    .get("http://127.0.0.1:4321/api/shared-sources")
    .then((r) => r.json());
  const fullWiki = fullGroups.find((g: any) => g.family.id === owner.family.id)
    .sources[0];
  assert.equal(fullWiki.selectedContent, undefined);
  assert.match(fullWiki.text, /Unselected boilerplate/);
  assert.ok(fullWiki.tables.length);
  assert.ok(!fullWiki.text.includes("Borderlens · Select content"));
  assert.ok(!fullWiki.text.includes("private-test-secret"));
  assert.ok(!fullWiki.text.includes("fixtureScript"));
  const wikiClosed = unsent.waitForEvent("close");
  await wholePanel
    .getByRole("button", { name: "Back to workshop", exact: true })
    .click();
  await wikiClosed;
  await app
    .getByRole("button", { name: "Close shared evidence", exact: true })
    .click();

  // Lootlemon can use a Webflow body without a main/article element. Include loaded hidden tabs, not forms/scripts.
  const lootUrl = "https://www.lootlemon.com/weapon/fixture-bl1";
  await context.route("https://www.lootlemon.com/**", (route) =>
    route.fulfill({
      contentType: "text/html",
      body: '<html><head><title>Lootlemon fixture</title></head><body><nav>Navigation junk</nav><div><h1>Lootlemon fixture</h1><p>The entire loaded item description is useful for this synthetic whole-page capture test.</p><section hidden><h2>Hidden loaded stats</h2><table><tr><th>Stat</th><th>Value</th></tr><tr><td>Damage</td><td>42</td></tr></table></section><p>Additional drop details outside the first text block remain available.</p></div><form><input value="loot-secret"></form><script>globalThis.lootScript=true</script></body></html>',
    }),
  );
  await sourceUrlInput.fill(lootUrl);
  const lootOpened = context.waitForEvent("page");
  await captureLink.click();
  const loot = await lootOpened;
  await loot.goto(lootUrl);
  const lootPopup = await context.newPage();
  await lootPopup.goto(`chrome-extension://${id}/popup.html`);
  await expect(
    lootPopup.getByRole("button", {
      name: "Send selections to Borderlens",
      exact: true,
    }),
  ).toBeDisabled();
  await expect(
    lootPopup.getByRole("button", {
      name: "Select content on page",
      exact: true,
    }),
  ).toBeVisible();
  await lootPopup.screenshot({
    path: ".test-data/screenshots/chrome-whole-page-option.png",
  });
  await lootPopup
    .getByRole("button", { name: "Capture whole page", exact: true })
    .click();
  await expect(lootPopup.locator("#title")).toHaveText("Whole page saved");
  const lootDetail = await app.request
    .get(`http://127.0.0.1:4321/api/items/${family.id}`)
    .then((r) => r.json());
  const lootSource = lootDetail.sources.find((s: any) => s.url === lootUrl);
  assert.equal(lootSource.captureMethod, "chrome");
  assert.equal(lootSource.selectedContent, undefined);
  assert.match(lootSource.text, /Additional drop details/);
  assert.match(lootSource.text, /Hidden loaded stats/);
  assert.equal(lootSource.tables[0].rows[1][1], "42");
  assert.ok(!/loot-secret|lootScript|Navigation junk/.test(lootSource.text));
  const lootClosed = loot.waitForEvent("close");
  await lootPopup
    .getByRole("button", { name: "Back to workshop", exact: true })
    .click();
  await lootClosed;
  await expect(app.locator(".tabs > button.active")).toContainText(
    "Sources & evidence",
  );
  assert.deepEqual(
    (
      await app.request
        .get("http://127.0.0.1:4321/api/state")
        .then((r) => r.json())
    ).run,
    runBeforeRecapture,
  );
  assert.deepEqual(
    await app.request
      .get("http://127.0.0.1:4321/__test/ai-count")
      .then((r) => r.json()),
    callsBeforeRecapture,
  );
  const returns = await worker.evaluate(
    async () =>
      (await (globalThis as any).chrome.storage.session.get("jobs")).jobs,
  );
  assert.ok(
    Object.values(returns)
      .filter((row: any) => row.completed)
      .every((row: any) => !row.token),
  );
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
    "MV3 Chrome fixture: automatic connection, open article, Ctrl selection, resize, table fit, overlap deduplication, scroll anchoring, local relay, cached HTML/tables and live saved status passed.",
  );
} finally {
  await context.close();
  server.kill("SIGTERM");
  await new Promise((r) => server.once("exit", r));
  rmSync(dir, { recursive: true, force: true });
}
