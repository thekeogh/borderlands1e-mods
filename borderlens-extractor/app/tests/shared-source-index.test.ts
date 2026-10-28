import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { Store } from "../src/server/store.ts";
import { Worker } from "../src/server/worker.ts";
import {
  readSources,
  sourceWritingPacket,
  type SourceReading,
} from "../src/server/source-analysis.ts";
import {
  sharedFactDecision,
  SHARED_READING_POLICY,
  type FactScope,
} from "../src/server/shared-source-index.ts";
import { buildPacket, packetHash } from "../src/server/evidence.ts";
import { savedSourceCache } from "../src/server/source-cache.ts";
import { emptySourceReading } from "./source-fixture.ts";
import type { Family } from "../src/shared/models.ts";
const url = "https://borderlands.fandom.com/wiki/Brick_Skills";
const sharedText =
  "General class mod rules remain useful. Heavy Handed boosts melee damage. Safeguard improves shields. Bash can stun enemies. Uncertain cross-skill interaction affects other equipment.";
const sharedHtml = `<h1>Brick skills</h1><p>${sharedText}</p>`;
function scope(overrides: Partial<FactScope> = {}): FactScope {
  return {
    certain: true,
    categories: [],
    characters: [],
    elements: [],
    weaponTypes: [],
    items: [],
    skills: [],
    ...overrides,
  };
}
function fact(detail: string, scopeTag?: FactScope) {
  return {
    field: "details" as const,
    detail,
    quote: detail,
    stat: null,
    ...(scopeTag ? { scope: scopeTag } : {}),
  };
}
function fixture(t: any) {
  const dir = mkdtempSync(path.join(tmpdir(), "shared-index-"));
  let s = new Store(dir);
  t.after(() => {
    s.close();
    rmSync(dir, { recursive: true, force: true });
  });
  const family = (id: string): Family => ({
    id,
    name: id,
    category: "Class mods",
    subtype: "Class mods",
    character: "Brick",
    aliases: [],
    roots: [],
    status: "queued",
    stage: "draft",
    revision: 0,
    notes: "",
    sourceUrls: [],
    history: [],
    inputHash: "",
    issue: null,
    gameOnly: false,
    manualOutput: false,
    updatedAt: new Date().toISOString(),
  });
  s.state.families = [family("Bad Ass"), family("Other mod")];
  s.save();
  const w = new Worker(s, {} as any),
    owner = s.ensureScope({ category: "Class mods", character: "Brick" });
  w.research.save(owner, url, sharedHtml, true);
  for (const f of s.state.families)
    w.research.save(
      f,
      `https://www.lootlemon.com/class-mod/${f.id.replaceAll(" ", "-")}`,
      `<h1>${f.name}</h1><p>${f.name} boosts ${f.id === "Bad Ass" ? "Heavy Handed and Bash" : "Safeguard"}.</p><p>Original synthetic item-specific evidence for shared-source selection tests.</p>`,
      true,
    );
  const calls: { shared: number; direct: number; prompts: string[] } = {
    shared: 0,
    direct: 0,
    prompts: [],
  };
  const ai = {
    run: async (label: string, prompt: string, schema: any) => {
      calls.prompts.push(prompt);
      if (label.startsWith("Read source shared article")) {
        calls.shared++;
        assert(!prompt.includes("Family: Bad Ass"));
        return schema.parse({
          ...emptySourceReading("Class mods"),
          facts: [
            fact(
              "General class mod rules remain useful.",
              scope({ categories: ["Class mods"] }),
            ),
            fact(
              "Heavy Handed boosts melee damage.",
              scope({ characters: ["Brick"], skills: ["Heavy Handed"] }),
            ),
            fact(
              "Safeguard improves shields.",
              scope({ characters: ["Brick"], skills: ["Safeguard"] }),
            ),
            fact(
              "Bash can stun enemies.",
              scope({ characters: ["Brick"], skills: ["Bash"] }),
            ),
            fact(
              "Uncertain cross-skill interaction affects other equipment.",
              scope({
                certain: false,
                categories: ["Shields"],
                skills: ["Unrelated"],
              }),
            ),
          ],
        });
      }
      calls.direct++;
      const first = label.includes("Bad Ass"),
        names = first ? ["Heavy Handed", "Bash"] : ["Safeguard"],
        quote = first
          ? "Bad Ass boosts Heavy Handed and Bash."
          : "Other mod boosts Safeguard.";
      return schema.parse({
        ...emptySourceReading("Class mods"),
        facts: [fact(quote)],
        applicability: {
          skills: { names, complete: true, quote },
          elements: { names: [], complete: false, quote: "" },
        },
      });
    },
  } as any;
  return {
    get s() {
      return s;
    },
    w,
    ai,
    calls,
    owner,
    reopen() {
      s.close();
      s = new Store(dir);
      return s;
    },
  };
}
test("shared page read once for different items; selected facts retain general rules, applicable skills, uncertainty and original sources", async (t) => {
  const { s, ai, calls } = fixture(t),
    [first, second] = s.state.families;
  const a = await readSources(s, ai, first, () => {}),
    b = await readSources(s, ai, second, () => {});
  assert.equal(calls.shared, 1);
  assert.equal(calls.direct, 2);
  const facts = (ledger: any) =>
    ledger
      .flatMap((p: any) => p.chunks.flatMap((c: any) => c.facts))
      .map((f: any) => f.detail);
  assert(facts(a).includes("Heavy Handed boosts melee damage."));
  assert(!facts(a).includes("Safeguard improves shields."));
  assert(facts(b).includes("Safeguard improves shields."));
  assert(!facts(b).includes("Bash can stun enemies."));
  for (const ledger of [a, b]) {
    assert(facts(ledger).includes("General class mod rules remain useful."));
    assert(
      facts(ledger).includes(
        "Uncertain cross-skill interaction affects other equipment.",
      ),
    );
  }
  const packet = sourceWritingPacket(buildPacket(s, first), a);
  assert(!JSON.stringify(packet).includes("Safeguard improves shields."));
  assert(
    s
      .sources(first.id)
      .find((p) => p.url === url)!
      .text.includes("Safeguard improves shields."),
  );
  const audit = s.get<any>(second.id, "sharedSourceSelection");
  assert.equal(audit.cachedChunks, 1);
  assert.equal(audit.excluded, 2);
  assert.equal(audit.policy, SHARED_READING_POLICY);
  assert(calls.prompts[0].includes("Family: Bad Ass")); // individual evidence is read before shared filtering
});
test("unchanged shared analysis persists across restart and fresh requests; changed page, model or agent is re-indexed", async (t) => {
  const x = fixture(t);
  await readSources(x.s, x.ai, x.s.state.families[0], () => {}, "fresh-one");
  const reopened = x.reopen();
  await readSources(
    reopened,
    x.ai,
    reopened.state.families[1],
    () => {},
    "fresh-two",
  );
  assert.equal(x.calls.shared, 1);
  const worker = new Worker(reopened, {} as any);
  worker.research.save(
    reopened.ensureScope({ category: "Class mods", character: "Brick" }),
    url,
    sharedHtml + "<p>New context.</p>",
    true,
  );
  await readSources(reopened, x.ai, reopened.state.families[1], () => {});
  assert.equal(x.calls.shared, 2);
  reopened.state.settings.agent = "codex";
  await readSources(reopened, x.ai, reopened.state.families[1], () => {});
  assert.equal(x.calls.shared, 3);
});
test("incomplete profiles, unknown selectors, manual corrections and uncertain interactions do not drop facts", (t) => {
  const { s } = fixture(t),
    f = s.state.families[0];
  const incomplete = {
    ...emptySourceReading("Class mods"),
    applicability: {
      skills: { names: ["Safeguard"], complete: false, quote: "" },
      elements: { names: [], complete: false, quote: "" },
    },
  };
  assert(
    sharedFactDecision(scope({ skills: ["Heavy Handed"] }), f, [incomplete])
      .included,
  );
  assert(sharedFactDecision(undefined, f, []).included);
  assert(
    sharedFactDecision(scope({ certain: false, characters: ["Lilith"] }), f, [])
      .included,
  );
  assert(
    sharedFactDecision(scope({ elements: ["Incendiary"] }), f, []).included,
  );
  const any = {
    ...incomplete,
    applicability: {
      ...incomplete.applicability,
      elements: { names: ["Any"], complete: true, quote: "Any" },
    },
  };
  assert(sharedFactDecision(scope({ elements: ["Shock"] }), f, [any]).included);
  f.notes = "Include this unusual skill interaction.";
  const complete = {
    ...incomplete,
    applicability: {
      ...incomplete.applicability,
      skills: { names: ["Safeguard"], complete: true, quote: "Safeguard" },
    },
  };
  assert(
    sharedFactDecision(scope({ skills: ["Heavy Handed"] }), f, [complete])
      .included,
  );
});
test("only established conflicting target dimensions exclude shared facts", (t) => {
  const { s } = fixture(t),
    f = s.state.families[0];
  assert(
    !sharedFactDecision(scope({ characters: ["Lilith"] }), f, []).included,
  );
  assert(
    !sharedFactDecision(scope({ categories: ["Weapons"] }), f, []).included,
  );
  assert(!sharedFactDecision(scope({ items: ["Other mod"] }), f, []).included);
  assert(
    sharedFactDecision(scope({ characters: ["Lilith", "Brick"] }), f, [])
      .included,
  );
  f.category = "Artifacts";
  f.element = "Incendiary";
  assert(sharedFactDecision(scope({ elements: ["Fire"] }), f, []).included);
  assert(!sharedFactDecision(scope({ elements: ["Shock"] }), f, []).included);
  f.category = "Weapons";
  f.subtype = "SMGs";
  assert(
    !sharedFactDecision(scope({ weaponTypes: ["Shotguns"] }), f, []).included,
  );
});
test("bad shared extraction falls back to full per-item reading; no partial index is cached", async (t) => {
  const { s, ai, calls } = fixture(t),
    f = s.state.families[0];
  const fallback = {
    run: async (label: string, prompt: string, schema: any) =>
      label.startsWith("Read source shared article")
        ? {
            ...emptySourceReading("Class mods"),
            facts: [fact("Invented fact which is not in this page.", scope())],
          }
        : prompt.includes(`Source: ${url}`)
          ? (calls.direct++,
            schema.parse({
              ...emptySourceReading("Class mods"),
              facts: [fact("General class mod rules remain useful.")],
            }))
          : ai.run(label, prompt, schema),
  } as any;
  const ledger = await readSources(s, fallback, f, () => {});
  assert.equal(ledger.length, 2);
  assert.equal(calls.direct, 2);
  assert.equal(s.get<any>(f.id, "sharedSourceSelection").fallbackChunks, 1);
  assert.equal(
    (
      s.db
        .prepare(
          "SELECT COUNT(*) AS n FROM artifacts WHERE family='_sharedSources'",
        )
        .get() as any
    ).n,
    0,
  );
});
test("saved ledger validation accepts only the current relevance policy and keeps selected stats accountable", async (t) => {
  const { s, ai } = fixture(t),
    f = s.state.families[0];
  f.inputHash = packetHash(buildPacket(s, f));
  await readSources(s, ai, f, () => {});
  assert(savedSourceCache(s, f).ledger);
  s.put(f.id, "sourceLedgerPolicy", "old-policy");
  assert.equal(savedSourceCache(s, f).ledger, undefined);
});

