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
    schemaVersion: "7",
    compilerVersion: COMPILER_VERSION,
    id: f.id,
    name: f.name,
    dlc: "Base Game",
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
          field: "dlc",
          evidenceIds: [p.evidence[0].id],
          basis: "Reviewed base-package fixture identity.",
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
  assert.equal(item.schemaVersion, "9");
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

test("rich sections retain useful prose, reject copied acquisition notes and public source labels", (t) => {
  const { store } = setup(t),
    { p, d } = draft(store);
  const quote =
    "This distinctive rifle creates a spreading cloud of fire that can ignite nearby enemies when several targets stand close together.";
  p.evidence.push({
    id: "page:details",
    kind: "page",
    label: "Saved source",
    value: { text: quote },
  });
  d.entry.details = [
    {
      heading: "Using the rifle",
      paragraphs: [
        "Its fire splash rewards shots aimed into densely packed enemy groups.",
      ],
    },
  ];
  d.claims.push({
    field: "details",
    evidenceIds: ["page:details"],
    basis: "Archived gameplay advice",
  });
  assert.doesNotThrow(() => validateDraft(d, p));
  d.entry.details[0].paragraphs = [
    "According to the wiki, this weapon is useful against groups.",
  ];
  assert.throws(() => validateDraft(d, p), /source-reporting labels/);
  d.entry.details[0].paragraphs = [
    "Its splash can set several nearby enemies alight.",
  ];
  d.entry.sources = [
    {
      label: "Fixture quest",
      url: null,
      kind: "quest",
      notes: quote,
      location: null,
      dlc: null,
      conditions: [],
      dropChance: null,
    },
  ];
  d.claims.push({
    field: "sources",
    evidenceIds: ["page:details"],
    basis: "Acquisition fixture",
  });
  assert.throws(() => validateDraft(d, p), /verbatim/);
});

test("restart retains a current-schema validation checkpoint while the last published output is older", (t) => {
  const env = setup(t),
    { p, d } = draft(env.store),
    f = env.store.state.families[0];
  env.store.put(f.id, "output", { ...d.entry, schemaVersion: "1" });
  env.store.put(f.id, "provenance", { compilerVersion: "older" });
  env.store.put(f.id, "draft", d);
  env.store.put(f.id, "packet", p);
  f.stage = "validate";
  f.status = "running";
  env.store.save();
  const recovered = env.reopen();
  assert.equal(recovered.family(f.id).stage, "validate");
  assert.equal(recovered.family(f.id).status, "queued");
  assert.deepEqual(recovered.get(f.id, "draft"), d);
  assert.deepEqual(
    recovered.get(f.id, "packet"),
    JSON.parse(JSON.stringify(p)),
  );
});

test("version upgrades also restart an older unfinished draft with no completed output", (t) => {
  const env = setup(t),
    f = env.store.state.families[0],
    { d } = draft(env.store);
  env.store.put(f.id, "draft", {
    ...d,
    entry: { ...d.entry, compilerVersion: "older" },
  });
  f.stage = "validate";
  f.status = "queued";
  env.store.save();
  const recovered = env.reopen();
  assert.equal(recovered.family(f.id).stage, "evidence");
  assert.equal(recovered.family(f.id).status, "queued");
  assert.equal(recovered.get(f.id, "draft"), null);
});

test("generic guide paragraphs are rejected in notes and mechanics, not just source extraction", (t) => {
  const { store } = setup(t),
    { p, d } = draft(store);
  d.entry.notes = [
    "Your last visited Fast Travel Station determines where you spawn; account for it when planning repeated farming runs.",
  ];
  assert.throws(() => validateDraft(d, p), /Generic fast-travel/);
  d.entry.notes = [];
  d.entry.details = [
    {
      heading: "Farming",
      paragraphs: ["Combine nearby loot sources and time your routes."],
    },
  ];
  assert.throws(() => validateDraft(d, p), /Generic farming/);
});

