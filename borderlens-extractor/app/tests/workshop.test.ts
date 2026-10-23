import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync, existsSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import AdmZip from "adm-zip";
import { Store, hash } from "../src/server/store.ts";
import { importZip, discover } from "../src/server/importer.ts";
import { Worker, type AI } from "../src/server/worker.ts";
import { Research, compareCoverage } from "../src/server/research.ts";
import { buildPacket, validateDraft } from "../src/server/evidence.ts";
import { api } from "../src/server/http.ts";
import {
  Draft,
  type Family,
  type PublicEntry,
  type Raw,
} from "../src/shared/models.ts";

const records: Raw[] = ["Hellfire", "Thunder"].map((name, i) => ({
  id: String(i),
  record_type: "object",
  path: `gd_weap_patrol_smg.Title.Title_${name}`,
  class: "WillowGame.WeaponNamePartDefinition",
  properties: { PartName: name },
}));
function capture(rows = records, tamper = false) {
  const zip = new AdmZip(),
    raw = Buffer.from(JSON.stringify(rows));
  zip.addFile("capture/data/0001.json", raw);
  zip.addFile(
    "capture/manifest.json",
    Buffer.from(
      JSON.stringify({
        format_version: 1,
        extractor_version: "test",
        chunks: [
          {
            file: "data/0001.json",
            sha256: tamper ? "bad" : hash(raw),
            records: rows.length,
          },
        ],
      }),
    ),
  );
  return zip.toBuffer();
}
function fixture(t: any) {
  const dir = mkdtempSync(path.join(tmpdir(), "borderlens-test-"));
  const s = new Store(dir);
  t.after(() => {
    s.close();
    rmSync(dir, { recursive: true, force: true });
  });
  return s;
}
function entry(f: Family): PublicEntry {
  return {
    schemaVersion: "2",
    compilerVersion: "0.2.0",
    description: [
      "An original fixture paragraph describing this item for players.",
    ],
    references: [],
    variants: [],
    parts: [],
    id: f.id,
    name: f.name,
    game: "borderlands-goty-enhanced",
    category: f.category,
    weaponType: f.subtype,
    summary: "A useful weapon family for exploring Pandora.",
    manufacturers: [],
    rarities: [],
    elements: [],
    redText: null,
    specialEffects: [],
    levels: { minimum: null, maximum: null, notes: "" },
    stats: [],
    sources: [],
    notes: [],
  };
}
function fakeAI(s: Store, wait?: () => Promise<void>): AI {
  return {
    status: async () => ({ chatgpt: true }),
    run: async (_label, prompt, schema) => {
      await wait?.();
      const f = s.family(s.state.run.currentId!);
      return schema.parse({
        entry: entry(f),
        partDefinitions: [],
        claims: [
          {
            field: "summary",
            evidenceIds: [buildPacket(s, f).evidence[0].id],
            basis: "Captured family name and type.",
          },
          {
            field: "description",
            evidenceIds: [buildPacket(s, f).evidence[0].id],
            basis: "Fixture description.",
          },
        ],
        uncertainties: ["Final stat ranges not established."],
        conflicts: [],
        requiresReview: false,
        reviewReason: null,
      });
    },
  };
}
const until = async (fn: () => boolean) => {
  for (let i = 0; i < 500; i++) {
    if (fn()) return;
    await new Promise((r) => setTimeout(r, 10));
  }
  throw new Error("Timed out waiting for worker");
};

