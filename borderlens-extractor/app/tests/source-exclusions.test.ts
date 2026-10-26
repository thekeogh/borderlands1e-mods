import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync, existsSync } from "node:fs";
import path from "node:path";
import { tmpdir } from "node:os";
import AdmZip from "adm-zip";
import { Store, hash } from "../src/server/store.ts";
import { importZip } from "../src/server/importer.ts";
import { Research } from "../src/server/research.ts";
import { Worker } from "../src/server/worker.ts";
import { api } from "../src/server/http.ts";
import { buildPacket } from "../src/server/evidence.ts";
import { sourceKey } from "../src/shared/research.ts";
function fixture(t: any) {
  const dir = mkdtempSync(path.join(tmpdir(), "source-exclusions-"));
  let s = new Store(dir);
  const z = new AdmZip(),
    rows = ["Fixture", "Other"].map((name) => ({
      id: name,
      path: `gd_weap_sniper.Title.${name}`,
      class: "WillowGame.WeaponNamePartDefinition",
      record_type: "object",
      properties: { PartName: name },
    })),
    data = Buffer.from(JSON.stringify(rows));
  z.addFile("data/0001.json", data);
  z.addFile(
    "manifest.json",
    Buffer.from(
      JSON.stringify({
        format_version: 1,
        extractor_version: "fixture",
        chunks: [
          { file: "data/0001.json", records: rows.length, sha256: hash(data) },
        ],
      }),
    ),
  );
  importZip(s, z.toBuffer(), "fixture.zip");
  const f = s.state.families[0],
    other = s.state.families[1],
    research = new Research(s);
  const bad = research.save(
    f,
    "https://borderlands.fandom.com/wiki/Wrong_Item",
    "<h1>Wrong item fixture</h1><p>This unrelated archived article must be excluded from future fixture builds and source discovery.</p>",
  );
  const good = research.save(
    f,
    "https://www.lootlemon.com/weapon/fixture-bl1",
    "<h1>Fixture • BL1 – Sniper | Lootlemon</h1><p>This original synthetic item article remains a valid active source for fixture builds.</p>",
  );
  research.save(
    other,
    bad.url,
    "<h1>Shared article fixture</h1><p>The same article is intentionally still available to another family in this synthetic test.</p>",
  );
  f.sourceUrls = [bad.url, good.url];
  s.save();
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
    bad,
    good,
    reopen() {
      s.close();
      s = new Store(dir);
      return s;
    },
  };
}
test("source X API retains HTML, invalidates stale work, scopes removal per item and restores without a build", async (t) => {
  const x = fixture(t),
    s = x.s,
    w = new Worker(s, {} as any),
    server = api(s, w).listen(0, "127.0.0.1");
  await new Promise<void>((r) => server.once("listening", r));
  t.after(() => server.close());
  const base = `http://127.0.0.1:${(server.address() as any).port}`;
  const { f, bad, good, other } = x;
  s.put(f.id, "draft", { old: true });
  s.put(f.id, "sourceLedger", [{ old: true }]);
  s.put(f.id, "output", { saved: true });
  f.status = "done";
  f.revision = 3;
  const action = (action: string, sourceId: string) =>
    fetch(base + `/api/items/${f.id}/action`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, sourceId }),
    });
  assert.equal((await action("exclude-source", bad.id)).status, 200);
  const detail = await fetch(base + `/api/items/${f.id}`).then((r) => r.json());
  assert.deepEqual(
    detail.sources.map((s: any) => s.id),
    [good.id],
  );
  assert.equal(detail.excludedSources[0].sourceId, bad.id);
  assert.equal(f.status, "queued");
  assert.equal(f.stage, "evidence");
  assert.equal(f.revision, 3);
  assert.equal(s.get(f.id, "draft"), null);
  assert.equal(s.get(f.id, "sourceLedger"), null);
  assert.deepEqual(s.get(f.id, "output"), { saved: true });
  assert.ok(existsSync(path.join(s.dir, "sources", bad.filename)));
  assert.ok(s.source(bad.id));
  assert.equal(s.sources(other.id).length, 1);
  assert.ok(!buildPacket(s, f).evidence.some((e) => e.id === bad.id));
  assert.equal((await action("restore-source", bad.id)).status, 200);
  assert.equal(s.sources(f.id).length, 2);
  assert.equal(s.sourceExclusions(f.id).length, 0);
  assert.equal(w.busy, false);
  const unrelated = new Research(s).save(
    other,
    "https://borderlands.fandom.com/wiki/Unrelated_fixture",
    "<h1>Unrelated fixture</h1><p>This separate article is not linked to the current item and cannot be removed through its source controls.</p>",
  );
  assert.equal((await action("exclude-source", unrelated.id)).status, 404);
  assert.equal((await action("exclude-source", bad.id)).status, 200);
  await new Promise<void>((r) => server.close(() => r()));
  const reopened = x.reopen();
  assert.equal(reopened.sources(f.id).length, 1);
  assert.equal(reopened.sourceExclusions(f.id).length, 1);
});
test("fresh fetch, import, Chrome capture, rediscovery and URL aliases cannot resurrect an excluded article", async (t) => {
  const { s, f, bad, good } = fixture(t);
  const w = new Worker(s, {
    status: async () => ({}),
    run: async (_l: string, _p: string, schema: any) =>
      schema.parse({
        matches: [
          {
            url: bad.url.replace("Wrong_Item", "Wrong%20Item"),
            title: bad.title,
            gameEvidence: "Synthetic candidate",
            reason: "Testing a deliberately excluded discovery result",
          },
        ],
        notFoundReason: null,
      }),
  } as any);
  const ticket = w.browserImports.create(f.id, bad.url);
  await w.action(f.id, "exclude-source", { sourceId: bad.id });
  assert.equal(
    sourceKey(bad.url),
    sourceKey(bad.url.replace("Wrong_Item", "Wrong%20Item") + "?oldid=123"),
  );
  let network = 0;
  const research = new Research(s, async () => {
    network++;
    throw Error("No network permitted");
  });
  w.research = research;
  await assert.rejects(() => research.fetchPage(f, bad.url, true), /removed/);
  assert.equal(network, 0);
  assert.throws(
    () =>
      research.save(
        f,
        bad.url,
        "<h1>Wrong source again</h1><p>Fresh HTML cannot bypass the per-item source exclusion record in this fixture.</p>",
      ),
    /removed/,
  );
  assert.throws(() => w.browserImports.create(f.id, bad.url), /removed/);
  const captured = w.browserImports.submit({
    jobId: ticket.jobId,
    token: ticket.token,
    url: bad.url,
    html: "<h1>Excluded article captured late</h1><p>This previously opened Chrome capture must not restore an excluded source.</p>",
  });
  assert.equal(captured.status, "failed");
  f.sourceUrls.push(bad.url);
  s.put(f.id, "packet", buildPacket(s, f));
  s.put(f.id, "rebuildPlan", {
    mode: "fresh",
    since: "2000-01-01T00:00:00.000Z",
  });
  await w.collectSources(f, true);
  assert.equal(network, 0);
  assert.deepEqual(
    s.sources(f.id).map((s) => s.id),
    [good.id],
  );
  assert.ok(!f.sourceUrls.some((url) => sourceKey(url) === sourceKey(bad.url)));
});
test("source removal protects the current call, permits future edits and clears source-derived category overrides", async (t) => {
  const { s, f, other, bad } = fixture(t),
    w = new Worker(s, {} as any);
  s.classifications.set(f.id, "research", {
    name: f.name,
    category: "Weapons",
    weaponType: "Sniper rifles",
    verifiedAt: "fixture",
    reason: "Synthetic source proof",
    evidence: [
      {
        id: bad.id,
        url: bad.url,
        title: bad.title,
        quote: "Synthetic source proof",
        hash: bad.hash,
      },
    ],
  });
  s.save();
  w.busy = true;
  s.state.run.status = "running";
  s.state.run.currentId = f.id;
  await assert.rejects(
    () => w.action(f.id, "exclude-source", { sourceId: bad.id }),
    /Pause processing/,
  );
  s.state.run.currentId = other.id;
  await w.action(f.id, "exclude-source", { sourceId: bad.id });
  assert.equal(s.classifications.data.entries[f.id], undefined);
  assert.equal(w.busy, true);
  w.busy = false;
});
test("generated reset keeps exclusions and manual output requires review after its sources change", async (t) => {
  const { s, f, bad } = fixture(t),
    w = new Worker(s, {} as any);
  f.manualOutput = true;
  await w.action(f.id, "exclude-source", { sourceId: bad.id });
  assert.equal(f.status, "blocked");
  await assert.rejects(() => w.step(f), /manually edited/);
  f.manualOutput = false;
  const server = api(s, w).listen(0, "127.0.0.1");
  await new Promise<void>((r) => server.once("listening", r));
  t.after(() => server.close());
  const res = await fetch(
    `http://127.0.0.1:${(server.address() as any).port}/api/reset`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scope: "generated", confirmation: "RESET" }),
    },
  );
  assert.equal(res.status, 200);
  assert.equal(s.isSourceExcluded(f.id, bad.url), true);
  assert.equal(
    new Set(s.allSources(f.id).map((source) => sourceKey(source.url))).size,
    2,
  );
});

