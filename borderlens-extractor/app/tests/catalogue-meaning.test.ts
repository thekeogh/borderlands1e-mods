import { test } from "node:test";
import assert from "node:assert/strict";
import {
  validateCatalogueMeaning,
  validateFactMeaning,
} from "../src/server/catalogue-meaning.ts";
import {
  validateSourceUsage,
  SourceReading,
  WriterSourceReading,
  type SourceLedger,
} from "../src/server/source-analysis.ts";
import { repairCatalogueStats } from "../src/server/stat-repair.ts";
import { StatContextError } from "../src/server/evidence.ts";
import type { Draft, Packet } from "../src/shared/models.ts";
function fixture(field: string, role: string, overrides: any = {}) {
  const fact = {
    id: "fact",
    field,
    catalogueRole: role,
    detail: "Synthetic exact family fact.",
    quote: "Maker is Workshop Co.",
    stat: null,
    manufacturerNames: [],
    origin: null,
    ...overrides,
  };
  const ledger = [
    {
      sourceId: "page",
      url: "https://www.lootlemon.com/item/fixture",
      hash: "fixture",
      characters: 100,
      chunks: [
        {
          index: 0,
          characters: 100,
          reading: { facts: [fact], fields: [], proposedFields: [] },
          facts: [fact],
        },
      ],
    },
  ] as SourceLedger[];
  const packet = {
    facts: { manufacturers: [], dlc: null },
    evidence: [{ id: "page", kind: "page", value: {} }],
  } as unknown as Packet;
  const draft = {
    entry: {
      manufacturers: [],
      dlc: null,
      stats: [],
      levels: { minimum: null, maximum: null, notes: "" },
      variants: [],
      details: [],
      parts: [],
    },
    claims: [{ field, evidenceIds: ["page"], basis: "Exact synthetic fact." }],
    sourceUsage: [
      {
        factId: "fact",
        disposition: "used",
        fields: [field],
        reason: "",
        duplicateOf: null,
      },
    ],
    partDefinitions: [],
    conflicts: [],
  } as unknown as Draft;
  return { fact, ledger, packet, draft };
}
const stat = {
  name: "Capacity",
  minimum: 12,
  maximum: 12,
  unit: "",
  level: null,
  notes: "",
};
test("numeric roles keep shared mechanics, sample values and progression out of item stats across equipment categories", () => {
  for (const category of [
    "Weapons",
    "Shields",
    "Grenade mods",
    "Class mods",
    "Artifacts",
    "Other equipment",
  ])
    for (const role of [
      "general_mechanic",
      "illustrative_example",
      "part_property",
      "progression",
    ]) {
      const { draft, ledger, packet } = fixture("stats", role, { stat });
      packet.category = category as any;
      draft.entry.stats = [{ ...stat, context: null }];
      assert.throws(
        () => validateCatalogueMeaning(draft, ledger, packet),
        /must not become item stats/,
      );
      draft.entry.stats = [];
      draft.entry.details = [
        { heading: "Mechanics", paragraphs: ["Scoped synthetic value 12."] },
      ];
      draft.sourceUsage[0].fields = ["details"];
      draft.claims = [
        { field: "details", evidenceIds: ["page"], basis: "Scope explained." },
      ];
      assert.doesNotThrow(() => validateSourceUsage(draft, ledger, packet));
      draft.sourceUsage[0].disposition = "irrelevant";
      draft.sourceUsage[0].fields = [];
      draft.sourceUsage[0].reason =
        "An illustrative value does not help compare this item.";
      assert.doesNotThrow(() => validateSourceUsage(draft, ledger, packet));
    }
});
test("genuine item-specific published ranges still require exact numeric retention", () => {
  const { draft, ledger, packet } = fixture("stats", "item_property", { stat });
  assert.throws(
    () => validateSourceUsage(draft, ledger, packet),
    /numeric|catalogue stat/i,
  );
  draft.entry.stats = [{ ...stat, context: null }];
  assert.doesNotThrow(() => validateSourceUsage(draft, ledger, packet));
});
test("manufacturer attribution needs explicit named maker evidence or defining raw facts, not a descriptive label", () => {
  const { draft, ledger, packet, fact } = fixture(
    "manufacturers",
    "descriptive_label",
  );
  draft.entry.manufacturers = ["Workshop Co."];
  assert.throws(
    () => validateCatalogueMeaning(draft, ledger, packet),
    /Manufacturer needs/,
  );
  fact.catalogueRole = "item_property";
  fact.manufacturerNames = ["Workshop Co."];
  assert.doesNotThrow(() => validateCatalogueMeaning(draft, ledger, packet));
  fact.manufacturerNames = ["Invented Co."];
  draft.entry.manufacturers = ["Invented Co."];
  assert.throws(
    () => validateCatalogueMeaning(draft, ledger, packet),
    /exact quote names/,
  );
  fact.manufacturerNames = [];
  packet.facts.manufacturers = ["Invented Co."];
  assert.doesNotThrow(() => validateCatalogueMeaning(draft, ledger, packet));
});
test("explicit Base Game origin cannot be lost; acquisition DLC and unknown package origin cannot manufacture it", () => {
  const { draft, ledger, packet, fact } = fixture("dlc", "item_property", {
    origin: "Base Game",
  });
  assert.throws(
    () => validateCatalogueMeaning(draft, ledger, packet),
    /established item origin/,
  );
  draft.entry.dlc = "Base Game";
  assert.doesNotThrow(() => validateCatalogueMeaning(draft, ledger, packet));
  packet.facts.dlc = "The Secret Armory of General Knoxx";
  assert.throws(
    () => validateCatalogueMeaning(draft, ledger, packet),
    /established item origin/,
  );
  packet.facts.dlc = null;
  fact.origin = null;
  assert.throws(
    () => validateCatalogueMeaning(draft, ledger, packet),
    /explicit item-origin/,
  );
  draft.entry.dlc = null;
  assert.doesNotThrow(() => validateCatalogueMeaning(draft, ledger, packet));
});
test("ordinal progression goes to details while substantive variant differences remain available", () => {
  const { draft, ledger, packet, fact } = fixture("variants", "progression");
  draft.entry.variants = [
    {
      name: "Level 1",
      description: "First upgrade.",
      differences: ["Replaces a lower level."],
    },
  ];
  assert.throws(
    () => validateCatalogueMeaning(draft, ledger, packet),
    /do not establish meaningful variants/,
  );
  draft.entry.variants = [];
  draft.sourceUsage[0].fields = ["details"];
  assert.doesNotThrow(() => validateCatalogueMeaning(draft, ledger, packet));
  fact.catalogueRole = "item_property";
  draft.sourceUsage[0].fields = ["variants"];
  draft.entry.variants = [
    {
      name: "Alternate configuration",
      description: "A different supported effect.",
      differences: ["Uses an alternate supported ability."],
    },
  ];
  assert.doesNotThrow(() => validateCatalogueMeaning(draft, ledger, packet));
});
test("stat repair cannot resurrect example/general numbers as item rows and requires no AI call", async () => {
  const { draft, ledger, packet } = fixture("stats", "illustrative_example", {
    stat,
  });
  const repaired = await repairCatalogueStats(
    draft,
    packet,
    ledger,
    new StatContextError("Capacity"),
    {
      run: async () => {
        throw Error("Unexpected AI call");
      },
    } as any,
    "",
    () => {},
  );
  assert.equal(repaired, false);
  assert.deepEqual(draft.entry.stats, []);
});
test("model schema exposes semantic metadata without changing the public entry schema", () => {
  const fact = SourceReading.shape.facts.element.parse({
    field: "details",
    detail: "A system rule.",
    quote: "System rule",
    stat: null,
    catalogueRole: "general_mechanic",
    manufacturerNames: [],
    origin: null,
  });
  assert.equal(fact.catalogueRole, "general_mechanic");
  assert.equal(
    WriterSourceReading.shape.facts.element.parse({ ...fact }).origin,
    null,
  );
});

test("reader repairs reject maker names absent from quotes and origin attached to acquisition instead of introduction", () => {
  const { fact } = fixture("sources", "item_property", {
    origin: "The Zombie Island of Dr. Ned",
  });
  assert.throws(() => validateFactMeaning(fact), /never a drop-location/);
  fact.origin = null;
  fact.field = "manufacturers";
  fact.manufacturerNames = ["Absent producer"];
  assert.throws(() => validateFactMeaning(fact), /exact quote names/);
});