test("ZIP validates checksums/counts/identities before writes and imports idempotently", (t) => {
  const s = fixture(t);
  assert.throws(
    () => importZip(s, capture(records, true), "bad.zip"),
    /Checksum/,
  );
  assert.equal(s.records.size, 0);
  assert.throws(
    () => importZip(s, capture([records[0], records[0]]), "duplicate.zip"),
    /duplicate record/,
  );
  assert.equal(s.state.captures.length, 0);
  const result = importZip(s, capture(), "good.zip");
  assert.equal(result.families, 2);
  assert.equal(s.records.size, 2);
  assert.equal(importZip(s, capture(), "again.zip").duplicate, true);
  assert.equal(s.state.captures.length, 1);
});
test("family discovery includes ordinary titles, keeps category identities separate", () => {
  const rows = new Map(records.map((r) => [r.path.toLowerCase(), r]));
  const families = discover(rows);
  assert.deepEqual(
    families.map((f) => f.name),
    ["Hellfire", "Thunder"],
  );
  assert.equal(discover(rows)[0].id, families[0].id);
});
test("queue pauses at saved stage, browsing never changes current work, resumes sequentially", async (t) => {
  const s = fixture(t);
  importZip(s, capture(), "data.zip");
  s.state.settings.research = false;
  let release!: () => void,
    entered = false;
  const ai = fakeAI(s, async () => {
    entered = true;
    await new Promise<void>((r) => (release = r));
  });
  const w = new Worker(s, ai);
  w.start();
  await until(() => entered);
  const current = s.state.run.currentId;
  const other = s.state.families[1];
  s.family(other.id);
  assert.equal(s.state.run.currentId, current);
  w.pause();
  release();
  await until(() => !w.busy);
  assert.equal(s.state.run.status, "paused");
  assert.equal(s.family(current!).stage, "validate");
  w.ai = fakeAI(s);
  w.resume();
  await until(() => !w.busy);
  assert.equal(s.state.run.status, "complete");
  assert.ok(s.state.families.every((f) => f.status === "done"));
  assert.equal(s.get<any>(current!, "output").name, "Hellfire");
});
test("blocked work retains prior output; corrections and manual output survive rebuild", async (t) => {
  const s = fixture(t);
  importZip(s, capture(), "data.zip");
  s.state.settings.research = false;
  const w = new Worker(s, fakeAI(s));
  const f = s.state.families[0];
  w.start(undefined, f.id);
  await until(() => !w.busy);
  const old = s.get(f.id, "output");
  w.ai = {
    ...fakeAI(s),
    run: async () => {
      throw new Error("Network interrupted");
    },
  };
  await w.action(f.id, "rebuild", {});
  await until(() => !w.busy);
  assert.equal(f.status, "blocked");
  assert.deepEqual(s.get(f.id, "output"), old);
  await w.action(f.id, "resolve", {
    notes: "Keep this correction",
    gameOnly: true,
  });
  assert.equal(f.notes, "Keep this correction");
  const manual = {
    ...entry(f),
    summary: "A manually reviewed family description for players.",
  };
  await w.action(f.id, "save-output", { output: manual });
  assert.equal(f.status, "done");
  await w.action(f.id, "rebuild", {});
  await until(() => !w.busy);
  assert.equal(s.get<any>(f.id, "output").summary, manual.summary);
  assert.equal(f.notes, "Keep this correction");
});
test("rebuild requested during a batch waits and is not lost", async (t) => {
  const s = fixture(t);
  importZip(s, capture(), "data.zip");
  s.state.settings.research = false;
  let release!: () => void,
    first = true,
    entered = false;
  const w = new Worker(
    s,
    fakeAI(s, async () => {
      if (first) {
        first = false;
        entered = true;
        await new Promise<void>((r) => (release = r));
      }
    }),
  );
  w.start();
  await until(() => entered);
  const f = s.state.families[0];
  await w.action(f.id, "rebuild", {});
  release();
  await until(() => !w.busy);
  assert.equal(f.revision, 2);
  assert.equal(s.state.run.status, "complete");
});
test("interrupted run recovers as paused without discarding checkpoints", (t) => {
  const dir = mkdtempSync(path.join(tmpdir(), "borderlens-restart-"));
  let s = new Store(dir);
  importZip(s, capture(), "data.zip");
  const f = s.state.families[0];
  f.stage = "validate";
  f.status = "running";
  s.state.run = {
    ...s.state.run,
    status: "running",
    queue: [f.id],
    currentId: f.id,
  };
  s.put(f.id, "draft", { saved: true });
  s.save();
  s.close();
  s = new Store(dir);
  t.after(() => {
    s.close();
    rmSync(dir, { recursive: true, force: true });
  });
  assert.equal(s.state.run.status, "paused");
  assert.equal(s.family(f.id).stage, "validate");
  assert.deepEqual(s.get(f.id, "draft"), { saved: true });
});
test("validation rejects unsupported evidence IDs, engine prose and false ranges", (t) => {
  const s = fixture(t);
  importZip(s, capture(), "data.zip");
  const f = s.state.families[0],
    p = buildPacket(s, f);
  const d = Draft.parse({
    entry: entry(f),
    partDefinitions: [],
    claims: [
      {
        field: "summary",
        evidenceIds: [p.evidence[0].id],
        basis: "Captured family.",
      },
      {
        field: "description",
        evidenceIds: [p.evidence[0].id],
        basis: "Fixture description.",
      },
    ],
    uncertainties: [],
    conflicts: [],
    requiresReview: false,
    reviewReason: null,
  });
  validateDraft(d, p);
  assert.throws(
    () =>
      validateDraft(
        {
          ...d,
          partDefinitions: [],
          claims: [{ ...d.claims[0], evidenceIds: ["invented"] }],
        },
        p,
      ),
    /unavailable/,
  );
  assert.throws(
    () =>
      validateDraft(
        {
          ...d,
          entry: {
            ...d.entry,
            summary: "Weapon uses gd_weap_smg engine data.",
          },
        },
        p,
      ),
    /debug/,
  );
  assert.throws(
    () =>
      validateDraft(
        {
          ...d,
          entry: { ...d.entry, levels: { minimum: 10, maximum: 1, notes: "" } },
          partDefinitions: [],
          claims: [
            ...d.claims,
            { field: "levels", evidenceIds: [p.evidence[0].id], basis: "test" },
          ],
        },
        p,
      ),
    /Minimum/,
  );
});
test("local HTTP service protects origins, exports schema-valid JSON, fully resets disk", async (t) => {
  const s = fixture(t);
  importZip(s, capture(), "data.zip");
  const w = new Worker(s, fakeAI(s)),
    server = api(s, w).listen(0, "127.0.0.1");
  await new Promise<void>((r) => server.once("listening", r));
  t.after(() => server.close());
  const port = (server.address() as any).port,
    base = `http://127.0.0.1:${port}`;
  assert.equal(
    (
      await fetch(base + "/api/state", {
        headers: { Origin: "https://example.org" },
      })
    ).status,
    403,
  );
  const missing = await fetch(base + "/api/items/nope");
  assert.equal(missing.status, 404);
  const f = s.state.families[0];
  await w.action(f.id, "save-output", { output: entry(f) });
  const r = await fetch(base + "/api/export");
  const z = new AdmZip(Buffer.from(await r.arrayBuffer()));
  assert.deepEqual(
    z.getEntries().map((e) => e.entryName),
    ["weapons/hellfire.json"],
  );
  assert.equal(JSON.parse(z.readAsText("weapons/hellfire.json")).id, f.id);
  assert.equal(
    JSON.parse(z.readAsText("weapons/hellfire.json")).schemaVersion,
    "3",
  );
  writeFileSync(path.join(s.dir, "ai", "test-cache"), "cached");
  const reset = await fetch(base + "/api/reset", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scope: "all", confirmation: "RESET" }),
  });
  assert.equal(reset.status, 200);
  assert.equal(s.records.size, 0);
  assert.equal(s.state.families.length, 0);
  assert.equal(existsSync(path.join(s.dir, "ai", "test-cache")), false);
});
test(
  "Postman simulation: real research HTTP, continuation, saved HTML, robots and failures",
  { skip: !process.env.BORDERLENS_SIMULATION },
  async (t) => {
    const s = fixture(t);
    importZip(s, capture(), "data.zip");
    const research = new Research(s, fetch, process.env.BORDERLENS_SIMULATION);
    const f = s.state.families[0];
    const page = await research.fetchPage(
      f,
      "https://borderlands.fandom.com/wiki/Hellfire_(Borderlands)",
    );
    assert.match(page.text, /Borderlands 1/);
    assert.equal(existsSync(path.join(s.dir, "sources", page.filename)), true);
    await assert.rejects(
      () => research.fetchText("https://borderlands.fandom.com/wiki/blocked"),
      /disallows/,
    );
    await assert.rejects(
      () =>
        research.fetchText("https://borderlands.fandom.com/wiki/upstream-fail"),
      /503/,
    );
    await assert.rejects(
      () => research.fetchText("https://example.org/wiki/foo"),
      /HTTPS wiki/,
    );
    const inventory = await research.inventory(() => {});
    assert.ok(inventory.some((e) => e.name === "Thunder"));
    assert.ok(
      compareCoverage(inventory, s.state.families).some(
        (e) => e.status === "matched",
      ),
    );
    assert.equal(s.state.coverage.errors.length, 0);
  },
);
test("validation errors receive bounded AI repair; unresolved identity conflicts still block", async (t) => {
  const s = fixture(t);
  importZip(s, capture(), "data.zip");
  s.state.settings.research = false;
  const good = fakeAI(s);
  let calls = 0;
  const w = new Worker(s, {
    ...good,
    run: async (...args) => {
      const d: any = await good.run(...args);
      if (calls++ === 0) d.claims = [];
      return d;
    },
  });
  w.start(undefined, s.state.families[0].id);
  await until(() => !w.busy);
  assert.equal(s.state.families[0].status, "done");
  assert.equal(calls, 2);
  const f = s.state.families[1];
  w.ai = {
    ...good,
    run: async (...args) => ({
      ...((await good.run(...args)) as any),
      requiresReview: true,
      reviewReason: "Unresolved family identity.",
    }),
  };
  w.start(undefined, f.id);
  await until(() => !w.busy);
  assert.equal(f.status, "blocked");
  assert.match(f.issue!, /Unresolved family identity/);
});

