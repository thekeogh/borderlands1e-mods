import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { z } from "zod";
import { agentOutputSchema } from "../src/shared/agent-schema.ts";
import { Store, hash, stable } from "../src/server/store.ts";
import { Research } from "../src/server/research.ts";
import { Worker } from "../src/server/worker.ts";
import { buildPacket, validateDraft } from "../src/server/evidence.ts";
import {
  readSources,
  validateSourceUsage,
  type SourceLedger,
  WriterSourceReading,
} from "../src/server/source-analysis.ts";
import { savedSourceCache } from "../src/server/source-cache.ts";
import { interpretationContent } from "../src/server/deterministic-source.ts";
import {
  factualOutline,
  assembleProse,
  writingOutline,
} from "../src/server/factual-outline.ts";
import {
  ProseDraft,
  ProsePatch,
  NormalizedFact,
} from "../src/shared/factual-build.ts";
import { writeOfflineProse } from "../src/server/prose-writer.ts";
import { assembleWebsiteEntry } from "../src/server/final-entry.ts";
import { validateParts } from "../src/server/parts.ts";
import { resetProject } from "../src/server/project-reset.ts";
import type { Family } from "../src/shared/models.ts";
function fixture(t: any, category: Family["category"] = "Weapons") {
  const dir = mkdtempSync(path.join(tmpdir(), "offline-build-")),
    s = new Store(dir);
  const f: Family = {
    id: "fixture",
    name: "Fixture",
    category,
    subtype: category === "Weapons" ? "SMGs" : category,
    roots: ["gd_fixture.Title.Name"],
    aliases: [],
    sourceUrls: [],
    history: [],
    status: "queued",
    stage: "draft",
    revision: 0,
    notes: "",
    inputHash: "",
    issue: null,
    gameOnly: false,
    manualOutput: false,
    updatedAt: "",
  };
  s.state.families = [f];
  s.state.settings.research = false;
  s.records.set(f.roots[0].toLowerCase(), {
    id: "root",
    path: f.roots[0],
    class: "WillowGame.WeaponNamePartDefinition",
    record_type: "object",
    properties: {
      PartName: f.name,
      UnusedGraph: Array.from({ length: 200 }, (_, i) => ({
        Value: i,
        Unused: "No final item-stat meaning",
      })),
    },
  });
  const source = new Research(s).save(
    f,
    "https://www.lootlemon.com/item/fixture-bl1",
    "<main><h1>Fixture</h1><table><tr><th>Stat</th><th>Minimum</th><th>Maximum</th><th>Unit</th><th>Context</th></tr><tr><td>Damage</td><td>12</td><td>24</td><td></td><td>Card</td></tr></table><table><tr><th>Property</th><th>Value</th></tr><tr><td>Manufacturer</td><td>Workshop Co.</td></tr></table></main>",
    true,
  );
  t.after(() => {
    s.close();
    rmSync(dir, { recursive: true, force: true });
  });
  return { s, f, dir, source };
}
function prose(
  outline: ReturnType<typeof factualOutline>,
  packet: ReturnType<typeof buildPacket>,
) {
  return ProseDraft.parse({
    entry: {
      summary: "A focused equipment family with a useful combat role.",
      description: [
        "This equipment delivers its documented strengths through a straightforward combat design.",
      ],
      details: [],
      specialEffects: [],
      notes: [],
      levels: { notes: "" },
      stats: outline.slots.stats.map((slot) => ({
        id: slot.id,
        context: slot.context,
        notes: "",
      })),
      sources: outline.slots.sources.map((slot) => ({
        id: slot.id,
        notes: "Original reward explanation.",
        conditions: slot.conditions.map((c) => c.replace("Complete", "Finish")),
        dropConditions: slot.dropConditions.map((c) =>
          c.replace("Complete", "Finish"),
        ),
      })),
      variants: outline.slots.variants.map((slot) => ({
        id: slot.id,
        description: "An independently written alternate configuration.",
        differences: slot.distinctions.map((c) =>
          c.replace("Increase", "Raises"),
        ),
      })),
      parts: [],
    },
    partDefinitions: [],
    claims: ["summary", "description"].map((field) => ({
      field,
      evidenceIds: [packet.evidence[0].id],
      basis: "Captured family identity.",
    })),
    sourceUsage: [],
    uncertainties: [],
    conflicts: [],
    requiresReview: false,
    reviewReason: null,
  });
}
async function facts(x: ReturnType<typeof fixture>) {
  return readSources(
    x.s,
    {
      run: async () => {
        throw Error("Recognised tables must not require AI");
      },
    } as any,
    x.f,
    () => {},
  );
}
test("recognised complete item tables bypass AI across equipment categories, preserve original files and reuse derived readings", async (t) => {
  for (const category of [
    "Weapons",
    "Shields",
    "Grenade mods",
    "Class mods",
    "Artifacts",
    "Other equipment",
  ] as const) {
    const x = fixture(t, category),
      before = readFileSync(path.join(x.dir, "sources", x.source.filename));
    const ledger = await facts(x);
    assert.equal(ledger[0].chunks[0].index, -1);
    assert.equal(ledger[0].chunks[0].facts.length, 2);
    const packet = buildPacket(x.s, x.f),
      outline = factualOutline(packet, ledger, x.f),
      draft = assembleProse(outline, prose(outline, packet));
    assert.deepEqual(draft.entry.manufacturers, ["Workshop Co."]);
    assert.equal(draft.entry.stats[0].minimum, 12);
    assert.equal(draft.entry.stats[0].maximum, 24);
    assert.doesNotThrow(() => validateDraft(draft, packet));
    assert.equal(
      assembleWebsiteEntry(draft.entry, draft.partDefinitions).schemaVersion,
      "9",
    );
    assert.doesNotThrow(() => validateSourceUsage(draft, ledger, packet));
    x.f.inputHash = (await import("../src/server/evidence.ts")).packetHash(
      packet,
    );
    x.s.put(x.f.id, "sourceLedgerInput", x.f.inputHash);
    assert.ok(savedSourceCache(x.s, x.f).ledger);
    assert.deepEqual(
      readFileSync(path.join(x.dir, "sources", x.source.filename)),
      before,
    );
    for (const fact of outline.facts)
      assert.ok(NormalizedFact.safeParse(fact).success);
  }
});
test("partial, sample, mixed-game, shared and unfamiliar layouts fall back instead of guessing", (t) => {
  const x = fixture(t);
  for (const source of [
    { ...x.source, selectedContent: { boxes: 1, warnings: 1 } },
    { ...x.source, text: x.source.text + " example roll" },
    { ...x.source, text: x.source.text + " Borderlands 3" },
    { ...x.source, familyId: "another-owner" },
    { ...x.source, title: "Different family" },
  ])
    assert.equal(interpretationContent(x.s, x.f, source).facts.length, 0);
  const ambiguous = new Research(x.s).save(
    x.f,
    "https://www.lootlemon.com/item/other",
    "<main><h1>Fixture</h1><p>The following unfamiliar table needs interpretation before its meaning can be established.</p><table><tr><th>Damage</th></tr><tr><td>999</td></tr></table></main>",
    true,
  );
  assert.equal(interpretationContent(x.s, x.f, ambiguous).facts.length, 0);
});
test("prose cannot replace fixed identity, stats, maker, origin or relationships", async (t) => {
  const x = fixture(t),
    ledger = await facts(x),
    packet = buildPacket(x.s, x.f),
    outline = factualOutline(packet, ledger, x.f),
    words = prose(outline, packet);
  const malicious = ProseDraft.parse({
    ...words,
    entry: {
      ...words.entry,
      name: "Wrong name",
      manufacturers: ["Invented"],
      dlc: "Invented",
      stats: words.entry.stats.map((row) => ({
        ...row,
        minimum: 999,
        maximum: 999,
      })),
    },
  });
  const draft = assembleProse(outline, malicious);
  assert.equal(draft.entry.name, x.f.name);
  assert.deepEqual(draft.entry.manufacturers, ["Workshop Co."]);
  assert.equal(draft.entry.stats[0].minimum, 12);
  assert.equal(draft.entry.stats[0].context, "Card");
  assert.equal(draft.entry.dlc, null);
  assert.throws(
    () =>
      assembleProse(outline, {
        ...words,
        entry: {
          ...words.entry,
          stats: [{ id: "unknown", notes: "" }],
        },
      }),
    /Unexpected/,
  );
  assert.throws(
    () =>
      assembleProse(outline, {
        ...words,
        entry: { ...words.entry, stats: [] },
      }),
    /Missing original stat/,
  );
});
test("numerical wording differences are advisory while fixed data and source URLs stay owned by code", async (t) => {
  const x = fixture(t),
    ledger = await facts(x),
    packet = buildPacket(x.s, x.f);
  const base = ledger[0].chunks[0].facts[0];
  ledger[0].chunks[0].facts.push({
    ...base,
    id: "quest",
    field: "sources",
    stat: null,
    structured: {
      kind: "source",
      kindOfSource: "quest",
      label: "Fixture Quest",
      url: "https://invented.invalid/",
      location: null,
      dlc: null,
      conditions: ["Complete 50 objectives"],
      dropChance: null,
    },
  });
  const outline = factualOutline(packet, ledger, x.f),
    words = prose(outline, packet);
  assert.equal(outline.fixed.sources[0].url, x.source.url);
  assert.doesNotThrow(() => assembleProse(outline, words));
  words.entry.sources[0].conditions = ["Finish 10 objectives"];
  const imperfect = assembleProse(outline, words);
  assert.deepEqual(imperfect.entry.sources[0].conditions, [
    "Finish 10 objectives",
  ]);
  assert.ok(imperfect.uncertainties.some((w) => /Numerical wording/.test(w)));
  assert.equal(imperfect.requiresReview, false);
});
test("same-scope Lootlemon priority is deterministic while incompatible quantities retain their contexts", async (t) => {
  const x = fixture(t),
    ledger = await facts(x),
    packet = buildPacket(x.s, x.f);
  const wiki = structuredClone(ledger[0]);
  wiki.sourceId = "wiki";
  wiki.url = "https://borderlands.fandom.com/wiki/Fixture";
  wiki.chunks[0].facts = [
    {
      ...wiki.chunks[0].facts[0],
      id: "wiki-range",
      stat: { ...wiki.chunks[0].facts[0].stat!, minimum: 100, maximum: 200 },
    },
  ];
  const outline = factualOutline(packet, [wiki, ...ledger], x.f);
  assert.equal(outline.fixed.stats.length, 1);
  assert.equal(outline.fixed.stats[0].minimum, 12);
  assert.equal(
    outline.usage.find((u) => u.factId === "wiki-range")?.disposition,
    "overridden",
  );
  const conditional = {
    ...structuredClone(ledger[0].chunks[0].facts[0]),
    id: "scoped",
    stat: {
      ...ledger[0].chunks[0].facts[0].stat!,
      context: "While scoped",
      minimum: 30,
      maximum: 60,
    },
  };
  ledger[0].chunks[0].facts.push(conditional);
  assert.equal(factualOutline(packet, ledger, x.f).fixed.stats.length, 2);
});
test("compact outline removes unused raw graphs, still carries all Always include facts and excludes Never before any reading", async (t) => {
  const x = fixture(t),
    ledger = await facts(x),
    packet = buildPacket(x.s, x.f),
    outline = factualOutline(packet, ledger, x.f);
  for (const fact of ledger[0].chunks[0].facts)
    fact.relevance = {
      forced: true,
      automaticIncluded: true,
      reason: "Always",
    };
  const input = writingOutline(outline, packet, ledger);
  assert.equal(input.sources[0].facts.length, 2);
  assert.ok(!JSON.stringify(input).includes("UnusedGraph"));
  assert.ok(JSON.stringify(input).length < JSON.stringify(packet).length);
  const w = new Worker(x.s, {
    run: async () => {
      throw Error("Never source submitted");
    },
  } as any);
  const parent = w.promoteSource(x.f.id, x.source.url);
  w.setSharedSourceMode(x.f.id, x.source.url, "never");
  assert.equal((await readSources(x.s, w.ai, x.f, () => {})).length, 0);
  assert.ok(parent.scope);
});
test("accepted facts survive generated reset and changed source content invalidates the cached interpretation", async (t) => {
  const x = fixture(t),
    ledger = await facts(x),
    packet = buildPacket(x.s, x.f),
    outline = factualOutline(packet, ledger, x.f);
  x.s.put(x.f.id, "factualOutline", outline);
  x.s.put(x.f.id, "factualDecisions", outline.facts);
  x.s.put(x.f.id, "proseDraft", {});
  resetProject(
    new Worker(x.s, {
      run: async () => {
        throw Error("No AI");
      },
    } as any),
    "generated",
  );
  assert.equal(x.s.get(x.f.id, "factualOutline"), null);
  assert.equal(x.s.get(x.f.id, "proseDraft"), null);
  assert.ok(x.s.get(x.f.id, "factualDecisions"));
  new Research(x.s).save(
    x.f,
    x.source.url,
    "<main><h1>Fixture</h1><p>Changed source content requires interpretation and is long enough to save as a useful evidence passage.</p></main>",
    true,
  );
  assert.equal(savedSourceCache(x.s, x.f).ledger, undefined);
});
test("writer correction patches prose without resending a raw graph or changing established facts", async (t) => {
  const x = fixture(t),
    ledger = await facts(x),
    packet = buildPacket(x.s, x.f);
  let calls = 0;
  const ai: any = {
    run: async (_label: string, prompt: string, schema: any) => {
      calls++;
      assert.ok(!prompt.includes("UnusedGraph"));
      const outline = x.s.get<any>(x.f.id, "factualOutline");
      if (schema === ProsePatch)
        return schema.parse({
          entry: {
            stats: outline.slots.stats.map((s: any) => ({
              id: s.id,
              context: "Card",
              notes: "",
            })),
          },
        });
      const words = prose(outline, packet);
      return schema.parse({ ...words, entry: { ...words.entry, stats: [] } });
    },
  };
  const draft = await writeOfflineProse(
    x.s,
    x.f,
    packet,
    ledger,
    ai,
    false,
    "Build Fixture",
    () => {},
  );
  assert.equal(calls, 2);
  assert.equal(draft.entry.stats[0].minimum, 12);
  assert.deepEqual(draft.entry.manufacturers, ["Workshop Co."]);
  assert.equal(x.s.get(x.f.id, "proseAssemblyFeedback"), null);
});
test("every model-facing outline writer/patch/reading object is strict and requires its properties", () => {
  const visit = (value: any) => {
    if (!value || typeof value !== "object") return;
    assert.equal(
      value.oneOf,
      undefined,
      "strict provider schemas cannot contain oneOf",
    );
    if (value.type === "object") {
      assert.deepEqual(
        new Set(value.required || []),
        new Set(Object.keys(value.properties || {})),
      );
      assert.equal(value.additionalProperties, false);
    }
    for (const child of Object.values(value))
      if (Array.isArray(child)) child.forEach(visit);
      else visit(child);
  };
  for (const schema of [ProseDraft, ProsePatch, WriterSourceReading])
    visit(agentOutputSchema(schema));
});

