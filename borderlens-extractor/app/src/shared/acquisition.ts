import type { PublicEntry } from "./models.ts";
import { AcquisitionSource } from "./website.ts";
import type { z } from "zod";
const conditionText = (text: string) =>
  text
    .trim()
    .toLowerCase()
    .replace(/[.;]+$/, "")
    .replace(/\s+/g, " ");
export function playerCondition(text: string): number | null {
  const words = text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
  if (/^(?:solo|single player(?: game)?)$/.test(words)) return 1;
  const match = words.match(/^(one|two|three|four|[1-4]) players?(?: game)?$/);
  return match
    ? { one: 1, two: 2, three: 3, four: 4 }[match[1]] || Number(match[1])
    : null;
}
export function conditionKey(text: string) {
  const players = playerCondition(text);
  if (players) return "players:" + players;
  const words = text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
  if (
    /^(?:enhanced(?: edition)?|goty enhanced|borderlands goty enhanced)$/.test(
      words,
    )
  )
    return "edition:enhanced";
  if (
    /^(?:original (?:borderlands|edition|game)|borderlands (?:original|2009))$/.test(
      words,
    )
  )
    return "edition:original";
  return conditionText(text);
}
const uniqueConditions = (values: string[]) => {
  const seen = new Set<string>();
  return values
    .map((text) => text.trim())
    .filter((text) => {
      const key = conditionKey(text);
      if (!text || seen.has(key)) return false;
      seen.add(key);
      return true;
    });
};
/** Group acquisition identities, retaining every condition-specific probability. */
export function acquisitionSources(sources: PublicEntry["sources"]) {
  const groups = new Map<string, PublicEntry["sources"]>();
  for (const original of sources) {
    const source = structuredClone(original);
    const suffix = source.label.match(/^(.*?)\s*\(([^()]*)\)\s*$/);
    const qualifiers = suffix?.[2].split(/[,;]+/).map((s) => s.trim()) || [];
    if (
      suffix?.[1].trim() &&
      qualifiers.length &&
      qualifiers.every((q) => /^(?:players|edition):/.test(conditionKey(q)))
    ) {
      source.label = suffix[1].trim();
      source.conditions = [...source.conditions, ...qualifiers];
    }
    source.conditions = uniqueConditions(source.conditions);
    if (source.dropChance) {
      source.dropChance.conditions = uniqueConditions(
        Array.isArray(source.dropChance.conditions)
          ? source.dropChance.conditions
          : [String(source.dropChance.conditions || "")],
      );
      const players = [
        ...new Set(
          [...source.conditions, ...source.dropChance.conditions]
            .map(playerCondition)
            .filter((p) => p !== null),
        ),
      ];
      if (
        players.length > 1 ||
        (source.dropChance.players &&
          players.some((p) => p !== source.dropChance!.players))
      )
        throw new Error(
          "Contradictory player counts for " + source.label + ".",
        );
      if (!source.dropChance.players && players.length === 1)
        source.dropChance.players = players[0];
    }
    const key = JSON.stringify([
      source.label.trim().toLowerCase(),
      source.kind,
      source.location?.trim().toLowerCase(),
      source.dlc?.trim().toLowerCase(),
      source.dropChance ? "rated" : [...source.conditions].sort(),
    ]);
    groups.set(key, [...(groups.get(key) || []), source]);
  }
  return [...groups.values()].map((rows): z.infer<typeof AcquisitionSource> => {
    const first = rows[0];
    const conditions = uniqueConditions(first.conditions).filter((condition) =>
      rows.every((row) =>
        row.conditions.some(
          (other) => conditionKey(other) === conditionKey(condition),
        ),
      ),
    );
    const dropChances: z.infer<typeof AcquisitionSource>["dropChances"] = [];
    for (const row of rows) {
      if (!row.dropChance) continue;
      const chance = row.dropChance;
      const scoped = [
        ...new Set([
          ...row.conditions.filter(
            (c) =>
              !conditions.some(
                (common) => conditionKey(common) === conditionKey(c),
              ),
          ),
          ...(Array.isArray(chance.conditions)
            ? chance.conditions
            : [String(chance.conditions || "")]
          )
            .map((text) => text.trim())
            .filter(Boolean),
        ]),
      ];
      const rate = {
        percent: chance.percent,
        players: chance.players ?? null,
        conditions: uniqueConditions(scoped).filter(
          (c) =>
            !conditions.some(
              (common) => conditionKey(common) === conditionKey(c),
            ) && !(chance.players && playerCondition(c) === chance.players),
        ),
      };
      const sameScope = dropChances.find(
        (existing) =>
          existing.players === rate.players &&
          JSON.stringify(existing.conditions.map(conditionKey).sort()) ===
            JSON.stringify(rate.conditions.map(conditionKey).sort()),
      );
      if (sameScope && sameScope.percent !== rate.percent)
        throw new Error(
          "Conflicting drop chances for " +
            first.label +
            "; resolve the conditions before exporting.",
        );
      if (!sameScope) dropChances.push(rate);
    }
    return {
      label: first.label,
      kind: first.kind,
      url: first.url,
      location: first.location,
      dlc: first.dlc,
      notes:
        [...new Set(rows.map((row) => row.notes.trim()).filter(Boolean))].join(
          " ",
        ) || undefined,
      conditions: conditions.filter(
        (c) =>
          !(
            playerCondition(c) &&
            dropChances.length &&
            dropChances.every((rate) => rate.players === playerCondition(c))
          ),
      ),
      dropChances,
    };
  });
}
