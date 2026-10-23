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
          path: `gd_weap_${native}.Title.Title_${itemSlug(name)}`,
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
      schemaVersion: "2",
      compilerVersion: COMPILER_VERSION,
      id: f.id,
      name,
      category,
      game: "borderlands-goty-enhanced",
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
  for (const file of zip.getEntries())
    WebsiteEntry.parse(JSON.parse(zip.readAsText(file)));
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