test("a validated shared interpretation correction is cached for future eligible items and retained as research", async (t) => {
  const x = fixture(t),
    w = new Worker(x.s, {} as any);
  const text =
    "This synthetic equipment rule describes a useful interaction without establishing an item damage range.";
  const source = w.addTextEvidence(x.f.id, {
    label: "Shared synthetic rule",
    text,
  });
  const { sharedChunkReading } =
    await import("../src/server/shared-source-index.ts");
  const { emptySourceReading } = await import("./source-fixture.ts");
  let calls = 0;
  const ai: any = {
    run: async (_label: string, _prompt: string, schema: any) => {
      calls++;
      return schema.parse({
        ...emptySourceReading(),
        facts: [
          {
            field: "description",
            catalogueRole: "general_mechanic",
            detail: text,
            quote: text,
            stat: null,
            structured:
              calls === 1 ? { kind: "levels", minimum: 1, maximum: 10 } : null,
          },
        ],
      });
    },
  };
  const first = await sharedChunkReading(x.s, ai, source, text, () => {});
  assert.equal(first?.cached, false);
  assert.equal(calls, 2);
  const second = await sharedChunkReading(x.s, ai, source, text, () => {});
  assert.equal(second?.cached, true);
  assert.equal(calls, 2);
  const corrections = x.s.db
    .prepare(
      "SELECT kind FROM artifacts WHERE family='_sharedSources' AND kind LIKE 'readingCorrection:%'",
    )
    .all();
  assert.equal(corrections.length, 1);
  resetProject(
    new Worker(x.s, {
      run: async () => {
        throw Error("No automatic AI");
      },
    } as any),
    "generated",
  );
  assert.equal(
    x.s.db
      .prepare(
        "SELECT kind FROM artifacts WHERE family='_sharedSources' AND kind LIKE 'readingCorrection:%'",
      )
      .all().length,
    1,
  );
});

