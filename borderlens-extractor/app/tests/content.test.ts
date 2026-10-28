import { test } from "node:test";
import assert from "node:assert/strict";
import { extractedContent } from "../src/server/content.ts";
import { buildPacket, validateDraft } from "../src/server/evidence.ts";
import { contentPacks } from "../src/shared/content.ts";
import {
  PublicEntry,
  Draft,
  type Family,
  type Raw,
} from "../src/shared/models.ts";
import {
  CATALOGUE_SCHEMA_VERSION,
  COMPILER_VERSION,
} from "../src/shared/versions.ts";
import { assembleWebsiteEntry } from "../src/server/final-entry.ts";
import { WebsiteEntry } from "../src/shared/website.ts";
import { commonFields, SourceReading } from "../src/server/source-analysis.ts";
const family = (roots: string[]): Family => ({
  id: "origin",
  name: "Origin Fixture",
  category: "Shields",
  subtype: "Shields",
  roots,
  aliases: [],
  sourceUrls: [],
  status: "queued",
  stage: "evidence",
  notes: "",
  history: [],
  inputHash: "",
  issue: null,
  gameOnly: false,
  manualOutput: false,
  revision: 0,
  updatedAt: "",
});
const raw = (path: string, properties = {}): Raw => ({
  id: path,
  path,
  class: "WillowGame.ItemNamePartDefinition",
  record_type: "object",
  properties,
});
function packet(roots: string[], extra: Raw[] = []) {
  const records = new Map(
    [...roots.map((p) => raw(p)), ...extra].map((r) => [
      r.path.toLowerCase(),
      r,
    ]),
  );
  return {
    records,
    f: family(roots),
    p: buildPacket(
      { records, sources: () => [], get: () => null },
      family(roots),
    ),
  };
}
function draft(
  p: ReturnType<typeof buildPacket>,
  dlc: (typeof contentPacks)[number] | null,
) {
  const entry = PublicEntry.parse({
    schemaVersion: CATALOGUE_SCHEMA_VERSION,
    compilerVersion: COMPILER_VERSION,
    id: p.familyId,
    name: p.name,
    category: p.category,
    weaponType: null,
    dlc,
    summary: "A synthetic shield for origin validation.",
    description: [
      "Original synthetic prose describing this shield for testing.",
    ],
    variants: [],
    parts: [],
    manufacturers: [],
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
  return Draft.parse({
    entry,
    partDefinitions: [],
    claims: ["summary", "description", ...(dlc ? ["dlc"] : [])].map(
      (field) => ({
        field,
        evidenceIds: [p.evidence[0].id],
        basis: "Explicit fixture identity/origin evidence.",
      }),
    ),
    sourceUsage: [],
    uncertainties: [],
    conflicts: [],
    requiresReview: false,
    reviewReason: null,
  });
}
test("reviewed original identity packages distinguish Base Game, DLC and unknown packages", () => {
  for (let i = 1; i <= 4; i++) {
    const x = packet([`DLC${i}_gd_items.Title.Origin`]);
    assert.equal(extractedContent(x.f, x.records).dlc, contentPacks[i]);
    assert.equal(x.p.facts.dlc, contentPacks[i]);
  }
  const x = packet(["gd_shields.Title.Origin"]);
  assert.equal(x.p.facts.dlc, "Base Game");
  assert.equal(packet(["gd_unreviewed.Title.Origin"]).p.facts.dlc, null);
  assert.equal(
    packet(["gd_shields.Title.Origin", "dlc3_gd_items.Title.Origin"]).p.facts
      .dlc,
    null,
  );
  assert.equal(
    extractedContent(family(["dlc3_missing.Title.Origin"]), x.records).dlc,
    null,
  );
});
test("shared DLC loot/parts do not assign origin; contradictory identity roots remain unknown", () => {
  const base = "gd_shields.Title.Origin",
    shared = "dlc3_gd_itempools.Origin";
  const records = new Map(
    [raw(base, { Pool: { $ref: shared } }), raw(shared)].map((r) => [
      r.path.toLowerCase(),
      r,
    ]),
  );
  assert.equal(
    buildPacket({ records, sources: () => [], get: () => null }, family([base]))
      .facts.dlc,
    "Base Game",
  );
  assert.equal(
    packet(["dlc2_gd_items.Title.Origin", "dlc3_gd_items.Title.Origin"]).p.facts
      .dlc,
    null,
  );
});
test("build validation preserves extracted DLC and requires an evidence claim for every known origin", () => {
  const { p } = packet(["dlc3_gd_items.Title.Origin"]),
    d = draft(p, contentPacks[3]);
  validateDraft(d, p);
  d.entry.dlc = "Base Game";
  assert.throws(() => validateDraft(d, p), /DLC differs/);
  d.entry.dlc = contentPacks[3];
  d.claims = d.claims.filter((c) => c.field !== "dlc");
  assert.throws(() => validateDraft(d, p), /claim for dlc/);
});
test("final JSON keeps item origin independent of acquisition DLC and rejects game/series metadata", () => {
  const { p } = packet(["gd_shields.Title.Origin"]),
    d = draft(p, "Base Game");
  d.entry.sources = [
    {
      label: "DLC chest",
      url: null,
      kind: "other",
      location: null,
      dlc: contentPacks[3],
      conditions: [],
      notes: "",
      dropChance: null,
    },
  ];
  const result = assembleWebsiteEntry(d.entry, []);
  assert.equal(result.dlc, "Base Game");
  assert.equal(result.sources[0].dlc, contentPacks[3]);
  assert(!("game" in result));
  assert.equal(
    WebsiteEntry.safeParse({ ...result, game: "borderlands-goty-enhanced" })
      .success,
    false,
  );
  assert.equal(
    PublicEntry.safeParse({ ...d.entry, game: "borderlands-goty-enhanced" })
      .success,
    false,
  );
  d.entry.dlc = null;
  assert.equal(assembleWebsiteEntry(d.entry, []).dlc, null);
  assert(commonFields.includes("dlc"));
  assert(
    SourceReading.shape.facts.element.shape.field.safeParse("dlc").success,
  );
});