test("missing captured-part modifiers get one focused prose repair, preserving identity and final stats", async (t) => {
  const { repairMissingModifier } =
    await import("../src/server/modifier-repair.ts");
  const { MissingCatalogueStat, validateSourceUsage } =
    await import("../src/server/source-analysis.ts");
  const { store } = setup(t),
    { p, d } = draft(store),
    candidate = partCandidates(p)[0];
  p.evidence.push({
    id: "page:modifier",
    kind: "page",
    label: "Saved article",
    value: { text: "Damage: +30%", url: "https://example.org/modifier" },
  });
  const fact = {
    id: "page:modifier:0:0",
    sourceId: "page:modifier",
    field: "stats" as const,
    detail: "Unique accessory adds damage.",
    quote: "Damage: +30%",
    stat: {
      name: "Damage",
      minimum: 30,
      maximum: 30,
      unit: "%",
      level: null,
      notes: partPath.split(".").pop() + " damage modifier.",
    },
  };
  const ledger = [
    {
      sourceId: "page:modifier",
      url: "https://example.org/modifier",
      hash: "fixture",
      characters: 12,
      chunks: [
        {
          index: 0,
          characters: 12,
          reading: { facts: [fact], fields: [], proposedFields: [] },
          facts: [fact],
        },
      ],
    },
  ];
  d.sourceUsage = [
    {
      factId: fact.id,
      disposition: "used",
      fields: ["parts"],
      reason: "Accessory effect",
      duplicateOf: null,
    },
  ];
  d.claims
    .find((claim) => claim.field === "parts")!
    .evidenceIds.push("page:modifier");
  assert.throws(() => validateSourceUsage(d, ledger, p), MissingCatalogueStat);
  const identity = d.entry.id,
    stats = structuredClone(d.entry.stats);
  let calls = 0;
  const ai = {
    status: async () => ({}),
    run: async (_label: string, prompt: string, schema: any) => {
      calls++;
      assert.match(prompt, /30/);
      return schema.parse({
        paragraph: "This signature accessory increases damage by +30%.",
        effects: ["Increases damage by +30%."],
      });
    },
  };
  assert.equal(
    await repairMissingModifier(
      d,
      p,
      new MissingCatalogueStat(fact),
      ai,
      "",
      () => {},
    ),
    true,
  );
  assert.equal(calls, 1);
  assert.equal(d.entry.id, identity);
  assert.deepEqual(d.entry.stats, stats);
  assert.doesNotThrow(() => validateSourceUsage(d, ledger, p));
  assert.doesNotThrow(() => validateDraft(d, p));
  assert.doesNotThrow(() => validateParts(d, p));
  assert.equal(
    await repairMissingModifier(
      d,
      p,
      new MissingCatalogueStat({
        ...fact,
        stat: { ...fact.stat!, notes: "No matching captured part" },
      }),
      ai,
      "",
      () => {},
    ),
    false,
  );
  assert.equal(calls, 1);
  assert.equal(d.entry.parts[0].partId, candidate.id);
});

test("public quality rejects raw scope identifiers and vague damage benchmarks, while preserving precise human mechanics", (t) => {
  const { store } = setup(t),
    { p, d } = draft(store);
  for (const text of [
    "The sight4_Jakobs_Bessie gives greater magnification.",
    "Zoom End FOV -350%.",
    "This scope titles the Bessie family.",
    "With a suitable character, skills and class mod, it deals 12,000 damage in one shot.",
  ]) {
    d.entry.description = [text];
    assert.throws(() => validateDraft(d, p), /player-facing|benchmark/);
  }
  d.entry.description = [
    "The signature scope adds +30% damage and magnifies distant targets more strongly.",
  ];
  d.entry.stats = [
    {
      name: "Accuracy",
      context: "Card",
      minimum: 97.2,
      maximum: 98.8,
      unit: "",
      level: null,
      notes: "",
    },
    {
      name: "Accuracy",
      context: "While scoped",
      minimum: 100,
      maximum: 100,
      unit: "%",
      level: null,
      notes: "",
    },
  ];
  d.claims.push({
    field: "stats",
    evidenceIds: [p.evidence[0].id],
    basis: "Fixture ranges",
  });
  assert.doesNotThrow(() => validateDraft(d, p));
  d.entry.stats[1].context = "Card";
  assert.throws(() => validateDraft(d, p), /distinct evidenced contexts/);
});

