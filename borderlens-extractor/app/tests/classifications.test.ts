import { emptySourceReading } from "./source-fixture.ts";
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import AdmZip from "adm-zip";
import { Store, hash } from "../src/server/store.ts";
import { importZip } from "../src/server/importer.ts";
import { Worker, type AI } from "../src/server/worker.ts";
import { Research } from "../src/server/research.ts";
import { catalogueGroup } from "../src/shared/taxonomy.ts";
import { buildPacket } from "../src/server/evidence.ts";
import { api } from "../src/server/http.ts";

const raw = {
  id: "ajax-title",
  record_type: "object",
  class: "WillowGame.WeaponNamePartDefinition",
  path: "dlc3_gd_weap_UniqueParts.Title.TitleU_SupportMG_AjaxsSpear",
  properties: { PartName: "Ajax's Spear" },
};
function archive(version = "fixture") {
  const zip = new AdmZip(),
    data = Buffer.from(JSON.stringify([raw]));
  zip.addFile("data/0001.json", data);
  zip.addFile(
    "manifest.json",
    Buffer.from(
      JSON.stringify({
        format_version: 1,
        extractor_version: version,
        chunks: [{ file: "data/0001.json", records: 1, sha256: hash(data) }],
      }),
    ),
  );
  return zip.toBuffer();
}
function setup(t: any) {
  const dir = mkdtempSync(path.join(tmpdir(), "borderlens-classify-"));
  let s = new Store(dir);
  importZip(s, archive(), "fixture.zip");
  s.state.settings.research = false;
  const f = s.state.families[0];
  const page = new Research(s).save(
    f,
    "https://www.lootlemon.com/weapon/test-fixture-bl1",
    "<main><h1>Test fixture only</h1><p>Ajax's Spear is a combat rifle in Borderlands. This synthetic article tests classification; it is not scraped production evidence.</p></main>",
  );
  t.after(() => {
    s.close();
    rmSync(dir, { recursive: true, force: true });
  });
  return {
    s,
    f,
    page,
    reopen: () => {
      s.close();
      s = new Store(dir);
      return s;
    },
  };
}
const until = async (fn: () => boolean) => {
  for (let i = 0; i < 500; i++) {
    if (fn()) return;
    await new Promise((r) => setTimeout(r, 10));
  }
  throw new Error("Worker wait timed out");
};
function ai(
  s: Store,
  page: any,
  onDraft?: () => Promise<void>,
  decision: Record<string, unknown> = {},
): AI {
  return {
    status: async () => ({ chatgpt: true }),
    run: async (label, _prompt, schema) => {
      if (label.startsWith("Read source"))
        return schema.parse(emptySourceReading());
      if (label.startsWith("Classify"))
        return schema.parse({
          weaponType: "Combat rifles",
          identityVerified: true,
          availability: "obtainable",
          reason:
            "Synthetic saved article identifies this exact fixture family.",
          evidence: [
            {
              id: page.id,
              quote: "Ajax's Spear is a combat rifle in Borderlands.",
            },
          ],
          conflicts: [],
          ...decision,
        });
      await onDraft?.();
      const f = s.state.families[0],
        p = buildPacket(s, f);
      return schema.parse({
        entry: {
          schemaVersion: "7",
          compilerVersion: "0.11.2",
          description: [
            "An original fixture paragraph describing this item for players.",
          ],
          references: [],
          variants: [],
          parts: [],
          id: f.id,
          name: f.name,
          dlc: p.facts.dlc || null,
          category: "Weapons",
          weaponType: "SMGs",
          summary: "A synthetic reference entry for a classification test.",
          manufacturers: [],
          rarities: [],
          elements: [],
          redText: null,
          specialEffects: [],
          levels: { minimum: null, maximum: null, notes: "" },
          stats: [],
          sources: [],
          notes: [],
        },
        partDefinitions: [],
        claims: [
          ...(p.facts.dlc
            ? [
                {
                  field: "dlc",
                  evidenceIds: [p.evidence[0].id],
                  basis: "Captured DLC identity package.",
                },
              ]
            : []),
          {
            field: "summary",
            evidenceIds: [p.evidence[0].id],
            basis: "Fixture family name.",
          },
          {
            field: "description",
            evidenceIds: [p.evidence[0].id],
            basis: "Fixture description.",
          },
        ],
        uncertainties: [],
        conflicts: [],
        requiresReview: false,
        reviewReason: null,
      });
    },
  };
}

test("research classification moves a stable item live before drafting completes, without changing capture data", async (t) => {
  const { s, f, page } = setup(t),
    original = s.state.captures[0].id;
  let release!: () => void,
    entered = false,
    revisions = 0;
  s.on("change", () => revisions++);
  const w = new Worker(
    s,
    ai(s, page, async () => {
      entered = true;
      await new Promise<void>((r) => (release = r));
    }),
  );
  const id = f.id;
  assert.equal(catalogueGroup(f), "Needs review");
  w.start(undefined, id);
  await until(() => entered);
  assert.equal(catalogueGroup(f), "Combat rifles");
  assert.equal(f.id, id);
  assert.equal(f.subtype, "Other weapons");
  assert.equal(s.state.run.currentId, id);
  assert.equal(s.state.run.queue[0], id);
  assert.equal(s.state.run.status, "running");
  assert.ok(revisions > 0);
  assert.equal(
    s.classifications.data.entries[id].research!.evidence[0].hash,
    page.hash,
  );
  assert.equal(
    hash(readFileSync(path.join(s.dir, "captures", original + ".zip"))),
    original,
  );
  release();
  await until(() => !w.busy);
  assert.equal(f.status, "done");
  assert.equal(s.get<any>(id, "output").weaponType, "Combat rifles");
});

