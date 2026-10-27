import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync, readdirSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { readFileSync } from "node:fs";
import { evidenceLibrary } from "../src/server/saved-evidence.ts";
import { sharedChunkReading } from "../src/server/shared-source-index.ts";
import { emptySourceReading } from "./source-fixture.ts";
import { Store } from "../src/server/store.ts";
import { Worker } from "../src/server/worker.ts";
import { api } from "../src/server/http.ts";
import { evidenceParent } from "../src/shared/evidence-scopes.ts";
import type { Family } from "../src/shared/models.ts";
const url = "https://www.lootlemon.com/skill/brick-fixture",
  alias = url + "#notes";
const html =
  "<h1>Shared Brick skill</h1><p>Original synthetic skill content available to each class mod which boosts the same skill. This content must survive moving its owner.</p>";
function fixture(t: any) {
  const dir = mkdtempSync(path.join(tmpdir(), "promote-"));
  let s = new Store(dir);
  t.after(() => {
    s.close();
    rmSync(dir, { recursive: true, force: true });
  });
  const family = (
    id: string,
    category: Family["category"],
    character?: Family["character"],
  ): Family => ({
    id,
    name: id,
    category,
    subtype: category,
    character,
    aliases: [],
    roots: [],
    status: "done",
    stage: "complete",
    revision: 2,
    notes: "",
    sourceUrls: [],
    history: [],
    inputHash: "",
    issue: null,
    gameOnly: false,
    manualOutput: false,
    updatedAt: new Date().toISOString(),
  });
  s.state.families = [
    family("Bad Ass", "Class mods", "Brick"),
    family("Other Brick", "Class mods", "Brick"),
    family("Lilith mod", "Class mods", "Lilith"),
    family("Shield", "Shields"),
  ];
  s.save();
  const w = new Worker(s, {
    run: async () => {
      throw new Error("No agent call expected");
    },
  } as any);
  return {
    get s() {
      return s;
    },
    w,
    reopen() {
      s.close();
      s = new Store(dir);
      return s;
    },
  };
}
test("promotion moves one parent at a time, preserving content, output, exclusions and restart", (t) => {
  const x = fixture(t),
    { s, w } = x,
    [first, sibling, lilith, shield] = s.state.families;
  const page = w.research.save(first, url, html, true);
  s.put(first.id, "output", { unchanged: true });
  s.put(sibling.id, "sourceExclusions", [
    {
      sourceId: page.id,
      url,
      title: page.title,
      excludedAt: new Date().toISOString(),
    },
  ]);
  const files = readdirSync(path.join(s.dir, "sources"));
  const result = w.promoteSource(first.id, alias);
  assert.deepEqual(result.scope, {
    category: "Class mods",
    character: "Brick",
  });
  const brick = s.ensureScope(result.scope);
  assert.equal(first.sourceUrls.length, 0);
  assert.equal(s.rawSources(first.id).length, 0);
  assert.equal(s.sources(first.id)[0].id, page.id);
  assert.equal(s.sources(first.id)[0].text, page.text);
  assert.equal(s.sources(first.id)[0].inheritedFrom?.id, brick.id);
  assert.equal(s.sources(sibling.id).length, 0);
  assert.equal(s.sources(lilith.id).length, 0);
  assert.equal(s.sources(shield.id).length, 0);
  assert.deepEqual(s.get(first.id, "output"), { unchanged: true });
  const parentResult = w.promoteSource(brick.id, url);
  assert.deepEqual(parentResult.scope, { category: "Class mods" });
  assert.equal(brick.sourceUrls.length, 0);
  assert.equal(s.sources(brick.id).length, 0);
  assert.equal(s.sources(lilith.id).length, 1);
  assert.equal(s.sources(shield.id).length, 0);
  const category = s.ensureScope(parentResult.scope);
  w.promoteSource(category.id, url);
  assert.equal(s.sources(shield.id).length, 1);
  const everything = s.ensureScope({ category: "Everything" });
  assert.throws(() => w.promoteSource(everything.id, url), /no parent/);
  assert.deepEqual(readdirSync(path.join(s.dir, "sources")), files);
  const reopened = x.reopen();
  assert.equal(reopened.sources(first.id)[0].id, page.id);
  assert.equal(reopened.sources(shield.id)[0].text, page.text);
  assert.equal(reopened.sources(sibling.id).length, 0);
});
test("borrowed pages and pending links deduplicate in their immediate parent without taking another item's capture", (t) => {
  const { s, w } = fixture(t),
    [first, sibling, lilith] = s.state.families;
  const page = w.research.save(lilith, url, html, true);
  first.sourceUrls = [alias];
  sibling.sourceUrls = [url];
  w.promoteSource(first.id, alias);
  w.promoteSource(sibling.id, url);
  const brick = s.ensureScope({ category: "Class mods", character: "Brick" });
  assert.equal(brick.sourceUrls.length, 1);
  assert.equal(s.rawSources(lilith.id)[0].id, page.id);
  assert.equal(s.sources(first.id)[0].id, page.id);
  assert.throws(() => w.promoteSource(first.id, url), /directly attached/);
  const pending = "https://borderlands.fandom.com/wiki/Pending";
  first.sourceUrls.push(pending);
  w.promoteSource(first.id, pending);
  assert(
    s
      .inheritedEvidence(first)
      .some((row) => row.url === pending && !row.captured),
  );
});
test("evidence edits and promotions never append to live or paused queues or alter saved build checkpoints", async (t) => {
  const { s, w } = fixture(t),
    [first, , , shield] = s.state.families;
  const page = w.research.save(first, url, html, true);
  Object.assign(s.state.run, {
    status: "paused",
    queue: [shield.id],
    index: 0,
    currentId: null,
  });
  s.state.buildCheckpoint = structuredClone(s.state.run);
  const before = structuredClone(s.state.run),
    checkpoint = structuredClone(s.state.buildCheckpoint);
  w.promoteSource(first.id, url);
  const group = s.ensureScope({ category: "Class mods", character: "Brick" });
  w.sharedArticleChanged(group, url);
  await w.action(first.id, "exclude-source", { sourceId: page.id });
  await w.action(first.id, "restore-source", { sourceId: page.id });
  assert.deepEqual(s.state.run, before);
  assert.deepEqual(s.state.buildCheckpoint, checkpoint);
  assert.equal(w.busy, false);
});
test("promotion rejects active affected items, invalid URLs, unrelated references and top-level owners", async (t) => {
  const { s, w } = fixture(t),
    [first, sibling] = s.state.families;
  w.research.save(first, url, html, true);
  const count = s.state.sharedScopes!.length;
  w.busy = true;
  s.state.run.currentId = sibling.id;
  assert.throws(() => w.promoteSource(first.id, url), /Pause processing/);
  assert.equal(s.state.sharedScopes!.length, count);
  assert.equal(first.sourceUrls.length, 1);
  w.busy = false;
  assert.throws(
    () => w.promoteSource(first.id, "https://example.com/a"),
    /Unsupported|Only|source/i,
  );
  assert.throws(() => w.promoteSource(sibling.id, url), /directly attached/);
  const server = api(s, w).listen(0, "127.0.0.1");
  await new Promise<void>((r) => server.once("listening", r));
  t.after(() => {
    server.closeAllConnections();
    server.close();
  });
  const base = `http://127.0.0.1:${(server.address() as any).port}`;
  const response = await fetch(base + "/api/evidence/promote", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ownerId: first.id, url }),
  });
  assert.equal(response.status, 200);
  assert.deepEqual((await response.json()).scope, {
    category: "Class mods",
    character: "Brick",
  });
  const invalid = await fetch(base + "/api/evidence/promote", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ownerId: sibling.id,
      url: "https://example.com/no",
    }),
  });
  assert.equal(invalid.status, 400);
});
test("parent hierarchy follows weapon types, character equipment, categories and Everything", (t) => {
  const { s } = fixture(t),
    first = s.state.families[0];
  assert.deepEqual(evidenceParent(first), {
    category: "Class mods",
    character: "Brick",
  });
  assert.deepEqual(
    evidenceParent({
      ...first,
      category: "Weapons",
      subtype: "SMGs",
      character: undefined,
    }),
    { category: "Weapons", group: "SMGs" },
  );
  assert.deepEqual(
    evidenceParent(s.ensureScope({ category: "Weapons", group: "SMGs" })),
    { category: "Weapons" },
  );
  assert.deepEqual(evidenceParent(s.ensureScope({ category: "Shields" })), {
    category: "Everything",
  });
  assert.equal(evidenceParent(s.ensureScope({ category: "Everything" })), null);
});

