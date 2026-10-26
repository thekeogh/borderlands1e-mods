import { Images } from "../src/server/images.ts";
import { applyNameDecision } from "../src/server/name-verification.ts";
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  mkdtempSync,
  rmSync,
  readFileSync,
  mkdirSync,
  writeFileSync,
} from "node:fs";
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
function archive(version = "fixture") {
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
        extractor_version: version,
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

test("manual names immediately override metadata and block automatic naming at every layer, without model calls", async (t) => {
  const x = fixture(t),
    p = buildPacket(x.s, x.f),
    d = proposal(x),
    id = x.f.id,
    before = gameData(x.s, id),
    run = JSON.stringify(x.s.state.run);
  const w = new Worker(x.s, {
    run: async () => {
      throw Error("Manual names must not invoke an agent");
    },
  } as any);
  assert(w.setManualName(id, '  My "keeper" rifle  ').changed);
  assert.equal(x.f.name, 'My "keeper" rifle');
  assert.equal(x.f.rawName, "Rifle");
  assert(x.f.aliases.includes("Rifle"));
  assert.equal(x.f.nameOverride?.origin, "manual");
  assert.equal(x.s.get(id, "output"), null);
  assert.equal(x.f.revision, 0);
  assert.deepEqual(gameData(x.s, id), before);
  assert.equal(JSON.stringify(x.s.state.run), run);
  assert.equal(x.other.name, "Rifle");
  assert(!(await w.syncIdentity(id, "name")).changed);
  assert(!(await verifyAndApplyName(x.s, x.f, p, d, w.ai, () => {})));
  assert(!applyNameDecision(x.s, x.f, p, d, true));
  const locked = structuredClone(x.s.names.data.entries[id]);
  assert.equal(
    x.s.names.set(id, {
      ...locked,
      origin: "research",
      name: "Eridian Rifle",
      corroboration: d.corroboration,
    }),
    false,
  );
  assert.equal(x.s.names.data.entries[id].name, 'My "keeper" rifle');
  w.setManualName(id, "My final rifle");
  assert.equal(x.f.name, "My final rifle");
  assert(x.f.aliases.includes('My "keeper" rifle'));
  assert.equal(x.f.rawName, "Rifle");
  const reopened = x.reopen();
  importZip(reopened, archive("manual-reimport"), "new-capture.zip");
  assert.equal(reopened.family(id).name, "My final rifle");
  assert.equal(reopened.family(id).nameOverride?.origin, "manual");
  const server = api(reopened, new Worker(reopened, {} as any)).listen(
    0,
    "127.0.0.1",
  );
  await new Promise<void>((r) => server.once("listening", r));
  t.after(() => server.close());
  assert.equal(
    (
      await fetch(
        `http://127.0.0.1:${(server.address() as any).port}/api/reset`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ scope: "generated", confirmation: "RESET" }),
        },
      )
    ).status,
    200,
  );
  assert.equal(reopened.family(id).name, "My final rifle");
  assert.equal(reopened.names.data.entries[id].origin, "manual");
});
test("manual name updates completed JSON, manual drafts, packets and exports while preserving prose, readiness and paused queues", (t) => {
  const x = fixture(t),
    { s, f } = x;
  const e = {
    schemaVersion: CATALOGUE_SCHEMA_VERSION,
    compilerVersion: COMPILER_VERSION,
    id: f.id,
    name: f.name,
    category: "Weapons",
    weaponType: "Eridian weapons",
    dlc: null,
    summary: "An independent synthetic energy rifle used for name editing.",
    description: [
      "The original saved player wording stays exactly as it was before the manual edit.",
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
  };
  s.put(f.id, "output", e);
  s.put(f.id, "manualDraft", { entry: e });
  s.put(f.id, "draft", { entry: e });
  s.put(f.id, "packet", buildPacket(s, f));
  s.put(f.id, "validatedPacket", buildPacket(s, f));
  f.status = "done";
  f.stage = "complete";
  f.revision = 1;
  f.manualOutput = true;
  s.state.run.status = "paused";
  s.state.run.queue = [f.id];
  s.state.buildCheckpoint = structuredClone(s.state.run);
  s.save();
  const run = JSON.stringify(s.state.run),
    checkpoint = JSON.stringify(s.state.buildCheckpoint);
  new Worker(s, {
    run: async () => {
      throw Error("No agent");
    },
  } as any).setManualName(f.id, 'My "keeper" rifle');
  assert.equal(f.status, "done");
  assert.equal(f.stage, "complete");
  assert(f.manualOutput);
  assert.equal(f.revision, 2);
  for (const k of ["output", "draft", "manualDraft"]) {
    const v = s.get<any>(f.id, k);
    assert.equal((v.entry || v).name, 'My "keeper" rifle');
    assert.deepEqual((v.entry || v).description, e.description);
  }
  assert.equal(s.get<any>(f.id, "packet").name, f.name);
  assert.equal(s.get<any>(f.id, "validatedPacket").name, f.name);
  assert.equal(websiteEntry(s, f)!.name, f.name);
  assert.deepEqual(
    new AdmZip(websiteZip(s)).getEntries().map((e) => e.entryName),
    ["weapons/my-keeper-rifle.json"],
  );
  assert(!("nameOverride" in websiteEntry(s, f)!));
  assert.equal(JSON.stringify(s.state.run), run);
  assert.equal(JSON.stringify(s.state.buildCheckpoint), checkpoint);
});
test("manual name API rejects empty/oversized/control names and busy or removed items without unlocking a saved name", async (t) => {
  const x = fixture(t),
    w = new Worker(x.s, {} as any),
    server = api(x.s, w).listen(0, "127.0.0.1");
  await new Promise<void>((r) => server.once("listening", r));
  t.after(() => server.close());
  const url = `http://127.0.0.1:${(server.address() as any).port}/api/items/${x.f.id}/name`,
    post = (body: any) =>
      fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
  for (const name of ["", "  ", "a".repeat(161), "bad\nname", "bad\u0000name"])
    assert.equal((await post({ name })).status, 400);
  assert.equal((await post({ name: "Mine", origin: "research" })).status, 400);
  assert.equal((await post({ name: "  My rifle  " })).status, 200);
  assert.equal(x.f.name, "My rifle");
  assert.equal(x.f.nameOverride?.origin, "manual");
  w.busy = true;
  assert.equal((await post({ name: "Blocked" })).status, 409);
  w.busy = false;
  x.f.status = "excluded";
  assert.equal((await post({ name: "Blocked" })).status, 409);
  assert.equal(x.f.name, "My rifle");
});
test("future AI builds use original identity aliases but cannot publish the old name or replace the manual lock", async (t) => {
  const x = fixture(t),
    { s, f } = x,
    w = new Worker(s, {} as any),
    d = proposal(x),
    calls: string[] = [];
  w.setManualName(f.id, "My favourite rifle");
  f.stage = "draft";
  w.ai = {
    run: async (label: string, prompt: string, schema: any) => {
      calls.push(label);
      if (label.startsWith("Read source")) {
        assert(prompt.includes("locked user display name"));
        assert(prompt.includes('"Rifle"'));
        return schema.parse(emptySourceReading());
      }
      assert(label.startsWith("Build "));
      assert(prompt.includes("MANUAL NAME LOCK"));
      assert(prompt.includes("My favourite rifle"));
      const p = buildPacket(s, f);
      return schema.parse({
        nameDecision: d,
        entry: {
          schemaVersion: CATALOGUE_SCHEMA_VERSION,
          compilerVersion: COMPILER_VERSION,
          id: f.id,
          name: "Rifle",
          category: "Weapons",
          weaponType: "Eridian weapons",
          dlc: null,
          summary: "An ancient energy rifle with unusual alien construction.",
          description: [
            "This synthetic catalogue paragraph explains the energy weapon with independently written wording.",
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
          basis: "Synthetic game definition proof.",
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
  await w.step(f);
  assert.equal(s.get<any>(f.id, "draft").entry.name, "My favourite rifle");
  await w.step(f);
  assert.equal(f.stage, "complete");
  assert.equal(s.get<any>(f.id, "output").name, "My favourite rifle");
  assert.equal(f.nameOverride?.origin, "manual");
  assert(!calls.some((c) => c.startsWith("Verify item name")));
});

test("a cosmetic manual name cannot switch the item image to a different real weapon", async (t) => {
  const x = fixture(t),
    { s, f } = x,
    d = proposal(x),
    root = path.join(s.dir, "image-library");
  mkdirSync(path.join(root, "weapons"), { recursive: true });
  for (const name of ["rifle", "eridian-rifle", "bessie"])
    writeFileSync(path.join(root, "weapons", name + ".png"), "fixture");
  s.images = new Images(root, path.join(s.dir, "test-image-overrides.json"));
  assert(
    await verifyAndApplyName(
      s,
      f,
      buildPacket(s, f),
      d,
      { run: async () => d } as any,
      () => {},
    ),
  );
  assert.equal(s.images.match(f).image, "weapons/eridian-rifle.png");
  const w = new Worker(s, {} as any);
  w.setManualName(f.id, "Bessie");
  assert.equal(f.name, "Bessie");
  assert.equal(s.images.match(f).image, "weapons/eridian-rifle.png");
  w.setManualName(f.id, "Fancy rifle");
  assert.equal(s.images.match(f).image, "weapons/eridian-rifle.png");
  assert(!f.nameOverride?.identityAliases?.includes("Bessie"));
});