test("manual > research > raw; file survives restart, reimport and generated reset, and is exported", async (t) => {
  const env = setup(t);
  let s = env.s;
  const id = env.f.id;
  const w = new Worker(s, ai(s, env.page));
  w.start(undefined, id);
  await until(() => !w.busy);
  await w.action(id, "classification", {
    weaponType: "Shotguns",
    notes: "Manual fixture correction.",
  });
  assert.equal(catalogueGroup(s.family(id)), "Shotguns");
  assert.equal(
    s.classifications.data.entries[id].research!.weaponType,
    "Combat rifles",
  );
  s = env.reopen();
  assert.equal(catalogueGroup(s.family(id)), "Shotguns");
  importZip(s, archive("second-fixture"), "new-capture.zip");
  assert.equal(s.state.families.length, 1);
  assert.equal(catalogueGroup(s.family(id)), "Shotguns");
  const worker = new Worker(s, ai(s, env.page));
  await worker.action(id, "rebuild", {});
  await until(() => !worker.busy);
  const server = api(s, worker).listen(0, "127.0.0.1");
  await new Promise<void>((r) => server.once("listening", r));
  t.after(() => server.close());
  const base = `http://127.0.0.1:${(server.address() as any).port}`;
  const exported = new AdmZip(
    Buffer.from(await (await fetch(base + "/api/export")).arrayBuffer()),
  );
  assert.deepEqual(
    exported.getEntries().map((e) => e.entryName),
    ["weapons/ajaxs-spear.json"],
  );
  assert.equal(
    JSON.parse(exported.readAsText("weapons/ajaxs-spear.json")).weaponType,
    "Shotguns",
  );
  assert.equal(
    s.classifications.data.entries[id].manual?.weaponType,
    "Shotguns",
  );
  const post = async (url: string, data: unknown) =>
    fetch(base + url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(data),
    });
  assert.equal(
    (await post("/api/reset", { scope: "generated", confirmation: "RESET" }))
      .status,
    200,
  );
  assert.equal(catalogueGroup(s.family(id)), "Shotguns");
  assert.equal(
    (
      await post("/api/items/" + id + "/action", {
        action: "classification",
        weaponType: null,
      })
    ).status,
    200,
  );
  assert.equal(catalogueGroup(s.family(id)), "Combat rifles");
  assert.equal(
    (
      await post("/api/items/" + id + "/action", {
        action: "classification",
        weaponType: "invented type",
      })
    ).status,
    400,
  );
  assert.equal(
    (await post("/api/reset", { scope: "all", confirmation: "RESET" })).status,
    200,
  );
  assert.deepEqual(
    JSON.parse(readFileSync(s.classifications.filename, "utf8")).entries,
    {},
  );
});

test("external overrides file edits are applied on refresh without replacing raw types", (t) => {
  const { s, f } = setup(t);
  const data = {
    schemaVersion: 1,
    entries: {
      [f.id]: {
        manual: {
          name: f.name,
          weaponType: "Combat rifles",
          reason: "User file correction.",
          verifiedAt: new Date().toISOString(),
          evidence: [],
        },
      },
    },
  };
  writeFileSync(s.classifications.filename, JSON.stringify(data));
  s.syncClassifications();
  assert.equal(catalogueGroup(f), "Combat rifles");
  assert.equal(f.subtype, "Other weapons");
  writeFileSync(s.classifications.filename, '{"schemaVersion":99}');
  assert.throws(() => s.syncClassifications());
  assert.equal(catalogueGroup(f), "Combat rifles");
  writeFileSync(
    s.classifications.filename,
    JSON.stringify({ schemaVersion: 1, entries: {} }),
  );
  s.syncClassifications();
  assert.equal(catalogueGroup(f), "Needs review");
});

test("ambiguous/cut identities and fabricated quotes cannot create researched overrides", async (t) => {
  for (const decision of [
    { identityVerified: false },
    { availability: "cut" },
    { conflicts: ["Source identity differs."] },
    { evidence: [{ id: "invented", quote: "Not in any source text." }] },
  ]) {
    const { s, f, page } = setup(t);
    const w = new Worker(s, ai(s, page, undefined, decision));
    w.start(undefined, f.id);
    await until(() => !w.busy);
    assert.equal(f.status, "blocked");
    assert.equal(catalogueGroup(f), "Needs review");
    assert.equal(s.classifications.effective(f.id), undefined);
    assert.equal(s.get(f.id, "output"), null);
  }
});