test("manual text promotes through character/category/Everything with exact content, scope isolation and preferences intact", async (t) => {
  const x = fixture(t),
    { s, w } = x,
    [first, sibling, lilith, shield] = s.state.families;
  const text =
    "Brick's Berserk punches gain an elemental effect.\n\nOnly these compiled facts should be shared; the full pages are not included.";
  const source = w.addTextEvidence(first.id, {
    label: "My compiled Brick facts",
    text,
  });
  s.put(first.id, "output", { retained: "Player wording" });
  const run = structuredClone(s.state.run);
  const file = readFileSync(
    path.join(s.dir, "sources", source.filename),
    "utf8",
  );
  const firstMove = w.promoteSource(first.id, source.url);
  assert.deepEqual(firstMove.scope, {
    category: "Class mods",
    character: "Brick",
  });
  const brick = s.ensureScope(firstMove.scope);
  assert.equal(
    s.rawSources(first.id).some((row) => row.id === source.id),
    false,
  );
  assert.equal(
    s.sources(sibling.id).find((row) => row.id === source.id)?.text,
    text,
  );
  assert(evidenceLibrary(s, sibling).some((row) => row.id === source.id));
  assert(!evidenceLibrary(s, lilith).some((row) => row.id === source.id));
  assert.equal(
    s.inheritedEvidence(first).find((row) => row.url === source.url)?.title,
    source.title,
  );
  w.setSharedSourceMode(sibling.id, source.url, "never");
  let indexCalls = 0;
  const ai: any = {
    run: async (_label: string, prompt: string, schema: any) => {
      indexCalls++;
      assert(prompt.includes(text));
      assert(!prompt.includes("My compiled Brick facts"));
      return schema.parse({ ...emptySourceReading("Class mods"), facts: [] });
    },
  };
  const page = s.sources(first.id).find((row) => row.id === source.id)!;
  await sharedChunkReading(s, ai, page, text, () => {});
  const categoryMove = w.promoteSource(brick.id, source.url);
  assert.deepEqual(categoryMove.scope, { category: "Class mods" });
  assert(s.sources(lilith.id).some((row) => row.id === source.id));
  assert(!s.sources(shield.id).some((row) => row.id === source.id));
  assert(!s.sources(sibling.id).some((row) => row.id === source.id));
  const category = s.ensureScope(categoryMove.scope);
  const everythingMove = w.promoteSource(category.id, source.url);
  assert.deepEqual(everythingMove.scope, { category: "Everything" });
  assert(s.sources(shield.id).some((row) => row.id === source.id));
  assert(evidenceLibrary(s, shield).some((row) => row.id === source.id));
  assert(!evidenceLibrary(s, sibling).some((row) => row.id === source.id));
  const cached = await sharedChunkReading(
    s,
    ai,
    s.sources(shield.id).find((row) => row.id === source.id)!,
    text,
    () => {},
  );
  assert.equal(cached?.cached, true);
  assert.equal(indexCalls, 1);
  assert.throws(
    () => w.promoteSource(s.ensureScope(everythingMove.scope).id, source.url),
    /Everything has no parent/,
  );
  assert.throws(
    () =>
      w.promoteSource(
        first.id,
        "https://manual.borderlens.invalid/evidence/spoof",
      ),
    /saved manual entry/,
  );
  assert.equal(
    readFileSync(path.join(s.dir, "sources", source.filename), "utf8"),
    file,
  );
  assert.deepEqual(s.get(first.id, "output"), { retained: "Player wording" });
  assert.deepEqual(s.state.run, run);
  const reopened = x.reopen();
  assert(
    reopened
      .sources(shield.id)
      .some(
        (row) => row.id === source.id && row.manualText && row.text === text,
      ),
  );
});

