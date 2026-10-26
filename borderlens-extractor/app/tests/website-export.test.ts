import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import AdmZip from "adm-zip";
import { Store } from "../src/server/store.ts";
import { discover } from "../src/server/importer.ts";
import { PublicEntry } from "../src/shared/models.ts";
import { websiteZip } from "../src/server/website-export.ts";
import { WebsiteEntry, itemSlug } from "../src/shared/website.ts";
import { COMPILER_VERSION } from "../src/shared/versions.ts";
function setup(t: any) {
  const dir = mkdtempSync(path.join(tmpdir(), "borderlens-website-")),
    s = new Store(dir);
  t.after(() => {
    s.close();
    rmSync(dir, { recursive: true, force: true });
  });
  return s;
}
function add(
  s: Store,
  name: string,
  native = "patrol_smg",
  category = "Weapons",
) {
  const f = discover(
    new Map([
      [
        name,
        {
          id: name,
          record_type: "object",
          path: `gd_weap_${native === "classmod" ? "patrol_smg" : native}.Title.Title_Fixture`,
          class: "WillowGame.WeaponNamePartDefinition",
          properties: { PartName: name },
        },
      ],
    ]),
  )[0];
  f.category = category as any;
  f.status = "done";
  s.state.families.push(f);
  s.put(
    f.id,
    "output",
    PublicEntry.parse({
      schemaVersion: "7",
      compilerVersion: COMPILER_VERSION,
      id: f.id,
      name,
      category,
      dlc: null,
      weaponType: category === "Weapons" ? "SMGs" : null,
      summary: "A useful synthetic entry for website export tests.",
      description: [
        "Original synthetic description for a website export fixture.",
      ],
      parts: [],
      variants: [],
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
    }),
  );
  return f;
}
test("type folders mirror the website, apostrophes are removed, and archive contains only item JSON", (t) => {
  const s = setup(t);
  add(s, "Ajax's Spear");
  add(s, "Fixture shield", "shield", "Shields");
  add(s, "Fixture class", "classmod", "Class mods");
  add(s, "Fixture grenade", "grenademod", "Grenade mods");
  const zip = new AdmZip(websiteZip(s));
  assert.deepEqual(
    zip
      .getEntries()
      .map((e) => e.entryName)
      .sort(),
    [
      "class-mods/fixture-class.json",
      "grenade-mods/fixture-grenade.json",
      "shields/fixture-shield.json",
      "weapons/ajaxs-spear.json",
    ],
  );
  for (const file of zip.getEntries()) {
    const item = WebsiteEntry.parse(JSON.parse(zip.readAsText(file)));
    assert.ok(!("references" in item));
    assert.ok(!("game" in item));
    assert.ok("dlc" in item);
    assert.ok(!("sourceUsage" in item));
    assert.ok(!("researchAudit" in item));
  }
});
test("same-name items never silently overwrite each other", (t) => {
  const s = setup(t);
  add(s, "Cobra", "combat_rifle");
  add(s, "Cobra", "sniper_rifle");
  const zip = new AdmZip(websiteZip(s)),
    names = zip.getEntries().map((e) => e.entryName);
  assert.equal(names.length, 2);
  assert.equal(new Set(names).size, 2);
  assert.ok(names.every((n) => n.startsWith("weapons/cobra-")));
});
test("unfinished, excluded and legacy entries are omitted; no-ready export is an explicit error", (t) => {
  const s = setup(t);
  assert.throws(() => websiteZip(s), /No completed/);
  const f = add(s, "Fixture");
  f.status = "blocked";
  assert.throws(() => websiteZip(s), /No completed/);
  f.status = "excluded";
  assert.throws(() => websiteZip(s), /No completed/);
  f.status = "done";
  s.put(f.id, "output", { schemaVersion: "1" });
  assert.throws(() => websiteZip(s), /No completed/);
});