test("unrelated pages never reach the writer, while supported numerical facts and full late chunks remain retained", async (t) => {
  const { s, w } = fixture(t),
    f = s.state.families[0];
  const owner = s.ensureScope({ category: "Everything" });
  const late = "Ammo regeneration is 2 to 25.";
  const irrelevant = "Only shields get this shield capacity bonus.";
  const statsUrl = "https://borderlands.fandom.com/wiki/Shared_Numeric_fixture";
  w.research.save(
    owner,
    statsUrl,
    `<h1>Long numeric source</h1><p>${"Long general context. ".repeat(1700)}</p><p>${late}</p>`,
    true,
  );
  w.research.save(
    owner,
    "https://borderlands.fandom.com/wiki/Only_Shields",
    `<h1>Shield context</h1><p>${irrelevant}</p><p>Additional original test content to reach the source minimum.</p>`,
    true,
  );
  // Remove other bindings to isolate these two shared pages.
  s.ensureScope({ category: "Class mods", character: "Brick" }).sourceUrls = [];
  f.sourceUrls = [];
  for (const source of s.rawSources(f.id))
    s.db.prepare("DELETE FROM sources WHERE id=?").run(source.id);
  let calls = 0;
  const ai = {
    run: async (_label: string, prompt: string, schema: any) => {
      calls++;
      const facts =
        prompt.includes("SOURCE CHUNK:\n") &&
        prompt.split("SOURCE CHUNK:\n")[1].includes(irrelevant)
          ? [fact(irrelevant, scope({ categories: ["Shields"] }))]
          : prompt.split("SOURCE CHUNK:\n")[1]?.includes(late)
            ? [
                {
                  ...fact(late, scope({ categories: ["Class mods"] })),
                  field: "stats",
                  stat: {
                    name: "Ammo regeneration",
                    minimum: 2,
                    maximum: 25,
                    unit: "",
                    level: null,
                    notes: "Card bonus",
                  },
                },
              ]
            : [];
      return schema.parse({ ...emptySourceReading("Class mods"), facts });
    },
  } as any;
  const ledger = await readSources(s, ai, f, () => {});
  assert(calls >= 3);
  const packet = sourceWritingPacket(buildPacket(s, f), ledger);
  assert.equal(packet.length, 1);
  assert(
    packet[0].chunks.some((chunk) =>
      chunk.facts.some(
        (fact) => fact.stat?.minimum === 2 && fact.stat.maximum === 25,
      ),
    ),
  );
  assert(!JSON.stringify(packet).includes(irrelevant));
  assert.equal(ledger.length, 2); // Every source stays accounted for privately, including omitted pages.
});