test("base, multiplier and total stats get a focused cited repair, never swapping numbers or rewriting the entry", async (t) => {
  const { repairCatalogueStats } = await import("../src/server/stat-repair.ts");
  const { MissingCatalogueStat, validateSourceUsage } =
    await import("../src/server/source-analysis.ts");
  const { StatContextError } = await import("../src/server/evidence.ts");
  const { store } = setup(t),
    { p, d } = draft(store);
  const facts = [
    {
      value: 150,
      notes: "scale",
      detail: "The scope applies a multiplicative critical bonus.",
      context: "Scope multiplier",
    },
    {
      value: 200,
      notes: "Base sniper rifle",
      detail: "The rifle has the standard base critical bonus.",
      context: "Base sniper bonus",
    },
    {
      value: 500,
      notes: "Total",
      detail: "The combined critical bonus is the total after the scope.",
      context: "Total critical bonus",
    },
  ].map((item, i) => ({
    id: `page:crit:0:${i}`,
    field: "stats" as const,
    detail: item.detail,
    quote: `${item.notes}: +${item.value}%`,
    stat: {
      name: "Critical hit bonus",
      minimum: item.value,
      maximum: item.value,
      unit: "%",
      level: null,
      notes: item.notes,
    },
  }));
  p.evidence.push({
    id: "page:crit",
    kind: "page",
    label: "Saved mechanics",
    value: {
      text: facts.map((f) => f.quote).join(" "),
      url: "https://example.org/crit",
    },
  });
  const ledger = [
    {
      sourceId: "page:crit",
      url: "https://example.org/crit",
      hash: "h",
      characters: 100,
      chunks: [
        {
          index: 0,
          characters: 100,
          reading: { facts, fields: [], proposedFields: [] },
          facts,
        },
      ],
    },
  ];
  d.sourceUsage = facts.map((fact) => ({
    factId: fact.id,
    disposition: "used" as const,
    fields: ["details"],
    reason: "Critical mechanics",
    duplicateOf: null,
  }));
  d.entry.details = [
    {
      heading: "Mechanics",
      paragraphs: [
        "The critical-hit calculation uses a +200% base, a +150% multiplier and a +500% total.",
      ],
    },
  ];
  d.claims.push({
    field: "details",
    evidenceIds: ["page:crit"],
    basis: "Critical bonus roles",
  });
  d.entry.stats = [{ ...facts[2].stat, context: null }];
  const originalProse = structuredClone({
    description: d.entry.description,
    details: d.entry.details,
    parts: d.partDefinitions,
  });
  let calls = 0;
  const ai = {
    status: async () => ({}),
    run: async (_label: string, prompt: string, schema: any) => {
      calls++;
      assert.match(prompt, /Do NOT return or calculate numeric values/);
      return schema.parse({
        rows: facts.map((fact, i) => ({
          factId: fact.id,
          context: [
            "Scope multiplier",
            "Base sniper bonus",
            "Total critical bonus",
          ][i],
          notes: "",
        })),
      });
    },
  };
  assert.equal(
    await repairCatalogueStats(
      d,
      p,
      ledger,
      new MissingCatalogueStat({ ...facts[0], sourceId: "page:crit" }),
      ai,
      "",
      () => {},
    ),
    true,
  );
  assert.equal(calls, 1);
  assert.deepEqual(
    d.entry.stats.map((s) => [s.minimum, s.context]),
    [
      [150, "Scope multiplier"],
      [200, "Base sniper bonus"],
      [500, "Total critical bonus"],
    ],
  );
  assert.deepEqual(
    {
      description: d.entry.description,
      details: d.entry.details,
      parts: d.partDefinitions,
    },
    originalProse,
  );
  assert.doesNotThrow(() => validateDraft(d, p));
  assert.doesNotThrow(() => validateSourceUsage(d, ledger, p));
  d.entry.stats.forEach((s) => (s.context = null));
  assert.throws(() => validateDraft(d, p), StatContextError);
  assert.equal(
    await repairCatalogueStats(
      d,
      p,
      ledger,
      new StatContextError("Critical hit bonus"),
      ai,
      "",
      () => {},
    ),
    true,
  );
  assert.doesNotThrow(() => validateDraft(d, p));
  const before = structuredClone(d);
  const invalid = {
    status: async () => ({}),
    run: async (_label: string, _prompt: string, schema: any) =>
      schema.parse({
        rows: [{ factId: "invented", context: "Total", notes: "" }],
      }),
  };
  await assert.rejects(
    () =>
      repairCatalogueStats(
        d,
        p,
        ledger,
        new StatContextError("Critical hit bonus"),
        invalid,
        "",
        () => {},
      ),
    /every requested source fact/,
  );
  assert.deepEqual(d, before);
  // Exhausted full-draft retries must not bypass the focused repair path.
  d.entry.stats.forEach((stat) => (stat.context = null));
  const f = store.state.families[0];
  f.stage = "validate";
  store.put(f.id, "draft", d);
  store.put(f.id, "packet", p);
  store.put(f.id, "sourceLedger", ledger);
  store.put(f.id, "validationFeedback", { attempt: 2 });
  const worker = new Worker(store, ai);
  const previousCalls = calls;
  await worker.step(f);
  assert.equal(calls, previousCalls + 1);
  assert.equal(f.stage, "validate");
  assert.equal(store.get(f.id, "statRepairs"), 1);
  await worker.step(f);
  assert.equal(f.stage, "complete");
  assert.equal(calls, previousCalls + 1);
});

