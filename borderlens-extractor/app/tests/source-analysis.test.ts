import { partId } from "../src/server/parts.ts";
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { Store } from "../src/server/store.ts";
import {
  SourceReading,
  sourceChunks,
  readSources,
  validateSourceUsage,
  statChecklist,
} from "../src/server/source-analysis.ts";
import { emptySourceReading } from "./source-fixture.ts";
import type { AI } from "../src/server/worker.ts";
import type { Draft, Family, Packet } from "../src/shared/models.ts";

test("full source chunks retain every character, including late mechanics", () => {
  const text = "a".repeat(41000) + "Late mechanics: Damage 80–1423";
  const chunks = sourceChunks(text);
  assert.equal(chunks.join(""), text);
  assert.ok(chunks.at(-1)!.includes("Damage 80–1423"));
  assert.equal(sourceChunks("").length, 1);
});
test("each saved source is independently read and checkpointed; changed content invalidates only its reading", async (t) => {
  const dir = mkdtempSync(path.join(tmpdir(), "borderlens-read-")),
    store = new Store(dir);
  t.after(() => {
    store.close();
    rmSync(dir, { recursive: true, force: true });
  });
  const f = {
    id: "fixture",
    name: "Volcano",
    inputHash: "fixture-input",
    category: "Weapons",
    notes: "",
  } as Family;
  let calls = 0;
  const ai: AI = {
    status: async () => ({}),
    run: async (_label, prompt, schema) => {
      calls++;
      const reading = emptySourceReading();
      assert.match(prompt, /Published damage\/accuracy/);
      return schema.parse(reading);
    },
  };
  const save = (id: string, text: string) =>
    store.db.prepare("INSERT OR REPLACE INTO sources VALUES(?,?,?)").run(
      id,
      f.id,
      JSON.stringify({
        id,
        familyId: f.id,
        url: "https://example.org/" + id,
        title: id,
        hash: text,
        text,
        filename: "unused",
        contentVersion: 2,
      }),
    );
  save("wiki", "a".repeat(38000) + " late wiki fact");
  save("lootlemon", "other facts");
  const first = await readSources(store, ai, f, () => {});
  assert.equal(first.length, 2);
  assert.ok(first[0].chunks.length >= 3);
  const previous = calls;
  await readSources(store, ai, f, () => {});
  assert.equal(calls, previous);
  save("lootlemon", "changed data");
  await readSources(store, ai, f, () => {});
  assert.equal(calls, previous + 1);
  f.notes = "Manual correction";
  await readSources(store, ai, f, () => {});
  assert.ok(calls > previous + 1);
});
test("fabricated quotes and incomplete checklist stop source extraction", async (t) => {
  const dir = mkdtempSync(path.join(tmpdir(), "borderlens-read-bad-")),
    store = new Store(dir);
  t.after(() => {
    store.close();
    rmSync(dir, { recursive: true, force: true });
  });
  const f = {
    id: "fixture",
    name: "Fixture",
    category: "Weapons",
    notes: "",
  } as Family;
  store.db.prepare("INSERT INTO sources VALUES(?,?,?)").run(
    "wiki",
    f.id,
    JSON.stringify({
      id: "wiki",
      familyId: f.id,
      title: "Wiki",
      url: "https://example.org/wiki",
      text: "Damage: 80–1423",
      hash: "hash",
      filename: "unused",
      contentVersion: 2,
    }),
  );
  const run = (value: any) =>
    readSources(
      store,
      {
        status: async () => ({}),
        run: async (_label, _prompt, schema) => schema.parse(value),
      },
      f,
      () => {},
    );
  await assert.rejects(
    run({
      ...emptySourceReading(),
      facts: [
        {
          field: "stats",
          detail: "Damage range",
          quote: "Never present in source",
          stat: null,
        },
      ],
    }),
    /unsupported quotation/,
  );
  await assert.rejects(
    run({ facts: [], fields: [], proposedFields: [] }),
    /missed checklist/,
  );
});
test("every extracted fact needs a disposition; used range survives without an invented level", () => {
  const stat = {
    name: "Damage",
    minimum: 80,
    maximum: 1423,
    unit: "",
    level: null,
    notes: "",
  };
  const reading = SourceReading.parse({
    ...emptySourceReading(),
    facts: [{ field: "stats", detail: "Damage", quote: "80–1423", stat }],
  });
  const ledger = [
    {
      sourceId: "wiki",
      url: "https://example.org",
      hash: "h",
      characters: 9,
      chunks: [
        {
          index: 0,
          characters: 9,
          reading,
          facts: [{ ...reading.facts[0], id: "wiki:0:0" }],
        },
      ],
    },
  ];
  const packet = { evidence: [{ id: "wiki" }] } as Packet;
  const draft = {
    sourceUsage: [],
    entry: { stats: [] },
    claims: [],
    conflicts: [],
  } as unknown as Draft;
  assert.throws(
    () => validateSourceUsage(draft, ledger, packet),
    /exactly once/,
  );
  draft.sourceUsage = [
    {
      factId: "wiki:0:0",
      disposition: "used",
      fields: ["stats"],
      reason: "Catalogue damage",
      duplicateOf: null,
    },
  ];
  draft.claims = [
    { field: "stats", evidenceIds: ["wiki"], basis: "Explicit range" },
  ];
  assert.throws(
    () => validateSourceUsage(draft, ledger, packet),
    /omitted or changed|matching public field/,
  );
  draft.entry.stats = [{ ...stat, context: null, minimum: 79 }];
  assert.throws(
    () => validateSourceUsage(draft, ledger, packet),
    /omitted or changed/,
  );
  draft.entry.stats = [{ ...stat, context: null }];
  assert.doesNotThrow(() => validateSourceUsage(draft, ledger, packet));
  assert.equal(draft.entry.stats[0].level, null);
  draft.sourceUsage[0].disposition = "irrelevant";
  assert.throws(
    () => validateSourceUsage(draft, ledger, packet),
    /silently discarded/,
  );
  draft.sourceUsage[0].disposition = "duplicate";
  assert.throws(
    () => validateSourceUsage(draft, ledger, packet),
    /actually used/,
  );
});
test("all equipment types have their own stable numeric checklist", () => {
  assert.ok(statChecklist.Weapons.includes("Accuracy"));
  assert.ok(statChecklist.Shields.includes("Capacity"));
  assert.ok(statChecklist["Class mods"].includes("Skill bonuses"));
  assert.ok(statChecklist["Grenade mods"].includes("Blast radius"));
});