test("a shared skill's own baseline cannot become an item's stat even when Always include supplies it", async (t) => {
  const x = fixture(t),
    ledger = await facts(x),
    packet = buildPacket(x.s, x.f);
  const fact = structuredClone(ledger[0].chunks[0].facts[0]);
  fact.id = "related-skill";
  fact.stat!.name = "Healing";
  fact.relevance = {
    forced: true,
    automaticIncluded: true,
    reason: "Related ability is selected",
  };
  fact.applicabilityScope = {
    certain: true,
    categories: [],
    characters: [],
    elements: [],
    weaponTypes: [],
    items: [],
    skills: ["Synthetic ability"],
  };
  ledger[0].chunks[0].facts.push(fact);
  const outline = factualOutline(packet, ledger, x.f);
  assert.ok(!outline.fixed.stats.some((s) => s.name === "Healing"));
  assert.ok(
    writingOutline(outline, packet, ledger).sources[0].facts.some(
      (f) => f.id === "related-skill",
    ),
  );
});

test("direct title-linked components are assembled from captured relationships with separate original prose", async (t) => {
  const x = fixture(t);
  const path = "gd_fixture.Barrel.barrel_unique";
  x.s.records.set(path.toLowerCase(), {
    id: "part",
    path,
    class: "WillowGame.WeaponPartDefinition",
    record_type: "object",
    properties: { TitleList: [{ $ref: x.f.roots[0] }] },
  });
  const ledger = await facts(x),
    packet = buildPacket(x.s, x.f),
    outline = factualOutline(packet, ledger, x.f),
    words = prose(outline, packet);
  words.partDefinitions = outline.parts.map((part) => ({
    id: part.id,
    name: "Defining component",
    effects: [],
    notes: [],
  }));
  const draft = assembleProse(outline, words);
  assert.equal(draft.entry.parts.length, 1);
  assert.equal(draft.partDefinitions[0].slot, "barrel");
  assert.doesNotThrow(() => validateParts(draft, packet));
  assert.equal(
    assembleWebsiteEntry(draft.entry, draft.partDefinitions).parts.length,
    1,
  );
});

