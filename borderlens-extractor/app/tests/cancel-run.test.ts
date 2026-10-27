import { test } from "node:test";
import assert from "node:assert/strict";
import {
  mkdtempSync,
  rmSync,
  writeFileSync,
  readFileSync,
  existsSync,
} from "node:fs";
import path from "node:path";
import { tmpdir } from "node:os";
import { z } from "zod";
import { Store } from "../src/server/store.ts";
import { Worker } from "../src/server/worker.ts";
import { api } from "../src/server/http.ts";
import { AgentRouter } from "../src/server/agents.ts";
import { CodexRunner } from "../src/server/codex.ts";
import { initial, type Family } from "../src/shared/models.ts";
import { beginEvidenceStats } from "../src/server/evidence-stats.ts";
function fixture(t: any) {
  const dir = mkdtempSync(path.join(tmpdir(), "cancel-run-"));
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
    revision: 3,
    status: "queued",
    stage: "draft",
    inputHash: "",
    issue: null,
    notes: "Keep my correction",
    gameOnly: false,
    manualOutput: false,
    updatedAt: new Date().toISOString(),
  });
  s.state.families = [family("one"), family("two")];
  s.save();
  t.after(() => {
    s.close();
    rmSync(dir, { recursive: true, force: true });
  });
  return {
    dir,
    get s() {
      return s;
    },
    reopen() {
      s.close();
      s = new Store(dir);
      return s;
    },
  };
}
async function waitFor(predicate: () => boolean) {
  for (let n = 0; n < 334; n++) {
    if (predicate()) return;
    await new Promise((r) => setTimeout(r, 30));
  }
  throw Error("Timed out waiting for isolated cancellation fixture");
}

