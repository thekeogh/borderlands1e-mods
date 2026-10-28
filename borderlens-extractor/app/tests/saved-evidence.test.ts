import { interpretationText } from "../src/server/deterministic-source.ts";
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { Store } from "../src/server/store.ts";
import { Worker } from "../src/server/worker.ts";
import { buildPacket, packetHash } from "../src/server/evidence.ts";
import { readSources } from "../src/server/source-analysis.ts";
import { savedSourceCache } from "../src/server/source-cache.ts";
import { sharedChunkReading } from "../src/server/shared-source-index.ts";
import {
  applySavedEvidence,
  evidenceLibrary,
  followupInputKey,
  MAX_FOLLOWUP_MATCHES,
  MAX_FOLLOWUP_QUOTE,
  searchSavedEvidence,
  recordBlockedEvidenceNotice,
} from "../src/server/saved-evidence.ts";
import {
  COMPILER_VERSION,
  CATALOGUE_SCHEMA_VERSION,
} from "../src/shared/versions.ts";
import type { Draft, Family } from "../src/shared/models.ts";
import { emptySourceReading } from "./source-fixture.ts";
const url = "https://borderlands.fandom.com/wiki/Context_SMG_Mechanics";
const quote =
  "The hidden amplifier changes ignition chance under sustained shooting. Its effect has a fixed duration of four seconds.";