test("publication commits output, revision and provenance together, or retains the previous entry on failure", async (t) => {
  const x = fixture(t),
    w = new Worker(x.s, {
      run: async (_label: string, _prompt: string, schema: any) =>
        schema.parse(
          prose(x.s.get<any>(x.f.id, "factualOutline"), buildPacket(x.s, x.f)),
        ),
    } as any);
  x.f.stage = "draft";
  await w.step(x.f);
  assert.equal(x.f.stage, "validate");
  const previous = {
    ...x.s.get<any>(x.f.id, "draft").entry,
    summary: "Previously saved original equipment summary.",
  };
  x.s.put(x.f.id, "output", previous);
  const revision = x.f.revision;
  const put = x.s.put.bind(x.s);
  x.s.put = (id, kind, value) => {
    if (kind === "provenance") throw Error("Simulated publication failure");
    put(id, kind, value);
  };
  await assert.rejects(w.step(x.f), /Simulated publication failure/);
  assert.deepEqual(x.s.get(x.f.id, "output"), previous);
  assert.equal(x.f.revision, revision);
  assert.equal(x.s.get(x.f.id, "revision:" + (revision + 1)), null);
  assert.equal(x.s.get(x.f.id, "factualRevision:" + (revision + 1)), null);
  x.s.put = put;
  await w.step(x.f);
  assert.equal(x.f.stage, "complete");
  assert.equal(x.f.revision, revision + 1);
  assert.ok(x.s.get(x.f.id, "provenance"));
  assert.ok(x.s.get(x.f.id, "factualRevision:" + (revision + 1)));
});

test("explicit exhaustive lists use source priority while maximum-roll rarity is complementary to available tiers", async (t) => {
  const x = fixture(t),
    ledger = await facts(x),
    packet = buildPacket(x.s, x.f);
  const maker = ledger[0].chunks[0].facts[1];
  const wiki = structuredClone(ledger[0]);
  wiki.url = "https://borderlands.fandom.com/wiki/Fixture";
  wiki.sourceId = "wiki";
  wiki.chunks[0].facts = [
    {
      ...maker,
      id: "wiki-maker",
      quote: "Manufacturer Other Co.",
      manufacturerNames: ["Other Co."],
      structured: {
        kind: "list",
        field: "manufacturers",
        values: ["Other Co."],
        coverage: "complete",
      },
    },
  ];
  const chosen = factualOutline(packet, [wiki, ...ledger], x.f);
  assert.deepEqual(chosen.fixed.manufacturers, ["Workshop Co."]);
  assert.equal(
    chosen.usage.find((u) => u.factId === "wiki-maker")?.disposition,
    "overridden",
  );
  const maximum = {
    ...maker,
    id: "maximum-tier",
    field: "rarities" as const,
    manufacturerNames: [],
    quote: "Epic at maximum rolls",
    structured: {
      kind: "list" as const,
      field: "rarities" as const,
      values: ["Epic"],
      coverage: "maximum_roll" as const,
    },
  };
  const available = {
    ...maker,
    id: "available-tiers",
    field: "rarities" as const,
    catalogueRole: "general_mechanic" as const,
    manufacturerNames: [],
    quote: "Common, Rare and Epic are available",
    structured: {
      kind: "list" as const,
      field: "rarities" as const,
      values: ["Common", "Rare", "Epic"],
      coverage: "complete" as const,
    },
  };
  ledger[0].chunks[0].facts.push(maximum, available);
  const complete = factualOutline(packet, ledger, x.f);
  assert.deepEqual(
    new Set(complete.fixed.rarities),
    new Set(["Common", "Rare", "Epic"]),
  );
  assert.deepEqual(complete.conflicts, []);
});

