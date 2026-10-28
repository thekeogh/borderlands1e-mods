import { recordEvidenceEvent } from "../src/server/evidence-stats.ts";
import { emptySourceReading } from "./source-fixture.ts";
// Isolated browser-test server. Fake drafting is never part of the application.
import express from "express";
import { cpSync } from "node:fs";
import path from "node:path";
import { Store } from "../src/server/store.ts";
import { Worker, type AI } from "../src/server/worker.ts";
import { api } from "../src/server/http.ts";
import { buildPacket } from "../src/server/evidence.ts";
import { Research } from "../src/server/research.ts";
const nameQuote =
  "Eridian Rifle is an obtainable Eridian weapon in Borderlands.";
const nameProposal = (f: any, page: any) => ({
  name: "Eridian Rifle",
  identityVerified: true,
  availability: "obtainable",
  identityPaths: f.roots,
  reason: "Synthetic exact name and Eridian identity proof",
  conflicts: [],
  evidence: [{ id: page.id, quote: nameQuote }],
  corroboration: [{ kind: "weaponType", id: page.id, quote: nameQuote }],
});
const imageRoot = path.join(process.env.BORDERLENS_DATA_DIR!, "image-library");
cpSync(path.resolve("img/borderlands"), imageRoot, { recursive: true });
const s = new Store(process.env.BORDERLENS_DATA_DIR!, imageRoot);
s.state.settings.research = false;
let agentCallCount = 0;
const ai: AI = {
  status: async () => ({
    available: true,
    chatgpt: true,
    version: "browser fixture",
    message: "Test fixture only",
  }),
  run: async (_label, _prompt, schema, _model, _web, progress, input) => {
    agentCallCount++;
    const context = w.identitySync?.familyId || s.state.run.currentId;
    if (context)
      recordEvidenceEvent(
        s,
        s.family(context),
        input || { phase: "other", sources: [] },
        {
          kind: "submitted",
          label: _label,
          agent: "codex",
          promptCharacters: _prompt.length,
        },
      );
    if (_label.startsWith("Sync item")) {
      const f = s.family(w.identitySync!.familyId);
      progress("Reading saved identity proof…");
      await new Promise((r) => setTimeout(r, 600));
      if (_label.startsWith("Sync item name"))
        return schema.parse({
          decision: nameProposal(
            f,
            s.sources(f.id).find((p) => p.text.includes(nameQuote)),
          ),
        });
      const page = s
        .sources(f.id)
        .find((p) =>
          p.text.includes(
            "Ironclad is an obtainable Pangolin shield in Borderlands.",
          ),
        )!;
      return schema.parse({
        category: "Shields",
        weaponType: null,
        identityVerified: true,
        availability: "obtainable",
        confidence: "high",
        identityPaths: f.roots,
        reason: "Synthetic explicit shield identity proof",
        conflicts: [],
        evidence: [
          {
            id: page.id,
            quote: "Ironclad is an obtainable Pangolin shield in Borderlands.",
          },
        ],
      });
    }
    if (_label.startsWith("Find missing sources")) {
      const current = s.family(s.state.run.currentId!);
      if (current.id === "browser-review")
        return schema.parse({
          matches: [
            {
              url: "https://www.lootlemon.com/weapon/browser-cyclone-bl1",
              title: "Browser Cyclone • BL1 SMG",
              gameEvidence: "Borderlands 1",
              reason: "Synthetic retail identity fixture",
            },
          ],
          notFoundReason: null,
          classification: {
            weaponType: "SMGs",
            identityVerified: true,
            availability: "obtainable",
            identityPaths: current.roots,
            reason: "Synthetic exact obtainable identity fixture",
            evidence: [
              {
                url: "https://www.lootlemon.com/weapon/browser-cyclone-bl1",
                title: "Browser Cyclone • BL1 SMG",
                quote:
                  "Browser Cyclone is an obtainable submachine gun in Borderlands 1.",
              },
            ],
            conflicts: [],
          },
        });
      return schema.parse({
        matches: [
          ...s
            .inheritedEvidence(s.family(s.state.run.currentId!))
            .slice(0, 2)
            .map((row) => ({
              url: row.url,
              title: row.title,
              gameEvidence: "BL1 inherited fixture",
              reason: "Deliberate duplicate to verify filtering",
            })),
          {
            url: "https://borderlands.fandom.com/wiki/Fixture_article",
            title: "Fixture article",
            gameEvidence: "BL1 synthetic test",
            reason: "URL-only fixture",
          },
        ],
        notFoundReason: "No Lootlemon item page for this synthetic fixture",
      });
    }
    if (_label.startsWith("Read source"))
      return schema.parse(
        emptySourceReading(s.family(s.state.run.currentId!).category),
      );
    await new Promise((r) => setTimeout(r, 1500));
    const f = s.family(s.state.run.currentId!),
      p = buildPacket(s, f);
    const namePage = s
      .sources(f.id)
      .find((page) => page.text.includes(nameQuote));
    if (_label.startsWith("Verify item name"))
      return schema.parse(nameProposal(f, namePage));
    if (_label.startsWith("Classify")) {
      const page = namePage || s.sources(f.id)[0];
      return schema.parse({
        weaponType: namePage ? "Eridian weapons" : "Combat rifles",
        identityVerified: true,
        availability: "obtainable",
        reason:
          "Synthetic browser test article identifies this fixture family.",
        evidence: [
          {
            id: page.id,
            quote: namePage
              ? nameQuote
              : "Ajax's Spear is a combat rifle in Borderlands.",
          },
        ],
        conflicts: [],
      });
    }
    const outline = s.get<any>(f.id, "factualOutline");
    return schema.parse({
      nameDecision: f.notes.includes("browser-name-fixture")
        ? nameProposal(f, namePage)
        : null,
      entry: {
        schemaVersion: "7",
        compilerVersion: "0.15.1",
        description: [
          "An original fixture paragraph describing this item for players.",
        ],
        references: [],
        variants:
          outline?.slots.variants.map((slot: any) => ({
            id: slot.id,
            description:
              "A synthetic alternate configuration with documented differences.",
            differences: slot.distinctions,
          })) || [],
        parts:
          outline?.fixed.parts.map((part: any) => ({
            partId: part.partId,
            notes: "",
          })) || [],
        id: f.id,
        name: f.name,
        dlc: p.facts.dlc || null,
        category: f.category,
        weaponType:
          f.category === "Weapons"
            ? f.classification?.weaponType || f.subtype
            : null,
        summary:
          "A browser test description backed by captured family definitions.",
        manufacturers: [],
        rarities: [],
        elements: f.element ? [f.element] : [],
        redText: p.facts.redText,
        specialEffects: [],
        levels: { minimum: null, maximum: null, notes: "" },
        stats:
          outline?.slots.stats.map((slot: any) => ({
            id: slot.id,
            context: slot.context,
            notes: "",
          })) || [],
        sources:
          outline?.slots.sources.map((slot: any) => ({
            id: slot.id,
            notes: "Original synthetic acquisition wording.",
            conditions: slot.conditions,
            dropConditions: slot.dropConditions,
          })) || [],
        notes: [],
      },
      partDefinitions:
        outline?.parts.map((part: any) => ({
          id: part.id,
          name: "Defining " + part.slot,
          effects: [],
          notes: [],
        })) || [],
      evidenceRequests:
        f.notes.includes("browser-followup-fixture") &&
        !_prompt.includes('"retrieval":{"topic":')
          ? [
              {
                topic: "Original catalogue context",
                terms: ["original", "catalogue"],
                reason:
                  "Check whether more original catalogue context was saved.",
              },
            ]
          : [],
      sourceUsage: w.compilationLedger(f).flatMap((page) =>
        page.chunks.flatMap((chunk) =>
          chunk.facts
            .filter((fact) => fact.retrieval)
            .map((fact) => ({
              factId: fact.id,
              disposition: "irrelevant",
              fields: [],
              duplicateOf: null,
              reason:
                "Synthetic browser draft does not need this supplementary passage.",
            })),
        ),
      ),
      claims: [
        "summary",
        "description",
        ...(p.facts.redText ? ["redText"] : []),
        ...(p.facts.dlc ? ["dlc"] : []),
        ...(f.element ? ["elements"] : []),
      ].map((field) => ({
        field,
        evidenceIds: [p.evidence[0].id],
        basis: "Browser fixture only.",
      })),
      uncertainties: f.notes.includes("browser-followup-fixture")
        ? ["An optional acquisition name has alternate spellings."]
        : [],
      conflicts: [],
      requiresReview: f.notes.includes("browser-followup-fixture"),
      reviewReason: f.notes.includes("browser-followup-fixture")
        ? "Optional rank progression is not fully established."
        : null,
    });
  },
};
const w = new Worker(s, ai),
  app = api(s, w);
