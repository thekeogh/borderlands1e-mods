import { test } from "node:test";
import assert from "node:assert/strict";
import {
  mkdtempSync,
  mkdirSync,
  writeFileSync,
  rmSync,
  symlinkSync,
  existsSync,
} from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import AdmZip from "adm-zip";
import { Images } from "../src/server/images.ts";
import { Store } from "../src/server/store.ts";
import { Worker } from "../src/server/worker.ts";
import { api } from "../src/server/http.ts";
import { discover } from "../src/server/importer.ts";
import { PublicEntry } from "../src/shared/models.ts";
import {
  COMPILER_VERSION,
  CATALOGUE_SCHEMA_VERSION,
} from "../src/shared/versions.ts";
import { websiteEntry, websiteZip } from "../src/server/website-export.ts";
const pixel = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jq1sAAAAASUVORK5CYII=",
  "base64",
);
function setup(t: any) {
  const dir = mkdtempSync(path.join(tmpdir(), "borderlens-images-")),
    root = path.join(dir, "img");
  mkdirSync(path.join(root, "weapons"), { recursive: true });
  mkdirSync(path.join(root, "shields"), { recursive: true });
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  const add = (file: string) => writeFileSync(path.join(root, file), pixel);
  const images = new Images(
    root,
    path.join(dir, "data", "image-overrides.json"),
  );
  const f = {
    id: "bessie",
    name: "Bessie",
    category: "Weapons" as const,
    aliases: [] as string[],
  };
  return { dir, root, add, images, f };
}
test("image matching is category-scoped, handles punctuation/aliases and exposes ambiguity without guessing", (t) => {
  const { images, add, f } = setup(t);
  add("weapons/bessie.png");
  add("shields/bessie.png");
  add("weapons/peace-keeper.png");
  add("weapons/ajaxs-spear.png");
  images.refresh();
  assert.equal(images.match(f).image, "weapons/bessie.png");
  assert.equal(
    images.match({ ...f, name: "Ajax’s Spear" }).image,
    "weapons/ajaxs-spear.png",
  );
  assert.equal(
    images.match({ ...f, name: "Peacekeeper" }).method,
    "normalized",
  );
  assert.equal(
    images.match({ ...f, name: "A different title", aliases: ["Bessie"] })
      .method,
    "alias",
  );
  assert.equal(images.match({ ...f, name: "Missing" }).image, null);
  assert.equal(
    images.match({ ...f, name: "Bessie", category: "Other equipment" }).method,
    "ambiguous",
  );
  add("weapons/bessie.webp");
  images.refresh();
  assert.equal(images.match(f).method, "ambiguous");
  images.set(f.id, "weapons/bessie.png");
  const reopened = new Images(images.root, images.overridesFile);
  assert.equal(reopened.match(f).method, "manual");
  reopened.set(f.id, null);
  assert.equal(reopened.match(f).image, null);
  reopened.set(f.id, null, true);
  assert.equal(reopened.match(f).method, "ambiguous");
});
test("new files refresh automatically; unsafe files and symlinks are never served", (t) => {
  const { images, add, root, dir, f } = setup(t);
  assert.equal(images.match(f).image, null);
  add("weapons/bessie.png");
  images.refresh();
  assert.equal(images.match(f).image, "weapons/bessie.png");
  writeFileSync(path.join(root, "weapons", "evil.svg"), "<svg/>");
  writeFileSync(path.join(dir, "outside.png"), pixel);
  symlinkSync(
    path.join(dir, "outside.png"),
    path.join(root, "weapons", "linked.png"),
  );
  assert.equal(images.file("weapons/linked.png"), null);
  assert.equal(images.file("weapons/evil.svg"), null);
  assert.equal(images.file("weapons/../../outside.png"), null);
  assert.throws(() => images.set(f.id, "weapons/nope.png"), /existing image/);
  assert.ok(images.file("weapons/bessie.png"));
});
test("image API, manual selection and website ZIP agree while preserving queue and generated resets", async (t) => {
  const { dir, root, add } = setup(t);
  add("weapons/bessie.png");
  add("weapons/alternate.png");
  const store = new Store(path.join(dir, "data"), root),
    worker = new Worker(store);
  t.after(() => store.close());
  const f = discover(
    new Map([
      [
        "bessie",
        {
          id: "bessie",
          record_type: "object",
          path: "gd_weap_sniper.Title.Title_Bessie",
          class: "WillowGame.WeaponNamePartDefinition",
          properties: { PartName: "Bessie" },
        },
      ],
    ]),
  )[0];
  store.state.families = [f];
  store.state.run.status = "paused";
  const server = api(store, worker).listen(0, "127.0.0.1");
  await new Promise<void>((r) => server.once("listening", r));
  t.after(() => server.close());
  const base = `http://127.0.0.1:${(server.address() as any).port}`;
  const json = async (url: string, body?: unknown) =>
    fetch(
      base + url,
      body
        ? {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify(body),
          }
        : {},
    );
  const detail = await (await json("/api/items/" + f.id)).json();
  assert.equal(detail.image.image, "weapons/bessie.png");
  assert.equal(detail.output, null);
  const coverage = await (await json("/api/images")).json();
  assert.equal(coverage.summary.matched, 1);
  const asset = await json("/api/images/file/weapons/bessie.png");
  assert.equal(asset.status, 200);
  assert.match(asset.headers.get("content-type")!, /image\/png/);
  assert.deepEqual(Buffer.from(await asset.arrayBuffer()), pixel);
  assert.equal(
    (await json("/api/images/file/weapons/missing.png")).status,
    404,
  );
  assert.equal((await json("/api/images/file/weapons/evil.svg")).status, 404);
  const run = structuredClone(store.state.run);
  assert.equal(
    (
      await json("/api/items/" + f.id + "/image", {
        image: "weapons/alternate.png",
      })
    ).status,
    200,
  );
  assert.deepEqual(store.state.run, run);
  assert.equal(f.stage, "evidence");
  assert.equal(
    (
      await json("/api/items/" + f.id + "/image", {
        image: "weapons/missing.png",
      })
    ).status,
    400,
  );
  const output = PublicEntry.parse({
    schemaVersion: CATALOGUE_SCHEMA_VERSION,
    compilerVersion: COMPILER_VERSION,
    id: f.id,
    name: f.name,
    dlc: null,
    category: f.category,
    weaponType: "Sniper rifles",
    summary: "A precise rifle used for the image export fixture.",
    description: ["A synthetic original paragraph for checking image export."],
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
  store.put(f.id, "output", output);
  f.status = "done";
  assert.equal(websiteEntry(store, f)!.image, "weapons/alternate.png");
  let zip = new AdmZip(websiteZip(store));
  assert.equal(zip.getEntries().length, 1);
  assert.equal(
    JSON.parse(zip.readAsText("weapons/bessie.json")).image,
    "weapons/alternate.png",
  );
  const manual = websiteEntry(store, f)!;
  manual.image = "weapons/bessie.png";
  assert.equal(
    (
      await json("/api/items/" + f.id + "/action", {
        action: "save-output",
        output: manual,
      })
    ).status,
    200,
  );
  assert.equal(websiteEntry(store, f)!.image, "weapons/bessie.png");
  assert.equal(
    (await json("/api/reset", { scope: "generated", confirmation: "RESET" }))
      .status,
    200,
  );
  assert.equal(store.images.match(f).image, "weapons/bessie.png");
  assert.equal(
    (await json("/api/reset", { scope: "all", confirmation: "RESET" })).status,
    200,
  );
  assert.ok(existsSync(path.join(root, "weapons/bessie.png")));
  assert.equal(
    new Images(root, store.images.overridesFile).match({
      ...f,
      name: "No match",
    }).image,
    null,
  );
});

test("refresh discovers new folders and serves their actual relative paths without changing an active run", async (t) => {
  const { root, dir, add } = setup(t);
  const store = new Store(path.join(dir, "data"), root),
    worker = new Worker(store);
  t.after(() => store.close());
  const server = api(store, worker).listen(0, "127.0.0.1");
  await new Promise<void>((r) => server.once("listening", r));
  t.after(() => server.close());
  const base = `http://127.0.0.1:${(server.address() as any).port}`;
  const before = await fetch(base + "/api/images").then((r) => r.json());
  mkdirSync(path.join(root, "artifact"));
  add("artifact/siren.png");
  mkdirSync(path.join(root, "new-images"));
  add("new-images/added.png");
  const outside = path.join(dir, "outside");
  mkdirSync(outside);
  writeFileSync(path.join(outside, "secret.png"), pixel);
  symlinkSync(outside, path.join(root, "escape"));
  store.state.run.status = "running";
  worker.busy = true;
  const run = structuredClone(store.state.run);
  const response = await fetch(base + "/api/images", { cache: "no-store" }),
    result = await response.json();
  assert.equal(response.headers.get("cache-control"), "no-store");
  assert.ok(result.files.includes("artifact/siren.png"));
  assert.ok(result.files.includes("new-images/added.png"));
  assert.notEqual(result.revision, before.revision);
  assert.ok(!result.files.includes("escape/secret.png"));
  assert.equal(
    (await fetch(base + "/api/images/file/escape/secret.png")).status,
    404,
  );
  const asset = await fetch(base + "/api/images/file/artifact/siren.png");
  assert.equal(asset.status, 200);
  assert.deepEqual(Buffer.from(await asset.arrayBuffer()), pixel);
  assert.deepEqual(store.state.run, run);
  assert.equal(worker.busy, true);
  worker.busy = false;
  store.images.set("manual", "artifact/siren.png");
  assert.equal(
    store.images.match({
      id: "manual",
      name: "Artifact",
      category: "Artifacts",
      aliases: [],
    }).image,
    "artifact/siren.png",
  );
});

test("restored images inside hidden project directories are served as PNGs without exposing other files", async (t) => {
  const { dir, root } = setup(t);
  const data = path.join(dir, ".data"),
    library = path.join(data, "image-library");
  mkdirSync(path.join(library, "weapons"), { recursive: true });
  writeFileSync(path.join(library, "weapons", "hellfire.png"), pixel);
  writeFileSync(path.join(data, "secret.json"), '{"private":true}');
  const store = new Store(data, root),
    worker = new Worker(store);
  t.after(() => store.close());
  assert.equal(store.images.root, library);
  const server = api(store, worker).listen(0, "127.0.0.1");
  await new Promise<void>((resolve) => server.once("listening", resolve));
  t.after(() => server.close());
  const base = `http://127.0.0.1:${(server.address() as any).port}`;
  const response = await fetch(
    base + "/api/images/file/weapons/hellfire.png?v=restored",
  );
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type")!, /image\/png/);
  assert.deepEqual(Buffer.from(await response.arrayBuffer()), pixel);
  assert.equal(
    (await fetch(base + "/api/images/file/weapons/.secret.png")).status,
    404,
  );
  assert.equal(
    (await fetch(base + "/api/images/file/weapons/secret.json")).status,
    404,
  );
  assert.equal(
    (await fetch(base + "/api/images/file/weapons/missing.png")).status,
    404,
  );
});
