import { websiteEntry } from "../src/server/website-export.ts";
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import AdmZip from "adm-zip";
import { Store, hash } from "../src/server/store.ts";
import { importZip } from "../src/server/importer.ts";
import { buildPacket, validateDraft } from "../src/server/evidence.ts";
import { partCandidates, validateParts } from "../src/server/parts.ts";
import { parseSource } from "../src/server/source-content.ts";
import { PublicEntry, Draft, type Family } from "../src/shared/models.ts";
import { COMPILER_VERSION } from "../src/shared/versions.ts";
import { Worker } from "../src/server/worker.ts";
import { api } from "../src/server/http.ts";
const title = "gd_weap_patrol_smg.Title.Title_Fixture",
  partPath = "gd_weap_patrol_smg.acc.acc5_fixture";
function capture() {
  const rows = [
    {
      id: "title",
      path: title,
      record_type: "object",
      class: "WillowGame.WeaponNamePartDefinition",
      properties: { PartName: "Fixture" },
    },
    {
      id: "part",
      path: partPath,
      record_type: "object",
      class: "WillowGame.WeaponPartDefinition",
      properties: {
        TitleList: { $type: "array", items: [{ $ref: title }] },
        TechLevelIncrease: 5,
      },
    },
  ];
  const data = Buffer.from(JSON.stringify(rows)),
    zip = new AdmZip();
  zip.addFile("data/one.json", data);
  zip.addFile(
    "manifest.json",
    Buffer.from(
      JSON.stringify({
        format_version: 1,
        extractor_version: "fixture",
        chunks: [
          { file: "data/one.json", records: rows.length, sha256: hash(data) },
        ],
      }),
    ),
  );
  return zip.toBuffer();
}
function setup(t: any) {
  const dir = mkdtempSync(path.join(tmpdir(), "borderlens-rich-"));
  let store = new Store(dir);
  importZip(store, capture(), "fixture.zip");
  t.after(() => {
    store.close();
    rmSync(dir, { recursive: true, force: true });
  });
  return {
    get store() {
      return store;
    },
    reopen() {
      store.close();
      store = new Store(dir);
      return store;
    },
  };
}
function entry(f: Family) {
  return PublicEntry.parse({
    schemaVersion: "2",
    compilerVersion: COMPILER_VERSION,
    id: f.id,
    name: f.name,
    game: "borderlands-goty-enhanced",
    category: f.category,
    weaponType: "SMGs",
    summary: "A short and useful overview of the fixture family.",
    description: [
      "An original player-facing paragraph explains the fixture without inventing unsupported mechanics.",
    ],
    manufacturers: [],
    rarities: [],
    elements: [],
    redText: null,
    specialEffects: [],
    levels: { minimum: null, maximum: null, notes: "" },
    stats: [],
    sources: [],
    variants: [],
    parts: [],
    notes: [],
    references: [],
  });
}
function draft(store: Store) {
  const f = store.state.families[0],
    p = buildPacket(store, f),
    candidate = partCandidates(p)[0];
  return {
    p,
    d: Draft.parse({
      entry: {
        ...entry(f),
        parts: [
          {
            partId: candidate.id,
            relationship: "defining",
            notes: "This accessory is associated with the family name.",
          },
        ],
      },
      partDefinitions: [
        {
          schemaVersion: "1",
          compilerVersion: COMPILER_VERSION,
          id: candidate.id,
          name: "Fixture accessory",
          slot: "accessory",
          manufacturers: [],
          effects: [],
          notes: [],
        },
      ],
      claims: [
        {
          field: "summary",
          evidenceIds: [p.evidence[0].id],
          basis: "Fixture identity.",
        },
        {
          field: "description",
          evidenceIds: [p.evidence[0].id],
          basis: "Fixture identity.",
        },
        {
          field: "parts",
          evidenceIds: [candidate.evidenceId],
          basis: "Direct title list links this part to the fixture family.",
        },
      ],
      uncertainties: [],
      conflicts: [],
      requiresReview: false,
      reviewReason: null,
    }),
  };
}

