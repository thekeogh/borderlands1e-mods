import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { Store, hash } from "../src/server/store.ts";
import { Worker } from "../src/server/worker.ts";
import { api } from "../src/server/http.ts";
import { buildPacket } from "../src/server/evidence.ts";
import {
  readSources,
  sourceWritingPacket,
} from "../src/server/source-analysis.ts";
import { evidenceLibrary } from "../src/server/saved-evidence.ts";
import { savedSourceCache } from "../src/server/source-cache.ts";
import { cleanPublicEntry } from "../src/shared/public-cleanup.ts";
import type { Family } from "../src/shared/models.ts";
import { emptySourceReading } from "./source-fixture.ts";
function fixture(t: any) {
  const dir = mkdtempSync(path.join(tmpdir(), "manual-evidence-"));
  let s = new Store(dir);
  const family = (id: string): Family => ({
    id,
    name: id,
    category: "Artifacts",
    subtype: "Artifacts",
    character: "Brick",
    element: "Corrosive",
    aliases: [],
    roots: [],
    sourceUrls: [],
    history: [],
    revision: 0,
    status: "queued",
    stage: "draft",
    inputHash: "",
    issue: null,
    notes: "",
    gameOnly: false,
    manualOutput: false,
    updatedAt: new Date().toISOString(),
  });
  s.state.families = [family("one"), family("two")];
  Object.assign(s.state.run, {
    status: "paused",
    queue: ["two"],
    currentId: null,
    index: 0,
  });
  s.state.buildCheckpoint = structuredClone(s.state.run);
  s.save();
  t.after(() => {
    s.close();
    rmSync(dir, { recursive: true, force: true });
  });
  return {
    get s() {
      return s;
    },
    dir,
    reopen() {
      s.close();
      s = new Store(dir);
      return s;
    },
  };
}
const excerpt =
  'Corrosive punches have an elemental effect.\n\nDamage bonus: +25%.\nLiteral <b>text</b> & "quotes" stay exactly as pasted.';

test("manual evidence API preserves selected plain text, private label, output and queue without calls or cross-item reuse", async (t) => {
  const { s, dir } = fixture(t),
    f = s.family("one");
  const w = new Worker(s, {
    run: async () => {
      throw Error("Unexpected AI call");
    },
  } as any);
  s.put(f.id, "output", { name: "one", summary: "Retained prose" });
  const run = structuredClone(s.state.run),
    checkpoint = structuredClone(s.state.buildCheckpoint);
  const server = api(s, w).listen(0, "127.0.0.1");
  await new Promise<void>((r) => server.once("listening", r));
  t.after(() => {
    server.closeAllConnections();
    server.close();
  });
  const base = `http://127.0.0.1:${(server.address() as any).port}`;
  const post = (body: unknown) =>
    fetch(`${base}/api/items/${f.id}/text-evidence`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  for (const body of [
    { text: " " },
    { text: "x", label: "x".repeat(161) },
    { text: "x".repeat(100001) },
    { text: "x", url: "https://example.com" },
  ])
    assert.equal((await post(body)).status, 400);
  const response = await post({
    text: "  " + excerpt + "  ",
    label: " My copied passage ",
  });
  assert.equal(response.status, 201);
  const { source } = await response.json();
  assert.equal(source.text, excerpt);
  assert.equal(source.title, "My copied passage");
  assert.equal(source.manualText, true);
  assert.equal(source.hash, hash(excerpt));
  assert.equal(
    readFileSync(path.join(dir, "sources", source.filename), "utf8"),
    excerpt,
  );
  assert.equal(s.sources(f.id)[0].text, excerpt);
  assert.equal(s.sources("two").length, 0);
  assert.equal(evidenceLibrary(s, s.family("two")).length, 0);
  assert.equal(evidenceLibrary(s, f).length, 1);
  assert.equal(s.effectiveSourceUrls(f).length, 0);
  assert.equal(f.sourceUrls.length, 0);
  assert(savedSourceCache(s, f).available);
  assert.deepEqual(s.get(f.id, "output"), {
    name: "one",
    summary: "Retained prose",
  });
  assert.deepEqual(s.state.run, run);
  assert.deepEqual(s.state.buildCheckpoint, checkpoint);
  const packet = buildPacket(s, f);
  const row = packet.evidence.find((e) => e.id === source.id)!;
  assert.equal(row.label, "Pasted text evidence");
  assert.equal((row.value as any).text, excerpt);
  await assert.rejects(
    w.research.fetchPage(f, source.url, true),
    /local and cannot be fetched/,
  );
});

test("pasted excerpts use the source-reading/fact/telemetry path and local identifiers stay out of public acquisition URLs", async (t) => {
  const { s } = fixture(t),
    f = s.family("one"),
    w = new Worker(s, {} as any);
  const source = w.addTextEvidence(f.id, {
    label: "A private label, not a fact",
    text: excerpt,
  });
  let count = 0;
  const ai: any = {
    run: async (
      _label: string,
      prompt: string,
      schema: any,
      _model: any,
      _search: any,
      _progress: any,
      input: any,
    ) => {
      count++;
      assert(prompt.includes(excerpt));
      assert(!prompt.includes(source.title));
      assert.equal(input.sources[0].id, source.id);
      return schema.parse({
        ...emptySourceReading("Artifacts"),
        facts: [
          {
            field: "details",
            detail: "Corrosive punches have an elemental effect.",
            quote: "Corrosive punches have an elemental effect.",
            stat: null,
          },
        ],
      });
    },
  };
  const ledger = await readSources(s, ai, f, () => {});
  assert.equal(count, 1);
  const actual = sourceWritingPacket(buildPacket(s, f), ledger);
  assert.equal(actual[0].sourceId, source.id);
  assert.equal(
    actual[0].chunks[0].facts[0].quote,
    "Corrosive punches have an elemental effect.",
  );
  const cleaned = cleanPublicEntry({
    sources: [{ label: "Mission reward", url: source.url }],
    stats: [],
  } as any);
  assert.equal(cleaned.sources[0].url, null);
  assert.equal(cleaned.sources[0].label, "Mission reward");
});

test("manual text survives remove/restore, website refresh, restart and generated reset; guards block active/shared/removed items", async (t) => {
  const x = fixture(t),
    { s } = x,
    w = new Worker(s, {} as any),
    f = s.family("one");
  const source = w.addTextEvidence(f.id, { text: excerpt });
  assert.equal(source.title, "Pasted text");
  w.busy = true;
  s.state.run.currentId = f.id;
  assert.throws(
    () => w.addTextEvidence(f.id, { text: "new" }),
    /Pause processing/,
  );
  w.busy = false;
  s.state.run.currentId = null;
  const owner = s.ensureScope({ category: "Artifacts" });
  assert.throws(
    () => w.addTextEvidence(owner.id, { text: "new" }),
    /individual item/,
  );
  f.status = "excluded";
  assert.throws(() => w.addTextEvidence(f.id, { text: "new" }), /Restore/);
  f.status = "queued";
  await w.action(f.id, "exclude-source", { sourceId: source.id });
  assert.equal(s.sources(f.id).length, 0);
  await w.action(f.id, "restore-source", { sourceId: source.id });
  assert.equal(s.sources(f.id)[0].text, excerpt);
  assert.equal(s.effectiveSourceUrls(f).length, 0);
  await w.action(f.id, "refresh", {});
  assert.equal(s.sources(f.id)[0].text, excerpt);
  const reopened = x.reopen();
  assert.equal(reopened.sources(f.id)[0].text, excerpt);
  const server = api(reopened, new Worker(reopened, {} as any)).listen(
    0,
    "127.0.0.1",
  );
  await new Promise<void>((r) => server.once("listening", r));
  t.after(() => {
    server.closeAllConnections();
    server.close();
  });
  const base = `http://127.0.0.1:${(server.address() as any).port}`;
  assert.equal(
    (
      await fetch(base + "/api/reset", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scope: "generated", confirmation: "RESET" }),
      })
    ).status,
    200,
  );
  assert.equal(reopened.sources(f.id)[0].text, excerpt);
});

