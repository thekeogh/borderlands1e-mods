import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import AdmZip from "adm-zip";
import { Store, hash } from "../src/server/store.ts";
import { importZip } from "../src/server/importer.ts";
import { Research } from "../src/server/research.ts";
import { Worker } from "../src/server/worker.ts";
import { equipmentCategoryCandidate } from "../src/server/equipment-classification.ts";
import { websiteEntry, websiteZip } from "../src/server/website-export.ts";
import { PublicEntry } from "../src/shared/models.ts";
const row = {
  id: "ironclad-title",
  record_type: "object",
  path: "dlc3_gd_item_UniqueParts.Title.Title_P_Pangolin_Ironclad",
  class: "WillowGame.ItemNamePartDefinition",
  properties: { PartName: "Ironclad" },
};
function archive(version = "fixture") {
  const z = new AdmZip(),
    raw = Buffer.from(JSON.stringify([row]));
  z.addFile("data/0001.json", raw);
  z.addFile(
    "manifest.json",
    Buffer.from(
      JSON.stringify({
        format_version: 1,
        extractor_version: version,
        chunks: [{ file: "data/0001.json", records: 1, sha256: hash(raw) }],
      }),
    ),
  );
  return z.toBuffer();
}
function setup(t: any) {
  const dir = mkdtempSync(path.join(tmpdir(), "equipment-category-"));
  let s = new Store(dir);
  importZip(s, archive(), "fixture.zip");
  t.after(() => {
    s.close();
    rmSync(dir, { recursive: true, force: true });
  });
  const f = s.state.families[0];
  const page = new Research(s).save(
    f,
    "https://www.lootlemon.com/shield/ironclad-bl1",
    "<title>Ironclad • BL1 – Pearlescent Shield | Lootlemon</title><main><h1>Ironclad • BL1 – Pearlescent Shield | Lootlemon</h1><p>The Pearlescent Shield Ironclad comes from the Borderlands 1 game.</p></main>",
  );
  return {
    get s() {
      return s;
    },
    f,
    page,
    reopen() {
      s.close();
      s = new Store(dir);
      return s;
    },
  };
}
test("equipment category requires exact typed BL1 item URL, matching title, and respects removal/manual priority", (t) => {
  const { s, f, page } = setup(t);
  assert.equal(equipmentCategoryCandidate(f, [page])?.category, "Shields");
  for (const bad of [
    { ...page, url: "https://www.lootlemon.com/db/borderlands-1/shields" },
    { ...page, url: "https://www.lootlemon.com/shield/ironclad-bl2" },
    { ...page, title: "Ironclad • BL2 – Shield" },
    { ...page, title: "Other item • BL1 – Shield" },
    { ...page, url: "https://www.lootlemon.com/shield/rose-bl1" },
  ])
    assert.equal(equipmentCategoryCandidate(f, [bad]), null);
  assert.equal(
    equipmentCategoryCandidate({ ...f, status: "excluded" }, [page]),
    null,
  );
  assert.equal(
    equipmentCategoryCandidate(
      {
        ...f,
        classification: {
          name: f.name,
          category: "Other equipment",
          weaponType: null,
          origin: "manual",
          reason: "Manual choice",
          evidence: [],
          verifiedAt: "now",
        },
      },
      [page],
    ),
    null,
  );
});
test("saved category override moves sidebar/export metadata, survives reset/reimport and keeps the stable ID", async (t) => {
  const fixture = setup(t),
    s = fixture.s,
    f = fixture.f,
    id = f.id;
  const noAI = {
    status: async () => ({}),
    run: async () => {
      throw Error("Typed source classification must not call a model");
    },
  } as any;
  const w = new Worker(s, noAI);
  await w.classify(f);
  assert.equal(f.category, "Shields");
  assert.equal(f.subtype, "Shields");
  assert.equal(f.id, id);
  assert.equal(f.rawCategory, "Other equipment");
  assert.equal(f.classification?.category, "Shields");
  assert.equal(
    s.classifications.data.entries[id].research?.category,
    "Shields",
  );
  const e = PublicEntry.parse({
    schemaVersion: "7",
    compilerVersion: "0.15.1",
    id,
    name: f.name,
    dlc: "The Secret Armory of General Knoxx",
    category: f.category,
    weaponType: null,
    summary: "Original synthetic shield for catalogue metadata tests.",
    description: [
      "This synthetic fixture verifies metadata correction without changing the item identity.",
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
  s.put(id, "output", e);
  s.put(id, "provenance", { compilerVersion: "0.15.1" });
  f.status = "done";
  f.stage = "complete";
  f.revision = 1;
  s.save();
  assert.equal(websiteEntry(s, f)?.category, "Shields");
  assert.deepEqual(
    new AdmZip(websiteZip(s)).getEntries().map((e) => e.entryName),
    ["shields/ironclad.json"],
  );
  const r = fixture.reopen(),
    same = r.family(id);
  assert.equal(same.category, "Shields");
  assert.equal(same.status, "done");
  assert.deepEqual(same.roots, [row.path]);
  importZip(r, archive("second"), "second.zip");
  assert.equal(r.family(id).category, "Shields");
  assert.equal(r.sources(id).length, 1);
  r.forget(id, ["output", "packet", "draft"]);
  r.family(id).status = "queued";
  r.family(id).stage = "evidence";
  r.save();
  assert.equal(r.family(id).category, "Shields");
});

test("a completed equipment draft can be revalidated under its corrected category without an AI rebuild", async (t) => {
  const { s, f, page } = setup(t);
  const entry = PublicEntry.parse({
    schemaVersion: "7",
    compilerVersion: "0.15.1",
    id: f.id,
    name: f.name,
    dlc: "The Secret Armory of General Knoxx",
    category: "Other equipment",
    weaponType: null,
    summary: "An original synthetic fixture with equipment category metadata.",
    description: [
      "This independent test description verifies category correction without rewriting saved item content.",
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
  const draft = {
    entry,
    partDefinitions: [],
    sourceUsage: [],
    claims: ["summary", "description", "dlc"].map((field) => ({
      field,
      evidenceIds: [page.id],
      basis: "Synthetic fixture identity",
    })),
    uncertainties: [],
    conflicts: [],
    requiresReview: false,
    reviewReason: null,
  };
  s.put(f.id, "output", entry);
  s.put(f.id, "draft", draft);
  f.stage = "complete";
  f.status = "done";
  f.revision = 1;
  const w = new Worker(s, {
    status: async () => ({}),
    run: async () => {
      throw Error("No model expected");
    },
  } as any);
  await w.classify(f);
  assert.equal(f.stage, "validate");
  assert.equal(f.status, "queued");
  await w.step(f);
  assert.equal(f.stage, "complete");
  assert.equal(f.revision, 2);
  assert.equal(s.get<any>(f.id, "output").category, "Shields");
  assert.equal(s.get<any>(f.id, "output").description[0], entry.description[0]);
  f.status = "done";
  s.save();
  assert.equal(websiteEntry(s, f)?.category, "Shields");
});
