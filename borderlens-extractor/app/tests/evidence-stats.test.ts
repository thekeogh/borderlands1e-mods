import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { z } from "zod";
import { Store } from "../src/server/store.ts";
import { Worker } from "../src/server/worker.ts";
import { AgentRouter } from "../src/server/agents.ts";
import { GrokRunner } from "../src/server/grok.ts";
import { CodexRunner } from "../src/server/codex.ts";
import { evidenceInput, evidenceTotals } from "../src/shared/evidence-stats.ts";
import {
  beginEvidenceStats,
  recordEvidenceEvent,
  finishEvidenceStats,
} from "../src/server/evidence-stats.ts";
import { sourceWritingPacket } from "../src/server/source-analysis.ts";
import type { Family } from "../src/shared/models.ts";
function setup(t: any) {
  const dir = mkdtempSync(path.join(tmpdir(), "borderlens-evidence-stats-"));
  let store = new Store(dir);
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
  store.state.families = [family("one"), family("two")];
  store.save();
  t.after(() => {
    store.close();
    rmSync(dir, { recursive: true, force: true });
  });
  return {
    get store() {
      return store;
    },
    dir,
    reopen() {
      store.close();
      store = new Store(dir);
      return store;
    },
  };
}
const url = "https://borderlands.fandom.com/wiki/Corrosive";

test("source counts come from final payload entries, not selected switches, duplicates or citation URLs", () => {
  const payload = {
    evidence: [
      {
        id: "page:a",
        kind: "page",
        label: "A",
        value: { url, text: "actual content" },
      },
      { id: "game:a", kind: "game", value: { unrelated: true } },
    ],
    pages: [
      {
        id: "page:b",
        url: "https://example.com/b",
        text: "actual saved excerpt",
      },
    ],
    facts: [{ sourceId: "page:b", quote: "A stat" }],
    sources: [
      { url: "https://example.com/acquisition", label: "Drop URL only" },
    ],
    excludedUrls: ["https://example.com/excluded"],
  };
  const input = evidenceInput("verify", payload);
  assert.deepEqual(
    input.sources.map((s) => s.id),
    ["page:a", "page:b"],
  );
  const ledger: any = [
    {
      sourceId: "page:a",
      url,
      chunks: [
        {
          index: 0,
          facts: [{ id: "fact:a" }],
          reading: { fields: [], proposedFields: [] },
        },
      ],
    },
    {
      sourceId: "page:unused",
      url: "https://example.com/empty",
      chunks: [
        { index: 0, facts: [], reading: { fields: [], proposedFields: [] } },
      ],
    },
  ];
  const actual = sourceWritingPacket({} as any, ledger);
  assert.deepEqual(
    evidenceInput("write", actual).sources.map((s) => s.id),
    ["page:a"],
  );
  assert.equal(
    evidenceInput("other", { passage: "Original prose", url }).sources.length,
    0,
  );
});

test("real CLI boundary counts fresh submissions, failures/fallbacks and local response caches separately", async (t) => {
  const x = setup(t),
    s = x.store,
    f = s.state.families[0];
  s.state.settings.agent = "codex";
  s.state.run.currentId = f.id;
  const owner = s.ensureScope({ category: "Everything" });
  owner.sourceUrls.push(url);
  const binary = path.join(x.dir, "fake-codex.cjs");
  writeFileSync(
    binary,
    `#!/usr/bin/env node
const fs=require('node:fs'),a=process.argv.slice(2);
if(a[0]==='--version'){console.log('fixture');process.exit(0)}
if(a[0]==='login'){console.log('Logged in using ChatGPT');process.exit(0)}
let data='';process.stdin.on('data',d=>data+=d);process.stdin.on('end',()=>{if(data.includes('FAIL_FIRST')){console.error('Synthetic failure');process.exit(1)} fs.writeFileSync(a[a.indexOf('--output-last-message')+1],JSON.stringify({ok:true}));});`,
    { mode: 0o700 },
  );
  const worker = new Worker(s, {} as any);
  worker.research.save(
    owner,
    url,
    "<h1>Corrosive</h1><p>This is the original saved corrosive page fixture describing corrosive effects and mechanics.</p>",
    true,
  );
  const page = s.sources(f.id)[0];
  const input = evidenceInput("write", [
    {
      sourceId: page.id,
      url,
      chunks: [{ facts: [{ quote: "corrosive effects" }] }],
    },
  ]);
  const router = new AgentRouter(s, {
    codex: new CodexRunner(path.join(x.dir, "cli"), binary),
  });
  const schema = z.object({ ok: z.boolean() }).strict();
  beginEvidenceStats(s, f);
  await router.run(
    "Build one",
    JSON.stringify(input.sources),
    schema,
    "",
    false,
    () => {},
    input,
  );
  await router.run(
    "Build one",
    JSON.stringify(input.sources),
    schema,
    "",
    false,
    () => {},
    input,
  );
  let total = evidenceTotals(s.state.evidenceStats!);
  assert.equal(total.calls, 1);
  assert.equal(total.sources, 1);
  assert.equal(total.cachedResponses, 1);
  assert.equal(s.state.evidenceStats!.events[0].sources[0].mode, "auto");
  await assert.rejects(
    router.run(
      "Build failing",
      "FAIL_FIRST " + JSON.stringify(input.sources),
      schema,
      "",
      false,
      () => {},
      input,
    ),
    /Synthetic failure/,
  );
  total = evidenceTotals(s.state.evidenceStats!);
  assert.equal(total.calls, 2);
  assert.equal(total.sends, 2);
  // Cooldown skips do not create fictional submissions.
  await assert.rejects(
    router.run("Build skipped", "another", schema, "", false, () => {}, input),
  );
  assert.equal(evidenceTotals(s.state.evidenceStats!).calls, 2);
  router.resetFailures();
  await router.run(
    "Build final manifest",
    JSON.stringify(input.sources),
    schema,
    "",
    false,
    () => {},
    {
      ...input,
      sources: [
        ...input.sources,
        { id: "page:not-in-prompt", url: "https://example.com/not-sent" },
      ],
    },
  );
  assert.equal(s.state.evidenceStats!.events.at(-1)!.sources.length, 1);
  assert.equal(evidenceTotals(s.state.evidenceStats!).calls, 3);
  finishEvidenceStats(s, f, "failed");
  const saved = s.get<any[]>(f.id, "evidenceStatsHistory")!;
  assert.equal(saved.length, 1);
  assert.equal(saved[0].outcome, "failed");
  assert(!JSON.stringify(saved).includes("actual unique prompt"));
});

