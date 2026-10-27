import { test } from "node:test";
import assert from "node:assert/strict";
import { storedTextBytes, sourceSize } from "../src/shared/source-size.ts";
test("stored document size measures UTF-8 bytes, including Unicode and line breaks, rather than JS character count", () => {
  for (const [text, bytes] of [
    ["ASCII", 5],
    ["é", 2],
    ["😀", 4],
    ["e\u0301", 3],
    ["\r\n", 2],
    ["", 0],
  ] as const) {
    assert.equal(storedTextBytes(text), bytes);
    assert.equal(storedTextBytes(text), Buffer.byteLength(text, "utf8"));
  }
});
test("source-size guides have explicit decimal byte boundaries and human readable units", () => {
  for (const [bytes, label] of [
    [0, "Small"],
    [7999, "Small"],
    [8000, "Medium"],
    [31999, "Medium"],
    [32000, "Large"],
    [95999, "Large"],
    [96000, "Very large"],
  ] as const)
    assert.equal(sourceSize(bytes).label, label);
  assert.equal(sourceSize(512).formatted, "512 B");
  assert.equal(sourceSize(1500).formatted, "1.5 KB");
  assert.equal(sourceSize(1250000).formatted, "1.3 MB");
  assert.match(sourceSize(96000).guidance, /manual excerpt/);
});