test("schema-changing upgrades archive validation drafts and retain paused work and source readings", (t) => {
  const env = setup(t),
    { store } = env,
    { p, d } = draft(store),
    f = store.state.families[0];
  const previous = structuredClone(d) as any;
  previous.entry.compilerVersion = "0.5.0";
  previous.entry.schemaVersion = "4";
  previous.partDefinitions.forEach(
    (part: any) => (part.compilerVersion = "0.5.0"),
  );
  store.put(f.id, "draft", previous);
  store.put(f.id, "packet", p);
  store.put(f.id, "sourceLedger", [{ retained: true }]);
  f.stage = "validate";
  f.status = "queued";
  store.state.run.status = "paused";
  store.state.run.queue = [f.id];
  store.state.run.index = 0;
  store.save();
  const reopened = env.reopen();
  assert.equal(reopened.state.run.status, "paused");
  assert.equal(reopened.state.families[0].stage, "evidence");
  assert.equal(reopened.get(f.id, "draft"), null);
  assert.deepEqual(reopened.get(f.id, "draft:compiler:0.5.0"), previous);
  assert.deepEqual(reopened.get(f.id, "sourceLedger"), [{ retained: true }]);
});

test("unclear scope wording gets one focused repair followed by whole-document validation", async (t) => {
  const { store } = setup(t),
    { p, d } = draft(store),
    f = store.state.families[0];
  d.partDefinitions[0].effects = [
    "Provides stronger magnification than the standard scopes compared with it.",
  ];
  const prose = structuredClone(d.entry.description);
  let calls = 0;
  const ai = {
    status: async () => ({}),
    run: async (label: string, prompt: string, schema: any) => {
      calls++;
      assert.match(label, /clarity/);
      assert.match(prompt, /must not invent a baseline/);
      return schema.parse({
        text: "The scope provides increased magnification.",
      });
    },
  };
  store.put(f.id, "draft", d);
  store.put(f.id, "packet", p);
  f.stage = "validate";
  const w = new Worker(store, ai);
  await w.step(f);
  assert.equal(f.stage, "validate");
  assert.equal(calls, 1);
  await w.step(f);
  assert.equal(f.stage, "complete");
  assert.equal(calls, 1);
  assert.deepEqual(store.get<any>(f.id, "output").description, prose);
  assert.ok(
    store.get<any>(f.id, "finalValidation").checks.includes("JSON syntax"),
  );
  assert.equal(
    websiteEntry(store, f)!.parts[0].effects[0],
    "The scope provides increased magnification.",
  );
});
test("whole-document errors cannot promote a draft; malformed submitted JSON gets HTTP 400", async (t) => {
  const { store } = setup(t),
    { p, d } = draft(store),
    f = store.state.families[0];
  const old = entry(f);
  store.put(f.id, "output", old);
  d.entry.sources = [
    {
      label: "Fixture",
      url: "javascript:alert(1)",
      kind: "enemy",
      location: null,
      dlc: null,
      notes: "",
      conditions: [],
      dropChance: null,
    },
  ];
  d.claims.push({
    field: "sources",
    evidenceIds: [p.evidence[0].id],
    basis: "Fixture acquisition",
  });
  store.put(f.id, "draft", d);
  store.put(f.id, "packet", p);
  f.stage = "validate";
  const w = new Worker(store);
  await w.step(f);
  assert.equal(f.stage, "draft");
  assert.match(
    store.get<any>(f.id, "validationFeedback").error,
    /HTTP or HTTPS/,
  );
  assert.deepEqual(store.get(f.id, "output"), old);
  assert.equal(store.get(f.id, "finalValidation"), null);
  const server = api(store, w).listen(0, "127.0.0.1");
  await new Promise<void>((r) => server.once("listening", r));
  t.after(() => server.close());
  const response = await fetch(
    `http://127.0.0.1:${(server.address() as any).port}/api/items/${f.id}/action`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: '{"action":"save-output","output":{"notes":["a "357" marking"]}}',
    },
  );
  assert.equal(response.status, 400);
  assert.deepEqual(store.get(f.id, "output"), old);
});

test("selection metadata must be bounded; ordinary full-page parsing remains unmarked", () => {
  const page = (boxes: string, warnings: string) =>
    `<html><head><meta name="borderlens-capture" content="selected"><meta name="borderlens-selection-count" content="${boxes}"><meta name="borderlens-selection-warnings" content="${warnings}"></head><body><main><p>Only selected text.</p></main></body></html>`;
  assert.deepEqual(parseSource(page("1", "0")).selectedContent, {
    boxes: 1,
    warnings: 0,
  });
  for (const [count, warnings] of [
    ["0", "0"],
    ["31", "0"],
    ["2", "3"],
    ["1.5", "0"],
    ["x", "0"],
  ])
    assert.equal(parseSource(page(count, warnings)).selectedContent, undefined);
  assert.equal(
    parseSource("<main><p>Ordinary full article.</p></main>").selectedContent,
    undefined,
  );
});
