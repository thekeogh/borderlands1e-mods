import { emptySourceReading } from "./source-fixture.ts";
// Isolated browser-test server. Fake drafting is never part of the application.
import express from "express";
import { cpSync } from "node:fs";
import path from "node:path";
import { Store } from "../src/server/store.ts";
import { Worker, type AI } from "../src/server/worker.ts";
import { api } from "../src/server/http.ts";
import { buildPacket } from "../src/server/evidence.ts";
const imageRoot = path.join(process.env.BORDERLENS_DATA_DIR!, "image-library");
cpSync(path.resolve("img/borderlands"), imageRoot, { recursive: true });
const s = new Store(process.env.BORDERLENS_DATA_DIR!, imageRoot);
s.state.settings.research = false;
const ai: AI = {
  status: async () => ({
    available: true,
    chatgpt: true,
    version: "browser fixture",
    message: "Test fixture only",
  }),
  run: async (_label, _prompt, schema) => {
    if (_label.startsWith("Find missing sources"))
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
    if (_label.startsWith("Read source"))
      return schema.parse(
        emptySourceReading(s.family(s.state.run.currentId!).category),
      );
    await new Promise((r) => setTimeout(r, 1500));
    const f = s.family(s.state.run.currentId!),
      p = buildPacket(s, f);
    if (_label.startsWith("Classify")) {
      const page = s.sources(f.id)[0];
      return schema.parse({
        weaponType: "Combat rifles",
        identityVerified: true,
        availability: "obtainable",
        reason:
          "Synthetic browser test article identifies this fixture family.",
        evidence: [
          {
            id: page.id,
            quote: "Ajax's Spear is a combat rifle in Borderlands.",
          },
        ],
        conflicts: [],
      });
    }
    return schema.parse({
      entry: {
        schemaVersion: "5",
        compilerVersion: "0.7.0",
        description: [
          "An original fixture paragraph describing this item for players.",
        ],
        references: [],
        variants: [],
        parts: [],
        id: f.id,
        name: f.name,
        game: "borderlands-goty-enhanced",
        category: f.category,
        weaponType: f.category === "Weapons" ? f.subtype : null,
        summary:
          "A browser test description backed by captured family definitions.",
        manufacturers: [],
        rarities: [],
        elements: f.element ? [f.element] : [],
        redText: p.facts.redText,
        specialEffects: [],
        levels: { minimum: null, maximum: null, notes: "" },
        stats: [],
        sources: [],
        notes: [],
      },
      partDefinitions: [],
      claims: [
        "summary",
        "description",
        ...(p.facts.redText ? ["redText"] : []),
        ...(f.element ? ["elements"] : []),
      ].map((field) => ({
        field,
        evidenceIds: [p.evidence[0].id],
        basis: "Browser fixture only.",
      })),
      uncertainties: [],
      conflicts: [],
      requiresReview: false,
      reviewReason: null,
    });
  },
};
const w = new Worker(s, ai),
  app = api(s, w);
app.use(express.static(path.resolve("dist/client")));
const server = app.listen(4321, "127.0.0.1", () => console.log("READY"));
process.on("SIGTERM", () => {
  server.closeAllConnections();
  server.close(() => {
    s.close();
    process.exit(0);
  });
});