test("unproven part-specific modifiers can be excluded without discarding family stat ranges", () => {
  const reading = SourceReading.parse({
    ...emptySourceReading(),
    facts: [
      {
        field: "parts",
        detail: "Unproven sight option",
        quote: "Sight 5: 5.9x",
        stat: {
          name: "Zoom",
          minimum: 5.9,
          maximum: 5.9,
          unit: "x",
          level: null,
          notes: "Sight-specific modifier",
        },
      },
    ],
  });
  const ledger = [
    {
      sourceId: "wiki",
      url: "https://example.org",
      hash: "h",
      characters: 9,
      chunks: [
        {
          index: 0,
          characters: 9,
          reading,
          facts: [{ ...reading.facts[0], id: "wiki:0:0" }],
        },
      ],
    },
  ];
  const draft = {
    sourceUsage: [
      {
        factId: "wiki:0:0",
        disposition: "irrelevant",
        fields: [],
        reason:
          "Shared sight option lacks evidence of compatibility with this family.",
        duplicateOf: null,
      },
    ],
    entry: { stats: [] },
    claims: [],
    conflicts: [],
  } as unknown as Draft;
  assert.doesNotThrow(() =>
    validateSourceUsage(draft, ledger, {
      evidence: [{ id: "wiki" }],
    } as Packet),
  );
});

