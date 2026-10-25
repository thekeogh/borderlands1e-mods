import { test } from "node:test";
import assert from "node:assert/strict";
import { rewriteCopiedProse } from "../src/server/prose-repair.ts";
import type { AI } from "../src/server/worker.ts";
import type { Draft } from "../src/shared/models.ts";
test("targeted prose repair changes only the copied passage, preserving all stats and source accounting", async () => {
  const copied =
    "A twelve word sequence from a source needs changing without altering any factual information.";
  const draft = {
    entry: {
      name: "Fixture",
      summary: "A different summary.",
      description: [copied],
      details: [],
      variants: [],
      parts: [],
      specialEffects: [],
      notes: [],
      stats: [{ name: "Damage", minimum: 80, maximum: 1423, notes: "" }],
      levels: { notes: "" },
      sources: [],
    },
    partDefinitions: [],
    claims: [{ field: "description", evidenceIds: ["wiki"] }],
    sourceUsage: [{ factId: "wiki:0:0", disposition: "used" }],
  } as unknown as Draft;
  const before = structuredClone(draft);
  const ai: AI = {
    status: async () => ({}),
    run: async (_label, prompt, schema) => {
      assert.ok(prompt.includes(copied));
      return schema.parse({
        text: "A freshly written explanation conveys the same factual meaning.",
      });
    },
  };
  assert.equal(
    await rewriteCopiedProse(
      draft,
      "Public prose repeats a substantial source passage verbatim (a twelve word sequence from a source needs changing without altering any). Rewrite it.",
      ai,
      "",
      () => {},
    ),
    true,
  );
  assert.notEqual(draft.entry.description[0], copied);
  assert.deepEqual(draft.entry.stats, before.entry.stats);
  assert.deepEqual(draft.sourceUsage, before.sourceUsage);
  assert.deepEqual(draft.claims, before.claims);
  assert.equal(
    await rewriteCopiedProse(draft, "Other validation error", ai, "", () => {}),
    false,
  );
});
