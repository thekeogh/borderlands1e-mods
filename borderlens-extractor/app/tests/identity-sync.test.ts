import { equipmentTypes } from "../src/shared/manual-type.ts";
import { weaponTypes, catalogueGroup } from "../src/shared/taxonomy.ts";
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import AdmZip from "adm-zip";
import { Store, hash } from "../src/server/store.ts";
import { importZip } from "../src/server/importer.ts";
import { Research } from "../src/server/research.ts";
import { Worker } from "../src/server/worker.ts";
import { buildPacket } from "../src/server/evidence.ts";
import { checkedType, reviewType } from "../src/server/identity-sync.ts";
import { PublicEntry } from "../src/shared/models.ts";
import { TypeSyncDecision } from "../src/shared/identity-sync.ts";
import {
  CATALOGUE_SCHEMA_VERSION,
  COMPILER_VERSION,
} from "../src/shared/versions.ts";
import { websiteEntry, websiteZip } from "../src/server/website-export.ts";
import { api } from "../src/server/http.ts";
import { effortForTask } from "../src/shared/agents.ts";
const shieldQuote = "Ironclad is an obtainable Pangolin shield in Borderlands.";
function setup(t: any, name = "Ironclad") {
  const dir = mkdtempSync(path.join(tmpdir(), "sync-identity-")),
    s = new Store(dir),
    z = new AdmZip();
  const row = {
    id: "raw",
    record_type: "object",
    class: "WillowGame.ItemNamePartDefinition",
    path: "dlc3_gd_item_UniqueParts.Title.Title_P_Pangolin_Ironclad",
    properties: { PartName: name },
  };
  const buf = Buffer.from(JSON.stringify([row]));
  z.addFile("data/0001.json", buf);
  z.addFile(
    "manifest.json",
    Buffer.from(
      JSON.stringify({
        format_version: 1,
        extractor_version: "fixture",
        chunks: [{ file: "data/0001.json", records: 1, sha256: hash(buf) }],
      }),
    ),
  );
  importZip(s, z.toBuffer(), "identity.zip");
  const f = s.state.families[0],
    page = new Research(s).save(
      f,
      "https://www.lootlemon.com/shield/ironclad-bl1",
      `<main><h1>Ironclad • BL1 Shield</h1><p>${shieldQuote}</p></main>`,
      true,
    );
  t.after(() => {
    s.close();
    rmSync(dir, { recursive: true, force: true });
  });
  return { s, f, page };
}
function decision(x: ReturnType<typeof setup>) {
  return TypeSyncDecision.parse({
    category: "Shields",
    weaponType: null,
    identityVerified: true,
    availability: "obtainable",
    confidence: "high",
    identityPaths: x.f.roots,
    reason:
      "Exact saved title/type and extracted identity identify the shield.",
    conflicts: [],
    evidence: [{ id: x.page.id, quote: shieldQuote }],
  });
}
function entry(x: ReturnType<typeof setup>) {
  return PublicEntry.parse({
    schemaVersion: CATALOGUE_SCHEMA_VERSION,
    compilerVersion: COMPILER_VERSION,
    id: x.f.id,
    name: x.f.name,
    category: x.f.category,
    weaponType: null,
    dlc: "The Secret Armory of General Knoxx",
    summary: "An independent shield description for a metadata-only test.",
    description: [
      "Original player wording stays exactly as saved when this item is moved.",
    ],
    details: [],
    variants: [],
    parts: [],
    manufacturers: ["Pangolin"],
    rarities: [],
    elements: [],
    redText: null,
    specialEffects: [],
    levels: { minimum: null, maximum: null, notes: "" },
    stats: [],
    sources: [],
    notes: [],
    references: [],
  });
}
test("Sync type moves an unbuilt item and its inheritance immediately without generating JSON, fetching or changing queues", async (t) => {
  const x = setup(t),
    { s, f } = x;
  const raw = JSON.stringify([...s.records]),
    roots = JSON.stringify(f.roots),
    run = JSON.stringify(s.state.run);
  const parent = s.ensureScope({ category: "Shields" });
  parent.sourceUrls.push("https://borderlands.fandom.com/wiki/Shield");
  s.save();
  let calls = 0;
  const w = new Worker(s, {
    run: async (label: string, _p: string, schema: any) => {
      calls++;
      assert.equal(effortForTask(label), "medium");
      assert(label.startsWith("Sync item type"));
      return schema.parse(decision(x));
    },
  } as any);
  w.research.fetchPage = async () => {
    throw Error("Must not fetch");
  };
  const result = await w.syncIdentity(f.id, "type");
  assert(result.changed);
  assert.equal(calls, 1);
  assert.equal(f.category, "Shields");
  assert.equal(f.subtype, "Shields");
  assert.equal(s.get(f.id, "output"), null);
  assert.equal(JSON.stringify(s.state.run), run);
  assert.equal(JSON.stringify([...s.records]), raw);
  assert.equal(JSON.stringify(f.roots), roots);
  assert(s.inheritedEvidence(f).some((row) => row.url.includes("/Shield")));
  assert.equal(w.identitySync, null);
  assert(!w.busy);
});
test("Sync type patches output, drafts and packets atomically, preserving prose, readiness and paused batch/checkpoint", async (t) => {
  const x = setup(t),
    { s, f } = x,
    e = entry(x);
  f.status = "done";
  f.stage = "complete";
  f.revision = 2;
  s.put(f.id, "output", e);
  s.put(f.id, "draft", { entry: e, claims: [], partDefinitions: [] });
  s.put(f.id, "manualDraft", { entry: e, claims: [], partDefinitions: [] });
  s.put(f.id, "packet", buildPacket(s, f));
  s.put(f.id, "validatedPacket", buildPacket(s, f));
  s.state.run.status = "paused";
  s.state.run.queue = [f.id];
  s.state.buildCheckpoint = structuredClone(s.state.run);
  s.save();
  const run = JSON.stringify(s.state.run),
    checkpoint = JSON.stringify(s.state.buildCheckpoint);
  const w = new Worker(s, { run: async () => decision(x) } as any);
  const result = await w.syncIdentity(f.id, "type");
  assert(result.changed);
  assert.equal(f.status, "done");
  assert.equal(f.stage, "complete");
  assert.equal(f.revision, 3);
  for (const k of ["output", "draft", "manualDraft"]) {
    const saved = s.get<any>(f.id, k);
    const value = k === "output" ? saved : saved.entry;
    assert.equal(value.category, "Shields");
    assert.deepEqual(value.description, e.description);
  }
  for (const k of ["packet", "validatedPacket"])
    assert.equal(s.get<any>(f.id, k).category, "Shields");
  assert.equal(websiteEntry(s, f)!.category, "Shields");
  assert.deepEqual(
    new AdmZip(websiteZip(s)).getEntries().map((e) => e.entryName),
    ["shields/ironclad.json"],
  );
  assert.equal(JSON.stringify(s.state.run), run);
  assert.equal(JSON.stringify(s.state.buildCheckpoint), checkpoint);
});
test("explicit Sync name updates manual saved JSON metadata with one verification, retaining wording and all type fields", async (t) => {
  const x = setup(t, "Rifle"),
    { s, f } = x;
  f.category = "Weapons";
  f.subtype = "Eridian weapons";
  f.manualOutput = true;
  f.gameOnly = true;
  const quote = "Eridian Rifle is an obtainable Eridian weapon in Borderlands.",
    page = new Research(s).save(
      f,
      "https://www.lootlemon.com/weapon/eridian-rifle-bl1",
      `<h1>Eridian Rifle</h1><p>${quote}</p>`,
      true,
    );
  const e = { ...entry(x), weaponType: "Eridian weapons" };
  f.status = "done";
  f.stage = "complete";
  f.revision = 1;
  s.put(f.id, "output", e);
  s.put(f.id, "manualDraft", { entry: e });
  s.save();
  let calls = 0;
  const w = new Worker(s, {
    run: async (label: string, _p: string, schema: any) => {
      calls++;
      assert(label.startsWith("Sync item name"));
      return schema.parse({
        decision: {
          name: "Eridian Rifle",
          identityVerified: true,
          availability: "obtainable",
          identityPaths: f.roots,
          reason:
            "The saved name and extracted type corroborate this released identity.",
          conflicts: [],
          evidence: [{ id: page.id, quote }],
          corroboration: [{ kind: "weaponType", id: page.id, quote }],
        },
      });
    },
  } as any);
  assert((await w.syncIdentity(f.id, "name")).changed);
  assert.equal(calls, 1);
  assert.equal(f.name, "Eridian Rifle");
  assert.equal(f.rawName, "Rifle");
  assert(f.manualOutput && f.gameOnly);
  assert.equal(f.status, "done");
  assert.deepEqual(s.get<any>(f.id, "output").description, e.description);
  assert.equal(s.get<any>(f.id, "manualDraft").entry.name, "Eridian Rifle");
  assert.equal(websiteEntry(s, f)!.slug, "eridian-rifle");
  s.put(f.id, "output", { ...s.get<any>(f.id, "output"), name: "Rifle" });
  w.ai = { run: async () => ({ decision: null }) } as any;
  assert((await w.syncIdentity(f.id, "name")).changed);
  assert.equal(s.get<any>(f.id, "output").name, "Eridian Rifle");
});
test("uncertainty, false quotes, generated JSON-only proof, prototypes and manual overrides do not reclassify items", async (t) => {
  const x = setup(t),
    p = buildPacket(x.s, x.f),
    good = decision(x);
  for (const bad of [
    { ...good, confidence: "uncertain" },
    { ...good, identityPaths: ["another"] },
    { ...good, evidence: [{ id: "json:output", quote: shieldQuote }] },
    {
      ...good,
      evidence: [
        {
          id: x.page.id,
          quote: "Ironclad is a grenade mod and is not a shield.",
        },
      ],
      category: "Grenade mods",
    },
    { ...good, availability: "cut" },
    { ...good, conflicts: ["identity differs"] },
  ])
    assert.equal(checkedType(x.s, x.f, p, bad as any), null);
  const w = new Worker(x.s, {
    run: async () => ({ ...good, confidence: "uncertain" }),
  } as any);
  assert(!(await w.syncIdentity(x.f.id, "type")).changed);
  assert.equal(x.f.category, "Other equipment");
  x.s.classifications.set(x.f.id, "manual", {
    name: x.f.name,
    category: "Shields",
    weaponType: null,
    reason: "Manual choice",
    verifiedAt: "now",
    evidence: [],
  });
  x.s.save();
  w.ai = {
    run: async () => {
      throw Error("Manual priority must skip AI");
    },
  } as any;
  assert(!(await w.syncIdentity(x.f.id, "type")).changed);
  assert.equal(x.f.category, "Shields");
  x.s.classifications.set(x.f.id, "manual", null);
  x.s.save();
  w.ai = {
    run: async () => {
      x.s.classifications.set(x.f.id, "manual", {
        name: x.f.name,
        category: "Grenade mods",
        weaponType: null,
        reason: "Manual change during verification",
        verifiedAt: "now",
        evidence: [],
      });
      return good;
    },
  } as any;
  assert(!(await w.syncIdentity(x.f.id, "type")).changed);
  assert.equal(x.f.category, "Grenade mods");
});
test("sync API exposes live progress, rejects concurrent writes and leaves the build checkpoint intact", async (t) => {
  const x = setup(t),
    { s, f } = x;
  let release!: (value: any) => void;
  const w = new Worker(s, {
    run: async (
      _label: string,
      _prompt: string,
      _schema: any,
      _model: string,
      _web: boolean,
      progress: (message: string) => void,
    ) => {
      progress("Reading exact type proof");
      return new Promise((r) => (release = r));
    },
  } as any);
  const server = api(s, w).listen(0, "127.0.0.1");
  await new Promise<void>((r) => server.once("listening", r));
  t.after(() => server.close());
  const base = `http://127.0.0.1:${(server.address() as any).port}`,
    run = JSON.stringify(s.state.run);
  const post = (url: string, data: any) =>
    fetch(base + url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
  const request = post(`/api/items/${f.id}/sync`, { target: "type" });
  for (let i = 0; i < 50 && !w.identitySync; i++)
    await new Promise((r) => setTimeout(r, 5));
  assert(w.identitySync);
  const live = await fetch(base + "/api/state").then((r) => r.json());
  assert.equal(live.identitySync.familyId, f.id);
  assert.equal((await post("/api/run", { action: "start" })).status, 409);
  assert.equal(
    (await post(`/api/items/${f.id}/sync`, { target: "name" })).status,
    409,
  );
  assert.equal(
    (await post("/api/reset", { scope: "all", confirmation: "RESET" })).status,
    409,
  );
  assert.equal((await fetch(base + `/api/items/${f.id}`)).status, 200);
  assert.throws(() => w.start(), /metadata sync/);
  release(decision(x));
  assert.equal((await request).status, 200);
  assert.equal(JSON.stringify(s.state.run), run);
  assert.equal(w.identitySync, null);
  assert(!w.busy);
});
test("invalid retained JSON cannot leave a partially applied override; failed agent calls release the sync lock", async (t) => {
  const x = setup(t),
    { s, f } = x,
    e = entry(x);
  e.parts = [
    { partId: "part-1234567890abcdef", relationship: "defining", notes: "" },
  ];
  s.put(f.id, "output", e);
  f.status = "done";
  f.stage = "complete";
  s.save();
  const w = new Worker(s, { run: async () => decision(x) } as any);
  await assert.rejects(w.syncIdentity(f.id, "type"), /Missing inline part/);
  assert.equal(f.category, "Other equipment");
  assert.equal(s.classifications.data.entries[f.id], undefined);
  assert.equal(w.identitySync, null);
  assert(!w.busy);
  w.ai = {
    run: async () => {
      throw Error("capacity");
    },
  } as any;
  await assert.rejects(w.syncIdentity(f.id, "type"), /capacity/);
  assert(!w.busy);
  assert.equal(w.identitySync, null);
});

test("title and actual defining-body property subsets jointly prove type; rarity/prefix observations do not block", async (t) => {
  const x = setup(t),
    { s, f } = x;
  const body = "dlc3_gd_item_UniqueParts.Shield.body3_Pangolin_Ironclad";
  s.records.set(body.toLowerCase(), {
    id: "body",
    path: body,
    record_type: "object",
    class: "WillowGame.ItemPartDefinition",
    properties: {
      TitleList: [{ $ref: f.roots[0] }],
      PrefixList: [{ $ref: "gd_shields.Prefix.Prefix_Max1_Reinforced" }],
      GestaltModeSkeletalMeshName: "Shield_Pickup_C-3",
      PartName: "",
    },
  });
  const p = buildPacket(s, f),
    title = p.evidence.find((e) => e.path === f.roots[0])!,
    part = p.evidence.find((e) => e.path === body)!;
  assert.equal((part.value as any).role, "family-defining");
  const d = {
    ...decision(x),
    identityPaths: [...f.roots, body],
    conflicts: [
      "Raw rarity calls it legendary while the articles call it pearlescent.",
      "The prefix list allows Reinforced and Hardened but the wiki names only Hardened.",
    ],
    evidence: [
      { id: title.id, quote: JSON.stringify({ PartName: f.name }) },
      {
        id: part.id,
        quote: JSON.stringify({
          path: body,
          GestaltModeSkeletalMeshName: "Shield_Pickup_C-3",
          TitleList: [f.roots[0]],
        }),
      },
    ],
  };
  const review = reviewType(s, f, p, d);
  assert(review.evidence);
  assert.equal(review.contextNotes.length, 2);
  assert.equal(review.ignored.length, 0);
  const changed = await new Worker(s, {
    run: async () => d,
  } as any).syncIdentity(f.id, "type");
  assert(changed.changed);
  assert.equal(f.category, "Shields");
  const invented = {
    ...d,
    evidence: [
      { id: part.id, quote: JSON.stringify({ ImaginaryShieldFlag: true }) },
    ],
  };
  assert.equal(checkedType(s, f, p, invented), null);
  assert.equal(
    checkedType(s, f, p, {
      ...d,
      conflicts: ["It is a different item family despite the same prefix."],
    }),
    null,
  );
});
test("invalid redundant citations are audited while exact primary identity/type proof can still pass", (t) => {
  const x = setup(t),
    p = buildPacket(x.s, x.f),
    d = decision(x);
  const result = reviewType(x.s, x.f, p, {
    ...d,
    evidence: [
      ...d.evidence,
      {
        id: "page:invented",
        quote: "A fabricated unsupported statement about a shield.",
      },
    ],
  });
  assert(result.evidence);
  assert.equal(result.evidence.length, 1);
  assert(result.ignored[0].includes("unavailable"));
});

test("manual picker covers every equipment/weapon type with no AI, fetch, raw changes, generated JSON or queued work", (t) => {
  const x = setup(t),
    { s, f } = x;
  const w = new Worker(s, {
    run: async () => {
      throw Error("Manual changes must not call AI");
    },
  } as any);
  w.research.fetchPage = async () => {
    throw Error("Manual changes must not fetch");
  };
  const roots = JSON.stringify(f.roots),
    raw = JSON.stringify([...s.records]),
    run = JSON.stringify(s.state.run);
  for (const type of [...weaponTypes, ...equipmentTypes]) {
    assert(w.setManualType(f.id, type).changed);
    assert.equal(
      f.category,
      weaponTypes.includes(type as any) ? "Weapons" : type,
    );
    assert.equal(catalogueGroup(f), type);
    assert.equal(f.classification?.origin, "manual");
    assert.equal(s.get(f.id, "output"), null);
    assert.equal(f.revision, 0);
  }
  assert(w.setManualType(f.id, null).changed);
  assert.equal(f.category, "Other equipment");
  assert.equal(f.classification, undefined);
  assert.equal(JSON.stringify(f.roots), roots);
  assert.equal(JSON.stringify([...s.records]), raw);
  assert.equal(JSON.stringify(s.state.run), run);
});
test("manual cross-category changes keep completed and manual JSON ready, update export and restore research on Automatic", (t) => {
  const x = setup(t),
    { s, f } = x,
    e = entry(x);
  s.classifications.set(f.id, "research", {
    name: f.name,
    category: "Shields",
    weaponType: null,
    reason: "Saved shield proof",
    verifiedAt: "now",
    evidence: [],
  });
  s.save();
  const saved = { ...e, category: "Shields" };
  s.put(f.id, "output", saved);
  s.put(f.id, "manualDraft", { entry: saved });
  f.status = "done";
  f.stage = "complete";
  f.revision = 1;
  f.manualOutput = true;
  s.state.run.status = "paused";
  s.state.run.queue = [f.id];
  s.state.buildCheckpoint = structuredClone(s.state.run);
  s.save();
  const run = JSON.stringify(s.state.run),
    checkpoint = JSON.stringify(s.state.buildCheckpoint);
  const w = new Worker(s, {
    run: async () => {
      throw Error("No AI");
    },
  } as any);
  s.put(f.id, "sourceLedgerInput", "keep-unchanged-analysis");
  w.setManualType(f.id, "Shields");
  assert.equal(s.get(f.id, "sourceLedgerInput"), "keep-unchanged-analysis");
  assert.equal(f.revision, 1);
  w.setManualType(f.id, null);
  assert.equal(s.get(f.id, "sourceLedgerInput"), "keep-unchanged-analysis");
  w.setManualType(f.id, "SMGs");
  assert.equal(s.get(f.id, "sourceLedgerInput"), null);
  assert.equal(f.category, "Weapons");
  assert.equal(f.status, "done");
  assert.equal(f.stage, "complete");
  assert.equal(f.revision, 2);
  assert(f.manualOutput);
  assert.equal(s.get<any>(f.id, "output").weaponType, "SMGs");
  assert.deepEqual(s.get<any>(f.id, "output").description, e.description);
  assert.equal(s.get<any>(f.id, "manualDraft").entry.category, "Weapons");
  assert.deepEqual(
    new AdmZip(websiteZip(s)).getEntries().map((e) => e.entryName),
    ["weapons/ironclad.json"],
  );
  w.setManualType(f.id, "Class mods");
  assert.equal(f.category, "Class mods");
  assert.equal(s.get<any>(f.id, "output").weaponType, null);
  w.setManualType(f.id, null);
  assert.equal(f.category, "Shields");
  assert.equal(f.classification?.origin, "research");
  assert.equal(s.get<any>(f.id, "output").category, "Shields");
  assert.equal(JSON.stringify(s.state.run), run);
  assert.equal(JSON.stringify(s.state.buildCheckpoint), checkpoint);
  const reopened = new Store(s.dir);
  try {
    assert.equal(reopened.family(f.id).category, "Shields");
  } finally {
    reopened.close();
  }
});
test("manual type API validates choices, respects worker/removal locks and persists equipment overrides across restart", async (t) => {
  const { s, f } = setup(t),
    w = new Worker(s, {
      run: async () => {
        throw Error("No AI");
      },
    } as any),
    server = api(s, w).listen(0, "127.0.0.1");
  await new Promise<void>((r) => server.once("listening", r));
  t.after(() => server.close());
  const url = `http://127.0.0.1:${(server.address() as any).port}/api/items/${f.id}/type`,
    post = (body: any) =>
      fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
  assert.equal((await post({ type: "banana" })).status, 400);
  assert.equal((await post({})).status, 400);
  assert.equal((await post({ type: "Shields", extra: true })).status, 400);
  w.busy = true;
  assert.equal((await post({ type: "Shields" })).status, 409);
  w.busy = false;
  f.status = "excluded";
  assert.equal((await post({ type: "Shields" })).status, 409);
  f.status = "queued";
  assert.equal((await post({ type: "Grenade mods" })).status, 200);
  assert.equal(f.category, "Grenade mods");
  const reopened = new Store(s.dir);
  try {
    assert.equal(reopened.family(f.id).category, "Grenade mods");
    assert.equal(reopened.family(f.id).classification?.origin, "manual");
  } finally {
    reopened.close();
  }
  assert.equal((await post({ type: null })).status, 200);
  assert.equal(f.category, "Other equipment");
});