test("an accessory modifier can remain in mechanics without being conflated with a card-stat range", () => {
  const stat = {
    name: "Fire rate",
    minimum: 25,
    maximum: 25,
    unit: "%",
    level: null,
    notes: "Additive accessory modifier",
  };
  const reading = SourceReading.parse({
    ...emptySourceReading(),
    facts: [
      {
        field: "stats",
        detail: "Accessory bonus",
        quote: "+25% fire rate",
        stat,
      },
    ],
  });
  const ledger = [
    {
      sourceId: "wiki",
      url: "https://example.org",
      hash: "h",
      characters: 9,
      chunks: [
        {
          index: 0,
          characters: 9,
          reading,
          facts: [{ ...reading.facts[0], id: "wiki:0:0" }],
        },
      ],
    },
  ];
  const draft = {
    sourceUsage: [
      {
        factId: "wiki:0:0",
        disposition: "used",
        fields: ["details"],
        reason: "Mechanics",
        duplicateOf: null,
      },
    ],
    entry: {
      details: [
        {
          heading: "Accessory",
          paragraphs: [
            "The signature accessory provides a +25% firing-rate boost.",
          ],
        },
      ],
      stats: [],
    },
    claims: [
      { field: "details", evidenceIds: ["wiki"], basis: "Explicit modifier" },
    ],
    conflicts: [],
  } as unknown as Draft;
  const p = { evidence: [{ id: "wiki" }] } as Packet;
  assert.doesNotThrow(() => validateSourceUsage(draft, ledger, p));
  draft.entry.details[0].paragraphs = ["A vague firing-rate advantage."];
  assert.throws(
    () => validateSourceUsage(draft, ledger, p),
    /omitted or changed/,
  );
});

test("filtered boilerplate remains auditable but cannot be used as an item fact", () => {
  const reading = SourceReading.parse({
    ...emptySourceReading(),
    facts: [
      {
        field: "notes",
        detail: "Time farming runs",
        quote: "time your routes",
        stat: null,
      },
    ],
  });
  const ledger = [
    {
      sourceId: "wiki",
      url: "https://example.org",
      hash: "h",
      characters: 9,
      chunks: [
        {
          index: 0,
          characters: 9,
          reading,
          facts: [
            {
              ...reading.facts[0],
              id: "wiki:0:0",
              excludedReason: "Generic farming advice",
            },
          ],
        },
      ],
    },
  ];
  const d = {
    sourceUsage: [
      {
        factId: "wiki:0:0",
        disposition: "used",
        fields: ["notes"],
        reason: "Guide",
        duplicateOf: null,
      },
    ],
    entry: { notes: ["Guide"] },
    claims: [{ field: "notes", evidenceIds: ["wiki"] }],
    conflicts: [],
  } as unknown as Draft;
  const p = { evidence: [{ id: "wiki" }] } as Packet;
  assert.throws(
    () => validateSourceUsage(d, ledger, p),
    /Non-catalogue content/,
  );
  d.sourceUsage[0].disposition = "irrelevant";
  assert.doesNotThrow(() => validateSourceUsage(d, ledger, p));
});

