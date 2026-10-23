import { test } from "node:test";
import assert from "node:assert/strict";
import {
  catalogueGroup,
  catalogueOrder,
  classificationNote,
} from "../src/shared/taxonomy.ts";
import { discover } from "../src/server/importer.ts";
test("navigation groups internal subtypes without merging distinct family IDs", () => {
  const rows = [
    "combat_rifle",
    "support_machinegun",
    "machine_pistol",
    "repeater_pistol",
    "grenade_launcher",
  ].map((type, i) => ({
    id: String(i),
    record_type: "object",
    class: "WillowGame.WeaponNamePartDefinition",
    path: `gd_weap_${type}.Title.Title_${i}`,
    properties: { PartName: "Family " + i },
  }));
  const families = discover(
    new Map(rows.map((r) => [r.path.toLowerCase(), r])),
  );
  assert.deepEqual(families.map(catalogueGroup), [
    "Combat rifles",
    "Combat rifles",
    "Repeater pistols",
    "Repeater pistols",
    "Needs review",
  ]);
  assert.equal(new Set(families.map((f) => f.id)).size, 5);
  assert.equal(
    families.find((f) => f.subtype === "Machine guns")?.subtype,
    "Machine guns",
  );
  assert.ok(classificationNote(families[4]));
  assert.equal(classificationNote(families[0]), null);
  assert.deepEqual([...families].reverse().sort(catalogueOrder), families);
});