test("Always include overrides relevance for one item, reuses indexed facts and returns to Auto without recapture", async (t) => {
  const x = fixture(t),
    { s, w, ai, calls } = x,
    [first, second] = s.state.families;
  assert.equal(s.inheritedEvidence(first)[0].alwaysInclude, false);
  await readSources(s, ai, first, () => {});
  s.put(first.id, "output", { retained: true });
  Object.assign(s.state.run, {
    status: "paused",
    queue: [second.id],
    index: 0,
    currentId: null,
  });
  s.state.buildCheckpoint = structuredClone(s.state.run);
  const run = structuredClone(s.state.run),
    checkpoint = structuredClone(s.state.buildCheckpoint),
    revision = first.revision;
  w.setSharedSourceMode(first.id, url + "#Notes", "always");
  assert.equal(s.inheritedEvidence(first)[0].alwaysInclude, true);
  assert.equal(s.inheritedEvidence(second)[0].alwaysInclude, false);
  assert.equal(s.get(first.id, "sourceLedger"), null);
  assert.deepEqual(s.get(first.id, "output"), { retained: true });
  assert.equal(first.revision, revision);
  assert.deepEqual(s.state.run, run);
  assert.deepEqual(s.state.buildCheckpoint, checkpoint);
  first.inputHash = packetHash(buildPacket(s, first));
  const forced = await readSources(s, ai, first, () => {});
  assert.equal(calls.shared, 1);
  const sent = sourceWritingPacket(buildPacket(s, first), forced).flatMap(
    (page) => page.chunks.flatMap((chunk) => chunk.facts),
  );
  const unrelated = sent.find(
    (fact) => fact.detail === "Safeguard improves shields.",
  )!;
  assert(unrelated);
  assert.equal(unrelated.relevance?.forced, true);
  assert.equal(unrelated.relevance?.automaticIncluded, false);
  assert(savedSourceCache(s, first).ledger);
  const reopened = x.reopen();
  assert.equal(
    reopened.inheritedEvidence(reopened.family(first.id))[0].alwaysInclude,
    true,
  );
  const newWorker = new Worker(reopened, {} as any);
  newWorker.setSharedSourceMode(first.id, url, "auto");
  const automatic = await readSources(
    reopened,
    ai,
    reopened.family(first.id),
    () => {},
  );
  assert(
    !JSON.stringify(
      sourceWritingPacket(
        buildPacket(reopened, reopened.family(first.id)),
        automatic,
      ),
    ).includes("Safeguard improves shields."),
  );
  assert.equal(calls.shared, 1);
  assert.equal(reopened.alwaysIncludedSources(first.id).length, 0);
});

