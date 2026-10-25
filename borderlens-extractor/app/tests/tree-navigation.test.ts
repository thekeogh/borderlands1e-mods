import { test } from "node:test";
import assert from "node:assert/strict";
import {
  familyTreePath,
  revealTreePath,
  stepTree,
} from "../src/client/tree-navigation.ts";
import type { Family } from "../src/shared/models.ts";
const paths = [
  ["Artifacts", "Artifacts:Brick"],
  ["Artifacts", "Artifacts:Lilith"],
  ["Class mods", "Class mods:Roland"],
  ["Shields"],
];
test("collapse closes deepest visible groups first, then their parents", () => {
  const first = stepTree({}, paths, "collapse");
  assert.equal(first["Artifacts:Brick"], true);
  assert.equal(first["Artifacts:Lilith"], true);
  assert.equal(first["Class mods:Roland"], true);
  assert.ok(!first.Artifacts);
  assert.ok(!first.Shields);
  const second = stepTree(first, paths, "collapse");
  assert.ok(paths.flat().every((key) => second[key]));
  assert.deepEqual(stepTree(second, paths, "collapse"), second);
});
test("expand opens parents without exposing their children, then all child groups", () => {
  const closed = Object.fromEntries(paths.flat().map((key) => [key, true]));
  const first = stepTree(closed, paths, "expand");
  assert.equal(first.Artifacts, false);
  assert.equal(first.Shields, false);
  assert.equal(first["Artifacts:Brick"], true);
  const second = stepTree(first, paths, "expand");
  assert.ok(paths.flat().every((key) => !second[key]));
});
test("mixed expand preserves already visible open branches and unrelated saved groups", () => {
  const before = {
    Artifacts: true,
    "Artifacts:Brick": false,
    "Artifacts:Lilith": false,
    "Class mods": false,
    "Class mods:Roland": false,
    Unrelated: true,
  };
  const copy = structuredClone(before),
    next = stepTree(before, paths, "expand");
  assert.equal(next["Artifacts:Brick"], true);
  assert.equal(next["Class mods:Roland"], false);
  assert.equal(next.Unrelated, true);
  assert.deepEqual(before, copy);
});
test("revealing an item opens every ancestor and can repeat for the same selection", () => {
  const f = {
    category: "Artifacts",
    subtype: "Artifacts",
    character: "Roland",
  } as Family;
  const path = familyTreePath(f);
  assert.deepEqual(path, ["Artifacts", "Artifacts:Roland"]);
  assert.deepEqual(
    revealTreePath(
      { Artifacts: true, "Artifacts:Roland": true, Shields: true },
      path,
    ),
    { Artifacts: false, "Artifacts:Roland": false, Shields: true },
  );
  assert.deepEqual(
    familyTreePath({ category: "Shields", subtype: "Shields" } as Family),
    ["Shields"],
  );
});
