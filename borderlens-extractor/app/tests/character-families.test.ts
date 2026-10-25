import { api } from "../src/server/http.ts";
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import {
  discover,
  discoverCharacterFamilies,
  reconcileCharacterFamilies,
} from "../src/server/importer.ts";
import { Store } from "../src/server/store.ts";
import { Worker } from "../src/server/worker.ts";
import { buildPacket } from "../src/server/evidence.ts";
import type { Raw, Family } from "../src/shared/models.ts";
const row = (path: string, cls: string, properties: any): Raw => ({
  id: path,
  path,
  record_type: "object",
  class: "WillowGame." + cls,
  properties,
});
function records() {
  const rows: Raw[] = [];
  for (const [character, required] of [
    ["Roland", 1],
    ["Lilith", 3],
  ] as const) {
    rows.push(
      row(`gd_CommandDecks.A_Item.${character}`, "ItemDefinition", {
        RequiredCharacter: required,
        BodyParts: { $ref: `gd_CommandDecks.Body.${character}` },
      }),
    );
    rows.push(
      row(`gd_CommandDecks.Body.${character}`, "ItemPartListDefinition", {
        WeightedParts: [
          {
            Part: { $ref: `gd_CommandDecks.Body.${character}_Leader` },
            DefaultWeight: { BaseValueConstant: 1 },
          },
        ],
      }),
    );
    rows.push(
      row(`gd_CommandDecks.Body.${character}_Leader`, "ItemPartDefinition", {
        PrefixList: [{ $ref: `gd_CommandDecks.Prefix.${character}_Leader` }],
      }),
    );
    rows.push(
      row(
        `gd_CommandDecks.Prefix.${character}_Leader`,
        "ItemNamePartDefinition",
        { PartName: "Leader" },
      ),
    );
    rows.push(
      row(`gd_ElementalUpgrade.A_Item.${character}`, "ItemDefinition", {
        RequiredCharacter: required,
        RightSideParts: { $ref: "gd_ElementalUpgrade.RightSide.List" },
      }),
    );
  }
  rows.push(
    row("gd_CommandDecks.Title.Generic", "ItemNamePartDefinition", {
      PartName: "Class Mod",
    }),
  );
  rows.push(
    row("gd_ElementalUpgrade.Title.Generic", "ItemNamePartDefinition", {
      PartName: "Artifact",
    }),
  );
  rows.push(
    row("gd_ElementalUpgrade.RightSide.List", "ItemPartListDefinition", {
      WeightedParts: [
        {
          Part: { $ref: "gd_ElementalUpgrade.RightSide.Fire" },
          DefaultWeight: { BaseValueConstant: 1 },
        },
      ],
    }),
  );
  rows.push(
    row("gd_ElementalUpgrade.RightSide.Fire", "ItemPartDefinition", {
      PrefixList: [{ $ref: "gd_ElementalUpgrade.Prefix.Fire" }],
    }),
  );
  rows.push(
    row("gd_ElementalUpgrade.Prefix.Fire", "ItemNamePartDefinition", {
      PartName: "Incendiary",
    }),
  );
  // Fixed DLC collections deliberately have zero default weight.
  rows.push(
    row(
      "dlc3_gd_customitems.Collection.Marine",
      "ItemPartListCollectionDefinition",
      {
        AssociatedItem: { $ref: "gd_CommandDecks.A_Item.Roland" },
        BodyPartData: {
          bEnabled: true,
          WeightedParts: [
            {
              Part: { $ref: "dlc3_gd_CommandDecks.Body.Marine" },
              DefaultWeight: { BaseValueConstant: 0 },
            },
          ],
        },
      },
    ),
  );
  rows.push(
    row("dlc3_gd_CommandDecks.Body.Marine", "ItemPartDefinition", {
      PrefixList: [{ $ref: "dlc3_gd_CommandDecks.Prefix.Marine" }],
    }),
  );
  rows.push(
    row("dlc3_gd_CommandDecks.Prefix.Marine", "ItemNamePartDefinition", {
      PartName: "Marine",
    }),
  );
  rows.push(
    row("gd_weap_sniper.Title.Thunder", "WeaponNamePartDefinition", {
      PartName: "Thunder",
    }),
  );
  return new Map(rows.map((r) => [r.path.toLowerCase(), r]));
}
function setup(t: any) {
  const dir = mkdtempSync(path.join(tmpdir(), "character-families-"));
  const s = new Store(dir);
  t.after(() => {
    s.close();
    rmSync(dir, { recursive: true, force: true });
  });
  return s;
}
test("discover class prefixes by restricted character, fixed DLC parts, artifact elements and unchanged weapons", () => {
  const r = records(),
    f = discover(r),
    mods = f.filter((x) => x.category === "Class mods"),
    artifacts = f.filter((x) => x.category === "Artifacts");
  assert.equal(mods.length, 3);
  assert.equal(artifacts.length, 2);
  assert.equal(
    new Set(mods.filter((x) => x.name === "Leader").map((x) => x.id)).size,
    2,
  );
  assert.equal(mods.find((x) => x.name === "Marine")?.character, "Roland");
  assert.ok(
    artifacts.every(
      (x) => x.element === "Incendiary" && x.name === "Incendiary Artifact",
    ),
  );
  assert.equal(f.filter((x) => x.category === "Weapons")[0].name, "Thunder");
  assert.ok(!f.some((x) => ["Class Mod", "Artifact"].includes(x.name)));
});
test("migration preserves broad output/research, excludes placeholders, is idempotent and links defining evidence", (t) => {
  const s = setup(t);
  s.records = records();
  const weapon = discover(s.records).find((f) => f.category === "Weapons")!;
  const broad = {
    ...weapon,
    id: "broad-old",
    name: "Class Mod",
    category: "Class mods",
    subtype: "Class mods",
    status: "done",
  } as Family;
  s.state.families = [broad, weapon];
  s.put(broad.id, "output", { original: true });
  s.state.run.queue = [broad.id, weapon.id];
  s.state.run.index = 0;
  reconcileCharacterFamilies(s);
  const count = s.state.families.length;
  reconcileCharacterFamilies(s);
  assert.equal(s.state.families.length, count);
  assert.equal(broad.status, "excluded");
  assert.ok(broad.supersededBy?.length);
  assert.deepEqual(s.get(broad.id, "output"), { original: true });
  assert.ok(s.state.run.queue.includes(weapon.id));
  assert.ok(!s.state.run.queue.includes(broad.id));
  assert.equal(s.state.run.queue.length, 6);
  assert.equal(weapon.status, "queued");
  const marine = s.state.families.find((f) => f.name === "Marine")!;
  const p = buildPacket(s, marine);
  assert.ok(
    p.evidence.some((e) => e.path === "dlc3_gd_CommandDecks.Body.Marine"),
  );
});
const until = async (fn: () => boolean) => {
  for (let i = 0; i < 300; i++) {
    if (fn()) return;
    await new Promise((r) => setTimeout(r, 10));
  }
  throw Error("worker timeout");
};
for (const mode of ["saved", "fresh"] as const)
  test(`batch ${mode} marks failure and continues and retains the failed item`, async (t) => {
    const s = setup(t);
    s.state.families = discoverCharacterFamilies(records()).slice(0, 2);
    s.state.settings.research = false;
    const [bad, good] = s.state.families;
    const w = new Worker(s, {} as any);
    const visits: string[] = [];
    w.step = async (f) => {
      visits.push(f.id);
      if (f === bad) throw Error("Synthetic item failure");
      f.stage = "complete";
    };
    const server = api(s, w).listen(0, "127.0.0.1");
    await new Promise<void>((resolve) => server.once("listening", resolve));
    const base = `http://127.0.0.1:${(server.address() as any).port}`;
    t.after(() => server.close());
    const response = await fetch(base + "/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "start", sourceMode: mode }),
    });
    assert.equal(response.status, 200);
    await until(() => !w.busy);
    assert.equal(s.state.run.status, "complete");
    assert.equal(bad.status, "blocked");
    assert.equal(bad.issue, "Synthetic item failure");
    assert.equal(good.status, "done");
    assert.equal(s.state.run.index, 2);
    assert.match(s.state.run.message, /1 item/);
    assert.deepEqual(visits, [bad.id, good.id]);
  });
test("individual rebuild remains blocked on failure", async (t) => {
  const s = setup(t);
  s.state.families = discoverCharacterFamilies(records()).slice(0, 1);
  const w = new Worker(s, {} as any);
  w.step = async () => {
    throw Error("Single failure");
  };
  w.start(undefined, s.state.families[0].id);
  await until(() => !w.busy);
  assert.equal(s.state.run.status, "blocked");
  assert.equal(s.state.run.index, 0);
});

test("reconciliation preserves pending queue order when no new families are discovered", (t) => {
  const s = setup(t);
  s.records = records();
  reconcileCharacterFamilies(s);
  s.state.run.queue = s.state.families.map((f) => f.id).reverse();
  s.state.run.index = 1;
  s.state.run.currentId = s.state.run.queue[1];
  const before = structuredClone(s.state.run);
  reconcileCharacterFamilies(s);
  assert.deepEqual(s.state.run, before);
});