test("live counts persist until next item; history survives rolling logs/restart and cache facts still count when submitted", async (t) => {
  const x = setup(t),
    s = x.store,
    [first, second] = s.state.families;
  beginEvidenceStats(s, first);
  const input = evidenceInput("read", {
    sourceId: "page:a",
    url,
    text: "actual",
  });
  recordEvidenceEvent(s, first, input, {
    kind: "analysis-cache",
    label: "Saved source analysis",
    chunks: 3,
  });
  assert.equal(evidenceTotals(s.state.evidenceStats!).calls, 0);
  recordEvidenceEvent(
    s,
    first,
    { ...input, phase: "write" },
    { kind: "submitted", label: "Build one", agent: "codex" },
  );
  finishEvidenceStats(s, first, "complete");
  finishEvidenceStats(s, first, "complete");
  assert.equal(s.get<any[]>(first.id, "evidenceStatsHistory")!.length, 1);
  const total = evidenceTotals(s.state.evidenceStats!);
  assert.equal(total.cachedSources, 1);
  assert.equal(total.cachedChunks, 3);
  assert.equal(total.writeSends, 1);
  assert.equal(total.sources, 1);
  const original = structuredClone(s.state.evidenceStats);
  const w = new Worker(s, {} as any);
  for (let n = 0; n < 120; n++) w.history(first, "later event");
  const reopened = x.reopen();
  assert.deepEqual(reopened.state.evidenceStats, original);
  assert.deepEqual(
    reopened.get<any[]>(first.id, "evidenceStatsHistory")![0],
    original,
  );
  beginEvidenceStats(reopened, reopened.family(second.id));
  assert.equal(reopened.state.evidenceStats!.familyId, second.id);
  assert.equal(evidenceTotals(reopened.state.evidenceStats!).sources, 0);
  const { api } = await import("../src/server/http.ts");
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
  const detail = await fetch(`${base}/api/items/${first.id}`).then((r) =>
    r.json(),
  );
  assert.equal(detail.evidenceStatsHistory.length, 1);
  assert.equal(detail.evidenceStatsHistory[0].events.length, 2);
});

test("an explicit provider fallback records both actual submissions with the same source manifest", async (t) => {
  const { store: s, dir } = setup(t);
  const f = s.state.families[0];
  s.state.run.currentId = f.id;
  s.state.settings.agent = "grok";
  const binary = path.join(dir, "fake-agents.cjs");
  writeFileSync(
    binary,
    `#!/usr/bin/env node
const fs=require('node:fs'),a=process.argv.slice(2);
if(a[0]==='--version'){console.log('fixture');process.exit(0)}
if(a[0]==='models'){console.log('You are logged in with grok.com. Available models: grok-4.6');process.exit(0)}
if(a[0]==='login'){console.log('Logged in using ChatGPT');process.exit(0)}
if(a.includes('--prompt-file')){console.error('Synthetic fallback failure');process.exit(1)}
process.stdin.resume();process.stdin.on('end',()=>fs.writeFileSync(a[a.indexOf('--output-last-message')+1],JSON.stringify({ok:true})));`,
    { mode: 0o700 },
  );
  const router = new AgentRouter(s, {
    grok: new GrokRunner(path.join(dir, "grok"), binary),
    codex: new CodexRunner(path.join(dir, "codex"), binary),
  });
  const payload = [
    {
      sourceId: "page:actual",
      url,
      chunks: [{ facts: [{ quote: "actual" }] }],
    },
  ];
  await router.run(
    "Build fallback",
    JSON.stringify(payload),
    z.object({ ok: z.boolean() }).strict(),
    "",
    false,
    () => {},
    evidenceInput("write", payload),
  );
  const stats = s.state.evidenceStats!;
  assert.deepEqual(
    stats.events.map((e) => e.agent),
    ["grok", "codex"],
  );
  assert(
    stats.events.every((e) => e.kind === "submitted" && e.sources.length === 1),
  );
  assert.equal(evidenceTotals(stats).sources, 1);
  assert.equal(evidenceTotals(stats).sends, 2);
  assert.equal(evidenceTotals(stats).calls, 2);
});