test("editing manual entries retains bindings/modes/outputs/queues and refreshes inherited text", async (t) => {
  const { s, dir } = fixture(t),
    w = new Worker(s, {} as any),
    f = s.family("one");
  const source = w.addTextEvidence(f.id, { label: "Before", text: excerpt });
  s.put(f.id, "output", { name: "Retained" });
  const run = structuredClone(s.state.run),
    checkpoint = structuredClone(s.state.buildCheckpoint);
  const server = api(s, w).listen(0, "127.0.0.1");
  await new Promise<void>((r) => server.once("listening", r));
  t.after(() => {
    server.closeAllConnections();
    server.close();
  });
  const base = `http://127.0.0.1:${(server.address() as any).port}`;
  const edit = (owner: string, body: unknown) =>
    fetch(
      `${base}/api/items/${owner}/text-evidence/${encodeURIComponent(source.id)}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      },
    );
  assert.equal((await edit(f.id, { text: " " })).status, 400);
  assert.equal((await edit("two", { text: "bad" })).status, 404);
  w.busy = true;
  s.state.run.currentId = f.id;
  assert.equal((await edit(f.id, { text: "bad" })).status, 409);
  w.busy = false;
  s.state.run.currentId = null;
  const first = await edit(f.id, { label: "After", text: "Updated facts." });
  assert.equal(first.status, 200);
  const updated = (await first.json()).source;
  assert.equal(updated.id, source.id);
  assert.equal(updated.url, source.url);
  assert.equal(updated.hash, hash("Updated facts."));
  assert.equal(updated.title, "After");
  assert.equal(
    readFileSync(path.join(dir, "sources", source.filename), "utf8"),
    "Updated facts.",
  );
  const moved = w.promoteSource(f.id, source.url),
    owner = s.ensureScope(moved.scope);
  w.setSharedSourceMode("two", source.url, "never");
  const response = await edit(owner.id, {
    label: "Shared edit",
    text: "New shared facts.",
  });
  assert.equal(response.status, 200);
  assert.equal(
    s.inheritedEvidence(f).find((row) => row.url === source.url)?.title,
    "Shared edit",
  );
  assert.equal(
    s.sources(f.id).find((row) => row.id === source.id)?.text,
    "New shared facts.",
  );
  assert.equal(s.sourceInclusionMode("two", source.url), "never");
  assert.deepEqual(s.get(f.id, "output"), { name: "Retained" });
  assert.deepEqual(s.state.run, run);
  assert.deepEqual(s.state.buildCheckpoint, checkpoint);
  assert.equal((await edit(f.id, { text: "not owned" })).status, 404);
});