test("schema-valid empty fields retain source claims without depending on absence wording", () => {
  const reading = SourceReading.parse({
    ...emptySourceReading(),
    facts: [
      {
        field: "elements",
        detail: "No elemental options.",
        quote: "none",
        stat: null,
      },
      { field: "variants", detail: "No variants.", quote: "none", stat: null },
    ],
  });
  const ledger = [
    {
      sourceId: "wiki",
      url: "https://example.org",
      hash: "h",
      characters: 4,
      chunks: [
        {
          index: 0,
          characters: 4,
          reading,
          facts: reading.facts.map((f, i) => ({ ...f, id: `wiki:0:${i}` })),
        },
      ],
    },
  ];
  const draft = {
    entry: { elements: [], variants: [] },
    claims: [
      { field: "elements", evidenceIds: ["wiki"], basis: "Explicitly none" },
      { field: "variants", evidenceIds: ["wiki"], basis: "Explicitly none" },
    ],
    sourceUsage: reading.facts.map((f, i) => ({
      factId: `wiki:0:${i}`,
      disposition: "used",
      fields: [f.field],
      reason: "Empty represents none",
      duplicateOf: null,
    })),
    conflicts: [],
  } as unknown as Draft;
  const packet = { evidence: [{ id: "wiki" }] } as Packet;
  assert.doesNotThrow(() => validateSourceUsage(draft, ledger, packet));
  ledger[0].chunks[0].facts[1].detail =
    "Weapon-part variants are presented as fixed parts.";
  ledger[0].chunks[0].facts[1].quote = "Weapon Parts variants fixed parts";
  assert.doesNotThrow(() => validateSourceUsage(draft, ledger, packet));
  draft.claims = draft.claims.filter((claim) => claim.field !== "variants");
  assert.throws(
    () => validateSourceUsage(draft, ledger, packet),
    /matching public field/,
  );
  draft.claims.push({
    field: "variants",
    evidenceIds: ["wiki"],
    basis: "Fixed-parts presentation",
  });
  delete (draft.entry as any).variants;
  assert.throws(
    () => validateSourceUsage(draft, ledger, packet),
    /matching public field/,
  );
});

test("a captured part attribution identifies a scoped modifier even without the word modifier", () => {
  const stat = {
    name: "Projectile speed",
    minimum: 100,
    maximum: 100,
    unit: "%",
    level: null,
    notes: "Projectile speed on sight4_Jakobs_Bessie.",
  };
  const reading = SourceReading.parse({
    ...emptySourceReading(),
    facts: [
      {
        field: "stats",
        detail: "Scope projectile speed",
        quote: "+100%",
        stat,
      },
    ],
  });
  const ledger = [
    {
      sourceId: "wiki",
      url: "https://example.org",
      hash: "h",
      characters: 9,
      chunks: [
        {
          index: 0,
          characters: 9,
          reading,
          facts: [{ ...reading.facts[0], id: "wiki:0:0" }],
        },
      ],
    },
  ];
  const draft = {
    sourceUsage: [
      {
        factId: "wiki:0:0",
        disposition: "used",
        fields: ["details"],
        reason: "Scope projectile speed",
        duplicateOf: null,
      },
    ],
    entry: {
      details: [
        {
          heading: "Scope",
          paragraphs: ["The scope increases projectile speed by +100%."],
        },
      ],
      stats: [],
    },
    claims: [
      {
        field: "details",
        evidenceIds: ["wiki"],
        basis: "Scope projectile speed",
      },
    ],
    conflicts: [],
    partDefinitions: [
      {
        id: partId("gd_scope.sight4_Jakobs_Bessie"),
        effects: ["Increases projectile speed by +100%."],
      },
    ],
  } as unknown as Draft;
  const packet = {
    evidence: [
      { id: "wiki" },
      {
        id: "game:scope",
        kind: "game",
        path: "gd_scope.sight4_Jakobs_Bessie",
        value: { class: "WillowGame.WeaponPartDefinition" },
      },
    ],
  } as Packet;
  assert.doesNotThrow(() => validateSourceUsage(draft, ledger, packet));
  draft.partDefinitions[0].effects = ["Increases projectile speed."];
  draft.entry.details[0].paragraphs = [
    "The scope has a field-of-view adjustment.",
  ];
  assert.throws(
    () => validateSourceUsage(draft, ledger, packet),
    /omitted or changed/,
  );
});

