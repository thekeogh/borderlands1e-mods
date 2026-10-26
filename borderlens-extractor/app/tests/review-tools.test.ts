import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { Store } from "../src/server/store.ts";
import { Worker } from "../src/server/worker.ts";
import { api } from "../src/server/http.ts";
import { findDuplicates } from "../src/server/duplicates.ts";
import { applyDiscoveryClassification } from "../src/server/discovery-classification.ts";
import { SourceMatches, type Family } from "../src/shared/models.ts";
import { catalogueGroup } from "../src/shared/taxonomy.ts";
const root = "gd_weap_smg.Title.Title_Unique_CycloneFixture";
const url = "https://www.lootlemon.com/weapon/cyclone-fixture-bl1";
const quote =
  "Cyclone Fixture is an obtainable submachine gun in Borderlands 1.";
function fixture(t: any) {
  const dir = mkdtempSync(path.join(tmpdir(), "review-tools-"));
  let s = new Store(dir);
  const family = (
    id: string,
    name: string,
    subtype = "Other weapons",
  ): Family => ({
    id,
    name,
    category: "Weapons",
    subtype,
    aliases: [],
    roots: [root],
    status: "queued",
    stage: "evidence",
    notes: "",
    sourceUrls: [],
    history: [],
    inputHash: "",
    issue: null,
    gameOnly: false,
    manualOutput: false,
    updatedAt: new Date().toISOString(),
    revision: 0,
  });
  s.state.families = [
    family("review", "Cyclone Fixture"),
    family("proper", "Cyclone Fixture", "SMGs"),
    family("other", "A Different Family", "Shotguns"),
  ];
  s.state.families[2].roots = ["gd_weap_shotgun.Title.Other"];
  s.records.set(root.toLowerCase(), {
    id: "raw",
    record_type: "object",
    path: root,
    class: "WillowGame.WeaponNamePartDefinition",
    properties: { PartName: "Cyclone Fixture" },
  });
  s.save();
  t.after(() => {
    s.close();
    rmSync(dir, { recursive: true, force: true });
  });
  const w = new Worker(s, {} as any);
  return {
    get s() {
      return s;
    },
    w,
    reopen() {
      s.close();
      s = new Store(dir);
      return s;
    },
  };
}
function discovery(overrides: any = {}) {
  return SourceMatches.parse({
    matches: [
      {
        url,
        title: "Cyclone Fixture • BL1 SMG",
        gameEvidence: "Borderlands 1 retail item page",
        reason: "Verified item identity/type",
      },
    ],
    notFoundReason: null,
    classification: {
      weaponType: "SMGs",
      identityVerified: true,
      availability: "obtainable",
      identityPaths: [root],
      reason:
        "Native SMG unique-title identity and inspected BL1 quotation establish this released family.",
      evidence: [{ url, title: "Cyclone Fixture • BL1 SMG", quote }],
      conflicts: [],
      ...overrides,
    },
  });
}
test("duplicate lookup returns explained properly grouped possibilities without changing either item or evidence", (t) => {
  const { s } = fixture(t),
    review = s.family("review"),
    proper = s.family("proper"),
    other = s.family("other");
  s.put(review.id, "output", { keep: "review" });
  s.put(proper.id, "output", { keep: "proper" });
  const before = JSON.stringify(s.state),
    rows = s.db.prepare("select count(*) as n from artifacts").get()!.n;
  const result = findDuplicates(s, review.id);
  assert.equal(result.matches[0].id, proper.id);
  assert(
    result.matches[0].reasons.some((reason) =>
      reason.includes("Same display name"),
    ),
  );
  assert(
    result.matches[0].reasons.some((reason) => reason.includes("extracted")),
  );
  assert(!result.matches.some((match) => match.id === other.id));
  assert.equal(JSON.stringify(s.state), before);
  assert.equal(
    s.db.prepare("select count(*) as n from artifacts").get()!.n,
    rows,
  );
  assert.throws(() => findDuplicates(s, proper.id), /Needs review/);
});
test("aliases, title references and conservative extended names match; common reference graphs do not create broad duplicates", (t) => {
  const { s } = fixture(t),
    review = s.family("review"),
    proper = s.family("proper"),
    other = s.family("other");
  proper.name = "Retail Cyclone";
  proper.aliases = [review.name];
  proper.roots = ["gd_weap_smg.Title.RetailCyclone"];
  assert(
    findDuplicates(s, review.id).matches.some(
      (match) =>
        match.id === proper.id &&
        match.reasons.some((reason) => reason.includes("alias")),
    ),
  );
  proper.aliases = [];
  proper.name = "Amplified Cyclone Fixture";
  assert(
    findDuplicates(s, review.id).matches.some(
      (match) =>
        match.id === proper.id &&
        match.reasons.some((reason) => reason.includes("additional words")),
    ),
  );
  const shared = "gd_manufacturers.Manufacturers.Maliwan";
  s.records.set(root.toLowerCase(), {
    id: "raw",
    record_type: "object",
    path: root,
    class: "WillowGame.WeaponNamePartDefinition",
    properties: { Manufacturer: { $ref: shared } },
  });
  s.records.set(other.roots[0].toLowerCase(), {
    id: "other",
    record_type: "object",
    path: other.roots[0],
    class: "WillowGame.WeaponNamePartDefinition",
    properties: { Manufacturer: { $ref: shared } },
  });
  s.records.set(shared.toLowerCase(), {
    id: "manu",
    record_type: "object",
    path: shared,
    class: "Engine.ManufacturerDefinition",
    properties: {},
  });
  assert(
    !findDuplicates(s, review.id).matches.some(
      (match) => match.id === other.id,
    ),
  );
  proper.status = "excluded";
  assert.equal(findDuplicates(s, review.id).matches.length, 0);
});
test("review removal API is reversible and cannot remove an already-classified match or an item classified after lookup", async (t) => {
  const { s, w } = fixture(t),
    review = s.family("review"),
    proper = s.family("proper");
  s.put(proper.id, "output", { keep: true });
  proper.sourceUrls = [url];
  const server = api(s, w).listen(0, "127.0.0.1");
  await new Promise<void>((r) => server.once("listening", r));
  t.after(() => {
    server.closeAllConnections();
    server.close();
  });
  const base = `http://127.0.0.1:${(server.address() as any).port}`;
  const before = JSON.stringify(proper);
  const get = await fetch(`${base}/api/items/${review.id}/duplicates`);
  assert.equal(get.status, 200);
  assert.equal(
    (
      await fetch(`${base}/api/items/${proper.id}/duplicates/remove`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      })
    ).status,
    409,
  );
  assert.equal(
    (
      await fetch(`${base}/api/items/${review.id}/duplicates/remove`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      })
    ).status,
    200,
  );
  assert.equal(review.status, "excluded");
  assert.equal(JSON.stringify(proper), before);
  assert.deepEqual(s.get(proper.id, "output"), { keep: true });
  await w.action(review.id, "restore", {});
  assert.notEqual(review.status, "excluded");
  applyDiscoveryClassification(s, review, discovery());
  assert.equal(
    (
      await fetch(`${base}/api/items/${review.id}/duplicates/remove`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      })
    ).status,
    409,
  );
  assert.notEqual(review.status, "excluded");
});
test("one URL-discovery call can move a verified family, preserve raw/output/queue data and inherit its new group's sources without fetching", async (t) => {
  const { s, w } = fixture(t),
    f = s.family("review"),
    rawSubtype = f.subtype,
    roots = [...f.roots];
  const shared = s.ensureScope({ category: "Weapons", group: "SMGs" });
  shared.sourceUrls = ["https://borderlands.fandom.com/wiki/Submachine_Gun"];
  s.put(f.id, "output", { retained: true });
  s.state.run.queue = [f.id, "proper"];
  const queue = [...s.state.run.queue];
  let calls = 0;
  w.ai = {
    run: async (label: string, _prompt: string, schema: any) => {
      calls++;
      assert(label.startsWith("Find missing sources"));
      return schema.parse(discovery());
    },
  } as any;
  w.research.fetchPage = async () => {
    throw Error("URL-only must not fetch articles");
  };
  await w.discoverSourceUrls(f, true);
  assert.equal(calls, 1);
  assert.equal(catalogueGroup(f), "SMGs");
  assert.equal(f.classification!.verification, "discovery");
  assert.equal(f.subtype, rawSubtype);
  assert.deepEqual(f.roots, roots);
  assert.deepEqual(s.get(f.id, "output"), { retained: true });
  assert.equal(f.revision, 0);
  assert.deepEqual(s.state.run.queue, queue);
  assert.equal(s.rawSources(f.id).length, 0);
  assert(
    s
      .inheritedEvidence(f)
      .some((row) => row.parents.some((parent) => parent.id === shared.id)),
  );
});
test("discovery leaves cut, prototype, unknown, shared-modifier, wrong-game and weak identity proposals in Needs review", (t) => {
  for (const change of [
    { availability: "cut" },
    { identityVerified: false },
    { identityPaths: ["not-a-captured-path"] },
    { evidence: [] },
    { conflicts: ["Conflicting item identities"] },
    {
      evidence: [
        {
          url,
          title: "Cyclone Fixture",
          quote: "It is a powerful weapon in Borderlands.",
        },
      ],
    },
  ]) {
    const { s } = fixture(t),
      f = s.family("review");
    assert.equal(applyDiscoveryClassification(s, f, discovery(change)), false);
    assert.equal(catalogueGroup(f), "Needs review");
  }
  const { s } = fixture(t),
    f = s.family("review");
  f.roots = ["gd_weap_smg.Title.Prototype_CycloneFixture"];
  assert.equal(
    applyDiscoveryClassification(
      s,
      f,
      discovery({ identityPaths: [f.roots[0]] }),
    ),
    false,
  );
  f.roots = ["gd_weap_names_shared.Title.CycloneFixture"];
  assert.equal(
    applyDiscoveryClassification(
      s,
      f,
      discovery({ identityPaths: [f.roots[0]] }),
    ),
    false,
  );
  f.roots = [root];
  const wrong = discovery();
  wrong.matches[0].url = "https://www.lootlemon.com/weapon/cyclone-fixture-bl2";
  wrong.classification!.evidence[0].url = wrong.matches[0].url;
  assert.equal(applyDiscoveryClassification(s, f, wrong), false);
});
test("stored exclusions and real cached quotations guard discovery decisions; manual overrides win", (t) => {
  const { s, w } = fixture(t),
    f = s.family("review");
  w.research.save(
    f,
    url,
    "<h1>Cyclone Fixture</h1><p>This original saved page does not establish the proposed submachine gun identity or availability.</p>",
    true,
  );
  assert.equal(applyDiscoveryClassification(s, f, discovery()), false);
  const page = w.research.save(
    f,
    url,
    `<h1>Cyclone Fixture</h1><p>${quote}</p>`,
    true,
  );
  s.put(f.id, "sourceExclusions", [
    {
      sourceId: page.id,
      url,
      title: page.title,
      excludedAt: new Date().toISOString(),
    },
  ]);
  assert.equal(applyDiscoveryClassification(s, f, discovery()), false);
  s.put(f.id, "sourceExclusions", []);
  s.classifications.set(f.id, "manual", {
    name: f.name,
    weaponType: "Shotguns",
    reason: "Manual choice",
    verifiedAt: new Date().toISOString(),
    evidence: [],
  });
  s.save();
  assert.equal(applyDiscoveryClassification(s, f, discovery()), false);
  assert.equal(catalogueGroup(f), "Shotguns");
});
test("Build verifies discovery moves from saved pages, upgrades successful proof and rolls an unsupported proposal back to Needs review", async (t) => {
  for (const valid of [true, false]) {
    const x = fixture(t),
      { s, w } = x,
      f = s.family("review");
    assert(applyDiscoveryClassification(s, f, discovery()));
    const page = w.research.save(
      f,
      url,
      `<h1>Cyclone Fixture</h1><p>${quote}</p>`,
      true,
    );
    let calls = 0;
    w.ai = {
      run: async (label: string, _prompt: string, schema: any) => {
        calls++;
        assert(label.startsWith("Classify"));
        return schema.parse({
          weaponType: valid ? "SMGs" : null,
          identityVerified: valid,
          availability: valid ? "obtainable" : "unknown",
          reason: valid
            ? "Saved type and identity confirmed"
            : "Captured sources do not verify this extracted definition.",
          evidence: [{ id: page.id, quote }],
          conflicts: [],
        });
      },
    } as any;
    if (valid) {
      await w.classify(f);
      assert.equal(f.classification!.verification, "saved_sources");
      const reopened = x.reopen();
      assert.equal(
        reopened.family(f.id).classification!.verification,
        "saved_sources",
      );
    } else {
      await assert.rejects(w.classify(f), /classification needs review/);
      assert.equal(catalogueGroup(f), "Needs review");
    }
    assert.equal(calls, 1);
  }
});
