import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import AdmZip from "adm-zip";
import { Store, hash } from "../src/server/store.ts";
import { importZip } from "../src/server/importer.ts";
import { Research } from "../src/server/research.ts";
import { Worker } from "../src/server/worker.ts";
import { buildPacket } from "../src/server/evidence.ts";
import {
  checkedName,
  verifyAndApplyName,
} from "../src/server/name-verification.ts";
import { NameDecision } from "../src/shared/names.ts";
import {
  CATALOGUE_SCHEMA_VERSION,
  COMPILER_VERSION,
} from "../src/shared/versions.ts";
import { gameData } from "../src/server/game-data.ts";
import { websiteEntry, websiteZip } from "../src/server/website-export.ts";
import { emptySourceReading } from "./source-fixture.ts";
import { api } from "../src/server/http.ts";
import { effortForTask } from "../src/shared/agents.ts";
const quote = "Eridian Rifle is an obtainable Eridian weapon in Borderlands.";
function archive() {
  const zip = new AdmZip(),
    data = Buffer.from(
      JSON.stringify(
        ["alien_rifle", "combat_rifle"].map((type, i) => ({
          id: "raw-" + i,
          record_type: "object",
          path: `gd_weap_${type}.Title.Title_Rifle`,
          class: "WillowGame.WeaponNamePartDefinition",
          properties: { PartName: "Rifle" },
        })),
      ),
    );
  zip.addFile("data/0001.json", data);
  zip.addFile(
    "manifest.json",
    Buffer.from(
      JSON.stringify({
        format_version: 1,
        extractor_version: "fixture",
        chunks: [{ file: "data/0001.json", records: 2, sha256: hash(data) }],
      }),
    ),
  );
  return zip.toBuffer();
}
function fixture(t: any) {
  const dir = mkdtempSync(path.join(tmpdir(), "names-"));
  let s = new Store(dir);
  importZip(s, archive(), "names-fixture.zip");
  const f = s.state.families.find((f) => f.subtype === "Eridian weapons")!,
    other = s.state.families.find(
      (f) =>
        f.id !==
        s.state.families.find((f) => f.subtype === "Eridian weapons")!.id,
    )!;
  const page = new Research(s).save(
    f,
    "https://www.lootlemon.com/weapon/eridian-rifle-bl1",
    `<main><h1>Eridian Rifle</h1><p>${quote}</p></main>`,
    true,
  );
  t.after(() => {
    s.close();
    rmSync(dir, { recursive: true, force: true });
  });
  return {
    get s() {
      return s;
    },
    f,
    other,
    page,
    reopen() {
      s.close();
      s = new Store(dir);
      return s;
    },
  };
}
function proposal(x: ReturnType<typeof fixture>) {
  return NameDecision.parse({
    name: "Eridian Rifle",
    identityVerified: true,
    availability: "obtainable",
    identityPaths: x.f.roots,
    reason:
      "Exact released-game naming quote corroborated by the extracted Eridian weapon type.",
    conflicts: [],
    evidence: [{ id: x.page.id, quote }],
    corroboration: [{ kind: "weaponType", id: x.page.id, quote }],
  });
}
test("rename needs exact naming quotes plus independently compatible identity; a generic Rifle match is insufficient", async (t) => {
  const x = fixture(t),
    p = buildPacket(x.s, x.f),
    d = proposal(x);
  assert(checkedName(x.s, x.f, p, d));
  assert.equal(
    checkedName(x.s, x.other, buildPacket(x.s, x.other), {
      ...d,
      identityPaths: x.other.roots,
    }),
    null,
  );
  for (const bad of [
    { ...d, identityVerified: false },
    { ...d, availability: "cut" },
    { ...d, identityPaths: ["unrelated"] },
    { ...d, corroboration: [] },
    { ...d, conflicts: ["Wrong identity"] },
    { ...d, name: "Another Rifle" },
    { ...d, name: "Blaster" },
    {
      ...d,
      evidence: [
        { id: x.page.id, quote: "Invented quotation naming an Eridian Rifle." },
      ],
    },
  ])
    assert.equal(checkedName(x.s, x.f, p, bad as any), null);
  await new Worker(x.s, {} as any).action(x.f.id, "exclude-source", {
    url: x.page.url,
  });
  assert.equal(checkedName(x.s, x.f, p, d), null);
});
test("only proposed supported renames get one medium verification; uncertainty/failure keeps names and does not fail the build", async (t) => {
  const x = fixture(t),
    p = buildPacket(x.s, x.f),
    d = proposal(x);
  let calls = 0;
  const ai = {
    run: async (label: string) => {
      calls++;
      assert.equal(effortForTask(label), "medium");
      return { ...d, identityVerified: false };
    },
  } as any;
  assert.equal(
    await verifyAndApplyName(x.s, x.f, p, null, ai, () => {}),
    false,
  );
  assert.equal(calls, 0);
  assert.equal(
    await verifyAndApplyName(
      x.s,
      x.f,
      p,
      { ...d, corroboration: [] } as any,
      ai,
      () => {},
    ),
    false,
  );
  assert.equal(calls, 0);
  assert.equal(await verifyAndApplyName(x.s, x.f, p, d, ai, () => {}), false);
  assert.equal(calls, 1);
  assert.equal(x.f.name, "Rifle");
  assert.equal(
    await verifyAndApplyName(
      x.s,
      x.f,
      p,
      d,
      {
        run: async () => {
          throw Error("capacity");
        },
      } as any,
      () => {},
    ),
    false,
  );
  assert.equal(x.f.name, "Rifle");
});
test("verified names persist separately across restart/import/generated reset; IDs, raw view, sources and sibling remain unchanged", async (t) => {
  const x = fixture(t),
    p = buildPacket(x.s, x.f),
    d = proposal(x),
    id = x.f.id,
    other = JSON.stringify(x.other),
    before = gameData(x.s, id),
    run = JSON.stringify(x.s.state.run),
    roots = JSON.stringify(x.f.roots);
  assert(
    await verifyAndApplyName(
      x.s,
      x.f,
      p,
      d,
      { run: async () => d } as any,
      () => {},
    ),
  );
  assert.equal(x.f.name, "Eridian Rifle");
  assert.equal(x.f.rawName, "Rifle");
  assert(x.f.aliases.includes("Rifle"));
  assert.equal(JSON.stringify(x.other), other);
  assert.equal(JSON.stringify(x.f.roots), roots);
  assert.equal(JSON.stringify(x.s.state.run), run);
  assert.deepEqual(gameData(x.s, id), before);
  assert.equal(
    JSON.parse(readFileSync(path.join(x.s.dir, "name-overrides.json"), "utf8"))
      .entries[id].name,
    "Eridian Rifle",
  );
  const reopened = x.reopen();
  assert.equal(reopened.family(id).name, "Eridian Rifle");
  importZip(reopened, archive(), "names-again.zip");
  assert.equal(reopened.family(id).name, "Eridian Rifle");
  assert.equal(reopened.sources(id)[0].hash, x.page.hash);
  const server = api(reopened, new Worker(reopened, {} as any)).listen(
    0,
    "127.0.0.1",
  );
  await new Promise<void>((r) => server.once("listening", r));
  t.after(() => server.close());
  const base = `http://127.0.0.1:${(server.address() as any).port}`;
  assert.equal(
    (
      await fetch(base + "/api/reset", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scope: "generated", confirmation: "RESET" }),
      })
    ).status,
    200,
  );
  assert.equal(reopened.family(id).name, "Eridian Rifle");
  assert.equal(
    (
      await fetch(base + "/api/reset", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scope: "all", confirmation: "RESET" }),
      })
    ).status,
    200,
  );
  assert.deepEqual(reopened.names.data.entries, {});
});
test("normal AI build publishes the verified name and slug, preserves the other Rifle, and keeps rename proof private", async (t) => {
  const x = fixture(t),
    d = proposal(x),
    w = new Worker(x.s, {} as any);
  x.f.stage = "draft";
  x.f.gameOnly = false;
  w.ai = {
    run: async (label: string, _prompt: string, schema: any) => {
      if (label.startsWith("Read source"))
        return schema.parse(emptySourceReading());
      if (label.startsWith("Verify item name")) return schema.parse(d);
      const p = buildPacket(x.s, x.f);
      return schema.parse({
        nameDecision: d,
        entry: {
          schemaVersion: CATALOGUE_SCHEMA_VERSION,
          compilerVersion: COMPILER_VERSION,
          id: x.f.id,
          name: x.f.name,
          category: "Weapons",
          weaponType: "Eridian weapons",
          dlc: null,
          summary: "An ancient energy rifle with unusual alien construction.",
          description: [
            "This synthetic catalogue paragraph describes the energy weapon without borrowing source wording.",
          ],
          details: [],
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
        },
        claims: ["summary", "description"].map((field) => ({
          field,
          evidenceIds: [p.evidence[0].id],
          basis: "Synthetic independent game description.",
        })),
        partDefinitions: [],
        sourceUsage: [],
        uncertainties: [],
        conflicts: [],
        requiresReview: false,
        reviewReason: null,
      });
    },
  } as any;
  await w.step(x.f);
  assert.equal(x.f.stage, "validate");
  assert.equal(x.f.name, "Eridian Rifle");
  await w.step(x.f);
  assert.equal(x.f.stage, "complete");
  x.f.status = "done";
  x.s.save();
  const output = websiteEntry(x.s, x.f)!;
  assert.equal(output.name, "Eridian Rifle");
  assert.equal(output.slug, "eridian-rifle");
  assert(!("nameDecision" in output));
  assert(!("rawName" in output));
  assert.equal(x.other.name, "Rifle");
  assert.deepEqual(
    new AdmZip(websiteZip(x.s)).getEntries().map((e) => e.entryName),
    ["weapons/eridian-rifle.json"],
  );
});