const request = {
  topic: "Amplifier ignition duration",
  terms: ["amplifier", "ignition"],
  reason:
    "Need the duration of the amplifier interaction to explain its effect accurately.",
};
function fixture(
  t: any,
  options: {
    request?: boolean;
    missing?: boolean;
    failExtra?: boolean;
    blocked?: boolean;
  } = { request: true },
) {
  const dir = mkdtempSync(path.join(tmpdir(), "saved-evidence-"));
  let s = new Store(dir);
  t.after(() => {
    s.close();
    rmSync(dir, { recursive: true, force: true });
  });
  const family = (id: string): Family => ({
    id,
    name: id,
    category: "Weapons",
    subtype: "SMGs",
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
  s.state.families = [family("Context SMG"), family("Other item")];
  s.save();
  const [f, other] = s.state.families,
    calls: { label: string; prompt: string }[] = [];
  let w: Worker;
  const draft = (supplemental: boolean): Draft => {
    const base = s.sources(f.id)[0];
    const ledger = w.compilationLedger(f),
      extras = ledger.flatMap((page) =>
        page.chunks.flatMap((chunk) =>
          chunk.facts
            .filter((fact) => fact.retrieval)
            .map((fact) => ({ fact, sourceId: page.sourceId })),
        ),
      );
    return {
      entry: {
        schemaVersion: CATALOGUE_SCHEMA_VERSION,
        compilerVersion: COMPILER_VERSION,
        id: f.id,
        name: f.name,
        dlc: null,
        category: "Weapons",
        weaponType: "SMGs",
        summary: "A conventional submachine gun built for steady bursts.",
        description: [
          "This family offers familiar submachine-gun handling with a conventional magazine.",
        ],
        details: supplemental
          ? [
              {
                heading: "Amplifier interaction",
                paragraphs: [
                  "During sustained shooting, the amplifier improves ignition for four seconds.",
                ],
              },
            ]
          : [],
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
      partDefinitions: [],
      claims: [
        {
          field: "summary",
          evidenceIds: [base.id],
          basis: "Saved family definition.",
        },
        {
          field: "description",
          evidenceIds: [base.id],
          basis: "Saved family definition.",
        },
        ...(supplemental
          ? extras.map((extra) => ({
              field: "details" as const,
              evidenceIds: [extra.sourceId],
              basis:
                "Original saved amplifier passage supports the described duration.",
            }))
          : []),
      ],
      sourceUsage: extras.map((extra) => ({
        factId: extra.fact.id,
        disposition: "used" as const,
        fields: ["details"],
        duplicateOf: null,
        reason: "Explains the requested amplifier interaction.",
      })),
      reviewReason: null,
      uncertainties: [],
      conflicts: [],
      requiresReview: false,
      ...(options.request
        ? {
            evidenceRequests: [
              options.missing
                ? { ...request, terms: ["unobtainium", "quuxium"] }
                : request,
            ],
          }
        : {}),
    };
  };
  const ai = {
    run: async (label: string, prompt: string, schema: any) => {
      calls.push({ label, prompt });
      if (label.startsWith("Read source"))
        return schema.parse(emptySourceReading());
      if (label.includes("with saved context") && options.failExtra)
        throw new Error("Synthetic extra-pass timeout");
      const supplemental = prompt.includes('"retrieval":{"topic":');
      return schema.parse(draft(supplemental));
    },
  } as any;
  w = new Worker(s, ai);
  w.research.save(
    f,
    "https://www.lootlemon.com/weapon/context-smg-bl1",
    "<h1>Context SMG</h1><p>The Context SMG is a conventional submachine gun with a standard magazine and familiar burst firing.</p>",
    true,
  );
  const extra = w.research.save(
    other,
    url,
    `<h1>Context SMG mechanics</h1><p>${quote}</p>`,
    true,
  );
  if (options.blocked) {
    const owner = s.ensureScope({ category: "Everything" });
    owner.sourceUrls.push(url);
    w.setSharedSourceMode(f.id, url, "never");
    f.stage = "draft";
  }
  return {
    get s() {
      return s;
    },
    w,
    ai,
    f,
    other,
    extra,
    calls,
    reopen() {
      s.close();
      s = new Store(dir);
      return s;
    },
  };
}
test("writer requests saved context, gets one extra pass with grounded excerpts, and final validation accepts it without attaching sources", async (t) => {
  const { s, w, f, calls, extra } = fixture(t);
  const bound = [...f.sourceUrls];
  await w.step(f);
  assert.equal(f.stage, "validate");
  assert.equal(
    calls.filter((call) => call.label.startsWith("Build ")).length,
    2,
  );
  const report = s.get<any>(f.id, "evidenceFollowup");
  assert.equal(report.status, "supplied");
  assert.equal(report.roundUsed, true);
  assert.equal(report.ignoredRequests, 1);
  assert(report.matches.some((match: any) => match.sourceId === extra.id));
  assert(calls.at(-1)!.prompt.includes(quote));
  assert(
    calls.at(-1)!.prompt.includes("no further requests will be processed"),
  );
  assert.equal(s.sources(f.id).length, 1);
  assert.deepEqual(f.sourceUrls, bound);
  assert.equal(s.get<any>(f.id, "draft").evidenceRequests, undefined);
  await w.step(f);
  assert.equal(f.stage, "complete");
  assert(
    s
      .get<any>(f.id, "output")
      .details[0].paragraphs[0].includes("four seconds"),
  );
  assert(savedSourceCache(s, f).ledger);
  const before = calls.filter((call) => call.label.startsWith("Build ")).length;
  w.prepareRebuild(f, "saved");
  await w.step(f);
  assert.equal(
    calls.filter((call) => call.label.startsWith("Build ")).length,
    before + 1,
  );
  assert(calls.at(-1)!.prompt.includes(quote)); // restart/retry inputs reuse the same answer without another request round
});
test("no requests or no saved matches cost no extra writing pass and do not stall validation", async (t) => {
  for (const options of [
    { request: false },
    { request: true, missing: true },
  ]) {
    const { s, w, f, calls } = fixture(t, options);
    await w.step(f);
    assert.equal(
      calls.filter((call) => call.label.startsWith("Build ")).length,
      1,
    );
    assert.equal(
      s.get<any>(f.id, "evidenceFollowup").status,
      options.request ? "no_match" : "not_requested",
    );
    await w.step(f);
    assert.equal(f.stage, "complete");
  }
});
test("a failed extra writing pass keeps the original draft and canonical evidence; no missing retrieved usage is demanded", async (t) => {
  const { s, w, f, calls } = fixture(t, { request: true, failExtra: true });
  await w.step(f);
  assert.equal(
    calls.filter((call) => call.label.startsWith("Build ")).length,
    2,
  );
  assert.equal(s.get<any>(f.id, "evidenceFollowup").status, "writer_failed");
  assert.equal(w.compilationLedger(f).length, 1);
  assert.equal(s.get<any>(f.id, "packet").evidence.length, 1);
  await w.step(f);
  assert.equal(f.stage, "complete");
  assert.deepEqual(s.get<any>(f.id, "output").details, []);
  w.prepareRebuild(f, "saved");
  await w.step(f);
  assert.equal(
    calls.filter((call) => call.label.startsWith("Build ")).length,
    3,
  );
  assert.equal(s.get<any>(f.id, "evidenceFollowup").status, "supplied");
  await w.step(f);
  assert.equal(f.stage, "complete");
});
test("Never and item/ancestor removals cannot be requested back, including aliases and cross-catalogue cached pages", async (t) => {
  const { s, w, f, calls, extra } = fixture(t, {
    request: true,
    blocked: true,
  });
  assert(!evidenceLibrary(s, f).some((page) => page.id === extra.id));
  await w.step(f);
  assert.equal(
    calls.filter((call) => call.label.startsWith("Build ")).length,
    1,
  );
  assert(calls.every((call) => !call.prompt.includes(quote)));
  assert.equal(s.get<any>(f.id, "evidenceFollowup").status, "no_match");
  const report = searchSavedEvidence(s, f, [request], [], "test");
  assert.equal(report.matches.length, 0);
  w.setSharedSourceMode(f.id, url, "auto");
  const global = s.ensureScope({ category: "Everything" });
  s.put(global.id, "sourceExclusions", [
    {
      sourceId: extra.id,
      url: url + "#Notes",
      title: "removed",
      excludedAt: new Date().toISOString(),
    },
  ]);
  global.sourceUrls = [];
  assert.equal(
    searchSavedEvidence(s, f, [request], [], "test").matches.length,
    0,
  );
  s.put(global.id, "sourceExclusions", []);
  s.put(f.id, "sourceExclusions", [
    {
      sourceId: extra.id,
      url,
      title: "removed",
      excludedAt: new Date().toISOString(),
    },
  ]);
  assert.equal(
    searchSavedEvidence(s, f, [request], [], "test").matches.length,
    0,
  );
});
test("cached indexed facts can recover filtered Auto context with numerical values unchanged", async (t) => {
  const { s, w, f, other, extra } = fixture(t, { request: false });
  const body = quote + " Amplifier ignition chance is 30%.";
  const page = w.research.save(
    other,
    url,
    `<h1>Amplifier ignition</h1><p>${body}</p>`,
    true,
  );
  const text = interpretationText(page);
  await sharedChunkReading(
    s,
    {
      run: async (_label: string, _prompt: string, schema: any) =>
        schema.parse({
          ...emptySourceReading(),
          facts: [
            {
              field: "stats",
              detail: "Amplifier ignition chance is 30%.",
              quote: "Amplifier ignition chance is 30%.",
              stat: {
                name: "Ignition chance",
                minimum: 30,
                maximum: 30,
                unit: "%",
                level: null,
                notes: "Amplifier",
              },
              scope: {
                certain: true,
                categories: ["Weapons"],
                characters: [],
                elements: [],
                weaponTypes: [],
                items: ["Other item"],
                skills: [],
              },
            },
          ],
        }),
    } as any,
    page,
    text,
    () => {},
  );
  const report = searchSavedEvidence(s, f, [request], [], "test");
  assert.equal(report.matches[0].origin, "index");
  assert.equal(report.matches[0].fact.stat!.minimum, 30);
  const supplied = applySavedEvidence(s, f, buildPacket(s, f), [], report);
  assert.equal(supplied.ledger[0].chunks[0].facts[0].stat!.maximum, 30);
  assert.equal(
    s.sources(f.id).some((source) => source.id === page.id),
    false,
  );
});
test("local search reaches late saved text, is bounded, skips known other games, and never fetches missing evidence", async (t) => {
  const { s, w, f, other } = fixture(t, { request: false });
  w.research.save(
    other,
    url,
    `<h1>Context SMG mechanics</h1><p>${"Ordinary context. ".repeat(3000)}</p><p>${quote}</p>`,
    true,
  );
  w.research.save(
    other,
    "https://borderlands.fandom.com/wiki/Context_(Borderlands_2)",
    `<h1>Context (Borderlands 2)</h1><p>${quote}</p>`,
    true,
  );
  const report = searchSavedEvidence(
    s,
    f,
    [request, request, request],
    [],
    "test",
  );
  assert(
    report.matches.length > 0 && report.matches.length <= MAX_FOLLOWUP_MATCHES,
  );
  assert(
    report.matches.every(
      (match) =>
        match.fact.quote.length <= MAX_FOLLOWUP_QUOTE &&
        !match.url.includes("Borderlands_2"),
    ),
  );
  assert(
    report.matches.some((match) => match.fact.quote.includes("four seconds")),
  );
  const noMatch = searchSavedEvidence(
    s,
    f,
    [{ ...request, terms: ["notstoredanywhere"] }],
    [],
    "test",
  );
  assert.equal(noMatch.matches.length, 0);
});
test("retrieved snapshots survive restart, while recapture invalidates cached answers and cannot publish stale excerpts", async (t) => {
  const x = fixture(t);
  await x.w.step(x.f);
  const report = x.s.get<any>(x.f.id, "evidenceFollowup");
  const s = x.reopen(),
    w = new Worker(s, x.ai),
    f = s.family(x.f.id);
  assert.equal(f.stage, "validate");
  assert(w.compilationLedger(f).some((page) => page.url === url));
  const before = followupInputKey(
    s,
    f,
    buildPacket(s, f),
    s.get<any>(f.id, "sourceLedger") || [],
  );
  w.research.save(
    s.family(x.other.id),
    url,
    "<h1>Changed amplifier</h1><p>The saved amplifier entry has changed and no longer contains the previous quoted duration.</p>",
    true,
  );
  const after = followupInputKey(
    s,
    f,
    buildPacket(s, f),
    s.get<any>(f.id, "sourceLedger") || [],
  );
  assert.notEqual(before, after);
  assert.throws(
    () => applySavedEvidence(s, f, buildPacket(s, f), [], report),
    /changed/,
  );
  await assert.rejects(w.step(f), /changed/);
});

test("all model-facing request and source schemas require their properties for strict structured output", async () => {
  const { z } = await import("zod");
  const { WriterDraft, SourceMatches } =
    await import("../src/shared/models.ts");
  const { WriterSourceReading } =
    await import("../src/server/source-analysis.ts");
  const visit = (value: any) => {
    if (!value || typeof value !== "object") return;
    if (value.properties) {
      assert.deepEqual(
        new Set(value.required || []),
        new Set(Object.keys(value.properties)),
      );
      assert.equal(value.additionalProperties, false);
    }
    for (const child of Object.values(value))
      if (Array.isArray(child)) child.forEach(visit);
      else visit(child);
  };
  visit(z.toJSONSchema(WriterDraft));
  visit(z.toJSONSchema(SourceMatches));
  const { TypeSyncDecision, NameSyncResponse } =
    await import("../src/shared/identity-sync.ts");
  visit(z.toJSONSchema(TypeSyncDecision));
  visit(z.toJSONSchema(NameSyncResponse));
  assert.equal(z.toJSONSchema(NameSyncResponse).type, "object");
  visit(z.toJSONSchema(WriterSourceReading));
  const dir = mkdtempSync(path.join(tmpdir(), "strict-shared-")),
    s = new Store(dir);
  try {
    const source = {
      id: "fixture",
      url: "https://borderlands.fandom.com/wiki/Fixture",
      title: "Fixture",
      hash: "hash",
      text: "Original fixture content about a useful catalogue item and its mechanics.",
      familyId: "fixture",
      filename: "unused",
      fetchedAt: new Date().toISOString(),
      imported: true,
    };
    await sharedChunkReading(
      s,
      {
        run: async (_label: string, _prompt: string, schema: any) => {
          visit(z.toJSONSchema(schema));
          return schema.parse(emptySourceReading());
        },
      } as any,
      source,
      source.text,
      () => {},
    );
  } finally {
    s.close();
    rmSync(dir, { recursive: true, force: true });
  }
});

test("explicit game-only builds do not request additional article context", async (t) => {
  const { s, w, f, calls } = fixture(t);
  f.gameOnly = true;
  await w.step(f);
  assert.equal(
    calls.filter((call) => call.label.startsWith("Build ")).length,
    1,
  );
  assert(!calls.at(-1)!.prompt.includes(quote));
  assert.equal(s.get<any>(f.id, "evidenceFollowup").matches.length, 0);
});

test("blocked AI requests persist privately, survive restart, dismiss without changing sources or work, and reappear only for new requests", async (t) => {
  const x = fixture(t, { request: true, blocked: true });
  let { s } = x;
  const { w, f, calls, extra } = x;
  await w.step(f);
  const notice = s.get<any>(f.id, "evidenceRequestNotice");
  assert(notice?.id);
  assert.equal(notice.blocked[0].topic, request.topic);
  assert.equal(notice.blocked[0].url, extra.url);
  assert(!JSON.stringify(notice).includes(quote));
  assert(calls.every((call) => !call.prompt.includes(quote)));
  assert.equal(calls.filter((c) => c.label.startsWith("Build ")).length, 1);
  const report = s.get<any>(f.id, "evidenceFollowup");
  assert.equal(report.blocked.length, 1);
  s = x.reopen();
  assert.deepEqual(s.get(f.id, "evidenceRequestNotice"), notice);
  const { api } = await import("../src/server/http.ts");
  const server = api(s, new Worker(s, {} as any)).listen(0, "127.0.0.1");
  await new Promise<void>((r) => server.once("listening", r));
  t.after(() => {
    server.closeAllConnections();
    server.close();
  });
  const base = `http://127.0.0.1:${(server.address() as any).port}`;
  const post = (id: string) =>
    fetch(`${base}/api/items/${f.id}/evidence-request-notice/dismiss`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id }),
    });
  assert.equal((await post("stale-notice")).status, 409);
  const before = structuredClone(s.state);
  const draft = s.get(f.id, "draft");
  assert.equal((await post(notice.id)).status, 200);
  assert(s.get<any>(f.id, "evidenceRequestNotice").dismissedAt);
  assert.equal(s.sourceInclusionMode(f.id, url), "never");
  assert.deepEqual(s.state.run, before.run);
  assert.deepEqual(s.state.families, before.families);
  assert.deepEqual(s.get(f.id, "draft"), draft);
  const fetched = await fetch(`${base}/api/items/${f.id}`).then((r) =>
    r.json(),
  );
  assert(fetched.evidenceRequestNotice.dismissedAt);
  recordBlockedEvidenceNotice(s, s.family(f.id), report);
  assert(s.get<any>(f.id, "evidenceRequestNotice").dismissedAt);
  recordBlockedEvidenceNotice(s, s.family(f.id), {
    ...report,
    inputKey: "new-build-input",
  });
  assert(!s.get<any>(f.id, "evidenceRequestNotice").dismissedAt);
  assert.notEqual(s.get<any>(f.id, "evidenceRequestNotice").id, notice.id);
});

test("Never remains authoritative when its parent binding moves and blocked-only cached context triggers a notice without an extra AI pass", async (t) => {
  const { s, w, f, calls } = fixture(t, { request: true, blocked: true });
  const owner = s.ensureScope({ category: "Everything" });
  owner.sourceUrls = [];
  f.sourceUrls.push(url + "#alias");
  assert(s.sourceNeverIncluded(f.id, url));
  assert(!s.sources(f.id).some((p) => p.url === url));
  assert(!s.effectiveSourceUrls(f).some((u) => u.startsWith(url)));
  await w.step(f);
  assert(calls.every((c) => !c.prompt.includes(quote)));
  assert(s.get<any>(f.id, "evidenceRequestNotice"));
  assert.equal(calls.filter((c) => c.label.startsWith("Build ")).length, 1);
});