test("optional component relationships require a quoted captured identifier and a positive selection rule", async (t) => {
  const x = fixture(t),
    defining = "gd_fixture.Barrel.barrel_unique",
    optional = "gd_fixture.Body.body_optional",
    list = "gd_fixture.List.Parts";
  x.s.records.set(defining.toLowerCase(), {
    id: "defining",
    path: defining,
    class: "WillowGame.WeaponPartDefinition",
    record_type: "object",
    properties: { TitleList: [{ $ref: x.f.roots[0] }] },
  });
  x.s.records.set(optional.toLowerCase(), {
    id: "optional",
    path: optional,
    class: "WillowGame.WeaponPartDefinition",
    record_type: "object",
    properties: {},
  });
  x.s.records.set(list.toLowerCase(), {
    id: "list",
    path: list,
    class: "WillowGame.WeaponPartListDefinition",
    record_type: "object",
    properties: {
      WeightedParts: [
        { Part: { $ref: defining }, DefaultWeight: { BaseValueConstant: 1 } },
        { Part: { $ref: optional }, DefaultWeight: { BaseValueConstant: 1 } },
      ],
    },
  });
  const ledger = await facts(x),
    packet = buildPacket(x.s, x.f),
    base = ledger[0].chunks[0].facts[0];
  ledger[0].chunks[0].facts.push({
    ...base,
    id: "optional",
    field: "parts",
    catalogueRole: "part_property",
    stat: null,
    quote: "This item can use body_optional as a supported optional component.",
    structured: {
      kind: "part",
      path: "body_optional",
      relationship: "possible",
      name: "Optional body",
      slot: "body",
      manufacturers: [],
    },
  });
  const outline = factualOutline(packet, ledger, x.f),
    words = prose(outline, packet);
  words.partDefinitions = outline.parts.map((part) => ({
    id: part.id,
    name: "Original component label",
    effects: [],
    notes: [],
  }));
  const draft = assembleProse(outline, words);
  assert.ok(draft.entry.parts.some((part) => part.relationship === "possible"));
  assert.doesNotThrow(() => validateParts(draft, packet));
  const evidence = packet.evidence.find((e) => e.path === list)!;
  (
    evidence.value as any
  ).properties.WeightedParts[1].DefaultWeight.BaseValueConstant = 0;
  assert.ok(
    !factualOutline(packet, ledger, x.f).fixed.parts.some(
      (part) => part.relationship === "possible",
    ),
  );
});

test("uncertain shared facts cannot assign fixed properties across incompatible scope dimensions", async (t) => {
  const x = fixture(t, "Artifacts"),
    ledger = await facts(x),
    packet = buildPacket(x.s, x.f);
  x.f.character = "Brick";
  x.f.element = "Corrosive";
  const chunk = ledger[0].chunks[0];
  const maker = ledger
    .flatMap((p) => p.chunks.flatMap((c) => c.facts))
    .find((f) => f.field === "manufacturers")!;
  for (const p of ledger)
    for (const c of p.chunks)
      c.facts = c.facts.filter((f) => f.field !== "manufacturers");
  for (const dimension of [
    "categories",
    "characters",
    "elements",
    "weaponTypes",
    "items",
    "skills",
  ] as const) {
    const foreign = {
      ...maker,
      id: "foreign-" + dimension,
      catalogueRole: "item_property" as const,
      quote: "Foreign equipment is manufactured by Foreign Co.",
      manufacturerNames: ["Foreign Co."],
      structured: {
        kind: "list" as const,
        field: "manufacturers" as const,
        values: ["Foreign Co."],
        coverage: "complete" as const,
      },
      applicabilityScope: {
        certain: false,
        categories: [],
        characters: [],
        elements: [],
        weaponTypes: [],
        items: [],
        skills: [],
        [dimension]: [dimension === "categories" ? "Shields" : "Other"],
      },
    };
    chunk.facts.push(foreign);
    const outline = factualOutline(packet, ledger, x.f);
    assert.deepEqual(outline.fixed.manufacturers, [], dimension);
    assert.notEqual(
      outline.facts.find((f) => f.id === foreign.id)?.status,
      "accepted",
    );
    chunk.facts.pop();
  }
});

test("special-effect corrections change only that prose group; factual review takes precedence over cosmetic errors", async (t) => {
  const x = fixture(t),
    ledger = await facts(x),
    packet = buildPacket(x.s, x.f);
  const ai: any = {
    run: async (_l: string, _p: string, schema: any) => {
      const outline = x.s.get<any>(x.f.id, "factualOutline");
      if (schema === ProsePatch)
        return schema.parse({
          entry: {
            specialEffects: ["Delivers a focused elemental attack."],
            description: ["Unrelated replacement must be ignored."],
          },
        });
      return prose(outline, packet);
    },
  };
  const first = await writeOfflineProse(
    x.s,
    x.f,
    packet,
    ledger,
    ai,
    false,
    "Build",
    () => {},
  );
  first.entry.specialEffects = ["One.", "Two.", "Three."];
  const message =
    "Special-effect explanation must be at most two short entries and 45 words total. Rewrite the saved article explanation in plain gameplay language.";
  x.s.put(x.f.id, "draft", first);
  x.s.put(x.f.id, "validationFeedback", { attempt: 1, error: message });
  const fixed = await writeOfflineProse(
    x.s,
    x.f,
    packet,
    ledger,
    ai,
    false,
    "Build",
    () => {},
  );
  assert.deepEqual(fixed.entry.specialEffects, [
    "Delivers a focused elemental attack.",
  ]);
  assert.deepEqual(fixed.entry.description, first.entry.description);
  first.requiresReview = true;
  first.conflicts = [
    "A fixed property belongs to a different equipment category.",
  ];
  first.reviewReason = "";
  assert.throws(
    () => validateDraft(first, packet),
    /different equipment category/,
  );
});