test("rich schema applies to every equipment category and enforces summary and scoped chances", (t) => {
  const { store } = setup(t),
    e = entry(store.state.families[0]);
  for (const category of [
    "Weapons",
    "Shields",
    "Grenade mods",
    "Class mods",
    "Artifacts",
    "Other equipment",
  ])
    assert.equal(PublicEntry.parse({ ...e, category }).description.length, 1);
  assert.equal(
    PublicEntry.safeParse({ ...e, summary: "x".repeat(201) }).success,
    false,
  );
  assert.equal(PublicEntry.safeParse({ ...e, description: [] }).success, false);
  assert.equal(
    PublicEntry.safeParse({
      ...e,
      sources: [
        {
          label: "Fixture enemy",
          url: null,
          kind: "enemy",
          notes: "",
          location: "Test map",
          dlc: null,
          conditions: [],
          dropChance: { percent: 101, conditions: "Fixture only" },
        },
      ],
    }).success,
    false,
  );
});
test("cached source parsing retains useful headings and tables and strips active content", () => {
  const p = parseSource(
    "<main><h1>Fixture</h1><h2>Unique ability</h2><p>Useful gameplay explanation.</p><h2>Variants</h2><table><caption>Parts</caption><tr><th>Part</th><th>Effect</th></tr><tr><td>Barrel</td><td>Greater range</td></tr></table><script>untrusted instructions</script></main>",
  );
  assert.ok(
    p.sections.some(
      (s) => s.heading === "Unique ability" && s.text.includes("gameplay"),
    ),
  );
  assert.equal(p.tables[0].rows[1][1], "Greater range");
  assert.ok(!p.text.includes("untrusted"));
});
test("substantial copied prose is rejected; original rewriting passes", (t) => {
  const { store } = setup(t),
    { p, d } = draft(store);
  const copied =
    "This unusual weapon sends a fresh wave of burning projectiles towards nearby opponents every time the trigger is pulled.";
  p.evidence.push({
    id: "page:copy-test",
    kind: "page",
    label: "Fixture source",
    value: { text: copied },
  });
  d.entry.description = [copied];
  assert.throws(() => validateDraft(d, p), /verbatim/);
  d.entry.description = [
    "Its burning shots can pressure enemies nearby, offering a different way to deal with groups.",
  ];
  validateDraft(d, p);
});
test("parts require captured identity links; graph presence cannot establish required compatibility", (t) => {
  const { store } = setup(t),
    { p, d } = draft(store);
  validateParts(d, p);
  d.entry.parts[0].relationship = "required";
  assert.throws(() => validateParts(d, p), /selection rule/);
  d.entry.parts[0].relationship = "defining";
  d.entry.parts[0].partId = "part-0000000000000000";
  assert.throws(() => validateParts(d, p), /correspond|lacks/);
});
test("website export embeds parts in the item JSON without extra files", async (t) => {
  const { store } = setup(t),
    { p, d } = draft(store),
    f = store.state.families[0],
    w = new Worker(store);
  store.put(f.id, "packet", p);
  store.put(f.id, "draft", d);
  f.stage = "validate";
  await w.step(f);
  f.status = "done";
  store.save();
  assert.equal(
    store.get<any>(f.id, "output").parts[0].partId,
    d.partDefinitions[0].id,
  );
  const server = api(store, w).listen(0, "127.0.0.1");
  await new Promise<void>((r) => server.once("listening", r));
  t.after(() => server.close());
  const r = await fetch(
    `http://127.0.0.1:${(server.address() as any).port}/api/export`,
  );
  assert.equal(r.status, 200);
  const zip = new AdmZip(Buffer.from(await r.arrayBuffer()));
  assert.deepEqual(
    zip.getEntries().map((e) => e.entryName),
    ["weapons/fixture.json"],
  );
  const item = JSON.parse(zip.readAsText("weapons/fixture.json"));
  assert.equal(item.schemaVersion, "3");
  assert.equal(item.slug, "fixture");
  assert.equal(item.parts[0].name, "Fixture accessory");
  assert.equal(item.parts[0].relationship, "defining");
  assert.ok(!JSON.stringify(item.parts).includes("gd_weap"));
});
test("schema/compiler upgrades queue old output without losing its content or saved corrections", (t) => {
  const env = setup(t),
    s = env.store,
    f = s.state.families[0];
  const old = { ...entry(f), schemaVersion: "1" };
  delete (old as any).description;
  delete (old as any).parts;
  s.put(f.id, "output", old);
  s.put(f.id, "provenance", { compilerVersion: "older" });
  f.status = "done";
  f.notes = "Keep this editorial correction.";
  s.save();
  const reopened = env.reopen();
  const recovered = reopened.family(f.id);
  assert.equal(recovered.status, "queued");
  assert.equal(recovered.stage, "evidence");
  assert.deepEqual(reopened.get(f.id, "output"), old);
  assert.equal(recovered.notes, "Keep this editorial correction.");
});

test("manual prose edits retain previously verified part references", async (t) => {
  const { store } = setup(t),
    { p, d } = draft(store),
    f = store.state.families[0],
    w = new Worker(store);
  store.put(f.id, "packet", p);
  store.put(f.id, "draft", d);
  f.stage = "validate";
  await w.step(f);
  f.status = "done";
  const output = store.get<any>(f.id, "output");
  output.description = [
    "An edited paragraph adds useful player context while keeping the verified part reference intact.",
  ];
  await w.action(f.id, "save-output", { output });
  assert.equal(f.status, "done");
  assert.equal(
    store.get<any>(f.id, "output").description[0],
    output.description[0],
  );
  assert.equal(store.get<any[]>(f.id, "parts")?.length, 1);
});

test("self-contained Final JSON round-trips manual inline part edits without altering other items", async (t) => {
  const { store } = setup(t),
    { p, d } = draft(store),
    f = store.state.families[0],
    w = new Worker(store);
  store.put(f.id, "packet", p);
  store.put(f.id, "draft", d);
  f.stage = "validate";
  await w.step(f);
  f.status = "done";
  const website = websiteEntry(store, f)!;
  website.parts[0].notes = ["A manually reviewed item-specific part note."];
  website.description = [
    "A fresh manually reviewed paragraph keeps all part data within this item.",
  ];
  await w.action(f.id, "save-output", { output: website });
  assert.equal(f.status, "done");
  const saved = websiteEntry(store, f)!;
  assert.deepEqual(saved.parts[0].notes, website.parts[0].notes);
  assert.deepEqual(
    store.get<any>("_parts", website.parts[0].id).definition.notes,
    [],
  );
  assert.equal(saved.description[0], website.description[0]);
});