test("cancel clears paused single/batch queues and discovery checkpoints, preserving all item content and revisions", async (t) => {
  for (const mode of ["build", "discover"] as const) {
    const x = fixture(t),
      { s } = x,
      w = new Worker(s, {} as any),
      [f, second] = s.state.families;
    const source = w.addTextEvidence(f.id, {
      label: "Retain source",
      text: "Keep this selected source text.",
    });
    s.put(f.id, "draft", { retained: "draft" });
    s.put(f.id, "output", { retained: "JSON" });
    s.put(f.id, "pendingRebuild", { mode: "fresh" });
    s.state.run = {
      ...initial().run,
      status: "paused",
      mode,
      queue: [f.id, second.id],
      currentId: f.id,
      index: 0,
      deferred: [second.id],
      pendingFrom: second.id,
      sourceMode: "fresh",
    };
    s.state.buildCheckpoint = {
      ...initial().run,
      status: "paused",
      queue: [f.id],
      currentId: f.id,
    };
    s.save();
    const before = structuredClone(s.state.families);
    const server = api(s, w).listen(0, "127.0.0.1");
    await new Promise<void>((r) => server.once("listening", r));
    t.after(() => {
      server.closeAllConnections();
      server.close();
    });
    const base = `http://127.0.0.1:${(server.address() as any).port}`;
    const post = (body: unknown) =>
      fetch(base + "/api/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
    assert.equal(
      (await post({ action: "cancel", sourceMode: "saved" })).status,
      400,
    );
    assert.equal((await post({ action: "cancel" })).status, 200);
    assert.equal(s.state.run.status, "idle");
    assert.deepEqual(s.state.run.queue, []);
    assert.deepEqual(s.state.run.deferred, []);
    assert.equal(s.state.run.currentId, null);
    assert.equal(s.state.buildCheckpoint, undefined);
    assert.equal(s.get(f.id, "pendingRebuild"), null);
    assert.deepEqual(s.get(f.id, "draft"), { retained: "draft" });
    assert.deepEqual(s.get(f.id, "output"), { retained: "JSON" });
    assert.equal(s.sources(f.id)[0].id, source.id);
    assert.equal(
      readFileSync(path.join(s.dir, "sources", source.filename), "utf8"),
      source.text,
    );
    for (let n = 0; n < before.length; n++) {
      assert.equal(s.state.families[n].revision, before[n].revision);
      assert.equal(s.state.families[n].notes, before[n].notes);
      assert.equal(s.state.families[n].stage, before[n].stage);
    }
    assert.equal((await post({ action: "resume" })).status, 409);
    assert.equal((await post({ action: "resume-build" })).status, 400);
  }
});

test("cancel terminates an active CLI build without fallback, cooldowns or starting the next item, then a new run works", async (t) => {
  const { s, dir } = fixture(t),
    f = s.family("one");
  s.state.settings.agent = "codex";
  const pidFile = path.join(dir, "agent.pid"),
    binary = path.join(dir, "fake-codex.cjs");
  writeFileSync(
    binary,
    `#!/usr/bin/env node
const fs=require('node:fs'),a=process.argv.slice(2);
if(a[0]==='--version'){console.log('fixture');process.exit(0)}
if(a[0]==='login'){console.log('Logged in using ChatGPT');process.exit(0)}
fs.writeFileSync(${JSON.stringify(pidFile)},String(process.pid));
let prompt='';process.stdin.on('data',d=>prompt+=d);process.stdin.on('end',()=>{if(prompt==='FINISH'){fs.writeFileSync(a[a.indexOf('--output-last-message')+1],JSON.stringify({ok:true}));process.exit(0)} setInterval(()=>{},1000);});`,
    { mode: 0o700 },
  );
  let fallback = 0,
    finish = false;
  const router = new AgentRouter(s, {
    codex: new CodexRunner(path.join(dir, "codex"), binary),
    grok: {
      status: async () => ({}),
      run: async () => {
        fallback++;
        throw Error("Unexpected fallback");
      },
    },
  });
  const w = new Worker(s, router),
    visited: string[] = [];
  s.put(f.id, "draft", { retained: "earlier draft" });
  s.put(f.id, "output", { retained: "earlier JSON" });
  w.step = async (item) => {
    visited.push(item.id);
    await router.run(
      "Build fixture",
      finish ? "FINISH" : "HANG",
      z.object({ ok: z.boolean() }).strict(),
      "",
      false,
      () => {},
    );
    item.stage = "complete";
  };
  s.state.run = {
    ...initial().run,
    status: "running",
    sourceMode: "auto",
    queue: [f.id, "two"],
    continueOnError: true,
  };
  const running = w.loop();
  await waitFor(() => existsSync(pidFile));
  const pid = Number(readFileSync(pidFile, "utf8"));
  w.cancelRun();
  assert.equal(s.state.run.cancelRequested, true);
  await running;
  assert.equal(s.state.run.status, "idle");
  assert.deepEqual(visited, [f.id]);
  assert.equal(f.status, "queued");
  assert.equal(f.issue, null);
  assert.equal(fallback, 0);
  assert.throws(() => process.kill(pid, 0));
  assert.deepEqual(s.get(f.id, "draft"), { retained: "earlier draft" });
  assert.deepEqual(s.get(f.id, "output"), { retained: "earlier JSON" });
  assert.equal((await router.status()).providers.codex.lastError, null);
  assert.equal(
    s.get<any[]>(f.id, "evidenceStatsHistory")!.at(-1).outcome,
    "cancelled",
  );
  finish = true;
  w.start(undefined, f.id, "auto");
  await waitFor(() => !w.busy);
  assert.equal(s.state.run.status, "complete");
  assert.equal(f.status, "done");
  assert.equal(fallback, 0);
});

test("a saved cancellation request recovers idle instead of offering Resume after restart", (t) => {
  const x = fixture(t),
    { s } = x,
    f = s.family("one");
  s.put(f.id, "output", { retained: "JSON" });
  s.state.run = {
    ...initial().run,
    status: "pausing",
    cancelRequested: true,
    queue: [f.id],
    currentId: f.id,
  };
  s.state.buildCheckpoint = structuredClone(s.state.run);
  beginEvidenceStats(s, f);
  s.save();
  const again = x.reopen();
  assert.equal(again.state.run.status, "idle");
  assert.deepEqual(again.state.run.queue, []);
  assert.equal(again.state.buildCheckpoint, undefined);
  assert.equal(again.state.evidenceStats?.outcome, "cancelled");
  assert.deepEqual(again.get(f.id, "output"), { retained: "JSON" });
});
