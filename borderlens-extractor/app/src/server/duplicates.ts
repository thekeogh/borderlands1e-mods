import type { Family } from "../shared/models.ts";
import type { DuplicateResults } from "../shared/duplicates.ts";
import { catalogueGroup } from "../shared/taxonomy.ts";
import { rawRefs } from "./evidence.ts";
import { Store, HttpError } from "./store.ts";
const nameKey = (value: string) =>
  value
    .normalize("NFKD")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "");
const words = (value: string) =>
  value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
const generic = new Set([
  "weapon",
  "weapons",
  "shield",
  "mod",
  "artifact",
  "item",
  "classmod",
  "gun",
  "level",
]);
function identities(store: Store, family: Family) {
  const paths = new Set(family.roots.map((root) => root.toLowerCase()));
  for (const root of family.roots) {
    const record = store.records.get(root.toLowerCase());
    if (!record) continue;
    for (const ref of rawRefs(record.properties))
      if (
        store.records
          .get(ref.toLowerCase())
          ?.class?.endsWith("NamePartDefinition") &&
        !/gd_weap_names_shared\./i.test(ref)
      )
        paths.add(ref.toLowerCase());
  }
  return paths;
}
/** Suggestions only. Same names/shared definitions do not establish retail equivalence. */
export function findDuplicates(store: Store, id: string): DuplicateResults {
  const family = store.family(id);
  if (
    catalogueGroup(family) !== "Needs review" ||
    family.status === "excluded" ||
    family.supersededBy
  )
    throw new HttpError(
      400,
      "Duplicate lookup is available for active Needs review entries only.",
    );
  const targetNames = [family.name, ...family.aliases],
    targetKeys = new Set(targetNames.map(nameKey).filter(Boolean)),
    paths = identities(store, family);
  const candidates = store.state.families.filter(
    (other) =>
      other.id !== id &&
      !other.supersededBy &&
      other.status !== "excluded" &&
      catalogueGroup(other) !== "Needs review",
  );
  const scored = candidates
    .flatMap((other) => {
      const reasons: string[] = [];
      let score = 0;
      if (
        nameKey(family.name) &&
        nameKey(family.name) === nameKey(other.name)
      ) {
        reasons.push("Same display name.");
        score += 90;
      } else if (
        [other.name, ...other.aliases].some((name) =>
          targetKeys.has(nameKey(name)),
        )
      ) {
        reasons.push("A name or alias matches.");
        score += 70;
      }
      if ([...identities(store, other)].some((path) => paths.has(path))) {
        reasons.push("Shares an extracted family/title definition.");
        score += 100;
      }
      if (
        !reasons.length &&
        targetNames.some((name) =>
          [other.name, ...other.aliases].some((candidate) => {
            const shorter =
                words(name).length < words(candidate).length
                  ? words(name)
                  : words(candidate),
              longer =
                words(name).length < words(candidate).length
                  ? words(candidate)
                  : words(name);
            return (
              nameKey(shorter).length >= 5 &&
              !generic.has(nameKey(shorter)) &&
              ` ${longer} `.includes(` ${shorter} `)
            );
          }),
        )
      ) {
        reasons.push(
          "Similar name with additional words; identity is unverified.",
        );
        score += 25;
      }
      if (!score) return [];
      if (family.category !== other.category)
        reasons.push(
          "Different equipment category; inspect the definitions before deciding.",
        );
      return [
        {
          score,
          match: {
            id: other.id,
            name: other.name,
            category: catalogueGroup(other),
            character: other.character,
            reasons,
          },
        },
      ];
    })
    .sort(
      (a, b) =>
        b.score - a.score ||
        a.match.name.localeCompare(b.match.name) ||
        a.match.id.localeCompare(b.match.id),
    );
  return {
    itemId: id,
    searched: candidates.length,
    total: scored.length,
    matches: scored.slice(0, 20).map((row) => row.match),
  };
}