test("best-effort publication retains uncertainty and numerical imperfections as notes without another model call", async (t) => {
  const x = fixture(t);
  let calls = 0;
  const w = new Worker(x.s, {
    run: async (_l: string, _p: string, schema: any) => {
      calls++;
      const words = prose(
        x.s.get<any>(x.f.id, "factualOutline"),
        buildPacket(x.s, x.f),
      );
      words.requiresReview = true;
      words.reviewReason =
        "Resolve the rank progression and ambiguous source spelling.";
      words.conflicts = ["An optional source name is ambiguous."];
      return schema.parse(words);
    },
  } as any);
  await w.step(x.f);
  assert.equal(x.f.stage, "validate");
  const draft = x.s.get<any>(x.f.id, "draft");
  assert.equal(draft.requiresReview, false);
  draft.entry.stats[0].minimum = 12.1;
  draft.entry.specialEffects = [
    "A focused combat effect.",
    "A secondary elemental benefit.",
    "A minor supporting interaction.",
  ];
  draft.claims.push({
    field: "specialEffects",
    evidenceIds: [buildPacket(x.s, x.f).evidence[0].id],
    basis: "Saved equipment context.",
  });
  x.s.put(x.f.id, "draft", draft);
  await w.step(x.f);
  assert.equal(x.f.stage, "complete");
  assert.equal(calls, 1);
  assert.equal(x.s.get<any>(x.f.id, "output").stats[0].minimum, 12.1);
  const warnings = x.s.get<any>(x.f.id, "finalValidation").warnings;
  assert.ok(warnings.some((m: string) => /rank progression/.test(m)));
  assert.ok(warnings.some((m: string) => /Special-effect/.test(m)));
  assert.ok(warnings.some((m: string) => /stat/i.test(m)));
  assert.equal(x.f.issue, null);
});

test("optional acquisition gaps are omitted while actual player requirements survive", async (t) => {
  const x = fixture(t),
    ledger = await facts(x),
    packet = buildPacket(x.s, x.f);
  const base = ledger[0].chunks[0].facts[0];
  ledger[0].chunks[0].facts.push({
    ...base,
    id: "quest-gap",
    field: "sources",
    stat: null,
    structured: {
      kind: "source",
      kindOfSource: "quest",
      label: "Optional quest",
      url: x.source.url,
      location: null,
      dlc: null,
      conditions: [
        "Complete 50 objectives",
        "Playthrough requirement is not established",
        "The source does not specify a character requirement",
      ],
      dropChance: null,
    },
  });
  const outline = factualOutline(packet, ledger, x.f);
  assert.deepEqual(outline.slots.sources[0].conditions, [
    "Complete 50 objectives",
  ]);
  const words = prose(outline, packet);
  words.entry.sources = [];
  const draft = assembleProse(outline, words);
  assert.deepEqual(draft.entry.sources, []);
  assert.ok(
    draft.uncertainties.some((m) => /Omitted an optional acquisition/.test(m)),
  );
});

test("equally ranked stat disagreements keep a supported value and do not stop the prose writer", async (t) => {
  const x = fixture(t),
    ledger = await facts(x),
    packet = buildPacket(x.s, x.f);
  const base = ledger
    .flatMap((p) => p.chunks.flatMap((c) => c.facts))
    .find((f) => f.stat)!;
  ledger[0].chunks[0].facts.push({
    ...base,
    id: "nearby-value",
    stat: { ...base.stat!, minimum: 12.1 },
  });
  let calls = 0;
  const ai: any = {
    run: async (_l: string, _p: string, schema: any) => {
      calls++;
      return schema.parse(
        prose(x.s.get<any>(x.f.id, "factualOutline"), packet),
      );
    },
  };
  const draft = await writeOfflineProse(
    x.s,
    x.f,
    packet,
    ledger,
    ai,
    false,
    "Build",
    () => {},
  );
  assert.equal(calls, 1);
  assert.equal(draft.entry.stats[0].minimum, 12);
  assert.ok(draft.uncertainties.some((m) => /Sources disagree/.test(m)));
  assert.equal(draft.requiresReview, false);
});

function acquisitionFact(
  base: any,
  id: string,
  label: string,
  conditions: string[],
  detail: string,
  location: string | null = null,
  rate: any = null,
) {
  return {
    ...base,
    id,
    field: "sources" as const,
    stat: null,
    catalogueRole: "item_property" as const,
    detail,
    quote: detail,
    structured: {
      kind: "source" as const,
      label,
      url: null,
      kindOfSource: "quest" as const,
      location,
      dlc: null,
      conditions,
      dropChance: rate,
    },
  };
}