test("item mode API persists pending inherited references, rejects categories/unrelated/active mutations, and survives generated reset", async (t) => {
  const { api } = await import("../src/server/http.ts");
  const { s, w, owner } = fixture(t),
    [first, second] = s.state.families;
  const pending = "https://borderlands.fandom.com/wiki/Uncaptured_Skill";
  owner.sourceUrls.push(pending);
  s.save();
  const server = api(s, w).listen(0, "127.0.0.1");
  await new Promise<void>((r) => server.once("listening", r));
  t.after(() => {
    server.closeAllConnections();
    server.close();
  });
  const base = `http://127.0.0.1:${(server.address() as any).port}`;
  const post = (id: string, body: any) =>
    fetch(`${base}/api/items/${id}/shared-source-mode`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  assert.equal(
    (await post(first.id, { url: pending, mode: "always" })).status,
    200,
  );
  const detail = await fetch(`${base}/api/items/${first.id}`).then((r) =>
    r.json(),
  );
  assert(
    detail.inheritedEvidence.some(
      (row: any) => row.url === pending && row.alwaysInclude && !row.captured,
    ),
  );
  assert.equal((await post(owner.id, { url, mode: "always" })).status, 400);
  assert.equal(
    (
      await post(first.id, {
        url: "https://borderlands.fandom.com/wiki/Unrelated",
        mode: "always",
      })
    ).status,
    404,
  );
  assert.equal(
    (await post(first.id, { url, mode: "unsupported" })).status,
    400,
  );
  w.busy = true;
  s.state.run.currentId = first.id;
  assert.equal((await post(first.id, { url, mode: "always" })).status, 409);
  assert.equal(s.sourceAlwaysIncluded(first.id, url), false);
  w.busy = false;
  const before = s.alwaysIncludedSources(first.id);
  const reset = await fetch(base + "/api/reset", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scope: "generated", confirmation: "RESET" }),
  });
  assert.equal(reset.status, 200);
  assert.deepEqual(s.alwaysIncludedSources(first.id), before);
  assert.equal(s.alwaysIncludedSources(second.id).length, 0);
});

