import { emptySourceReading } from "./source-fixture.ts";
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import AdmZip from "adm-zip";
import { Store, hash } from "../src/server/store.ts";
import { importZip } from "../src/server/importer.ts";
import { Worker, type AI } from "../src/server/worker.ts";
import { api } from "../src/server/http.ts";
import { buildPacket } from "../src/server/evidence.ts";
const url = "https://borderlands.fandom.com/wiki/Fixture_(Borderlands)";
const html =
  '<main><h1>Fixture article</h1><div class="mw-parser-output"><h2>Useful information</h2><p>This is a synthetic browser-capture test article with sufficient text to exercise local caching and source parsing.</p></div></main>';
function setup(t: any) {
  const dir = mkdtempSync(path.join(tmpdir(), "borderlens-chrome-"));
  let s = new Store(dir);
  const rows = ["First", "Second"].map((name, i) => ({
      id: String(i),
      path: "gd_weap_patrol_smg.Title.Title_" + name,
      record_type: "object",
      class: "WillowGame.WeaponNamePartDefinition",
      properties: { PartName: name },
    })),
    data = Buffer.from(JSON.stringify(rows)),
    zip = new AdmZip();
  zip.addFile("data/one.json", data);
  zip.addFile(
    "manifest.json",
    Buffer.from(
      JSON.stringify({
        format_version: 1,
        extractor_version: "fixture",
        chunks: [{ file: "data/one.json", records: 2, sha256: hash(data) }],
      }),
    ),
  );
  importZip(s, zip.toBuffer(), "fixture.zip");
  s.state.settings.research = false;
  t.after(() => {
    s.close();
    rmSync(dir, { recursive: true, force: true });
  });
  return {
    get store() {
      return s;
    },
    reopen() {
      s.close();
      s = new Store(dir);
      return s;
    },
  };
}
function ai(s: Store, wait?: () => Promise<void>): AI {
  return {
    status: async () => ({ chatgpt: true }),
    run: async (_label, _prompt, schema) => {
      if (_label.startsWith("Read source"))
        return schema.parse(emptySourceReading());
      await wait?.();
      const f = s.family(s.state.run.currentId!),
        p = buildPacket(s, f);
      return schema.parse({
        entry: {
          schemaVersion: "5",
          compilerVersion: "0.9.0",
          id: f.id,
          name: f.name,
          game: "borderlands-goty-enhanced",
          category: f.category,
          weaponType: "SMGs",
          summary: "A useful synthetic browser-import fixture weapon.",
          description: [
            "An original fixture paragraph describes this item without adding unsupported game information.",
          ],
          parts: [],
          variants: [],
          references: [],
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
        claims: ["summary", "description"].map((field) => ({
          field,
          evidenceIds: [p.evidence[0].id],
          basis: "Fixture identity.",
        })),
        uncertainties: [],
        conflicts: [],
        requiresReview: false,
        reviewReason: null,
      });
    },
  };
}
const until = async (fn: () => boolean) => {
  for (let i = 0; i < 600; i++) {
    if (fn()) return;
    await new Promise((r) => setTimeout(r, 10));
  }
  throw new Error("Worker wait timed out");
};
test("Chrome ticket binds the capture to its item/article, rejects invalid/expired tickets and replays idempotently", (t) => {
  const { store: s } = setup(t),
    w = new Worker(s),
    f = s.state.families[0],
    ticket = w.browserImports.create(f.id, url);
  assert.throws(
    () => w.browserImports.submit({ ...ticket, token: "wrong", html }),
    /invalid/,
  );
  assert.throws(
    () =>
      w.browserImports.submit({
        ...ticket,
        url: "https://borderlands.fandom.com/wiki/Wrong",
        html,
      }),
    /not the page/,
  );
  assert.throws(
    () => w.browserImports.create(f.id, "https://example.org/"),
    /HTTPS wiki/,
  );
  const result = w.browserImports.submit({
    ...ticket,
    url: url + "#section",
    html,
  });
  assert.equal(result.status, "imported");
  assert.equal(s.sources(f.id).length, 1);
  assert.equal(s.sources(f.id)[0].captureMethod, "chrome");
  assert.equal(s.get<any>(f.id, "research").providers[0].status, "saved");
  assert.equal(s.family(f.id).stage, "sources");
  assert.equal(w.browserImports.submit({ ...ticket, html }).status, "imported");
  assert.equal(s.sources(f.id).length, 1);
  const expired = w.browserImports.create(f.id, url),
    job = s.get<any>("_chrome", expired.jobId);
  job.expiresAt = 0;
  s.put("_chrome", expired.jobId, job);
  assert.throws(() => w.browserImports.submit({ ...expired, html }), /expired/);
});
test("capture received during drafting waits for a checkpoint and is included in the next draft", async (t) => {
  const { store: s } = setup(t);
  let release!: () => void,
    entered = false,
    calls = 0;
  const w = new Worker(
    s,
    ai(s, async () => {
      if (calls++ === 0) {
        entered = true;
        await new Promise<void>((r) => (release = r));
      }
    }),
  );
  const f = s.state.families[0];
  w.start(undefined, f.id);
  await until(() => entered);
  const ticket = w.browserImports.create(f.id, url);
  assert.equal(w.browserImports.submit({ ...ticket, html }).status, "queued");
  assert.equal(s.sources(f.id).length, 0);
  release();
  await until(() => !w.busy);
  assert.equal(f.status, "done");
  assert.equal(calls, 2);
  assert.equal(s.sources(f.id).length, 1);
  assert.ok(
    s
      .get<any>(f.id, "validatedPacket")
      .evidence.some((e: any) => e.kind === "page"),
  );
});
test("accepted queued captures survive service restart", (t) => {
  const env = setup(t),
    s = env.store,
    w = new Worker(s),
    f = s.state.families[0],
    ticket = w.browserImports.create(f.id, url);
  w.busy = true;
  w.browserImports.submit({ ...ticket, html });
  const reopened = env.reopen();
  new Worker(reopened);
  assert.equal(reopened.sources(f.id).length, 1);
  assert.equal(reopened.get<any>("_chrome", ticket.jobId).status, "imported");
});
test("helper endpoints keep same-origin protection and package only extension files", async (t) => {
  const { store: s } = setup(t),
    w = new Worker(s),
    server = api(s, w).listen(0, "127.0.0.1");
  await new Promise<void>((r) => server.once("listening", r));
  t.after(() => server.close());
  const base = `http://127.0.0.1:${(server.address() as any).port}`;
  const metadata = await fetch(base + "/api/chrome-helper").then((r) =>
    r.json(),
  );
  assert.ok(existsSync(path.join(metadata.extensionPath, "manifest.json")));
  assert.equal(
    (
      await fetch(base + "/api/chrome-helper/jobs", {
        method: "POST",
        headers: {
          Origin: "https://borderlands.fandom.com",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ familyId: s.state.families[0].id, url }),
      })
    ).status,
    403,
  );
  const archive = new AdmZip(
    Buffer.from(
      await (
        await fetch(base + "/api/chrome-helper/extension.zip")
      ).arrayBuffer(),
    ),
  );
  assert.equal(archive.getEntries().length, 7);
  assert.ok(archive.getEntry("borderlens-chrome-helper/manifest.json"));
  const manifest = JSON.parse(
    archive.readAsText("borderlens-chrome-helper/manifest.json"),
  );
  assert.ok(manifest.permissions.includes("activeTab"));
  assert.ok(
    !manifest.host_permissions.some(
      (host: string) => host.includes("fandom") || host.includes("all_urls"),
    ),
  );
});

test("import of an already-processed item waits for a requested rebuild without extending a paused run", (t) => {
  const { store: s } = setup(t),
    w = new Worker(s),
    first = s.state.families[0],
    second = s.state.families[1];
  s.state.run = {
    ...s.state.run,
    status: "paused",
    queue: [first.id, second.id],
    index: 1,
    currentId: second.id,
  };
  const ticket = w.browserImports.create(first.id, url);
  assert.equal(w.browserImports.submit({ ...ticket, html }).status, "imported");
  assert.deepEqual(s.state.run.queue, [first.id, second.id]);
  assert.equal(s.state.run.status, "paused");
  assert.equal(s.state.run.currentId, second.id);
});