test("known game/manual accounting is separated without hiding missing, duplicate or invented page facts", async () => {
  const { separateEvidenceUsage } =
    await import("../src/server/source-analysis.ts");
  const reading = SourceReading.parse({
    ...emptySourceReading(),
    facts: [
      { field: "summary", detail: "A rifle", quote: "A rifle", stat: null },
    ],
  });
  const ledger = [
    {
      sourceId: "wiki",
      url: "https://example.org",
      hash: "h",
      characters: 7,
      chunks: [
        {
          index: 0,
          characters: 7,
          reading,
          facts: [{ ...reading.facts[0], id: "wiki:0:0" }],
        },
      ],
    },
  ];
  const usage = (factId: string) => ({
    factId,
    disposition: "used" as const,
    fields: ["summary"],
    reason: "Fact",
    duplicateOf: null,
  });
  const draft = {
    entry: { summary: "A rifle" },
    claims: [{ field: "summary", evidenceIds: ["wiki"], basis: "Fact" }],
    sourceUsage: [
      usage("wiki:0:0"),
      usage("game:known"),
      usage("manual:known"),
    ],
    conflicts: [],
  } as unknown as Draft;
  const packet = {
    evidence: [
      { id: "wiki", kind: "page" },
      { id: "game:known", kind: "game" },
      { id: "manual:known", kind: "manual" },
    ],
  } as Packet;
  assert.equal(separateEvidenceUsage(draft, ledger, packet).length, 2);
  assert.equal(draft.sourceUsage.length, 1);
  assert.doesNotThrow(() => validateSourceUsage(draft, ledger, packet));
  draft.sourceUsage.push(usage("game:invented"));
  assert.equal(separateEvidenceUsage(draft, ledger, packet).length, 0);
  assert.throws(
    () => validateSourceUsage(draft, ledger, packet),
    /Unexpected IDs:.*game:invented/,
  );
  draft.sourceUsage = [usage("wiki:0:0"), usage("wiki:0:0")];
  assert.throws(
    () => validateSourceUsage(draft, ledger, packet),
    /Duplicate IDs:.*wiki:0:0/,
  );
  draft.sourceUsage = [];
  assert.throws(
    () => validateSourceUsage(draft, ledger, packet),
    /Missing IDs:.*wiki:0:0/,
  );
});

test("source quotations accept serialized table layout without accepting altered facts", async () => {
  const { sourceQuoteMatches } =
    await import("../src/server/source-analysis.ts");
  const table = JSON.stringify({
    rows: [["Support Gunner\nS&S, Vladof", "+2 – +25 Team Ammo Regeneration"]],
  });
  assert.ok(sourceQuoteMatches(table, "Support Gunner\n S&S, Vladof"));
  assert.ok(sourceQuoteMatches(table, "Support Gunner S&S, Vladof"));
  assert.ok(sourceQuoteMatches('A \\"quoted\\" label', 'A "quoted" label'));
  assert.ok(!sourceQuoteMatches(table, "Support Gunner S&S, Dahl"));
  assert.ok(!sourceQuoteMatches(table, "+2 – +50 Team Ammo Regeneration"));
  assert.ok(!sourceQuoteMatches(table, ""));
});