test("forced input does not force unrelated numerical facts into final JSON; relevant stat validation stays strict", async () => {
  const { validateSourceUsage } =
    await import("../src/server/source-analysis.ts");
  const numerical = {
    id: "page:test:0:0",
    field: "stats",
    detail: "Other class's shield bonus.",
    quote: "Shield bonus 25%",
    stat: {
      name: "Shield bonus",
      minimum: 25,
      maximum: 25,
      unit: "%",
      level: null,
      notes: "Other character",
    },
    relevance: {
      forced: true,
      automaticIncluded: false,
      reason: "Another character",
    },
  };
  const ledger = [
    {
      sourceId: "page:test",
      url,
      hash: "hash",
      characters: 30,
      chunks: [
        {
          index: 0,
          characters: 30,
          reading: { ...emptySourceReading("Class mods"), facts: [numerical] },
          facts: [numerical],
        },
      ],
    },
  ] as any;
  const draft = {
    sourceUsage: [
      {
        factId: numerical.id,
        disposition: "irrelevant",
        fields: [],
        duplicateOf: null,
        reason: "Specific to a different character.",
      },
    ],
    entry: { stats: [] },
    claims: [],
    conflicts: [],
    partDefinitions: [],
  } as any;
  const packet = { evidence: [{ id: "page:test", kind: "page" }] } as any;
  assert.doesNotThrow(() => validateSourceUsage(draft, ledger, packet));
  // A broad automatic match is only a retrieval hint; synthesis can reject
  // this base-skill/other-character stat even when the source was forced.
  numerical.relevance.automaticIncluded = true;
  assert.doesNotThrow(() => validateSourceUsage(draft, ledger, packet));
  draft.sourceUsage[0].disposition = "used";
  draft.sourceUsage[0].fields = ["stats"];
  draft.claims = [
    { field: "stats", evidenceIds: ["page:test"], basis: "Explicit range" },
  ];
  assert.throws(
    () => validateSourceUsage(draft, ledger, packet),
    /omitted or changed/,
  );
  draft.sourceUsage[0].disposition = "irrelevant";
  draft.sourceUsage[0].fields = [];
  draft.sourceUsage[0].reason = "   ";
  assert.throws(
    () => validateSourceUsage(draft, ledger, packet),
    /exclusion reason/,
  );
  draft.sourceUsage[0].reason = "Base skill stat, not an artifact bonus.";
  delete (numerical as any).relevance;
  assert.throws(
    () => validateSourceUsage(draft, ledger, packet),
    /stat cannot be silently discarded/,
  );
});

