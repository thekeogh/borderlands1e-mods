import { test } from "node:test";
import assert from "node:assert/strict";
import { evidenceSizeTotals } from "../src/shared/evidence-size.ts";
import type { InheritedEvidence } from "../src/shared/research.ts";
const inherited = (
  url: string,
  inclusionMode: "always" | "auto" | "never",
  textBytes?: number,
): InheritedEvidence => ({
  url,
  inclusionMode,
  textBytes,
  title: url,
  captured: textBytes !== undefined,
  parents: [],
});
test("evidence totals separate definite and Auto text, omit Never, deduplicate and count uncaptured sizes", () => {
  const rows = [
    inherited("https://example.com/a", "always", 1000),
    inherited("https://example.com/b", "auto", 9000),
    inherited("https://example.com/c", "never", 99000),
    inherited("https://example.com/unknown", "always"),
    inherited("https://example.com/auto-missing", "auto"),
  ];
  const result = evidenceSizeTotals(
    [
      { url: "https://example.com/direct", text: "é😀" },
      { url: "https://example.com/direct?tracking=1", text: "duplicate" },
      { url: "https://example.com/a", text: "overlap" },
      { url: "https://example.com/c", text: "never overlap" },
    ],
    rows,
    [
      "https://example.com/direct",
      "https://example.com/new",
      "https://example.com/new#fragment",
      "https://example.com/c",
    ],
  );
  assert.deepEqual(result, {
    included: { bytes: 1006, count: 4, missing: 2 },
    auto: { bytes: 9000, count: 2, missing: 1 },
  });
});
test("empty evidence is zero and legacy Always include is respected", () => {
  assert.deepEqual(evidenceSizeTotals([], []), {
    included: { bytes: 0, count: 0, missing: 0 },
    auto: { bytes: 0, count: 0, missing: 0 },
  });
  const row = {
    ...inherited("https://example.com/legacy", "always", 0),
    inclusionMode: undefined,
    alwaysInclude: true,
  };
  assert.deepEqual(evidenceSizeTotals([], [row]).included, {
    bytes: 0,
    count: 1,
    missing: 0,
  });
});
