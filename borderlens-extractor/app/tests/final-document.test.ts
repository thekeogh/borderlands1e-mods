import { test } from "node:test";
import assert from "node:assert/strict";
import { PublicEntry } from "../src/shared/models.ts";
import {
  CATALOGUE_SCHEMA_VERSION,
  COMPILER_VERSION,
} from "../src/shared/versions.ts";
import { assembleWebsiteEntry } from "../src/server/final-entry.ts";
import {
  serializeWebsiteDocument,
  parseWebsiteJSON,
  validateWebsiteDocument,
} from "../src/shared/final-document.ts";
import { acquisitionSources } from "../src/shared/acquisition.ts";
function fixture() {
  return PublicEntry.parse({
    schemaVersion: CATALOGUE_SCHEMA_VERSION,
    compilerVersion: COMPILER_VERSION,
    id: "fixture",
    name: "Fixture",
    game: "borderlands-goty-enhanced",
    category: "Weapons",
    weaponType: "Sniper rifles",
    summary: "A precise synthetic rifle used for final validation.",
    description: [
      "Original synthetic player-facing content used for final document checks.",
    ],
    details: [],
    variants: [],
    parts: [],
    manufacturers: ["Jakobs"],
    rarities: ["Pearlescent"],
    elements: ["Non-elemental"],
    redText: null,
    specialEffects: [],
    levels: { minimum: null, maximum: null, notes: "" },
    stats: [],
    sources: [],
    notes: ['Reloading exposes a "357" marking on the cartridges.'],
    references: [],
  });
}
test("whole JSON round-trips quoted prose, strips value-only notes and enforces canonical elements", () => {
  const entry = fixture();
  entry.stats = [
    {
      name: "Damage",
      context: "Card",
      minimum: 825,
      maximum: 1911,
      unit: "",
      level: null,
      notes: "825-1911.",
    },
    {
      name: "Magazine capacity",
      context: "Card",
      minimum: 3,
      maximum: 6,
      unit: "rounds",
      level: null,
      notes: "3–6 rounds.",
    },
    {
      name: "Sway",
      context: "While scoped",
      minimum: 0,
      maximum: 0,
      unit: "%",
      level: null,
      notes: "0%.",
    },
    {
      name: "Critical hit bonus",
      context: "scale",
      minimum: 150,
      maximum: 150,
      unit: "%",
      level: null,
      notes: "Unique scope multiplier",
    },
  ];
  const doc = assembleWebsiteEntry(entry, []),
    json = serializeWebsiteDocument(doc);
  assert.ok(json.includes('\\"357\\"'));
  assert.equal(parseWebsiteJSON(json).notes[0], entry.notes[0]);
  assert.ok(doc.stats.slice(0, 3).every((s) => s.notes === undefined));
  assert.equal(doc.stats[3].notes, "Unique scope multiplier");
  assert.equal(doc.stats[3].context, "Multiplier");
  assert.throws(
    () => parseWebsiteJSON('{"notes":["A "357" marking"]}'),
    SyntaxError,
  );
  assert.throws(() => validateWebsiteDocument({ ...doc, elements: ["None"] }));
  for (const category of [
    "Shields",
    "Grenade mods",
    "Class mods",
    "Artifacts",
    "Other equipment",
  ] as const)
    assert.doesNotThrow(() =>
      assembleWebsiteEntry({ ...entry, category, weaponType: null }, []),
    );
});
test("whole-document checks reject reversed bounds, repeated contexts, missing parts and malformed rates", () => {
  const e = fixture(),
    doc = assembleWebsiteEntry(e, []);
  assert.throws(
    () =>
      validateWebsiteDocument({ ...doc, levels: { minimum: 10, maximum: 2 } }),
    /reversed/,
  );
  const stat = {
    name: "Accuracy",
    context: "Card",
    minimum: 1,
    maximum: 2,
    unit: "",
    level: null,
  };
  assert.throws(
    () => validateWebsiteDocument({ ...doc, stats: [stat, stat] }),
    /stat context/,
  );
  assert.throws(
    () =>
      validateWebsiteDocument({ ...doc, stats: [{ ...stat, notes: "1-2." }] }),
    /repeat the structured/,
  );
  assert.throws(
    () =>
      assembleWebsiteEntry(
        {
          ...e,
          parts: [
            {
              partId: "part-0000000000000000",
              relationship: "defining",
              notes: "",
            },
          ],
        },
        [],
      ),
    /Missing inline part/,
  );
  const source = {
    label: "Crawmerax",
    url: null,
    kind: "enemy" as const,
    location: "Craw's Lair",
    dlc: "General Knoxx",
    conditions: ["Enhanced Edition"],
    dropChances: [{ percent: 0.143, players: 1, conditions: [] }],
  };
  assert.doesNotThrow(() =>
    validateWebsiteDocument({ ...doc, sources: [source] }),
  );
  assert.throws(
    () =>
      validateWebsiteDocument({
        ...doc,
        sources: [
          {
            ...source,
            dropChances: [
              { percent: 0.143, players: 1, conditions: ["Enhanced"] },
            ],
          },
        ],
      }),
    /common acquisition/,
  );
  assert.throws(
    () =>
      validateWebsiteDocument({
        ...doc,
        sources: [
          {
            ...source,
            dropChances: [
              { percent: 0.143, players: 1, conditions: ["Four players"] },
            ],
          },
        ],
      }),
    /contradictory/,
  );
  assert.throws(
    () =>
      validateWebsiteDocument({
        ...doc,
        sources: [
          {
            ...source,
            dropChances: [
              {
                percent: 0.122,
                players: null,
                conditions: ["0.122% to 0.139%"],
              },
            ],
          },
        ],
      }),
    /range/,
  );
  assert.throws(
    () =>
      validateWebsiteDocument({
        ...doc,
        sources: [{ ...source, conditions: ["Original Borderlands"] }],
      }),
    /Enhanced catalogue/,
  );
  assert.throws(
    () => validateWebsiteDocument({ ...doc, sources: [source, source] }),
    /repeats a rated/,
  );
  assert.throws(
    () =>
      validateWebsiteDocument({
        ...doc,
        sources: [{ ...source, url: "javascript:alert(1)" }],
      }),
    /HTTP/,
  );
});
test("conditional labels group cleanly without losing rates, editions or player counts", () => {
  const base = {
    url: null,
    kind: "enemy" as const,
    location: "Craw's Lair",
    dlc: "Knoxx",
    conditions: ["Enhanced Edition"],
    notes: "",
  };
  const sources = acquisitionSources([
    {
      ...base,
      label: "Crawmerax (1 player, Enhanced)",
      dropChance: {
        percent: 0.143,
        players: 1,
        conditions: ["One player", "Enhanced Edition"],
      },
    },
    {
      ...base,
      label: "Crawmerax (4 players, Enhanced)",
      dropChance: {
        percent: 0.159,
        players: 4,
        conditions: ["Four players", "Enhanced Edition"],
      },
    },
  ]);
  assert.equal(sources.length, 1);
  assert.equal(sources[0].label, "Crawmerax");
  assert.deepEqual(sources[0].conditions, ["Enhanced Edition"]);
  assert.deepEqual(sources[0].dropChances, [
    { percent: 0.143, players: 1, conditions: [] },
    { percent: 0.159, players: 4, conditions: [] },
  ]);
});
