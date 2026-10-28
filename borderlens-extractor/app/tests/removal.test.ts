import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import AdmZip from "adm-zip";
import { Store, hash } from "../src/server/store.ts";
import { importZip } from "../src/server/importer.ts";
import { Worker } from "../src/server/worker.ts";
import { Research } from "../src/server/research.ts";
import { api } from "../src/server/http.ts";
import { PublicEntry } from "../src/shared/models.ts";
import { websiteZip } from "../src/server/website-export.ts";
function capture(version = "fixture") {
  const zip = new AdmZip(),
    raw = Buffer.from(
      JSON.stringify(
        ["Keep", "Remove"].map((name) => ({
          id: name,
          record_type: "object",
          path: `gd_weap_sniper.Title.${name}`,
          class: "WillowGame.WeaponNamePartDefinition",
          properties: { PartName: name },
        })),
      ),
    );
  zip.addFile("data/0001.json", raw);
  zip.addFile(
    "manifest.json",
    Buffer.from(
      JSON.stringify({
        format_version: 1,
        extractor_version: version,
        chunks: [{ file: "data/0001.json", records: 2, sha256: hash(raw) }],
      }),
    ),
  );
  return zip.toBuffer();
}
function setup(t: any) {
  const dir = mkdtempSync(path.join(tmpdir(), "borderlens-removal-"));
  let s = new Store(dir);
  importZip(s, capture(), "fixture.zip");
  t.after(() => {
    s.close();
    rmSync(dir, { recursive: true, force: true });
  });
  return {
    get s() {
      return s;
    },
    reopen() {
      s.close();
      s = new Store(dir);
      return s;
    },
  };
}
function output(s: Store, name: string) {
  const f = s.state.families.find((f) => f.name === name)!;
  s.put(
    f.id,
    "output",
    PublicEntry.parse({
      schemaVersion: "7",
      compilerVersion: "0.15.1",
      id: f.id,
      name: f.name,
      dlc: null,
      category: f.category,
      weaponType: "Sniper rifles",
      summary: "Original synthetic equipment for removal tests.",
      description: [
        "This original synthetic fixture verifies catalogue removal and restoration.",
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
    }),
  );
  f.status = "done";
  f.stage = "complete";
  f.revision = 2;
  return f;
}
const until = async (fn: () => boolean) => {
  for (let i = 0; i < 300; i++) {
    if (fn()) return;
    await new Promise((r) => setTimeout(r, 10));
  }
  throw Error("worker timeout");
};
test("HTTP removal persists, omits exports, preserves sources/output and restores without a build", async (t) => {
  const fixture = setup(t),
    s = fixture.s;
  output(s, "Keep");
  const f = output(s, "Remove");
  new Research(s).save(
    f,
    "https://www.lootlemon.com/weapon/removal-fixture-bl1",
    "<main><h1>Synthetic fixture</h1><p>Original stored fixture text verifies that removing an item retains all saved research.</p></main>",
  );
  s.save();
  const prior = s.get(f.id, "output"),
    sources = s.sources(f.id);
  const w = new Worker(s, {} as any),
    server = api(s, w).listen(0, "127.0.0.1");
  await new Promise<void>((r) => server.once("listening", r));
  t.after(() => server.close());
  const base = `http://127.0.0.1:${(server.address() as any).port}`;
  let res = await fetch(base + `/api/items/${f.id}/action`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action: "remove" }),
  });
  assert.equal(res.status, 200);
  assert.equal(f.status, "excluded");
  assert.deepEqual(s.get(f.id, "output"), prior);
  assert.deepEqual(s.sources(f.id), sources);
  assert.deepEqual(
    new AdmZip(websiteZip(s)).getEntries().map((e) => e.entryName),
    ["weapons/keep.json"],
  );
  assert.equal(
    (
      await fetch(base + `/api/items/${f.id}/action`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "rebuild" }),
      })
    ).status,
    409,
  );
  res = await fetch(base + `/api/items/${f.id}/action`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action: "restore" }),
  });
  assert.equal(res.status, 200);
  assert.equal(f.status, "done");
  assert.equal(f.revision, 2);
  assert.equal(w.busy, false);
  await w.action(f.id, "remove", {});
  await new Promise<void>((r) => server.close(() => r()));
  const reopened = fixture.reopen();
  assert.equal(reopened.family(f.id).status, "excluded");
  assert.deepEqual(reopened.get(f.id, "output"), prior);
  importZip(reopened, capture("second"), "second.zip");
  const w2 = new Worker(reopened, {} as any);
  w2.refreshImported();
  assert.equal(reopened.family(f.id).status, "excluded");
});
test("future items can be removed while processing, current item cannot, and later batches skip removals", async (t) => {
  const { s } = setup(t);
  const [current, future] = s.state.families;
  const w = new Worker(s, {} as any);
  w.busy = true;
  s.state.run.currentId = current.id;
  s.state.run.status = "running";
  await w.action(future.id, "remove", {});
  assert.equal(future.status, "excluded");
  await assert.rejects(
    () => w.action(current.id, "remove", {}),
    /Pause processing/,
  );
  w.busy = false;
  s.state.run.status = "paused";
  const visits: string[] = [];
  w.step = async (f) => {
    visits.push(f.id);
    f.stage = "complete";
  };
  w.start();
  await until(() => !w.busy);
  assert.deepEqual(visits, [current.id]);
  assert.equal(future.status, "excluded");
  await w.action(future.id, "restore", {});
  assert.equal(future.status, "queued");
  assert.equal(w.busy, false);
});
test("generated reset keeps removals and restore queues deleted output rather than claiming ready", async (t) => {
  const { s } = setup(t),
    f = output(s, "Remove"),
    w = new Worker(s, {} as any);
  await w.action(f.id, "remove", {});
  const server = api(s, w).listen(0, "127.0.0.1");
  await new Promise<void>((r) => server.once("listening", r));
  t.after(() => server.close());
  const response = await fetch(
    `http://127.0.0.1:${(server.address() as any).port}/api/reset`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scope: "generated", confirmation: "RESET" }),
    },
  );
  assert.equal(response.status, 200);
  assert.equal(f.status, "excluded");
  await w.action(f.id, "restore", {});
  assert.equal(f.status, "queued");
  assert.equal(f.stage, "evidence");
});