test("capture rows and project checkpoints roll back together if saving fails", (t) => {
  const s = fixture(t),
    save = s.save.bind(s);
  s.save = () => {
    throw new Error("Simulated checkpoint failure");
  };
  assert.throws(
    () => importZip(s, capture(), "interrupted.zip"),
    /checkpoint failure/,
  );
  assert.equal(s.state.captures.length, 0);
  assert.equal(s.records.size, 0);
  assert.equal(
    (s.db.prepare("SELECT count(*) AS total FROM raw").get() as any).total,
    0,
  );
  s.save = save;
  assert.equal(importZip(s, capture(), "retry.zip").families, 2);
});

test("effect prose rejects internals and requires saved-page claims", (t) => {
  const s = fixture(t);
  importZip(s, capture(), "data.zip");
  const f = s.state.families[0],
    p = buildPacket(s, f);
  p.evidence.push({
    id: "page:test",
    kind: "page",
    label: "Saved ability",
    value: { text: "Fixture gameplay effect" },
  });
  const d: any = {
    entry: {
      ...entry(f),
      specialEffects: ["Shots create a small fire explosion."],
    },
    partDefinitions: [],
    claims: [
      { field: "summary", evidenceIds: [p.evidence[0].id], basis: "Identity" },
      {
        field: "specialEffects",
        evidenceIds: [p.evidence[0].id],
        basis: "Raw definition",
      },
      {
        field: "description",
        evidenceIds: [p.evidence[0].id],
        basis: "Fixture description.",
      },
    ],
    uncertainties: [],
    conflicts: [],
    requiresReview: false,
    reviewReason: null,
  };
  assert.throws(() => validateDraft(d, p), /must cite/);
  d.claims[1].evidenceIds = ["page:test"];
  validateDraft(d, p);
  d.entry.specialEffects = [
    "Its defining accessory adds 14 elemental tech levels.",
  ];
  assert.throws(() => validateDraft(d, p), /too technical/);
  d.entry.specialEffects = ["word ".repeat(46)];
  assert.throws(() => validateDraft(d, p), /45 words/);
});