test("Never skips shared content before AI, packet assembly and fetching while preserving the visible saved reference and sibling use", async (t) => {
  const x = fixture(t),
    { s, w, ai, calls } = x,
    [first, second] = s.state.families;
  const original = s.sources(first.id).find((page) => page.url === url)!;
  const rows = (s.db.prepare("SELECT COUNT(*) AS n FROM sources").get() as any)
    .n;
  first.sourceUrls.push(url + "#duplicate-direct-binding");
  w.setSharedSourceMode(first.id, url, "always");
  w.setSharedSourceMode(first.id, url + "#Notes", "never");
  assert.equal(s.sourceAlwaysIncluded(first.id, url), false);
  assert.equal(s.sourceNeverIncluded(first.id, url), true);
  const reference = s
    .inheritedEvidence(first)
    .find((page) => page.url === url)!;
  assert.equal(reference.inclusionMode, "never");
  assert.equal(reference.captured, true);
  assert.equal(reference.title, original.title);
  assert.equal(reference.textBytes, Buffer.byteLength(original.text, "utf8"));
  assert(!s.sources(first.id).some((page) => page.id === original.id));
  assert(
    !s
      .effectiveSourceUrls(first)
      .some((candidate) => candidate.startsWith(url)),
  );
  assert(s.sources(second.id).some((page) => page.id === original.id));
  assert(s.sources(x.owner.id).some((page) => page.id === original.id));
  first.inputHash = packetHash(buildPacket(s, first));
  const ledger = await readSources(s, ai, first, () => {});
  assert.equal(calls.shared, 0);
  assert.equal(calls.direct, 1);
  assert(!ledger.some((page) => page.sourceId === original.id));
  const packet = buildPacket(s, first);
  assert(!packet.evidence.some((page) => page.id === original.id));
  assert(
    !JSON.stringify(sourceWritingPacket(packet, ledger)).includes(
      "Safeguard improves shields.",
    ),
  );
  assert(savedSourceCache(s, first).ledger);
  let fetches = 0;
  w.research.fetchText = async () => {
    fetches++;
    throw new Error("Must not fetch this source");
  };
  await assert.rejects(w.research.fetchPage(first, url, true), /Never include/);
  assert.equal(fetches, 0);
  await readSources(s, ai, second, () => {});
  assert.equal(calls.shared, 1);
  assert.equal(
    (s.db.prepare("SELECT COUNT(*) AS n FROM sources").get() as any).n,
    rows,
  );
  const reopened = x.reopen();
  assert.equal(
    reopened
      .inheritedEvidence(reopened.family(first.id))
      .find((page) => page.url === url)!.inclusionMode,
    "never",
  );
  const again = new Worker(reopened, {} as any);
  again.setSharedSourceMode(first.id, url, "auto");
  await readSources(reopened, ai, reopened.family(first.id), () => {});
  assert.equal(calls.shared, 1);
  assert(reopened.sources(first.id).some((page) => page.id === original.id));
});

test("Never for a pending source is visible, persists through generated reset and does not alter either queue", async (t) => {
  const { api } = await import("../src/server/http.ts");
  const { s, w, owner } = fixture(t),
    [first, second] = s.state.families;
  const pending = "https://borderlands.fandom.com/wiki/New_Never_Fixture";
  owner.sourceUrls.push(pending);
  s.save();
  Object.assign(s.state.run, {
    status: "paused",
    queue: [second.id],
    index: 0,
    currentId: null,
  });
  s.state.buildCheckpoint = structuredClone(s.state.run);
  const before = structuredClone(s.state.run),
    checkpoint = structuredClone(s.state.buildCheckpoint);
  const server = api(s, w).listen(0, "127.0.0.1");
  await new Promise<void>((r) => server.once("listening", r));
  t.after(() => {
    server.closeAllConnections();
    server.close();
  });
  const base = `http://127.0.0.1:${(server.address() as any).port}`;
  const response = await fetch(
    `${base}/api/items/${first.id}/shared-source-mode`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: pending, mode: "never" }),
    },
  );
  assert.equal(response.status, 200);
  const reference = s
    .inheritedEvidence(first)
    .find((row) => row.url === pending)!;
  assert.equal(reference.inclusionMode, "never");
  assert.equal(reference.captured, false);
  assert.equal(reference.textBytes, null);
  assert.deepEqual(s.state.run, before);
  assert.deepEqual(s.state.buildCheckpoint, checkpoint);
  const reset = await fetch(base + "/api/reset", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scope: "generated", confirmation: "RESET" }),
  });
  assert.equal(reset.status, 200);
  assert.equal(s.sourceNeverIncluded(first.id, pending), true);
  assert.equal(s.sourceNeverIncluded(second.id, pending), false);
});