test("pending evidence URL can be excluded before capture, restored, and kept out of rediscovery and old Chrome tickets", async (t) => {
  const x = fixture(t),
    { s, f, other } = x,
    w = new Worker(s, {} as any),
    pending = "https://www.lootlemon.com/class/brick#_0000000_0000000_0000000";
  f.sourceUrls.push(pending);
  other.sourceUrls.push(pending);
  s.put(f.id, "matches", {
    matches: [
      {
        url: pending,
        title: "Brick skill calculator",
        gameEvidence: "BL1",
        reason: "Fixture",
      },
    ],
    notFoundReason: null,
  });
  s.put(f.id, "research", {
    discovered: ["Lootlemon"],
    providers: [
      {
        provider: "Lootlemon",
        status: "urls_ready",
        urls: [pending],
        message: "URL only",
        checkedAt: new Date().toISOString(),
      },
    ],
  });
  s.save();
  const ticket = w.browserImports.create(f.id, pending),
    savedSourceIds = s.sources(f.id).map((source) => source.id),
    server = api(s, w).listen(0, "127.0.0.1");
  await new Promise<void>((resolve) => server.once("listening", resolve));
  t.after(() => {
    server.closeAllConnections();
    server.close();
  });
  const base = `http://127.0.0.1:${(server.address() as any).port}`,
    action = (body: unknown) =>
      fetch(base + `/api/items/${f.id}/action`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
  assert.equal(
    (await action({ action: "exclude-source", url: pending })).status,
    200,
  );
  assert(!f.sourceUrls.includes(pending));
  assert.equal(
    s.isSourceExcluded(f.id, "https://lootlemon.com/class/brick"),
    true,
  );
  assert.deepEqual(
    s.sources(f.id).map((source) => source.id),
    savedSourceIds,
  );
  assert(other.sourceUrls.includes(pending));
  const excluded = s
    .sourceExclusions(f.id)
    .find((row) => sourceKey(row.url) === sourceKey(pending))!;
  assert.match(excluded.sourceId, /^url:/);
  assert.equal(excluded.title, "Brick skill calculator");
  assert.equal(s.get(f.id, "research"), null);
  assert.throws(
    () => w.browserImports.create(f.id, pending),
    /Restore it first/,
  );
  const result = w.browserImports.submit({
    ...ticket,
    url: pending,
    html: "<h1>Brick calculator fixture</h1><p>This synthetic capture was opened before its pending source URL was removed from this item.</p>",
  });
  assert.equal(result.status, "failed");
  w.ai = {
    run: async () => ({
      matches: [
        {
          url: "https://lootlemon.com/class/brick",
          title: "Brick",
          gameEvidence: "BL1",
          reason: "Excluded alias fixture",
        },
      ],
      notFoundReason: null,
    }),
  } as any;
  await w.discoverSourceUrls(f, true);
  assert(!f.sourceUrls.some((url) => sourceKey(url) === sourceKey(pending)));
  assert(
    !s
      .get<any>(f.id, "matches")
      .matches.some((row: any) => sourceKey(row.url) === sourceKey(pending)),
  );
  assert.equal(
    (await action({ action: "restore-source", sourceId: excluded.sourceId }))
      .status,
    200,
  );
  assert.equal(s.isSourceExcluded(f.id, pending), false);
  assert(f.sourceUrls.includes(pending));
  assert.equal(
    (
      await action({
        action: "exclude-source",
        url: "https://lootlemon.com/class/brick",
      })
    ).status,
    200,
  );
  await new Promise<void>((resolve) => server.close(() => resolve()));
  assert.equal(x.reopen().isSourceExcluded(f.id, pending), true);
});
test("pending removal rejects unknown URLs and protects active items without fetching anything", async (t) => {
  const { s, f, other } = fixture(t),
    w = new Worker(s, {} as any),
    pending = "https://www.lootlemon.com/class/brick";
  other.sourceUrls.push(pending);
  await assert.rejects(
    w.action(f.id, "exclude-source", { url: pending }),
    /not found for this item/,
  );
  await assert.rejects(
    w.action(f.id, "exclude-source", {
      url: "https://example.com/not-allowed",
    }),
    /HTTPS wiki or Lootlemon/,
  );
  await assert.rejects(
    w.action(f.id, "exclude-source", {}),
    /saved source or an evidence URL/,
  );
  assert.equal(s.sourceExclusions(f.id).length, 0);
  f.sourceUrls.push(pending);
  s.state.run.currentId = f.id;
  w.busy = true;
  await assert.rejects(
    w.action(f.id, "exclude-source", { url: pending }),
    /Pause processing/,
  );
  assert(f.sourceUrls.includes(pending));
  w.busy = false;
  await w.action(f.id, "exclude-source", { url: pending });
  assert.equal(s.isSourceExcluded(f.id, pending), true);
  assert.equal(w.busy, false);
});