test("shared manual removal/restore uses only an existing scope-owned entry and never fetches or starts work", async (t) => {
  const { s, w } = fixture(t),
    first = s.state.families[0];
  const source = w.addTextEvidence(first.id, {
    label: "Brick excerpt",
    text: "The chosen Brick excerpt remains exactly the selected passage.",
  });
  const promoted = w.promoteSource(first.id, source.url);
  const server = api(s, w).listen(0, "127.0.0.1");
  await new Promise<void>((r) => server.once("listening", r));
  t.after(() => {
    server.closeAllConnections();
    server.close();
  });
  const base = `http://127.0.0.1:${(server.address() as any).port}`;
  const post = (body: unknown) =>
    fetch(base + "/api/shared-sources", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  const run = structuredClone(s.state.run);
  assert.equal(
    (await post({ scope: promoted.scope, url: source.url, remove: true }))
      .status,
    200,
  );
  assert(!s.sources(first.id).some((row) => row.id === source.id));
  assert.equal(
    (await post({ scope: promoted.scope, url: source.url })).status,
    200,
  );
  assert(s.sources(first.id).some((row) => row.id === source.id));
  assert.equal(
    (await post({ scope: { category: "Everything" }, url: source.url })).status,
    400,
  );
  assert.equal(
    (
      await post({
        scope: promoted.scope,
        url: source.url,
        html: "<p>Replace it</p>",
      })
    ).status,
    400,
  );
  assert.deepEqual(s.state.run, run);
});
