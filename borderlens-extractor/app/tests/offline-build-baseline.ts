/** Isolated request-boundary benchmark; no provider/network calls or live project data. */
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { Store } from "../src/server/store.ts";
import { Worker } from "../src/server/worker.ts";
import { buildPacket } from "../src/server/evidence.ts";
import {
  COMPILER_VERSION,
  CATALOGUE_SCHEMA_VERSION,
} from "../src/shared/versions.ts";
import { emptySourceReading } from "./source-fixture.ts";
import type { Family } from "../src/shared/models.ts";
const root = mkdtempSync(path.join(tmpdir(), "offline-baseline-"));
const results: any[] = [];
try {
  for (const category of [
    "Weapons",
    "Shields",
    "Grenade mods",
    "Class mods",
    "Artifacts",
  ] as const) {
    const store = new Store(path.join(root, category));
    const f: Family = {
      id: "fixture",
      name: "Fixture equipment",
      category,
      subtype: category,
      roots: ["gd_fixture.Item.Definition"],
      aliases: [],
      sourceUrls: [],
      history: [],
      status: "queued",
      stage: "draft",
      revision: 0,
      notes: "",
      inputHash: "",
      issue: null,
      gameOnly: false,
      manualOutput: false,
      updatedAt: "",
    };
    store.state.families = [f];
    store.state.settings.research = false;
    store.records.set(f.roots[0].toLowerCase(), {
      id: "raw",
      path: f.roots[0],
      class: "WillowGame.ItemDefinition",
      record_type: "object",
      properties: {
        ItemName: f.name,
        UnrelatedGraphContext: Array.from({ length: 100 }, (_, i) => ({
          Index: i,
          SharedDefault: i,
          UnusedText: "Raw shared context does not establish item stats.",
        })),
      },
    });
    const requests: any[] = [];
    const ai: any = {
      run: async (label: string, prompt: string, schema: any) => {
        requests.push({
          label,
          characters: prompt.length,
          bytes: Buffer.byteLength(prompt),
        });
        if (label.startsWith("Read source"))
          return schema.parse(emptySourceReading(category));
        const current = store.family(store.state.run.currentId || f.id);
        const packet = buildPacket(store, current);
        return schema.parse({
          entry: {
            schemaVersion: CATALOGUE_SCHEMA_VERSION,
            compilerVersion: COMPILER_VERSION,
            id: current.id,
            name: current.name,
            category,
            weaponType: null,
            dlc: null,
            summary: "Original synthetic equipment summary for this benchmark.",
            description: [
              "Original fixture wording describes the equipment without borrowing the captured passage.",
            ],
            details: [],
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
          claims: ["summary", "description"].map((field) => ({
            field,
            evidenceIds: [packet.evidence[0].id],
            basis: "Captured identity.",
          })),
          sourceUsage: [],
          uncertainties: [],
          conflicts: [],
          requiresReview: false,
          reviewReason: null,
        });
      },
    };
    const w = new Worker(store, ai);
    w.addTextEvidence(f.id, {
      label: "Synthetic passage",
      text: "This is synthetic saved evidence used only to measure request payloads in isolation.",
    });
    f.stage = "draft";
    store.state.run.currentId = f.id;
    await w.step(f);
    const freshRequests = requests.splice(0);
    w.prepareRebuild(f, "saved");
    f.stage = "draft";
    await w.step(f);
    const cachedRequests = requests.splice(0);
    if(category==="Weapons")f.subtype="SMGs";
    const source = store.sources(f.id)[0];
    w.promoteSource(f.id, source.url);
    w.prepareRebuild(f, "saved");
    f.stage = "draft";
    await w.step(f);
    const sharedColdRequests = requests.splice(0);
    const second: Family = {
      ...structuredClone(f),
      id: "second",
      name: "Second fixture equipment",
      roots: ["gd_fixture.Item.SecondDefinition"],
      sourceUrls: [],
      history: [],
      stage: "draft",
      status: "queued",
      revision: 0,
      inputHash: "",
    };
    store.records.set(second.roots[0].toLowerCase(), {
      id: "second-raw",
      path: second.roots[0],
      class: "WillowGame.ItemDefinition",
      record_type: "object",
      properties: { ItemName: second.name },
    });
    store.state.families.push(second);
    store.state.run.currentId = second.id;
    await w.step(second);
    const sharedReuseRequests = requests.splice(0);
    results.push({
      category,
      requests: freshRequests,
      writer: freshRequests.filter((r) => r.label.startsWith("Build ")),
      cachedRequests,
      sharedColdRequests,
      sharedReuseRequests,
    });
    store.close();
  }
  const output = {
    compilerVersion: COMPILER_VERSION,
    method:
      "Actual prompts at Worker AI.run boundary on five isolated synthetic fixtures. Mock responses only; no token, cost or provider latency measurements. Source-reading fixture intentionally empty; raw graph size is synthetic, not a real-game average.",
    results,
  };
  writeFileSync(
    path.resolve("../temp/offline-build-baseline.json"),
    JSON.stringify(output, null, 2) + "\n",
  );
  console.log(JSON.stringify(output));
} finally {
  rmSync(root, { recursive: true, force: true });
}