// Isolated fixture preparation; this route never exists in the workshop server.
app.post("/__test/review-tools", (_req, res) => {
  const base = s.state.families.find(
    (f) => f.name.toLowerCase() === "hellfire",
  )!;
  s.state.families.push({
    ...structuredClone(base),
    id: "browser-review",
    name: "Browser Cyclone",
    aliases: [],
    subtype: "Other weapons",
    classification: undefined,
    status: "queued",
    stage: "evidence",
    sourceUrls: [],
    history: [],
    issue: null,
    revision: 0,
  });
  base.name = "Browser Cyclone";
  base.aliases = [];
  s.save();
  res.json({ ok: true, properId: base.id });
});
app.post("/__test/name-tools", (_req, res) => {
  const f = s.state.families.find(
    (f) => f.name === "Rifle" && f.subtype === "Other weapons",
  )!;
  f.notes = "browser-name-fixture";
  f.gameOnly = false;
  new Research(s).save(
    f,
    "https://www.lootlemon.com/weapon/browser-eridian-rifle-bl1",
    `<main><h1>Eridian Rifle</h1><p>${nameQuote}</p></main>`,
    true,
  );
  s.save();
  res.json({ id: f.id });
});
app.post("/__test/sync-type-tools", (_req, res) => {
  const f = s.state.families.find((f) => f.name === "Ironclad")!;
  s.classifications.set(f.id, "research", null);
  s.classifications.set(f.id, "manual", null);
  f.category = "Other equipment";
  f.subtype = "Other equipment";
  delete f.rawCategory;
  delete f.rawSubtype;
  delete f.classification;
  const existing = s.get<any>(f.id, "output");
  if (existing)
    s.put(f.id, "output", {
      ...existing,
      category: "Other equipment",
      weaponType: null,
    });

  new Research(s).save(
    f,
    "https://www.lootlemon.com/shield/ironclad-bl1",
    "<main><h1>Ironclad • BL1 Shield</h1><p>Ironclad is an obtainable Pangolin shield in Borderlands.</p></main>",
    true,
  );
  s.save();
  res.json({
    id: f.id,
    hadOutput: Boolean(existing),
    description: existing?.description,
  });
});
app.post("/__test/sync-name-tools", (_req, res) => {
  const f = s.state.families.find((f) => f.name === "Eridian Rifle")!;
  s.names.clear();
  s.save();
  const entry = { ...s.get<any>(f.id, "output"), name: "Rifle" };
  s.put(f.id, "output", entry);
  s.put(f.id, "manualDraft", { entry });
  f.status = "done";
  f.stage = "complete";
  f.manualOutput = true;
  f.gameOnly = true;
  s.save();
  res.json({ id: f.id, description: entry.description });
});
app.get("/__test/ai-count", (_req, res) => res.json({ calls: agentCallCount }));
app.use(express.static(path.resolve("dist/client")));
const server = app.listen(4321, "127.0.0.1", () => console.log("READY"));
process.on("SIGTERM", () => {
  server.closeAllConnections();
  server.close(() => {
    s.close();
    process.exit(0);
  });
});