test("complementary acquisition facts consolidate before AI and retain every reward context and evidence page", async (t) => {
  const x = fixture(t),
    ledger = await facts(x),
    packet = buildPacket(x.s, x.f),
    base = ledger[0].chunks[0].facts[0];
  ledger[0].chunks[0].facts.push(
    acquisitionFact(
      base,
      "reward-a",
      "Crystal Mission",
      ["First playthrough"],
      "The first playthrough awards a rank 2 artifact.",
    ),
  );
  const dedicated = structuredClone(ledger[0]);
  dedicated.sourceId = "dedicated";
  dedicated.url = "https://borderlands.fandom.com/wiki/Crystal_Mission";
  dedicated.chunks[0].facts = [
    acquisitionFact(
      base,
      "reward-b",
      "Crystal Mission",
      ["Second playthrough", "Collect 50 crystals"],
      "The second playthrough awards rank 4; artifacts match the receiving character.",
      "Crystal Cavern",
    ),
  ];
  const outline = factualOutline(packet, [...ledger, dedicated], x.f);
  assert.equal(outline.fixed.sources.length, 1);
  assert.equal(outline.fixed.sources[0].location, "Crystal Cavern");
  assert.equal(outline.fixed.sources[0].url, dedicated.url);
  assert.deepEqual(
    new Set(outline.slots.sources[0].factIds),
    new Set(["reward-a", "reward-b"]),
  );
  assert.equal(outline.slots.sources[0].facts!.length, 2);
  assert.deepEqual(outline.slots.sources[0].facts![0].conditions, [
    "First playthrough",
  ]);
  const input = writingOutline(outline, packet, [...ledger, dedicated]);
  assert.match(JSON.stringify(input.slots.sources), /rank 2/);
  assert.match(JSON.stringify(input.slots.sources), /rank 4/);
  assert(
    outline.claims
      .find((c) => c.field === "sources")!
      .evidenceIds.includes("dedicated"),
  );
  const words = prose(outline, packet);
  words.entry.sources[0].notes =
    "The reward matches the receiving class: rank 2 in the first playthrough or rank 4 in the second.";
  words.entry.sources[0].conditions = ["Gather 50 crystals in the cavern."];
  const result = assembleWebsiteEntry(assembleProse(outline, words).entry, []);
  assert.equal(result.sources.length, 1);
  assert.match(result.sources[0].notes!, /rank 4/);
});

test("acquisition aliases require explicit captured equivalence; similar spellings alone stay separate", async (t) => {
  const x = fixture(t),
    ledger = await facts(x),
    packet = buildPacket(x.s, x.f),
    base = ledger[0].chunks[0].facts[0];
  const a = acquisitionFact(
    base,
    "enemy-a",
    "Karn",
    ["First playthrough"],
    "Karn can drop a rank 1 artifact.",
    "Arena",
  );
  const b = acquisitionFact(
    base,
    "enemy-b",
    "Karrn",
    ["Second playthrough"],
    "Karrn can drop a rank 6 artifact.",
    "Arena",
  );
  a.structured.kindOfSource = b.structured.kindOfSource = "enemy" as any;
  ledger[0].chunks[0].facts.push(a, b);
  assert.equal(factualOutline(packet, ledger, x.f).fixed.sources.length, 2);
  ledger[0].chunks[0].facts.push({
    ...base,
    id: "explicit-alias",
    field: "notes",
    stat: null,
    structured: null,
    detail: "Alternate spelling.",
    quote: "Karn is also spelled Karrn.",
  });
  const combined = factualOutline(packet, ledger, x.f);
  assert.equal(combined.fixed.sources.length, 1);
  assert.equal(combined.slots.sources[0].facts!.length, 2);
  a.structured.dropChance = { percent: 1, players: 1, conditions: [] } as any;
  b.structured.dropChance = { percent: 2, players: 4, conditions: [] } as any;
  const rated = factualOutline(packet, ledger, x.f);
  assert.equal(rated.fixed.sources.length, 2);
  assert.equal(rated.fixed.sources[0].label, rated.fixed.sources[1].label);
  const result = assembleWebsiteEntry(
    assembleProse(rated, prose(rated, packet)).entry,
    [],
  );
  assert.equal(result.sources.length, 1);
  assert.equal(result.sources[0].dropChances.length, 2);
});

test("consolidation preserves separate known locations and condition-specific drop rates", async (t) => {
  const x = fixture(t),
    ledger = await facts(x),
    packet = buildPacket(x.s, x.f),
    base = ledger[0].chunks[0].facts[0];
  ledger[0].chunks[0].facts.push(
    acquisitionFact(
      base,
      "loc-a",
      "Named Enemy",
      [],
      "An arena drop.",
      "Arena",
    ),
    acquisitionFact(
      base,
      "loc-b",
      "Named Enemy",
      [],
      "A canyon drop.",
      "Canyon",
    ),
    acquisitionFact(
      base,
      "rate-a",
      "Rated Enemy",
      ["One player"],
      "A solo rate.",
      "Cave",
      { percent: 1, players: 1, conditions: [] },
    ),
    acquisitionFact(
      base,
      "rate-b",
      "Rated Enemy",
      ["Four players"],
      "A team rate.",
      "Cave",
      { percent: 2, players: 4, conditions: [] },
    ),
  );
  const outline = factualOutline(packet, ledger, x.f);
  assert.equal(outline.fixed.sources.length, 4);
  const result = assembleWebsiteEntry(
    assembleProse(outline, prose(outline, packet)).entry,
    [],
  );
  assert.equal(
    result.sources.filter((s) => s.label === "Named Enemy").length,
    2,
  );
  assert.deepEqual(
    result.sources
      .find((s) => s.label === "Rated Enemy")!
      .dropChances.map((r) => r.players),
    [1, 4],
  );
});

test("compatible 0.14 source interpretation remains reusable after an assembly-only compiler upgrade", async (t) => {
  const x = fixture(t);
  const source = new Research(x.s).save(
    x.f,
    "https://borderlands.fandom.com/wiki/Fixture_Mechanics",
    "<main><h1>Fixture Mechanics</h1><p>This unfamiliar equipment interaction needs interpretation and must remain available on future builds without another model read.</p></main>",
    true,
  );
  const text = interpretationContent(x.s, x.f, source).content;
  const key =
    "sourceReading:" +
    hash(
      stable({
        version: "0.14.0",
        freshRequest: undefined,
        text,
        source: source.hash,
        sourceId: source.id,
        family: x.f.id,
        category: x.f.category,
        correction: x.f.notes,
        model: x.s.state.settings.model,
        agent: x.s.state.settings.agent,
      }),
    );
  x.s.put(x.f.id, key, { facts: [], fields: [], proposedFields: [] });
  const result = await readSources(
    x.s,
    {
      run: async () => {
        throw Error("Compatible cached reading must not call AI");
      },
    } as any,
    x.f,
    () => {},
  );
  assert.ok(result.some((page) => page.sourceId === source.id));
});

