import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync, readFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import AdmZip from "adm-zip";
import { Store, hash } from "../src/server/store.ts";
import { importZip } from "../src/server/importer.ts";
import { Research } from "../src/server/research.ts";
import { Worker } from "../src/server/worker.ts";
import { api } from "../src/server/http.ts";
import { gameData } from "../src/server/game-data.ts";
import type { Raw } from "../src/shared/models.ts";
const title = "gd_weap_patrol_smg.Title.Title_Fixture",
  part = "gd_weap_patrol_smg.acc.Fixture",
  presentation = title + ":Presentation",
  manufacturer = "gd_manufacturers.Manufacturers.Maliwan";
function rows(name = "Fixture"): Raw[] {
  return [
    {
      id: "title",
      record_type: "object",
      path: title,
      class: "WillowGame.WeaponNamePartDefinition",
      complete: true,
      properties: {
        PartName: name,
        MinExpLevelRequirement: 1,
        MaxExpLevelRequirement: 100,
        Rarity: { BaseValueAttribute: { $ref: "gd_Balance.Rarity.Legendary" } },
        CustomPresentations: [{ $ref: presentation }],
      },
    },
    {
      id: "part",
      record_type: "object",
      path: part,
      class: "WillowGame.WeaponPartDefinition",
      complete: true,
      properties: {
        PartName: "Incendiary",
        TitleList: {
          $type: "array",
          items: [{ $ref: title }],
          length: 1,
          truncated: false,
        },
        TechLevelIncrease: 14,
        CustomDamageTypeDefinition: { $ref: "gd_Incendiary.DamageType.Impact" },
        WeaponAttributeEffects: [
          {
            AttributeToModify: { $ref: "d_attributes.Weapon.Damage" },
            ModifierType: 0,
            BaseModifierValue: { BaseValueConstant: 0 },
          },
        ],
      },
    },
    {
      id: "text",
      record_type: "object",
      path: presentation,
      class: "WillowGame.AttributePresentationDefinition",
      properties: {
        bDontDisplayNumber: true,
        NoConstraintText: "Original extracted red text.",
      },
    },
    {
      id: "selection",
      record_type: "object",
      path: "gd_weap_patrol_smg.Parts.Accessory",
      class: "WillowGame.WeaponPartListDefinition",
      properties: {
        WeightedParts: [
          {
            Part: { $ref: part },
            DefaultWeight: { BaseValueConstant: 0 },
            Manufacturers: [
              {
                Manufacturer: { $ref: manufacturer },
                DefaultWeight: { BaseValueConstant: 1 },
              },
            ],
          },
        ],
      },
    },
    {
      id: "manufacturer",
      record_type: "object",
      path: manufacturer,
      class: "Engine.ManufacturerDefinition",
      properties: { ManufacturerName: "Maliwan" },
    },
  ];
}
function zip(records = rows()) {
  const archive = new AdmZip(),
    bytes = Buffer.from(JSON.stringify(records));
  archive.addFile("capture/data/0001.json", bytes);
  archive.addFile(
    "capture/manifest.json",
    Buffer.from(
      JSON.stringify({
        format_version: 1,
        extractor_version: "fixture",
        chunks: [
          {
            file: "data/0001.json",
            records: records.length,
            sha256: hash(bytes),
          },
        ],
      }),
    ),
  );
  return archive.toBuffer();
}
function fixture(t: any) {
  const dir = mkdtempSync(path.join(tmpdir(), "game-data-"));
  let store = new Store(dir);
  t.after(() => {
    store.close();
    rmSync(dir, { recursive: true, force: true });
  });
  importZip(store, zip(), "game.zip");
  return {
    get s() {
      return store;
    },
    reopen() {
      store.close();
      store = new Store(dir);
      return store;
    },
  };
}
test("game view is available before building and exposes only original identity, defining parts and exact captured records", (t) => {
  const { s } = fixture(t),
    f = s.state.families[0],
    before = JSON.stringify(s.state),
    view = gameData(s, f.id);
  assert.equal(view.family.name, "Fixture");
  assert.equal(view.family.subtype, "SMGs");
  assert.deepEqual(view.facts, {
    redText: "Original extracted red text.",
    manufacturers: ["Maliwan"],
    rarities: ["Legendary"],
    elements: ["incendiary"],
  });
  const definition = view.definitions.find((record) => record.path === part)!;
  assert.equal(definition.role, "defining");
  assert.equal(definition.properties.TechLevelIncrease, 14);
  assert.deepEqual(definition.raw, rows()[1]);
  assert.equal(
    view.definitions.find((record) => record.path === title)?.role,
    "root",
  );
  assert.equal(
    view.definitions.find((record) => record.path === manufacturer)?.role,
    "related",
  );
  assert.equal(JSON.stringify(s.state), before);
  assert.equal(s.db.prepare("SELECT COUNT(*) AS n FROM artifacts").get()!.n, 0);
});
test("view stays identical after source capture, shared evidence, overrides, manual corrections, output changes and restart", (t) => {
  const x = fixture(t),
    s = x.s,
    f = s.state.families[0],
    original = JSON.stringify(gameData(s, f.id));
  const scope = s.ensureScope({ category: "Everything" });
  new Research(s).save(
    scope,
    "https://borderlands.fandom.com/wiki/External",
    "<h1>Website only data</h1><p>External-only fixture description must never enter the imported game view, regardless of generated work or source overrides.</p>",
    true,
  );
  s.put(f.id, "packet", { facts: { redText: "Generated packet text" } });
  s.put(f.id, "output", {
    schemaVersion: "5",
    compilerVersion: "0.7.0",
    summary: "Generated output",
  });
  f.name = "Corrected name";
  f.notes = "Manual user correction";
  f.manualOutput = true;
  f.roots = ["not-from-the-zip"];
  f.category = "Shields";
  f.subtype = "Shields";
  f.status = "done";
  f.stage = "complete";
  f.revision = 7;
  s.save();
  assert.equal(JSON.stringify(gameData(s, f.id)), original);
  assert.equal(JSON.stringify(gameData(x.reopen(), f.id)), original);
});
test("game view cannot read source or compiled-artifact storage; changed extraction refreshes it and reset removes it", (t) => {
  const { s } = fixture(t),
    id = s.state.families[0].id,
    originalGet = s.get,
    originalSources = s.sources;
  s.get = () => {
    throw Error("Artifact access prohibited");
  };
  s.sources = () => {
    throw Error("Source access prohibited");
  };
  assert.equal(gameData(s, id).family.name, "Fixture");
  s.get = originalGet;
  s.sources = originalSources;
  importZip(s, zip(rows("Changed name")), "new-game.zip");
  const replacement = s.state.families.find((f) => f.name === "Changed name")!;
  assert.equal(gameData(s, replacement.id).family.name, "Changed name");
  assert.throws(() => gameData(s, id), /No family definition/);
  s.state.captures = [];
  s.records.clear();
  assert.throws(() => gameData(s, replacement.id), /No family definition/);
});
test("GET game-data is read-only and does not populate Preview, source packets or Final JSON", async (t) => {
  const { s } = fixture(t),
    w = new Worker(s, {
      run: async () => {
        throw Error("No AI calls");
      },
    } as any),
    server = api(s, w).listen(0, "127.0.0.1");
  await new Promise<void>((resolve) => server.once("listening", resolve));
  t.after(() => {
    server.closeAllConnections();
    server.close();
  });
  const base = `http://127.0.0.1:${(server.address() as any).port}`,
    f = s.state.families[0],
    before = JSON.stringify(s.state);
  const response = await fetch(base + `/api/items/${f.id}/game-data`);
  assert.equal(response.status, 200);
  assert.equal((await response.json()).family.name, "Fixture");
  assert.equal(JSON.stringify(s.state), before);
  assert.equal(s.get(f.id, "packet"), null);
  assert.equal(s.get(f.id, "output"), null);
  assert.equal(w.busy, false);
  assert.equal(
    (await fetch(base + "/api/items/not-a-family/game-data")).status,
    404,
  );
});
const realZip = path.resolve(
  "../temp/imports/borderlens-20261023-153827-931444.zip",
);
test(
  "real extraction: Hellfire game data has supported facts and native settings before any build",
  { skip: !existsSync(realZip) },
  (t) => {
    const { s } = fixture(t);
    importZip(s, readFileSync(realZip), "real-game.zip");
    const f = s.state.families.find((f) => /^hellfire$/i.test(f.name))!,
      view = gameData(s, f.id);
    assert.equal(view.facts.redText, "We don't need no water...");
    assert.deepEqual(view.facts.elements, ["incendiary"]);
    assert(view.facts.manufacturers.includes("Maliwan"));
    assert(
      view.definitions.some(
        (record) =>
          record.role === "defining" &&
          record.properties.TechLevelIncrease === 14,
      ),
    );
    assert.equal(s.get(f.id, "output"), null);
  },
);