test("bulk modes apply to saved and uncaptured inherited sources only, preserving siblings, cache, output and paused work", async (t) => {
  const { api } = await import("../src/server/http.ts");
  const { s, w, owner, ai, calls } = fixture(t);
  const [first, second] = s.state.families;
  const pending = "https://borderlands.fandom.com/wiki/Uncaptured_Bulk_Fixture";
  owner.sourceUrls.push(pending);
  Object.assign(s.state.run, {
    status: "paused",
    queue: [second.id],
    index: 0,
    currentId: null,
  });
  s.state.buildCheckpoint = structuredClone(s.state.run);
  const run = structuredClone(s.state.run),
    checkpoint = structuredClone(s.state.buildCheckpoint);
  s.put(first.id, "output", { retained: "untouched prose" });
  const server = api(s, w).listen(0, "127.0.0.1");
  await new Promise<void>((r) => server.once("listening", r));
  t.after(() => {
    server.closeAllConnections();
    server.close();
  });
  const base = `http://127.0.0.1:${(server.address() as any).port}`;
  const post = (id: string, mode: string, extra = {}) =>
    fetch(`${base}/api/items/${id}/shared-source-modes`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode, ...extra }),
    });
  assert.equal((await post(first.id, "wrong")).status, 400);
  assert.equal((await post(first.id, "never", { url })).status, 400);
  assert.equal((await post(owner.id, "never")).status, 400);
  w.busy = true;
  s.state.run.currentId = first.id;
  assert.equal((await post(first.id, "never")).status, 409);
  w.busy = false;
  s.state.run.currentId = null;
  const response = await post(first.id, "never");
  assert.equal(response.status, 200);
  assert.equal((await response.json()).changed, 2);
  assert(s.inheritedEvidence(first).every((r) => r.inclusionMode === "never"));
  assert(s.inheritedEvidence(second).every((r) => r.inclusionMode === "auto"));
  assert.equal((await (await post(first.id, "never")).json()).changed, 0);
  await readSources(s, ai, first, () => {}, "first-ever-build");
  assert.equal(calls.shared, 0); // No first-read indexing, including uncaptured Never references.
  assert(calls.prompts.every((prompt) => !prompt.includes(sharedText)));
  await readSources(s, ai, second, () => {}, "second-build");
  assert.equal(calls.shared, 1); // First permitted consumer pays for the shared index.
  await post(first.id, "always");
  assert(s.inheritedEvidence(first).every((r) => r.inclusionMode === "always"));
  await readSources(s, ai, first, () => {}, "third-build");
  assert.equal(calls.shared, 1); // Shared analysis is reused once permitted.
  await post(first.id, "auto");
  assert(s.inheritedEvidence(first).every((r) => r.inclusionMode === "auto"));
  assert.deepEqual(s.get(first.id, "output"), { retained: "untouched prose" });
  assert.deepEqual(s.state.run, run);
  assert.deepEqual(s.state.buildCheckpoint, checkpoint);
  assert.equal(
    s.sourceInclusionMode(first.id, s.rawSources(first.id)[0].url),
    "auto",
  );
});

test("source-reader telemetry describes only actual allowed payloads before dispatch, including first-time indexes and cache reuse", async (t) => {
  const x = fixture(t),
    { s, w, ai } = x;
  const f = s.state.families[0];
  const seen: any[] = [];
  const originalRun = ai.run;
  ai.run = async (...args: any[]) => {
    seen.push({ label: args[0], prompt: args[1], input: args[6] });
    return originalRun(...args);
  };
  w.setSharedSourceMode(f.id, url, "always");
  const secondUrl = "https://borderlands.fandom.com/wiki/Shared_Second";
  w.research.save(x.owner, secondUrl, sharedHtml, true);
  const blocked = "https://borderlands.fandom.com/wiki/Shared_Blocked";
  w.research.save(x.owner, blocked, sharedHtml, true);
  w.setSharedSourceMode(f.id, blocked, "never");
  await readSources(s, ai, f, () => {}, "first-run");
  assert.equal(seen.filter((e) => e.input.phase === "index").length, 2);
  assert(seen.every((e) => e.input.sources.length === 1));
  assert(seen.every((e) => e.input.sources[0].url !== blocked));
  for (const event of seen)
    assert(event.prompt.includes(event.input.sources[0].url));
  seen.length = 0;
  await readSources(s, ai, f, () => {}, "fresh-two");
  assert.equal(seen.filter((e) => e.input.phase === "index").length, 0);
  assert(
    s.state.evidenceStats?.events.some((e) => e.kind === "analysis-cache"),
  );
});