test("conditional drop rates group by acquisition identity without choosing or rounding a rate", async (t) => {
  const { acquisitionSources } = await import("../src/shared/acquisition.ts");
  const s = setup(t),
    f = add(s, "Bessie");
  const output = s.get<PublicEntry>(f.id, "output")!;
  const base = {
    label: "Crawmerax",
    url: "https://example.org/bessie",
    kind: "enemy" as const,
    notes: "",
    location: "Craw's Lair",
    dlc: "General Knoxx",
    conditions: ["Requires DLC"],
  };
  output.sources = [
    {
      ...base,
      conditions: [...base.conditions, "One-player game"],
      dropChance: {
        percent: 0.143,
        players: 1,
        conditions: ["Enhanced edition"],
      },
    },
    {
      ...base,
      url: "https://example.org/second",
      conditions: [...base.conditions, "Four-player game"],
      dropChance: {
        percent: 0.159,
        players: 4,
        conditions: ["Enhanced edition"],
      },
    },
  ];
  s.put(f.id, "output", output);
  const { websiteEntry } = await import("../src/server/website-export.ts");
  const entry = websiteEntry(s, f)!;
  assert.equal(entry.sources.length, 1);
  assert.deepEqual(entry.sources[0].conditions, ["Requires DLC"]);
  assert.deepEqual(
    entry.sources[0].dropChances.map((r) => [r.percent, r.players]),
    [
      [0.143, 1],
      [0.159, 4],
    ],
  );
  assert.ok(
    !entry.sources[0].dropChances[0].conditions.includes("One-player game"),
  );
  assert.ok(!JSON.stringify(entry).includes('"notes":""'));
  const server = (await import("../src/server/http.ts"))
    .api(s, new (await import("../src/server/worker.ts")).Worker(s))
    .listen(0, "127.0.0.1");
  await new Promise<void>((resolve) => server.once("listening", resolve));
  t.after(() => server.close());
  const response = await fetch(
    `http://127.0.0.1:${(server.address() as any).port}/api/items/${f.id}/action`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ action: "save-output", output: entry }),
    },
  );
  assert.equal(response.status, 200, await response.text());
  assert.deepEqual(websiteEntry(s, f)!.sources, entry.sources);
  assert.deepEqual(
    acquisitionSources([...output.sources, output.sources[0]]),
    entry.sources,
  );
  assert.throws(
    () =>
      acquisitionSources([
        output.sources[0],
        {
          ...output.sources[0],
          dropChance: { ...output.sources[0].dropChance!, percent: 0.2 },
        },
      ]),
    /Conflicting drop chances/,
  );
  // Different locations and unknown-rate conditions must never be lost to grouping.
  const unknown = acquisitionSources([
    { ...base, dropChance: null, conditions: ["After mission"] },
    { ...base, dropChance: null, conditions: ["Before mission"] },
    { ...output.sources[0], location: "Another map" },
  ]);
  assert.equal(unknown.length, 3);
  assert.deepEqual(unknown[0].conditions, ["After mission"]);
});

test("character equipment has self-contained restrictions and readable distinct export filenames", (t) => {
  const s = setup(t);
  for (const [character, native] of [
    ["Roland", "patrol_smg"],
    ["Lilith", "sniper_rifle"],
  ] as const) {
    const f = add(s, "Incendiary Artifact", native, "Artifacts");
    f.character = character;
    const output = s.get<PublicEntry>(f.id, "output")!;
    output.character = character;
    s.put(f.id, "output", output);
  }
  const old = add(s, "Artifact");
  old.supersededBy = s.state.families.slice(0, 2).map((f) => f.id);
  const zip = new AdmZip(websiteZip(s));
  assert.deepEqual(
    zip
      .getEntries()
      .map((e) => e.entryName)
      .sort(),
    [
      "artifacts/incendiary-artifact-lilith.json",
      "artifacts/incendiary-artifact-roland.json",
    ],
  );
  for (const e of zip.getEntries()) {
    const output = WebsiteEntry.parse(JSON.parse(zip.readAsText(e)));
    assert.ok(e.entryName.includes(output.character!.toLowerCase()));
  }
});

test("item revision survives views/exports and saved edits cannot spoof the counter", async (t) => {
  const s = setup(t),
    f = add(s, "Revision fixture");
  f.revision = 3;
  const { websiteEntry } = await import("../src/server/website-export.ts");
  const { Worker } = await import("../src/server/worker.ts");
  const before = websiteEntry(s, f)!;
  assert.deepEqual(Object.keys(before).slice(0, 3), [
    "schemaVersion",
    "compilerVersion",
    "revision",
  ]);
  assert.equal(before.schemaVersion, "9");
  assert.equal(before.revision, 3);
  for (let i = 0; i < 2; i++) {
    const zip = new AdmZip(websiteZip(s));
    const doc = JSON.parse(zip.readAsText(zip.getEntries()[0]));
    assert.equal(doc.revision, 3);
    assert.equal(f.revision, 3);
  }
  const w = new Worker(s, {
    status: async () => ({}),
    run: async () => {
      throw Error("No model expected");
    },
  } as any);
  await w.action(f.id, "save-output", { output: { ...before, revision: 999 } });
  assert.equal(f.revision, 4);
  assert.equal(websiteEntry(s, f)!.revision, 4);
  s.save();
  const persisted = JSON.parse(
    (s.db.prepare("select value from meta where key='project'").get() as any)
      .value,
  );
  assert.equal(persisted.families[0].revision, 4);
});
