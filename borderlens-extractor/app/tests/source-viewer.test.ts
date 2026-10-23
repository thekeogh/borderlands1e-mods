import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync, unlinkSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { Store } from "../src/server/store.ts";
import { Worker } from "../src/server/worker.ts";
import { Research } from "../src/server/research.ts";
import { discover } from "../src/server/importer.ts";
import { api } from "../src/server/http.ts";
test("source HTML endpoint returns exact cached bytes as inert text, with no live fetch or source edits", async (t) => {
  const dir = mkdtempSync(path.join(tmpdir(), "borderlens-source-viewer-")),
    store = new Store(dir);
  t.after(() => {
    store.close();
    rmSync(dir, { recursive: true, force: true });
  });
  const f = discover(
    new Map([
      [
        "fixture",
        {
          id: "fixture",
          path: "gd_weap_patrol_smg.Title.Title_fixture",
          class: "WillowGame.WeaponNamePartDefinition",
          record_type: "object",
          properties: { PartName: "Fixture" },
        },
      ],
    ]),
  )[0];
  store.state.families = [f];
  const research = new Research(store, async () => {
    throw new Error("Source viewer must not make live fetches.");
  });
  const html =
    "<!doctype html>\n<html><main><h1>Saved source — exact</h1><p>A saved paragraph includes Unicode, punctuation and enough text to preserve a useful source snapshot.</p><script>globalThis.shouldNotRun=true;</script></main></html>\n";
  const source = research.save(
    f,
    "https://borderlands.fandom.com/wiki/Fixture",
    html,
  );
  const before = store.source(source.id),
    revision = store.state.revision;
  const worker = new Worker(store, undefined, research),
    server = api(store, worker).listen(0, "127.0.0.1");
  await new Promise<void>((r) => server.once("listening", r));
  t.after(() => server.close());
  const base = `http://127.0.0.1:${(server.address() as any).port}`,
    url = base + "/api/sources/" + encodeURIComponent(source.id) + "/html";
  const response = await fetch(url);
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") || "", /text\/plain/);
  assert.match(
    response.headers.get("content-security-policy") || "",
    /sandbox/,
  );
  assert.equal(await response.text(), html);
  assert.deepEqual(store.source(source.id), before);
  assert.equal(store.state.revision, revision);
  assert.equal((await fetch(base + "/api/sources/unknown/html")).status, 404);
  assert.equal(
    (await fetch(url, { headers: { Origin: "https://example.org" } })).status,
    403,
  );
  unlinkSync(path.join(store.dir, "sources", source.filename));
  assert.equal((await fetch(url)).status, 404);
});