test("explicit item-owned origin tables are parsed locally without treating a game label as item origin", (t) => {
  const x = fixture(t);
  const source = new Research(x.s).save(
    x.f,
    "https://borderlands.fandom.com/wiki/Fixture_Origin",
    "<main><h1>Fixture</h1><p>This is an explicit item property table with useful original context for an origin parser regression.</p><table><tr><th>Property</th><th>Value</th></tr><tr><td>Origin</td><td>Base Game</td></tr></table></main>",
    true,
  );
  const result = interpretationContent(x.s, x.f, source);
  assert.equal(
    result.facts.find((f) => f.field === "dlc")?.origin,
    "Base Game",
  );
  const other = new Research(x.s).save(
    x.f,
    "https://borderlands.fandom.com/wiki/Fixture_Game",
    "<main><h1>Fixture</h1><p>This table names only the game and cannot establish which content pack first introduced an item.</p><table><tr><th>Property</th><th>Value</th></tr><tr><td>Game</td><td>Borderlands</td></tr></table></main>",
    true,
  );
  assert.equal(
    interpretationContent(x.s, x.f, other).facts.some((f) => f.field === "dlc"),
    false,
  );
});

test("AI citations for part effects and other prose slots survive factual assembly", async (t) => {
  const x = fixture(t);
  const path = "gd_fixture.Accessory.accessory_unique";
  x.s.records.set(path.toLowerCase(), {
    id: "part",
    path,
    class: "WillowGame.WeaponPartDefinition",
    record_type: "object",
    properties: { TitleList: [{ $ref: x.f.roots[0] }] },
  });
  const ledger = await facts(x),
    packet = buildPacket(x.s, x.f),
    outline = factualOutline(packet, ledger, x.f),
    words = prose(outline, packet);
  const factId = "part-page:0:7",
    sourceId = "part-page";
  const fact = {
    id: factId,
    field: "parts" as const,
    structured: null,
    catalogueRole: "part_property" as const,
    detail: "Accessory tech is added before other calculations.",
    quote: "Tech Level +14 (Pre-add)",
    stat: null,
  };
  const reading = { facts: [fact], fields: [], proposedFields: [] };
  const page: SourceLedger = {
    sourceId,
    url: "https://borderlands.fandom.com/wiki/Fixture_Parts",
    hash: "fixture",
    characters: 100,
    chunks: [{ index: 0, characters: 100, reading, facts: [fact] }],
  };
  words.partDefinitions = outline.parts.map((part) => ({
    id: part.id,
    name: "Defining accessory",
    effects: ["Adds 14 tech levels before other calculations."],
    notes: [],
  }));
  words.entry.parts = outline.fixed.parts.map((part) => ({
    partId: part.partId,
    notes: "The bonus is applied before the remaining tech calculations.",
  }));
  words.claims.push({
    field: "parts",
    evidenceIds: [factId],
    basis: "Archived accessory timing rule.",
  });
  words.sourceUsage.push({
    factId,
    disposition: "used",
    fields: ["parts"],
    duplicateOf: null,
    reason: "Explains the accessory's effect timing.",
  });
  const assembled = assembleProse(outline, words);
  assert.ok(
    assembled.claims.some(
      (c) => c.field === "parts" && c.evidenceIds.includes(factId),
    ),
  );
  assert.deepEqual(
    assembled.entry.parts,
    outline.fixed.parts.map((part) => ({
      ...part,
      notes: words.entry.parts[0].notes,
    })),
  );
  const preserved = JSON.stringify(words.claims);
  for (const claim of assembled.claims)
    claim.evidenceIds = claim.evidenceIds.map((id) =>
      id === factId ? sourceId : id,
    );
  assert.equal(
    JSON.stringify(words.claims),
    preserved,
    "assembling must not mutate the saved prose's citations",
  );
  const related = structuredClone(assembled);
  assert.doesNotThrow(() =>
    validateSourceUsage(related, [...ledger, page], {
      ...packet,
      evidence: [
        ...packet.evidence,
        {
          id: sourceId,
          kind: "page",
          label: "Parts",
          value: { text: fact.detail },
        },
      ],
    }),
  );
});

test("incomplete used-fact citation is advisory in automatic builds, while unknown fact references remain invalid", async (t) => {
  const x = fixture(t),
    ledger = await facts(x),
    packet = buildPacket(x.s, x.f),
    outline = factualOutline(packet, ledger, x.f),
    words = prose(outline, packet);
  const draft = assembleProse(outline, words),
    warnings: string[] = [];
  draft.claims = draft.claims.filter((c) => c.field !== "stats");
  assert.doesNotThrow(() =>
    validateSourceUsage(draft, ledger, packet, (message) =>
      warnings.push(message),
    ),
  );
  assert.ok(
    warnings.some((message) => /matching public field claims/.test(message)),
  );
  assert.throws(
    () => validateSourceUsage(draft, ledger, packet),
    /matching public field claims/,
  );
  draft.sourceUsage[0].factId = "unavailable-fact";
  assert.throws(
    () =>
      validateSourceUsage(draft, ledger, packet, (message) =>
        warnings.push(message),
      ),
    /Source fact accounting failed/,
  );
});