test("Lootlemon resolves direct Wiki conflicts while complementary Wiki facts remain required", () => {
  const make = (sourceId: string, url: string, fs: any[]) => ({
    sourceId,
    url,
    hash: sourceId,
    characters: 100,
    chunks: [
      {
        index: 0,
        characters: 100,
        reading: { ...emptySourceReading(), facts: fs },
        facts: fs.map((fact, i) => ({ ...fact, id: `${sourceId}:0:${i}` })),
      },
    ],
  });
  const fact = (field: string, detail: string, stat: any = null) => ({
    field,
    detail,
    quote: detail,
    stat,
  });
  const timer = {
    name: "Fuse time",
    minimum: 2,
    maximum: 2,
    unit: "s",
    level: null,
    notes: "",
  };
  const ledger: any = [
    make("ll", "https://www.lootlemon.com/grenade-mod/mirv-bl1", [
      fact("rarities", "Rare"),
      fact("stats", "2.5 seconds", { ...timer, minimum: 2.5, maximum: 2.5 }),
    ]),
    make("wiki", "https://borderlands.fandom.com/wiki/MIRV", [
      fact("rarities", "Common"),
      fact("stats", "2 seconds", timer),
      fact("notes", "Splits into child grenades."),
    ]),
  ];
  const packet = { evidence: [{ id: "ll" }, { id: "wiki" }] } as Packet;
  const draft = {
    entry: {
      rarities: ["Rare"],
      stats: [{ ...timer, minimum: 2.5, maximum: 2.5, context: "Parent fuse" }],
      notes: ["Splits into child grenades."],
    },
    claims: [
      { field: "rarities", evidenceIds: ["ll"], basis: "Preferred source" },
      { field: "stats", evidenceIds: ["ll"], basis: "Preferred source" },
      { field: "notes", evidenceIds: ["wiki"], basis: "Complementary detail" },
    ],
    conflicts: [],
    sourceUsage: [
      {
        factId: "ll:0:0",
        disposition: "used",
        fields: ["rarities"],
        reason: "Rare classification",
        duplicateOf: null,
      },
      {
        factId: "ll:0:1",
        disposition: "used",
        fields: ["stats"],
        reason: "Same-scope preferred fuse",
        duplicateOf: null,
      },
      {
        factId: "wiki:0:0",
        disposition: "overridden",
        fields: [],
        reason:
          "Same family/edition; Lootlemon wins the contradictory rarity classification.",
        duplicateOf: "ll:0:0",
      },
      {
        factId: "wiki:0:1",
        disposition: "overridden",
        fields: [],
        reason: "Same parent fuse scope; use Lootlemon duration.",
        duplicateOf: "ll:0:1",
      },
      {
        factId: "wiki:0:2",
        disposition: "used",
        fields: ["notes"],
        reason: "Additional useful mechanics",
        duplicateOf: null,
      },
    ],
  } as unknown as Draft;
  assert.doesNotThrow(() => validateSourceUsage(draft, ledger, packet));
  const clone = () => structuredClone(draft);
  let bad = clone();
  bad.entry.rarities = ["Common"];
  assert.throws(
    () => validateSourceUsage(bad, ledger, packet),
    /overridden Wiki rarity|omitted the preferred/,
  );
  bad = clone();
  bad.entry.rarities = [];
  assert.throws(
    () => validateSourceUsage(bad, ledger, packet),
    /omitted the preferred/,
  );
  bad = clone();
  bad.entry.stats.push({ ...timer, context: "Rejected value" });
  assert.throws(
    () => validateSourceUsage(bad, ledger, packet),
    /overridden Wiki stat/,
  );
  bad = clone();
  bad.sourceUsage[0] = {
    ...bad.sourceUsage[0],
    disposition: "overridden",
    fields: [],
    duplicateOf: "wiki:0:0",
  };
  assert.throws(
    () => validateSourceUsage(bad, ledger, packet),
    /Wiki fact to a used Lootlemon/,
  );
  bad = clone();
  bad.sourceUsage[2].duplicateOf = "ll:0:1";
  assert.throws(() => validateSourceUsage(bad, ledger, packet), /same field/);
  bad = clone();
  bad.sourceUsage[2].duplicateOf = "missing";
  assert.throws(
    () => validateSourceUsage(bad, ledger, packet),
    /used Lootlemon/,
  );
  bad = clone();
  bad.sourceUsage.pop();
  assert.throws(() => validateSourceUsage(bad, ledger, packet), /exactly once/);
  const sameProvider = structuredClone(ledger);
  sameProvider[0].url = "https://borderlands.fandom.com/wiki/MIRV/Mechanics";
  assert.throws(
    () => validateSourceUsage(draft, sameProvider, packet),
    /Wiki fact to a used Lootlemon/,
  );
});
