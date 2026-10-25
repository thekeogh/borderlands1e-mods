import { conditionKey, playerCondition } from "./acquisition.ts";
import { WebsiteEntry } from "./website.ts";
import { publicPassages, publicQualityIssue } from "./catalogue-policy.ts";
import { weaponTypes } from "./taxonomy.ts";
import { redundantStatNote } from "./public-cleanup.ts";
/** Entire self-contained consumer document, after parts/images/acquisition assembly. */
export function validateWebsiteDocument(value: unknown): WebsiteEntry {
  const entry = WebsiteEntry.parse(value);
  if (
    entry.category === "Weapons" &&
    entry.weaponType &&
    !weaponTypes.includes(entry.weaponType as any)
  )
    throw new Error("Final JSON has a noncanonical weapon type.");
  if (entry.category !== "Weapons" && entry.weaponType !== null)
    throw new Error("Final JSON equipment cannot have a weapon type.");
  const unique = (values: string[], label: string) => {
    if (
      new Set(values.map((v) => v.trim().toLowerCase())).size !== values.length
    )
      throw new Error("Final JSON repeats " + label + ".");
  };
  for (const key of ["manufacturers", "rarities", "elements"] as const)
    unique(entry[key], key);
  unique(
    entry.parts.map((part) => part.id),
    "a part ID",
  );
  unique(
    entry.stats.map((stat) =>
      JSON.stringify([
        stat.name.trim().toLowerCase(),
        stat.context?.trim().toLowerCase(),
        stat.level,
      ]),
    ),
    "a stat context",
  );
  const bounds = [entry.levels, ...entry.stats];
  if (
    bounds.some(
      (range) =>
        range.minimum !== null &&
        range.maximum !== null &&
        range.minimum > range.maximum,
    )
  )
    throw new Error("Final JSON contains reversed numeric bounds.");
  for (const stat of entry.stats) {
    if (redundantStatNote({ ...stat, notes: stat.notes || "" }))
      throw new Error("Final JSON stat notes repeat the structured value.");
    if (
      entry.stats.some(
        (other) =>
          other !== stat &&
          other.name.toLowerCase() === stat.name.toLowerCase() &&
          other.level === stat.level,
      ) &&
      !stat.context?.trim()
    )
      throw new Error(
        "Final JSON needs distinct contexts for repeated stat names.",
      );
  }
  const ratedSources = new Set<string>();
  for (const source of entry.sources) {
    const sourceKey = JSON.stringify([
      source.label.toLowerCase(),
      source.kind,
      source.location?.toLowerCase(),
      source.dlc?.toLowerCase(),
    ]);
    if (source.dropChances.length && ratedSources.has(sourceKey))
      throw new Error(
        "Final JSON repeats a rated acquisition source; group its conditional rates.",
      );
    if (source.dropChances.length) ratedSources.add(sourceKey);
    unique(source.conditions.map(conditionKey), "an acquisition condition");
    if (source.url && !/^https?:\/\//i.test(source.url))
      throw new Error("Final JSON acquisition URL must use HTTP or HTTPS.");
    if (source.url) new URL(source.url);
    const common = new Set(source.conditions.map(conditionKey));
    if (
      source.conditions.some(
        (c) =>
          playerCondition(c) &&
          source.dropChances.length &&
          source.dropChances.every(
            (rate) => rate.players === playerCondition(c),
          ),
      )
    )
      throw new Error(
        "Final JSON repeats structured player counts in source conditions.",
      );
    const scopes = new Set<string>();
    for (const rate of source.dropChances) {
      const scope = JSON.stringify([
        rate.players,
        rate.conditions.map(conditionKey).sort(),
      ]);
      if (scopes.has(scope))
        throw new Error(
          "Final JSON repeats or conflicts on a drop-rate scope.",
        );
      scopes.add(scope);
      unique(rate.conditions.map(conditionKey), "a drop condition");
      const players = [...source.conditions, ...rate.conditions]
        .map(playerCondition)
        .filter((p) => p !== null);
      if (players.some((p) => rate.players && p !== rate.players))
        throw new Error("Final JSON has contradictory player counts.");
      if (
        rate.players &&
        rate.conditions.some((c) => playerCondition(c) === rate.players)
      )
        throw new Error(
          "Final JSON repeats the structured player count in drop conditions.",
        );
      if (rate.conditions.some((c) => common.has(conditionKey(c))))
        throw new Error(
          "Final JSON repeats common acquisition conditions in a drop rate.",
        );
      if (
        rate.conditions.some((c) =>
          /\d[\d.]*\s*%\s*(?:to|[-–—])\s*\d[\d.]*\s*%/i.test(c),
        )
      )
        throw new Error(
          "A drop-rate range cannot be represented as a single percent; use supported conditional rates instead.",
        );
    }
    if (
      [
        ...source.conditions,
        ...source.dropChances.flatMap((rate) => rate.conditions),
      ].some((c) =>
        /^(?:original (?:borderlands|edition|game)|borderlands (?:original|2009))$/i.test(
          c.trim(),
        ),
      )
    )
      throw new Error(
        "Original-only drop conditions do not belong in the Enhanced catalogue.",
      );
  }
  for (const passage of publicPassages(entry)) {
    const issue = publicQualityIssue(passage);
    if (issue) throw new Error(issue);
  }
  const { schemaVersion, compilerVersion, revision, ...item } = entry;
  return { schemaVersion, compilerVersion, revision, ...item };
}
export function parseWebsiteJSON(json: string) {
  return validateWebsiteDocument(JSON.parse(json));
}
export function serializeWebsiteDocument(value: unknown) {
  const document = validateWebsiteDocument(value);
  const json = JSON.stringify(document, null, 2) + "\n";
  parseWebsiteJSON(json);
  return json;
}
