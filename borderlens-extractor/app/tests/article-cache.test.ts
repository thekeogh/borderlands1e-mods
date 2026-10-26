import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync, readdirSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { Store } from "../src/server/store.ts";
import { Research } from "../src/server/research.ts";
import { Worker } from "../src/server/worker.ts";
import { api } from "../src/server/http.ts";
import { readSources } from "../src/server/source-analysis.ts";
import { emptySourceReading } from "./source-fixture.ts";
import type { Family } from "../src/shared/models.ts";
const url = "https://borderlands.fandom.com/wiki/Shared_Article",
  alias =
    "https://borderlands.fandom.com/wiki/Shared%20Article?oldid=123#Notes";
const html =
  "<main><h1>Shared article fixture</h1><p>Original cached article content describing general item mechanics, available to every family which explicitly references this exact page.</p><table><tr><th>Key</th><td>Value</td></tr></table></main>";
function fixture(t: any) {
  const dir = mkdtempSync(path.join(tmpdir(), "article-cache-"));
  let s = new Store(dir);
  const family = (id: string): Family => ({
    id,
    name: id,
    category: "Weapons",
    subtype: "SMGs",
    aliases: [],
    roots: [],
    status: "queued",
    stage: "evidence",
    inputHash: "",
    issue: null,
    notes: "",
    gameOnly: false,
    sourceUrls: [],
    history: [],
    updatedAt: "2026-01-01T00:00:00Z",
    manualOutput: false,
    revision: 0,
  });
  s.state.families = ["First item", "Second item", "Unrelated"].map(family);
  s.save();
  t.after(() => {
    s.close();
    rmSync(dir, { recursive: true, force: true });
  });
  return {
    get s() {
      return s;
    },
    dir,
    reopen() {
      s.close();
      s = new Store(dir);
      return s;
    },
  };
}
test("saved URL references instantly reuse another item’s full article, without copies or unrelated attachments, across restart", async (t) => {
  const x = fixture(t),
    s = x.s,
    [first, second, unrelated] = s.state.families,
    r = new Research(s);
  const saved = r.save(first, url, html, true);
  saved.captureMethod = "chrome";
  s.db
    .prepare("UPDATE sources SET value=? WHERE id=?")
    .run(JSON.stringify(saved), saved.id);
  second.sourceUrls = [alias];
  s.save();
  let requests = 0;
  r.fetchText = async () => {
    requests++;
    throw Error("Must not fetch cached content");
  };
  const before = JSON.stringify(s.state),
    reused = s.sources(second.id)[0];
  assert.equal(reused.id, saved.id);
  assert.equal(reused.text, saved.text);
  assert.deepEqual(reused.tables, saved.tables);
  assert.equal(reused.captureMethod, "chrome");
  assert.equal(reused.reusedFrom?.name, first.name);
  assert.equal(reused.inheritedFrom, undefined);
  assert.equal(s.rawSources(second.id).length, 0);
  assert.equal(s.sources(unrelated.id).length, 0);
  assert.equal(JSON.stringify(s.state), before);
  assert.equal((await r.fetchPage(second, alias)).id, saved.id);
  assert.equal(requests, 0);
  assert.equal(readdirSync(path.join(x.dir, "sources")).length, 1);
  const restored = x.reopen();
  assert.equal(restored.sources(second.id)[0].id, saved.id);
  assert.equal(restored.sources(second.id)[0].reusedFrom?.id, first.id);
});
test("same HTML is saved once across individual items and parent scopes; exclusions remain per reference", async (t) => {
  const { s, dir } = fixture(t),
    [first, second] = s.state.families,
    r = new Research(s),
    w = new Worker(s, {} as any),
    saved = r.save(first, url, html, true);
  const reused = r.save(second, alias, html, true);
  assert.equal(reused.id, saved.id);
  const scope = s.ensureScope({ category: "Weapons" });
  assert.equal(r.save(scope, url, html, true).id, saved.id);
  assert.equal(s.rawSources(second.id).length, 0);
  assert.equal(s.rawSources(scope.id).length, 0);
  assert.equal(readdirSync(path.join(dir, "sources")).length, 1);
  await w.action(second.id, "exclude-source", { sourceId: saved.id });
  assert.equal(s.sources(second.id).length, 0);
  assert.equal(s.sources(first.id).length, 1);
  await w.action(first.id, "exclude-source", { sourceId: saved.id });
  assert.equal(s.sources(first.id).length, 0);
  await w.action(second.id, "restore-source", { sourceId: saved.id });
  assert.equal(s.sources(second.id)[0].id, saved.id);
  assert.equal(s.sources(first.id).length, 0);
});
test("discovery reports a previously stored page as saved immediately and reads its facts separately for each family", async (t) => {
  const { s } = fixture(t),
    [first, second] = s.state.families,
    r = new Research(s),
    saved = r.save(first, url, html, true),
    w = new Worker(s, {
      run: async () => ({
        matches: [
          {
            url: alias,
            title: "Shared article",
            gameEvidence: "BL1",
            reason: "Fixture",
          },
        ],
        notFoundReason: "",
      }),
    } as any);
  await w.discoverSourceUrls(second, true);
  assert.equal(
    s
      .get<any>(second.id, "research")
      .providers.find((row: any) => row.provider === "Wiki").status,
    "saved",
  );
  assert.equal(s.sources(second.id)[0].id, saved.id);
  const prompts: string[] = [];
  const ai = {
    run: async (_label: string, prompt: string, schema: any) => {
      prompts.push(prompt);
      return schema.parse(emptySourceReading());
    },
  } as any;
  await readSources(s, ai, first, () => {});
  await readSources(s, ai, second, () => {});
  assert.equal(prompts.length, 2);
  assert(prompts.some((p) => p.includes("Family: First item")));
  assert(prompts.some((p) => p.includes("Family: Second item")));
  assert.equal(s.get<any>(first.id, "sourceLedger")[0].sourceId, saved.id);
  assert.equal(s.get<any>(second.id, "sourceLedger")[0].sourceId, saved.id);
});
test("explicit recapture publishes the newest page to existing references while retaining output and protecting excluded references", (t) => {
  const { s } = fixture(t),
    [first, second, unrelated] = s.state.families,
    r = new Research(s),
    old = r.save(first, url, html, true),
    w = new Worker(s, {} as any);
  second.sourceUrls = [alias];
  for (const f of s.state.families) {
    f.status = "done";
    s.put(f.id, "output", { saved: f.id });
  }
  first.manualOutput = true;
  const ticket = w.browserImports.create(second.id, url);
  w.browserImports.submit({
    ...ticket,
    url,
    html: html.replace(
      "Original cached article content",
      "Updated cached article content",
    ),
  });
  const latest = s.sources(second.id)[0];
  assert.notEqual(latest.id, old.id);
  assert.equal(s.sources(first.id)[0].id, latest.id);
  assert.equal(first.status, "blocked");
  assert.equal(s.get(first.id, "manualSourceReviewRequired"), true);
  assert.equal(second.status, "queued");
  assert.equal(unrelated.status, "done");
  assert.deepEqual(s.get(first.id, "output"), { saved: first.id });
});
test("fresh refresh checks the article once per batch, while a later explicit fresh run fetches again", async (t) => {
  const { s } = fixture(t),
    [first, second] = s.state.families,
    r = new Research(s);
  r.save(first, url, html, true);
  second.sourceUrls = [alias];
  s.db.exec(
    "UPDATE sources SET value=json_set(value,'$.fetchedAt','2020-01-01T00:00:00Z')",
  );
  s.state.run.status = "running";
  s.state.run.startedAt = "2026-10-26T01:00:00Z";
  let requests = 0;
  r.fetchText = async () => {
    requests++;
    return { url, text: html + "<p>Fresh content.</p>" } as any;
  };
  const updated = await r.fetchPage(first, url, true);
  assert.equal((await r.fetchPage(second, alias, true)).id, updated.id);
  assert.equal(requests, 1);
  s.state.run.startedAt = "2099-10-26T02:00:00Z";
  await r.fetchPage(second, alias, true);
  assert.equal(requests, 2);
});
test("GET item serves reused pages immediately without a build or model call", async (t) => {
  const { s } = fixture(t),
    [first, second] = s.state.families,
    r = new Research(s),
    saved = r.save(first, url, html, true);
  second.sourceUrls = [alias];
  s.save();
  const w = new Worker(s, {
      run: async () => {
        throw Error("No AI");
      },
    } as any),
    server = api(s, w).listen(0, "127.0.0.1");
  await new Promise<void>((resolve) => server.once("listening", resolve));
  t.after(() => {
    server.closeAllConnections();
    server.close();
  });
  const before = JSON.stringify(s.state),
    response = await fetch(
      `http://127.0.0.1:${(server.address() as any).port}/api/items/${second.id}`,
    ),
    detail = await response.json();
  assert.equal(response.status, 200);
  assert.equal(detail.sources[0].id, saved.id);
  assert.equal(detail.sources[0].reusedFrom.id, first.id);
  assert.equal(detail.output, null);
  assert.equal(JSON.stringify(s.state), before);
  assert.equal(w.busy, false);
});
