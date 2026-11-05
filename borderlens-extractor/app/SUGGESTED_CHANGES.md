# Suggested Zod Schema Changes

## Shared item data

### Required character level

The character level required to use the item. Keep this separate from item level, artifact effect rank, and the level of the mission that awards it. For example, the Wiki identifies effect-rank 6 artifacts with a character-level requirement of 44.

Use one number for a fixed requirement and two for an evidenced minimum–maximum range. A requirement documented for one artifact rank or example roll does not establish the range for the entire item family. Rank-specific requirements should use this same schema inside the relevant rank record.

[Artifact — Application and comparison chart](https://borderlands.fandom.com/wiki/Artifact#Application)

> **Shared:** weapons, shields, grenade mods, class mods, artifacts, and other items with a character-level requirement. Omit the parent field when the requirement is unknown or not applicable; do not invent a value.

```typescript
z.union([
  z.tuple([z.int().nonnegative()]),
  z.tuple([z.int().nonnegative(), z.int().nonnegative()]),
])
  .refine(
    (range) => range.length === 1 || range[0] < range[1],
    { message: "Use [n] for a fixed requirement or [min, max] with min < max." },
  )
  .describe("Required character level to use the item, recorded as [n] for a fixed requirement or [min, max] for an evidenced range, lowest first. Use whole numbers. Record 0 only when the source explicitly gives a zero-level requirement; do not use it to mean unknown. Do not substitute item level, artifact effect rank, mission level, or the player's current level. Do not infer a family-wide range from one example or a maximum-only statement. When this value belongs to a particular rank or variant, it applies only to that parent record. Omit the parent field when reliable requirement data is unavailable.");
```

```json
[44]
```

### Acquisition method

How the player obtains an item from one particular source. Omega, for example, can be looted from enemies and chests. Both use the drop method; their source types, names, locations, and chances are separate fields.

This describes one acquisition route, not an item-wide restriction. An item can have several acquisition records with different methods.

[Omega — Drop Rates and All Sources](https://www.lootlemon.com/shield/omega-bl1)

> **Shared:** every item type. Use this schema on each acquisition record. It is separate from the existing `sources` object containing Wiki/Lootlemon reference links.

```typescript
z.enum([
  "drop",
  "mission-reward",
  "purchase",
  "pickup",
  "starting-gear",
  "redemption",
  "other",
]).describe("How the player obtains the item from this acquisition source. Use drop for enemy loot or randomly generated container loot, including chest loot; dedicated and world drops both use drop, with their source or pool identified separately. Use mission-reward when completing or turning in a mission grants the item directly; killing a mission enemy and looting its weapon is still drop. Use purchase for buying from a vendor or shop, pickup for a deliberately placed item collected from the world, starting-gear for equipment granted when creating a character, and redemption for a code or promotional claim. Use other only for an evidenced method outside these categories, with its explanation in the acquisition record. Do not use other to mean unknown. Choose one method for this record and create separate acquisition records for different routes. Do not put an enemy, location, loot-pool name, drop chance, Wiki URL, or Lootlemon URL here.");
```

```json
"drop"
```
