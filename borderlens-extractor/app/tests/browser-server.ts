// Isolated browser-test server. Fake drafting is never part of the application.
import express from "express";
import path from "node:path";
import { Store } from "../src/server/store.ts";
import { Worker, type AI } from "../src/server/worker.ts";
import { api } from "../src/server/http.ts";
import { buildPacket } from "../src/server/evidence.ts";
const s = new Store(process.env.BORDERLENS_DATA_DIR!);
s.state.settings.research = false;
const ai: AI = {
  status: async () => ({
    available: true,
    chatgpt: true,
    version: "browser fixture",
    message: "Test fixture only",
  }),
  run: async (_label, _prompt, schema) => {
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
        schemaVersion: "2",
        compilerVersion: "0.2.0",
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
        weaponType: f.subtype,
        summary:
          "A browser test description backed by captured family definitions.",
        manufacturers: [],
        rarities: [],
        elements: [],
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
