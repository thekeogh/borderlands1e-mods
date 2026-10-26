import {
  CATALOGUE_SCHEMA_VERSION,
  COMPILER_VERSION,
} from "../src/shared/versions.ts";
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { Store } from "../src/server/store.ts";
import { Worker } from "../src/server/worker.ts";
import { Research } from "../src/server/research.ts";
import { api } from "../src/server/http.ts";
import type { Family } from "../src/shared/models.ts";
function fixture(t: any) {
  const dir = mkdtempSync(path.join(tmpdir(), "group-batches-"));
  let s = new Store(dir);
  const family = (
    id: string,
    category: Family["category"],
    character?: Family["character"],
    status: Family["status"] = "done",
    subtype: string = category,
  ): Family => ({
    id,
    name: id,
    category,
    character,
    subtype,
    aliases: [],
    roots: [],
    status,
    stage: status === "done" ? "complete" : "evidence",
    inputHash: "",
    issue: null,
    notes: "",
    gameOnly: false,
    sourceUrls: [],
    history: [],
    updatedAt: new Date().toISOString(),
    manualOutput: false,
    revision: 3,
  });
  s.state.families = [
    family("roland-a", "Class mods", "Roland"),
    family("roland-b", "Class mods", "Roland", "queued"),
    family("lilith-a", "Class mods", "Lilith"),
    family("removed", "Class mods", "Roland", "excluded"),
    {
      ...family("retired", "Class mods", "Roland"),
      supersededBy: ["roland-a"],
    },
    family("artifact", "Artifacts", "Roland"),
    family("machinegun", "Weapons", undefined, "done", "Machine guns"),
    family("combat-rifle", "Weapons", undefined, "done", "Combat rifles"),
    family("smg", "Weapons", undefined, "done", "SMGs"),
  ];
  for (const f of s.state.families) {
    s.put(f.id, "output", {
      schemaVersion: CATALOGUE_SCHEMA_VERSION,
      retained: f.id,
    });
    s.put(f.id, "provenance", { compilerVersion: COMPILER_VERSION });
  }
  s.save();
  t.after(() => {
    s.close();
    rmSync(dir, { recursive: true, force: true });
  });
  const w = new Worker(s, {} as any);
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
async function idle(w: Worker) {
  for (let n = 0; n < 200 && w.busy; n++)
    await new Promise((r) => setTimeout(r, 5));
  assert.equal(w.busy, false);
}
async function serverFixture(t: any) {
  const x = fixture(t),
    server = api(x.s, x.w).listen(0, "127.0.0.1");
  await new Promise<void>((r) => server.once("listening", r));
  t.after(() => {
    server.closeAllConnections();
    server.close();
  });
  return {
    ...x,
    post: (body: unknown) =>
      fetch(
        `http://127.0.0.1:${(server.address() as any).port}/api/groups/run`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
      ),
  };
}
const article =
  "<h1>Group fixture evidence</h1><p>Original saved evidence fixture used to verify reuse of shared sources within a restricted catalogue group.</p>";
test("category saved rebuild includes completed descendants, reuses available sources, falls back for uncached children and touches no siblings", async (t) => {
  const { s, w } = fixture(t);
  new Research(s).save(
    s.family("roland-a"),
    "https://borderlands.fandom.com/wiki/Fixture",
    article,
    true,
  );
  const touched: string[] = [],
    modes: Record<string, string> = {};
  w.step = async (f) => {
    touched.push(f.id);
    modes[f.id] = s.get<any>(f.id, "rebuildPlan").mode;
    f.stage = "complete";
  };
  const outside = s.state.families
    .filter((f) => f.category !== "Class mods")
    .map((f) => [f.id, f.status, f.stage, f.revision, s.get(f.id, "output")]);
  w.start(undefined, undefined, "saved", "build", { category: "Class mods" });
  await idle(w);
  assert.deepEqual(
    new Set(touched),
    new Set(["roland-a", "roland-b", "lilith-a"]),
  );
  assert.equal(touched.length, 3);
  assert.equal(modes["roland-a"], "saved");
  assert.equal(modes["roland-b"], "fresh");
  assert.equal(modes["lilith-a"], "fresh");
  assert.equal(s.state.run.rebuildAll, true);
  assert.equal(s.state.run.continueOnError, true);
  assert.deepEqual(s.state.run.scope, { category: "Class mods" });
  assert.equal(s.state.run.status, "complete");
  assert.deepEqual(
    s.state.families
      .filter((f) => f.category !== "Class mods")
      .map((f) => [f.id, f.status, f.stage, f.revision, s.get(f.id, "output")]),
    outside,
  );
});
test("character fresh rebuild processes only that character exactly once even when all children were already complete", async (t) => {
  const { s, w } = fixture(t),
    scope = s.ensureScope({ category: "Class mods" });
  new Research(s).save(
    scope,
    "https://borderlands.fandom.com/wiki/Fixture",
    article,
    true,
  );
  const touched: string[] = [];
  let expected = "fresh";
  w.step = async (f) => {
    touched.push(f.id);
    assert.equal(s.get<any>(f.id, "rebuildPlan").mode, expected);
    assert.equal(s.sources(f.id).length, 1);
    f.stage = "complete";
  };
  w.start(undefined, undefined, "fresh", "build", {
    category: "Class mods",
    character: "Roland",
  });
  await idle(w);
  assert.deepEqual(touched, ["roland-a", "roland-b"]);
  assert.equal(s.family("lilith-a").status, "done");
  assert.equal(s.family("roland-a").status, "done");
  expected = "saved";
  w.start(undefined, undefined, "saved", "build", {
    category: "Class mods",
    character: "Roland",
  });
  await idle(w);
  assert.deepEqual(touched, ["roland-a", "roland-b", "roland-a", "roland-b"]);
  assert.equal(s.family("roland-a").status, "done");
  assert.equal(s.family("roland-b").status, "done");
});
test("group URL discovery uses the same membership, continues failures and preserves JSON/status/revisions and paused build", async (t) => {
  const { s, w } = fixture(t);
  const before = s.state.families.map((f) => [
    f.id,
    f.status,
    f.stage,
    f.revision,
    s.get(f.id, "output"),
  ]);
  Object.assign(s.state.run, {
    status: "paused",
    queue: ["smg"],
    currentId: "smg",
    index: 0,
  });
  const checkpoint = structuredClone(s.state.run);
  let calls = 0;
  w.ai = {
    run: async () => {
      calls++;
      if (calls === 1) throw Error("Synthetic lookup failure");
      return {
        matches: [
          {
            url: "https://borderlands.fandom.com/wiki/Item_fixture",
            title: "Fixture",
            gameEvidence: "BL1",
            reason: "Fixture",
          },
        ],
        notFoundReason: "",
      };
    },
  } as any;
  w.step = async () => {
    throw Error("Discovery must not compile");
  };
  w.research.fetchPage = async () => {
    throw Error("Discovery must not fetch articles");
  };
  w.start(undefined, undefined, "auto", "discover", {
    category: "Class mods",
    character: "Roland",
  });
  await idle(w);
  assert.equal(calls, 2);
  assert.equal(s.state.run.status, "complete");
  assert.equal(s.family("roland-a").urlDiscovery?.status, "failed");
  assert.equal(s.family("roland-b").urlDiscovery?.status, "complete");
  assert.deepEqual(s.state.buildCheckpoint, checkpoint);
  assert.deepEqual(
    s.state.families.map((f) => [
      f.id,
      f.status,
      f.stage,
      f.revision,
      s.get(f.id, "output"),
    ]),
    before,
  );
});
test("weapon-group matching uses player-facing merged types and build failures continue within the group", async (t) => {
  const { s, w } = fixture(t),
    visited: string[] = [];
  w.step = async (f) => {
    visited.push(f.id);
    if (f.id === "combat-rifle") throw Error("Synthetic build failure");
    f.stage = "complete";
  };
  w.start(undefined, undefined, "fresh", "build", {
    category: "Weapons",
    group: "Combat rifles",
  });
  await idle(w);
  assert.deepEqual(new Set(visited), new Set(["combat-rifle", "machinegun"]));
  assert.equal(s.family("combat-rifle").status, "blocked");
  assert.equal(s.family("machinegun").status, "done");
  assert.equal(s.family("smg").status, "done");
  assert.equal(s.state.run.status, "complete");
  assert.match(s.state.run.message, /1 item\(s\) need attention/);
});
test("scope and prepared-item checkpoint survive pause/restart without repeating source initialization", async (t) => {
  const x = fixture(t),
    { s, w } = x;
  let release!: () => void;
  const held = new Promise<void>((resolve) => (release = resolve));
  w.step = async (f) => {
    w.pause();
    await held;
    f.stage = "draft";
  };
  w.start(undefined, undefined, "fresh", "build", {
    category: "Class mods",
    character: "Roland",
  });
  assert.equal(w.busy, true);
  release();
  await idle(w);
  assert.equal(s.state.run.status, "paused");
  assert.deepEqual(s.state.run.sourcePrepared, ["roland-a"]);
  const attempts = s.get("roland-a", "buildAttempt");
  const restored = x.reopen(),
    next = new Worker(restored, {} as any),
    visited: string[] = [];
  next.step = async (f) => {
    visited.push(f.id);
    f.stage = "complete";
  };
  next.resume();
  await idle(next);
  assert.deepEqual(visited, ["roland-a", "roland-b"]);
  assert.equal(restored.get("roland-a", "buildAttempt"), attempts);
  assert.deepEqual(restored.state.run.scope, {
    category: "Class mods",
    character: "Roland",
  });
  assert.equal(restored.state.run.status, "complete");
});
test("later evidence changes and explicit item actions cannot silently append out-of-group work", async (t) => {
  const { s, w } = fixture(t);
  let release!: () => void;
  const held = new Promise<void>((resolve) => (release = resolve));
  w.step = async (f) => {
    await held;
    f.stage = "complete";
  };
  w.start(undefined, undefined, "fresh", "build", {
    category: "Class mods",
    character: "Roland",
  });
  const original = [...s.state.run.queue];
  await assert.rejects(
    w.action("smg", "rebuild-fresh", {}),
    /outside its group/,
  );
  assert.throws(() => w.start("smg"), /outside its selected range/);
  await w.action("removed", "restore", {});
  assert(
    s.state.run.queue.every((id) => original.includes(id) || id === "removed"),
  );
  assert(!s.state.run.queue.includes("smg"));
  release();
  await idle(w);
  assert(
    s.state.run.queue.every(
      (id) =>
        s.family(id).category === "Class mods" &&
        s.family(id).character === "Roland",
    ),
  );
});
test("group API exposes all three actions, validates scope and rejects active-job replacement", async (t) => {
  const x = await serverFixture(t),
    { s, w } = x;
  w.step = async (f) => {
    f.stage = "complete";
  };
  for (const action of ["rebuild-saved", "rebuild-fresh"]) {
    assert.equal(
      (
        await x.post({
          scope: { category: "Artifacts", character: "Roland" },
          action,
        })
      ).status,
      200,
    );
    await idle(w);
    assert.deepEqual(s.state.run.queue, ["artifact"]);
  }
  w.ai = {
    run: async () => ({
      matches: [
        {
          url: "https://borderlands.fandom.com/wiki/Fixture",
          title: "Fixture",
          gameEvidence: "BL1",
          reason: "Fixture",
        },
      ],
      notFoundReason: "",
    }),
  } as any;
  assert.equal(
    (await x.post({ scope: { category: "Artifacts" }, action: "discover" }))
      .status,
    200,
  );
  await idle(w);
  assert.deepEqual(s.state.run.queue, ["artifact"]);
  assert.equal(s.state.sharedScopes?.length, 0);
  w.busy = true;
  const prior = structuredClone(s.state.run);
  assert.equal(
    (await x.post({ scope: { category: "Class mods" }, action: "discover" }))
      .status,
    409,
  );
  assert.deepEqual(s.state.run, prior);
  w.busy = false;
  assert.equal(
    (
      await x.post({
        scope: { category: "Shields", character: "Roland" },
        action: "discover",
      })
    ).status,
    400,
  );
  assert.equal(
    (await x.post({ scope: { category: "Artifacts" }, action: "unsupported" }))
      .status,
    400,
  );
});