test(
  "Postman: cached Lootlemon does not skip missing wiki; provider failures stay visible",
  { skip: !process.env.BORDERLENS_SIMULATION },
  async (t) => {
    const s = fixture(t);
    importZip(s, capture(), "data.zip");
    s.state.coverage.status = "complete";
    const f = s.state.families[0];
    const research = new Research(s, fetch, process.env.BORDERLENS_SIMULATION);
    research.save(
      f,
      "https://www.lootlemon.com/weapon/hellfire-bl1",
      "<main><h1>Hellfire</h1><p>Test-only cached item ability description for the research fixture; not real weapon mechanics.</p></main>",
    );
    f.sourceUrls = ["https://www.lootlemon.com/weapon/hellfire-bl1"];
    let searches = 0;
    const ai: AI = {
      status: async () => ({ chatgpt: true }),
      run: async (_label, prompt, schema) => {
        searches++;
        assert.match(prompt, /missing providers: Wiki/);
        return schema.parse({
          matches: [
            {
              url: "https://borderlands.fandom.com/wiki/Hellfire_(Borderlands)",
              title: "Hellfire",
              gameEvidence: "BL1 fixture",
              reason: "Test matching page",
            },
          ],
          notFoundReason: null,
        });
      },
    };
    const w = new Worker(s, ai, research);
    await w.step(f);
    await w.step(f);
    assert.equal(searches, 1);
    assert.equal(s.sources(f.id).length, 2);
    assert.ok(
      s
        .get<any>(f.id, "research")
        .providers.every((r: any) => r.status === "saved"),
    );
    const other = s.state.families[1];
    research.save(
      other,
      "https://www.lootlemon.com/weapon/hellfire-bl1",
      "<main><h1>Test fixture</h1><p>This synthetic saved article exists only to verify a failure in the second provider does not discard an existing cache.</p></main>",
    );
    other.sourceUrls = ["https://borderlands.fandom.com/wiki/denied"];
    await w.collectSources(other);
    const report = s.get<any>(other.id, "research");
    assert.equal(
      report.providers.find((r: any) => r.provider === "Wiki").status,
      "unavailable",
    );
    assert.match(
      report.providers.find((r: any) => r.provider === "Wiki").message,
      /403/,
    );
    await w.collectSources(other);
    assert.equal(s.sources(other.id).length, 1);
    assert.equal(searches, 1);
  },
);
