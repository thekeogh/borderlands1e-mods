import {
  readSources,
  sourceWritingPacket,
} from "../src/server/source-analysis.ts";
import { emptySourceReading } from "./source-fixture.ts";
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync, readdirSync } from "node:fs";
import path from "node:path";
import { tmpdir } from "node:os";
import { Store } from "../src/server/store.ts";
import { Worker } from "../src/server/worker.ts";
import { Research } from "../src/server/research.ts";
import { api } from "../src/server/http.ts";
import { scopeMatches } from "../src/shared/evidence-scopes.ts";
import { buildPacket } from "../src/server/evidence.ts";
import type { Family } from "../src/shared/models.ts";
const article =
  "<h1>Shared mechanics fixture</h1><p>Original synthetic evidence for testing inheritance across matching categories and characters without any external requests or agent calls.</p>";
const url = "https://borderlands.fandom.com/wiki/Class_Mod_(Borderlands)";
function fixture(t: any) {
  const dir = mkdtempSync(path.join(tmpdir(), "shared-evidence-"));
  let s = new Store(dir);
  t.after(() => {
    s.close();
    rmSync(dir, { recursive: true, force: true });
  });
  const family = (
    id: string,
    category: Family["category"],
    character?: Family["character"],
  ): Family => ({
    id,
    name: id,
    category,
    subtype: category,
    character,
    aliases: [],
    roots: [],
    status: "done",
    stage: "complete",
    revision: 4,
    notes: "",
    sourceUrls: [],
    history: [],
    inputHash: "",
    issue: null,
    gameOnly: false,
    manualOutput: false,
    updatedAt: new Date().toISOString(),
  });
  s.state.families = [
    family("Roland fixture", "Class mods", "Roland"),
    family("Lilith fixture", "Class mods", "Lilith"),
    family("Shield fixture", "Shields"),
    family("Weapon fixture", "Weapons"),
  ];
  const w = new Worker(s, {} as any);
  return {
    get s() {
      return s;
    },
    w,
    dir,
    reopen() {
      s.close();
      s = new Store(dir);
      return s;
    },
  };
}
async function idle(w: Worker) {
  for (let n = 0; n < 200 && w.busy; n++)
    await new Promise((r) => setTimeout(r, 5));
  assert.equal(w.busy, false);
}
async function serverFixture(t: any) {
  const x = fixture(t),
    server = api(x.s, x.w).listen(0, "127.0.0.1");
  await new Promise<void>((r) => server.once("listening", r));
  t.after(() => {
    server.closeAllConnections();
    server.close();
  });
  const base = `http://127.0.0.1:${(server.address() as any).port}`;
  return {
    ...x,
    post: (route: string, body: unknown) =>
      fetch(base + route, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    get: (route: string) => fetch(base + route).then((r) => r.json()),
  };
}
test("shared category, character and weapon scopes inherit narrowly; canonical articles are cached once and persist", (t) => {
  const x = fixture(t),
    s = x.s,
    [roland, lilith, shield, weapon] = s.state.families;
  const all = s.ensureScope({ category: "Class mods" }),
    specific = s.ensureScope({ category: "Class mods", character: "Roland" }),
    guns = s.ensureScope({ category: "Weapons" });
  const research = new Research(s);
  const first = research.save(all, url, article, true);
  specific.sourceUrls.push(url);
  const reused = research.save(specific, url, article, true);
  assert.equal(first.id, reused.id);
  research.save(
    specific,
    "https://borderlands.fandom.com/wiki/Support_Gunner",
    article + "<p>Roland-specific skill context.</p>",
    true,
  );
  research.save(
    guns,
    "https://borderlands.fandom.com/wiki/Weapons",
    article,
    true,
  );
  assert.equal(s.sources(roland.id).length, 2);
  assert.equal(s.sources(lilith.id).length, 1);
  assert.equal(s.sources(shield.id).length, 0);
  assert.equal(s.sources(weapon.id).length, 1);
  assert.equal(
    scopeMatches(
      { category: "Weapons", group: "Combat rifles" },
      { ...weapon, subtype: "Machine guns" },
    ),
    true,
  );
  assert.equal(
    scopeMatches(
      { category: "Weapons", group: "SMGs" },
      { ...weapon, subtype: "Machine guns" },
    ),
    false,
  );
  assert.equal(s.sources(lilith.id)[0].inheritedFrom?.name, "Class mods");
  assert.equal(
    buildPacket(s, roland).evidence.filter((e) => e.kind === "page").length,
    2,
  );
  assert.equal(readdirSync(path.join(x.dir, "sources")).length, 3);
  s.save();
  const restored = x.reopen();
  assert.equal(restored.sources(roland.id).length, 2);
  assert.equal(restored.state.families.length, 4);
  assert.equal(
    restored.ensureScope({ character: "Roland", category: "Class mods" }).id,
    specific.id,
  );
});
test("shared-source API binds without fetching, imports once, excludes per-item, removes per-scope and preserves outputs", async (t) => {
  const x = await serverFixture(t),
    { s, w } = x,
    [roland, lilith] = s.state.families;
  s.put(roland.id, "output", { saved: true });
  let calls = 0;
  w.research.fetchText = async () => {
    calls++;
    throw Error("Must not fetch");
  };
  const scope = { category: "Class mods" };
  let response = await x.post("/api/shared-sources", { scope, url });
  assert.equal(response.status, 200);
  assert.equal(calls, 0);
  assert.equal(roland.status, "queued");
  assert.deepEqual(s.get(roland.id, "output"), { saved: true });
  assert.equal(roland.revision, 4);
  response = await x.post("/api/shared-sources", { scope, url, html: article });
  assert.equal(response.status, 200);
  const source = s.sources(roland.id)[0];
  assert(source);
  assert.equal(
    (
      await x.post(`/api/items/${roland.id}/action`, {
        action: "exclude-source",
        sourceId: source.id,
      })
    ).status,
    200,
  );
  assert.equal(s.sources(roland.id).length, 0);
  assert.equal(s.sources(lilith.id).length, 1);
  assert.equal(
    (
      await x.post(`/api/items/${roland.id}/action`, {
        action: "restore-source",
        sourceId: source.id,
      })
    ).status,
    200,
  );
  assert.equal(s.sources(roland.id).length, 1);
  assert.equal(
    (await x.post("/api/shared-sources", { scope, url, remove: true })).status,
    200,
  );
  assert.equal(s.sources(lilith.id).length, 0);
  assert.equal(s.rawSources(s.ensureScope(scope).id).length, 1);
  assert.equal(calls, 0);
});
test("Chrome capture updates all groups sharing an article; no synthetic group enters build queue", (t) => {
  const { s, w } = fixture(t),
    all = s.ensureScope({ category: "Class mods" }),
    specific = s.ensureScope({ category: "Shields" });
  all.sourceUrls.push(url);
  specific.sourceUrls.push(url);
  s.state.run.status = "paused";
  s.state.run.queue = [s.state.families[0].id];
  const ticket = w.browserImports.create(all.id, url);
  w.browserImports.submit({ ...ticket, url, html: article });
  assert.equal(s.sources(s.state.families[0].id).length, 1);
  assert.equal(s.sources(s.state.families[2].id).length, 1);
  assert.equal(s.state.families[2].status, "queued");
  assert(s.state.run.queue.every((id) => !id.startsWith("shared-")));
  assert.equal(s.state.run.queue.length, 3);
  assert.equal(s.state.families[3].status, "done");
});
test("URL-only discovery includes completed items, skips removed, continues failures, leaves JSON and stages untouched", async (t) => {
  const { s, w } = fixture(t);
  s.state.families[3].status = "excluded";
  for (const f of s.state.families) s.put(f.id, "output", { marker: f.id });
  const before = s.state.families.map((f) => ({
    id: f.id,
    status: f.status,
    stage: f.stage,
    revision: f.revision,
    output: s.get(f.id, "output"),
  }));
  let aiCalls = 0,
    fetches = 0;
  w.ai = {
    run: async () => {
      aiCalls++;
      if (aiCalls === 2) throw Error("Synthetic discovery error");
      return {
        matches: [
          {
            url: "https://www.lootlemon.com/class-mod/fixture-bl1",
            title: "BL1 fixture",
            gameEvidence: "Borderlands 1",
            reason: "Fixture",
          },
        ],
        notFoundReason: "Wiki unavailable; Lootlemon page verified",
      };
    },
  } as any;
  w.research.fetchPage = async () => {
    fetches++;
    throw Error("Must not fetch");
  };
  w.start(undefined, undefined, "auto", "discover");
  await idle(w);
  assert.equal(aiCalls, 3);
  assert.equal(fetches, 0);
  assert.equal(s.state.run.status, "complete");
  assert.match(s.state.run.message, /1 need attention/);
  assert.deepEqual(
    s.state.families
      .map((f) => ({
        id: f.id,
        status: f.status,
        stage: f.stage,
        revision: f.revision,
        output: s.get(f.id, "output"),
      }))
      .sort((a, b) => a.id.localeCompare(b.id)),
    before.sort((a, b) => a.id.localeCompare(b.id)),
  );
  assert.equal(s.family("Roland fixture").urlDiscovery?.status, "complete");
  assert.equal(s.family("Lilith fixture").urlDiscovery?.status, "failed");
  assert.equal(s.db.prepare("SELECT COUNT(*) AS n FROM sources").get()!.n, 0);
});
test("URL discovery pause/resume/restart preserves a separate build checkpoint and Chrome updates it only", async (t) => {
  const x = fixture(t),
    { s, w } = x;
  const original = s.state.run;
  Object.assign(original, {
    status: "paused",
    queue: [s.state.families[0].id],
    index: 0,
    currentId: s.state.families[0].id,
    sourceMode: "fresh",
    sourcePrepared: [s.state.families[0].id],
    message: "Build checkpoint",
  });
  let calls = 0;
  w.ai = {
    run: async () => {
      calls++;
      w.pause();
      return {
        matches: [
          { url, title: "fixture", gameEvidence: "BL1", reason: "fixture" },
        ],
        notFoundReason: "",
      };
    },
  } as any;
  w.start(undefined, undefined, "auto", "discover");
  await idle(w);
  assert.equal(calls, 1);
  assert.equal(s.state.run.index, 1);
  assert.equal(s.state.run.status, "paused");
  assert.deepEqual(s.state.buildCheckpoint, original);
  const group = s.ensureScope({ category: "Shields" }),
    ticket = w.browserImports.create(group.id, url);
  w.browserImports.submit({ ...ticket, url, html: article });
  assert.equal(s.state.run.queue.length, 4);
  assert(s.state.buildCheckpoint!.queue.includes(s.state.families[2].id));
  assert.equal(s.state.run.index, 1);
  const restored = x.reopen(),
    newWorker = new Worker(restored, {
      run: async () => ({ matches: [], notFoundReason: "No matching page" }),
    } as any);
  newWorker.step = async (f) => {
    f.stage = "complete";
    f.status = "done";
    return;
  };
  newWorker.resumeBuild();
  await idle(newWorker);
  assert.equal(restored.state.run.mode, undefined);
  assert.equal(restored.state.run.sourceMode, "fresh");
  assert.equal(restored.state.buildCheckpoint, undefined);
});
test("shared evidence mutation protects current descendants but allows unrelated groups", async (t) => {
  const x = await serverFixture(t),
    { s, w } = x;
  s.state.run.currentId = s.state.families[0].id;
  w.busy = true;
  assert.equal(
    (
      await x.post("/api/shared-sources", {
        scope: { category: "Class mods" },
        url,
      })
    ).status,
    409,
  );
  assert.equal(
    (
      await x.post("/api/shared-sources", {
        scope: { category: "Shields" },
        url,
      })
    ).status,
    200,
  );
  w.busy = false;
  assert.equal(
    (
      await x.post("/api/shared-sources", {
        scope: { category: "Shields", character: "Roland" },
        url,
      })
    ).status,
    400,
  );
});
test("shared refresh fetches once per batch, retains older archives, and uses newest article across scopes and local duplicates", async (t) => {
  const { s, w } = fixture(t),
    all = s.ensureScope({ category: "Class mods" }),
    [first, second] = s.state.families;
  const own = w.research.save(
    first,
    url,
    article + "<p>Old local copy.</p>",
    true,
  );
  w.research.save(all, url, article + "<p>Old shared copy.</p>", true);
  s.db.exec(
    "UPDATE sources SET value=json_set(value,'$.fetchedAt','2020-01-01T00:00:00.000Z')",
  );
  s.state.run.startedAt = new Date().toISOString();
  s.state.run.status = "running";
  let calls = 0;
  w.research.fetchText = async () => {
    calls++;
    return {
      url,
      text: article + "<p>New shared mechanics for all matching items.</p>",
    } as any;
  };
  // A real run starts before its fetch timestamp; set it just before the call.
  s.state.run.startedAt = new Date().toISOString();
  const updated = await w.research.fetchPage(first, url, true);
  await w.research.fetchPage(second, url, true);
  assert.equal(calls, 1);
  assert.notEqual(updated.id, own.id);
  assert.equal(s.sources(first.id)[0].id, updated.id);
  assert.equal(s.sources(second.id)[0].id, updated.id);
  assert.equal(s.rawSources(first.id).length, 1);
  assert.equal(s.rawSources(all.id).length, 2);
});
test("failed shared requests are not repeated per child in one run; next run can retry", async (t) => {
  const { s, w } = fixture(t),
    all = s.ensureScope({ category: "Class mods" }),
    [first, second] = s.state.families;
  all.sourceUrls = [url];
  s.state.run.status = "running";
  s.state.run.startedAt = "2026-10-25T10:00:00Z";
  let calls = 0;
  w.research.fetchText = async () => {
    calls++;
    throw Error("Synthetic 403");
  };
  await assert.rejects(w.research.fetchPage(first, url, true), /Synthetic 403/);
  await assert.rejects(
    w.research.fetchPage(second, url, true),
    /Synthetic 403/,
  );
  assert.equal(calls, 1);
  s.state.run.startedAt = "2026-10-25T11:00:00Z";
  await assert.rejects(
    w.research.fetchPage(second, url, true),
    /Synthetic 403/,
  );
  assert.equal(calls, 2);
});
test(
  "Postman: real research HTTP captures one shared article for matching descendants",
  { skip: !process.env.BORDERLENS_SIMULATION },
  async (t) => {
    const { s } = fixture(t),
      scope = s.ensureScope({ category: "Class mods" }),
      [first, second] = s.state.families;
    const target = "https://borderlands.fandom.com/wiki/Hellfire_(Borderlands)";
    scope.sourceUrls = [target];
    s.state.run.status = "running";
    s.state.run.startedAt = new Date().toISOString();
    let requests = 0;
    const research = new Research(
      s,
      async (...args: Parameters<typeof fetch>) => {
        requests++;
        return fetch(...args);
      },
      process.env.BORDERLENS_SIMULATION,
    );
    const page = await research.fetchPage(first, target, true);
    assert.match(page.text, /Borderlands 1/);
    const afterFirst = requests;
    assert(afterFirst > 0);
    await research.fetchPage(second, target, true);
    assert.equal(requests, afterFirst);
    assert.equal(s.sources(first.id)[0].id, page.id);
    assert.equal(s.sources(second.id)[0].id, page.id);
  },
);

test("detaching a shared URL rejects an older pending Chrome ticket; re-adding reuses saved content", async (t) => {
  const x = await serverFixture(t),
    { s, w } = x,
    scope = { category: "Class mods" },
    owner = s.ensureScope(scope);
  await x.post("/api/shared-sources", { scope, url, html: article });
  const ticket = w.browserImports.create(owner.id, url);
  await x.post("/api/shared-sources", { scope, url, remove: true });
  const result = w.browserImports.submit({ ...ticket, url, html: article });
  assert.equal(result.status, "failed");
  assert.equal(owner.sourceUrls.length, 0);
  assert.equal(s.sources(s.state.families[0].id).length, 0);
  assert.equal(
    (await x.post("/api/shared-sources", { scope, url })).status,
    200,
  );
  assert.equal(s.sources(s.state.families[0].id).length, 1);
});

test("Everything plus every matching ancestor reaches the full reader and writer packet; exclusions still win", async (t) => {
  const { s, w } = fixture(t),
    [roland, lilith, shield, weapon] = s.state.families;
  const global = s.ensureScope({ category: "Everything" }),
    category = s.ensureScope({ category: "Class mods" }),
    character = s.ensureScope({ category: "Class mods", character: "Roland" }),
    weapons = s.ensureScope({ category: "Weapons" }),
    weaponType = s.ensureScope({ category: "Weapons", group: "Combat rifles" });
  weapon.subtype = "Machine guns";
  const save = (owner: Family, name: string) =>
    w.research.save(
      owner,
      `https://borderlands.fandom.com/wiki/${name}`,
      `<h1>${name}</h1><p>Evidence marker ${name}. Original fixture facts to verify full multilevel evidence inheritance and reading for the matching catalogue family.</p>`,
      true,
    );
  const globalPage = save(global, "Global_fixture"),
    categoryPage = save(category, "Class_mod_fixture"),
    characterPage = save(character, "Roland_fixture"),
    localPage = save(roland, "Item_fixture");
  save(weapons, "Weapons_fixture");
  save(weaponType, "Combat_rifle_fixture");
  assert.equal(global.name, "Everything");
  assert.equal(s.scopeChildren(global).length, 4);
  assert.equal(s.state.families.length, 4);
  assert.deepEqual(
    new Set(s.sources(roland.id).map((source) => source.id)),
    new Set([globalPage.id, categoryPage.id, characterPage.id, localPage.id]),
  );
  assert.equal(s.sources(lilith.id).length, 2);
  assert.equal(s.sources(shield.id).length, 1);
  assert.equal(s.sources(weapon.id).length, 3);
  const packet = buildPacket(s, roland),
    prompts: string[] = [];
  const ledger = await readSources(
    s,
    {
      run: async (_label: string, prompt: string, schema: any) => {
        prompts.push(prompt);
        const name = /Evidence marker ([A-Za-z_]+)\./.exec(prompt)![1];
        return schema.parse({
          ...emptySourceReading(roland.category),
          facts: [
            {
              field: "details",
              detail: "Applicable fixture information " + name,
              quote: "Evidence marker " + name + ".",
              stat: null,
            },
          ],
        });
      },
    } as any,
    roland,
    () => {},
  );
  assert.equal(prompts.length, 4);
  assert.equal(ledger.length, 4);
  const writerPages = sourceWritingPacket(packet, ledger);
  assert.equal(writerPages.length, 4);
  assert.equal(
    writerPages.flatMap((page) => page.chunks.flatMap((chunk) => chunk.facts))
      .length,
    4,
  );
  for (const source of s.sources(roland.id)) {
    assert(
      prompts.some(
        (prompt) => prompt.includes(source.url) && prompt.includes(source.text),
      ),
    );
    assert(writerPages.some((page) => page.sourceId === source.id));
  }
  assert.equal((await xExclude(w, roland, globalPage.id)).length, 3);
  assert.equal(s.sources(lilith.id).length, 2);
  category.sourceUrls.push(globalPage.url);
  assert.equal(s.sources(roland.id).length, 3);
  assert.equal(s.sources(lilith.id).length, 2);
  s.save();
});
async function xExclude(w: Worker, f: Family, sourceId: string) {
  await w.action(f.id, "exclude-source", { sourceId });
  return w.store.sources(f.id);
}

test("global API queues all active items only, preserves outputs and rejects subgroups under Everything", async (t) => {
  const x = await serverFixture(t),
    { s } = x;
  s.state.families[3].status = "excluded";
  for (const f of s.state.families) s.put(f.id, "output", { saved: f.id });
  const response = await x.post("/api/shared-sources", {
    scope: { category: "Everything" },
    url,
    html: article,
  });
  assert.equal(response.status, 200);
  const result = await response.json();
  assert.equal(result.children, 3);
  assert.equal(result.family.name, "Everything");
  for (const f of s.state.families.filter((f) => f.status !== "excluded")) {
    assert.equal(f.status, "queued");
    assert.equal(f.revision, 4);
    assert.deepEqual(s.get(f.id, "output"), { saved: f.id });
    assert.equal(s.sources(f.id).length, 1);
  }
  assert.equal(s.state.families[3].status, "excluded");
  assert.equal(s.state.families.length, 4);
  assert.equal(
    (
      await x.post("/api/shared-sources", {
        scope: { category: "Everything", group: "SMGs" },
        url,
      })
    ).status,
    400,
  );
  assert.equal(
    (
      await x.post("/api/shared-sources", {
        scope: { category: "Everything", character: "Roland" },
        url,
      })
    ).status,
    400,
  );
});

test("item URL discovery filters inherited aliases, retains parent ownership, exposes capture status and preserves build checkpoint/output", async (t) => {
  const x = await serverFixture(t),
    { s, w } = x,
    [f, other] = s.state.families;
  const global = s.ensureScope({ category: "Everything" }),
    category = s.ensureScope({ category: "Class mods" }),
    ancestorUrl = "https://borderlands.fandom.com/wiki/Corrosive_Damage",
    pendingUrl = "https://borderlands.fandom.com/wiki/Shock_Damage";
  const articleSource = w.research.save(global, ancestorUrl, article, true);
  category.sourceUrls = [ancestorUrl];
  global.sourceUrls.push(pendingUrl);
  s.put(f.id, "output", { saved: "previous JSON" });
  const before = { status: f.status, stage: f.stage, revision: f.revision };
  Object.assign(s.state.run, {
    status: "paused",
    queue: [other.id],
    index: 0,
    currentId: other.id,
    sourcePrepared: [other.id],
  });
  const checkpoint = structuredClone(s.state.run);
  let prompts: string[] = [];
  w.ai = {
    run: async (_label: string, prompt: string) => {
      prompts.push(prompt);
      return {
        matches: [
          {
            url: "https://borderlands.fandom.com/wiki/corrosive%20damage?oldid=42",
            title: "Inherited alias",
            gameEvidence: "BL1",
            reason: "Fixture",
          },
          {
            url: pendingUrl,
            title: "Inherited pending",
            gameEvidence: "BL1",
            reason: "Fixture",
          },
          {
            url: "https://www.lootlemon.com/class-mod/fixture-bl1",
            title: "Individual page",
            gameEvidence: "BL1",
            reason: "Fixture",
          },
        ],
        notFoundReason: "",
      };
    },
  } as any;
  w.research.fetchPage = async () => {
    throw Error("URL-only action must not fetch article HTML");
  };
  assert.equal(
    (await x.post(`/api/items/${f.id}/action`, { action: "discover" })).status,
    200,
  );
  await idle(w);
  assert.deepEqual(s.state.run.queue, [f.id]);
  assert.equal(s.state.run.mode, "discover");
  assert.equal(f.urlDiscovery?.status, "complete");
  assert.deepEqual(s.state.buildCheckpoint, checkpoint);
  assert.deepEqual(
    { status: f.status, stage: f.stage, revision: f.revision },
    before,
  );
  assert.deepEqual(s.get(f.id, "output"), { saved: "previous JSON" });
  assert.deepEqual(f.sourceUrls, [
    "https://www.lootlemon.com/class-mod/fixture-bl1",
  ]);
  assert.equal(s.get<any>(f.id, "matches").matches.length, 1);
  assert.equal(s.rawSources(f.id).length, 0);
  assert.equal(s.source(articleSource.id)?.familyId, global.id);
  assert(
    prompts[0].includes(ancestorUrl) &&
      prompts[0].includes("Everything") &&
      prompts[0].includes("Class mods"),
  );
  const detail = await x.get(`/api/items/${f.id}`);
  assert.equal(detail.inheritedEvidence.length, 2);
  const shared = detail.inheritedEvidence.find(
    (row: any) => row.url === ancestorUrl,
  );
  assert.equal(shared.captured, true);
  assert.deepEqual(
    shared.parents.map((p: any) => p.name),
    ["Everything", "Class mods"],
  );
  assert.equal(
    detail.inheritedEvidence.find((row: any) => row.url === pendingUrl)
      .captured,
    false,
  );
});
test("inherited-only discovery succeeds without copying shared links; active jobs refuse single-item discovery", async (t) => {
  const x = await serverFixture(t),
    { s, w } = x,
    f = s.state.families[0],
    global = s.ensureScope({ category: "Everything" });
  global.sourceUrls = [url];
  w.ai = {
    run: async () => ({
      matches: [
        {
          url,
          title: "Shared overview",
          gameEvidence: "BL1",
          reason: "Fixture",
        },
      ],
      notFoundReason: "No individual page available",
    }),
  } as any;
  w.busy = true;
  const original = structuredClone(s.state.run);
  assert.equal(
    (await x.post(`/api/items/${f.id}/action`, { action: "discover" })).status,
    409,
  );
  assert.deepEqual(s.state.run, original);
  w.busy = false;
  assert.equal(
    (await x.post(`/api/items/${f.id}/action`, { action: "discover" })).status,
    200,
  );
  await idle(w);
  assert.equal(f.urlDiscovery?.status, "complete");
  assert.deepEqual(f.sourceUrls, []);
  assert.equal(
    s
      .get<any>(f.id, "research")
      .providers.find((row: any) => row.provider === "Wiki").status,
    "inherited",
  );
  await w.action(f.id, "resolve", { url, html: article });
  await w.action(f.id, "exclude-source", { sourceId: s.sources(f.id)[0].id });
  assert.equal(s.inheritedEvidence(f).length, 0);
});
