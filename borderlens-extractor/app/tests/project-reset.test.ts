import { test } from "node:test";
import assert from "node:assert/strict";
import {
  mkdtempSync,
  mkdirSync,
  writeFileSync,
  existsSync,
  rmSync,
  readdirSync,
} from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { Store } from "../src/server/store.ts";
import { Worker } from "../src/server/worker.ts";
import { resetProject } from "../src/server/project-reset.ts";
import { AgentRouter } from "../src/server/agents.ts";
import { Images, defaultImageRoot } from "../src/server/images.ts";
import { initial } from "../src/shared/models.ts";
function fixture(t: any) {
  const root = mkdtempSync(path.join(tmpdir(), "reset-test-")),
    dir = path.join(root, "project"),
    images = path.join(root, "images");
  mkdirSync(images);
  writeFileSync(path.join(images, "keep.txt"), "built in");
  const s = new Store(dir, images);
  let calls = 0,
    resets = 0;
  const w = new Worker(s, {
    run: async () => {
      calls++;
      throw Error("No AI expected");
    },
    resetFailures: () => resets++,
  } as any);
  s.state.families = [
    {
      id: "one",
      name: "One",
      category: "Artifacts",
      subtype: "Artifacts",
      character: "Brick",
      element: "Corrosive",
      aliases: [],
      roots: [],
      sourceUrls: [],
      history: [],
      revision: 1,
      status: "queued",
      stage: "draft",
      inputHash: "x",
      issue: null,
      notes: "keep correction",
      gameOnly: false,
      manualOutput: false,
      updatedAt: new Date().toISOString(),
    },
  ];
  const source = w.addTextEvidence("one", {
    label: "Manual facts",
    text: "Useful facts to retain.",
  });
  w.setManualName("one", "Locked name");
  for (const kind of [
    "output",
    "draft",
    "packet",
    "provenance",
    "finalValidation",
    "draft:compiler:old",
    "revision:old",
    "buildAttempt",
    "validationFeedback",
    "workingSourceLedger",
    "evidenceFollowup",
    "evidenceRequestNotice",
    "sourceLedger",
    "evidenceStatsHistory",
    "sourceExclusions",
    "sharedSourceSelection",
  ])
    s.put("one", kind, { kept: kind });
  s.put("_sharedSources", "indexed-facts", { saved: true });
  s.put("_parts", "part", { saved: true });
  s.put("_chrome", "ticket", { status: "queued" });
  s.state.run = {
    ...s.state.run,
    status: "paused",
    queue: ["one"],
    index: 0,
    currentId: "one",
  };
  s.state.buildCheckpoint = structuredClone(s.state.run);
  s.state.evidenceStats = {} as any;
  s.save();
  for (const file of [
    "ai/answer.json",
    "exports/output.json",
    ".stale",
    "captures/raw.zip",
    "image-library/old.png",
  ]) {
    mkdirSync(path.dirname(path.join(dir, file)), { recursive: true });
    writeFileSync(path.join(dir, file), "old data");
  }
  const recovery = dir + ".before-restore-fixture",
    stage = path.join(root, ".borderlens-restore-project-fixture"),
    foreign = path.join(root, "other.before-restore-fixture"),
    backup = path.join(root, "saved.zip");
  for (const d of [recovery, stage, foreign]) {
    mkdirSync(d);
    writeFileSync(path.join(d, "old"), "private data");
  }
  writeFileSync(backup, "export");
  t.after(() => {
    s.close();
    rmSync(root, { recursive: true, force: true });
  });
  return {
    s,
    w,
    dir,
    root,
    images,
    source,
    recovery,
    stage,
    foreign,
    backup,
    counts: () => ({ calls, resets }),
  };
}
test("full reset removes all project files, SQL data, overrides and owned recovery copies; preserves external assets/backups and Store listeners", (t) => {
  const f = fixture(t),
    { s, w, dir } = f;
  const oldResearch = w.research,
    oldImports = w.browserImports;
  s.cachedSource(f.source.url);
  let changes = 0;
  s.on("change", () => changes++);
  resetProject(w, "all");
  for (const table of ["raw", "artifacts", "sources"])
    assert.equal(
      (s.db.prepare(`SELECT count(*) AS n FROM ${table}`).get() as any).n,
      0,
    );
  assert.equal(s.records.size, 0);
  assert.deepEqual(s.names.data.entries, {});
  assert.deepEqual(s.classifications.data.entries, {});
  assert.equal(s.cachedSource(f.source.url), undefined);
  const expected = initial();
  expected.sharedScopes = [];
  expected.run.continueOnError = false;
  assert.deepEqual({ ...s.state, revision: expected.revision }, expected);
  for (const file of [
    ".stale",
    "image-library",
    "captures/raw.zip",
    "ai/answer.json",
    "exports/output.json",
  ])
    assert.equal(existsSync(path.join(dir, file)), false, file);
  for (const d of ["ai", "exports", "captures", "sources"])
    assert.deepEqual(readdirSync(path.join(dir, d)), []);
  assert.equal(existsSync(f.recovery), false);
  assert.equal(existsSync(f.stage), false);
  assert.ok(existsSync(f.foreign));
  assert.ok(existsSync(f.backup));
  assert.ok(existsSync(path.join(f.images, "keep.txt")));
  assert.notEqual(w.research, oldResearch);
  assert.notEqual(w.browserImports, oldImports);
  assert.equal(changes, 1);
  assert.deepEqual(f.counts(), { calls: 0, resets: 1 });
  s.put("new", "test", { fresh: true });
  assert.deepEqual(s.get("new", "test"), { fresh: true });
});
test("generated reset clears compiled/retry/run/cache state and parts, retains research, histories, corrections and source files", (t) => {
  const f = fixture(t),
    { s, w } = f;
  const sourceFile = path.join(f.dir, "sources", f.source.filename!);
  resetProject(w, "generated");
  for (const kind of [
    "output",
    "draft",
    "packet",
    "provenance",
    "finalValidation",
    "draft:compiler:old",
    "revision:old",
    "buildAttempt",
    "validationFeedback",
    "workingSourceLedger",
    "evidenceFollowup",
    "evidenceRequestNotice",
  ])
    assert.equal(s.get("one", kind), null, kind);
  for (const kind of [
    "sourceLedger",
    "evidenceStatsHistory",
    "sourceExclusions",
    "sharedSourceSelection",
  ])
    assert.deepEqual(s.get("one", kind), { kept: kind });
  assert.ok(s.get("_sharedSources", "indexed-facts"));
  assert.ok(s.get("_chrome", "ticket"));
  assert.equal(s.get("_parts", "part"), null);
  assert.ok(existsSync(sourceFile));
  assert.ok(existsSync(path.join(f.dir, "name-overrides.json")));
  assert.ok(existsSync(path.join(f.dir, "image-library/old.png")));
  assert.ok(existsSync(f.recovery));
  assert.equal(s.state.families[0].name, "Locked name");
  assert.equal(s.state.families[0].notes, "keep correction");
  assert.equal(s.state.families[0].stage, "evidence");
  assert.equal(s.state.families[0].status, "queued");
  assert.equal(s.state.buildCheckpoint, undefined);
  assert.equal(s.state.evidenceStats, undefined);
  assert.equal(s.state.run.status, "idle");
  assert.deepEqual(s.state.run.queue, []);
  assert.deepEqual(readdirSync(path.join(f.dir, "ai")), []);
  assert.deepEqual(readdirSync(path.join(f.dir, "exports")), []);
  assert.deepEqual(f.counts(), { calls: 0, resets: 1 });
});
test("generated reset preserves manual JSON, validation, dependencies and exclusion status", (t) => {
  const { s, w } = fixture(t);
  s.state.families[0].manualOutput = true;
  s.state.families[0].status = "excluded";
  resetProject(w, "generated");
  for (const kind of [
    "output",
    "draft",
    "provenance",
    "finalValidation",
    "revision:old",
  ])
    assert.ok(s.get("one", kind), kind);
  assert.ok(s.get("_parts", "part"));
  assert.equal(s.state.families[0].status, "excluded");
  assert.equal(s.get("one", "buildAttempt"), null);
});
test("every active-service guard rejects resets without deleting any data", (t) => {
  const f = fixture(t),
    { s, w } = f;
  for (const key of ["busy", "coverageBusy", "identitySync", "closed"]) {
    (w as any)[key] = true;
    assert.throws(() => resetProject(w, "all"), /Pause processing/);
    (w as any)[key] = false;
    assert.ok(s.get("one", "output"));
    assert.ok(existsSync(f.recovery));
  }
  for (const status of ["running", "pausing"]) {
    s.state.run.status = status as any;
    assert.throws(() => resetProject(w, "generated"), /Pause processing/);
    assert.ok(s.get("one", "output"));
  }
  assert.deepEqual(f.counts(), { calls: 0, resets: 0 });
});

test("full reset drops restored image root and production provider cooldowns without touching shipped assets", (t) => {
  const { s, w, dir } = fixture(t);
  s.images = new Images(
    path.join(dir, "image-library"),
    path.join(dir, "image-overrides.json"),
  );
  writeFileSync(
    path.join(dir, "ai", "agent-failures.json"),
    JSON.stringify({
      codex: { message: "old capacity failure", until: Date.now() + 600000 },
    }),
  );
  const router = new AgentRouter(s, {});
  w.ai = router;
  assert.ok((router as any).failures.codex);
  resetProject(w, "all");
  assert.equal(s.images.root, defaultImageRoot);
  assert.ok(existsSync(defaultImageRoot));
  assert.notEqual(w.ai, router);
  assert.deepEqual((w.ai as any).failures, {});
  assert.equal(existsSync(path.join(dir, "ai", "agent-failures.json")), false);
  assert.equal(existsSync(path.join(dir, "image-library")), false);
});
