import { test } from "node:test";
import assert from "node:assert/strict";
import {
  genericAdviceReason,
  publicPassages,
} from "../src/shared/catalogue-policy.ts";
test("shared farming and fast-travel boilerplate is excluded, while item mechanics and acquisition facts remain", () => {
  for (const text of [
    "Your last visited Fast Travel Station determines where you spawn; account for it when planning repeated farming runs.",
    "Combine nearby loot sources and time your routes. Shortcuts, movement speed and faster kills can increase the number of chances you get per session.",
    "Compare timed runs and reduce travel and combat time.",
    "Loot sources have a hidden Awesome Level that influences their chances of producing higher-rarity equipment.",
  ])
    assert.ok(genericAdviceReason(text), text);
  for (const text of [
    "Catalyst is a class mod that increases a skill bonus.",
    "Only drops from Crawmerax in the Secret Armory DLC.",
    "Incendiary splash ignites nearby enemies.",
    "Grants +12% movement speed while equipped.",
    "Fixed scope provides a +30% damage modifier.",
    "Available from the Fyrestone vendor after completing the mission.",
  ])
    assert.equal(genericAdviceReason(text), null, text);
});
test("scope checks cover nested notes, descriptions and mechanics without inspecting red text or bibliography", () => {
  const item = {
    description: ["Item identity"],
    details: [
      { heading: "Guide", paragraphs: ["Time your routes to farm faster."] },
    ],
    notes: [],
    redText: "Time your routes",
    references: [{ label: "Time your routes" }],
  };
  assert.ok(publicPassages(item).some((text) => genericAdviceReason(text)));
  assert.ok(
    !publicPassages({
      redText: "Time your routes",
      references: ["Time your routes"],
    }).length,
  );
});

test("raw FOV constants and unscoped damage benchmarks stay private; useful scope bonuses remain", async () => {
  const { sourceExclusionReason } =
    await import("../src/shared/catalogue-policy.ts");
  assert.match(sourceExclusionReason("Zoom End FOV: -350%")!, /Internal/);
  assert.match(
    sourceExclusionReason(
      "With a suitable build, deal 12,000 damage in one shot.",
    )!,
    /benchmark/,
  );
  assert.equal(
    sourceExclusionReason(
      "The scope adds +30% damage and +100% projectile speed.",
    ),
    null,
  );
});

test("class-mod cleanup labels card regeneration without changing per-second rates or numbers", async () => {
  const { cleanPublicEntry } = await import("../src/shared/public-cleanup.ts");
  const card = {
    name: "Ammo regeneration",
    context: "Team bonus",
    minimum: 2,
    maximum: 25,
    unit: "",
    level: null,
    notes: "",
  };
  const rate = {
    ...card,
    context: "Maximum team SMG rate",
    minimum: null,
    maximum: 7.5,
    unit: "/s",
  };
  const input = { category: "Class mods", stats: [card, rate] } as any;
  const output = cleanPublicEntry(input);
  assert.equal(output.stats[0].context, "Card bonus");
  assert.deepEqual({ ...output.stats[0], context: card.context }, card);
  assert.deepEqual(output.stats[1], rate);
  assert.equal(
    cleanPublicEntry({ ...input, category: "Weapons" }).stats[0].context,
    "Team bonus",
  );
});
