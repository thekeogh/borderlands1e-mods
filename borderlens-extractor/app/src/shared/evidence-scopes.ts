import { z } from "zod";
import { Category, type Family } from "./models.ts";
import { catalogueGroup, weaponTypes } from "./taxonomy.ts";
export const EvidenceScope = z
  .object({
    category: z.enum(["Everything", ...Category.options]),
    group: z.enum([...weaponTypes, "Needs review"]).optional(),
    character: z.enum(["Roland", "Lilith", "Mordecai", "Brick"]).optional(),
  })
  .strict()
  .refine(
    (s) =>
      (!s.group || s.category === "Weapons") &&
      (!s.character || ["Class mods", "Artifacts"].includes(s.category)) &&
      !(s.character && s.group),
    "Invalid evidence scope",
  );
export type EvidenceScope = z.infer<typeof EvidenceScope>;
export function scopeLabel(scope: EvidenceScope) {
  return [scope.category, scope.group || scope.character]
    .filter(Boolean)
    .join(" → ");
}
export function scopeMatches(scope: EvidenceScope, f: Family) {
  return (
    !f.evidenceScope &&
    (scope.category === "Everything" || f.category === scope.category) &&
    (!scope.group || catalogueGroup(f) === scope.group) &&
    (!scope.character || f.character === scope.character)
  );
}
export function scopeOptions(): EvidenceScope[] {
  return [
    { category: "Everything" },
    ...Category.options.map((category) => ({ category })),
    ...([...weaponTypes, "Needs review"] as const).map((group) => ({
      category: "Weapons" as const,
      group,
    })),
    ...(["Class mods", "Artifacts"] as const).flatMap((category) =>
      (["Roland", "Lilith", "Mordecai", "Brick"] as const).map((character) => ({
        category,
        character,
      })),
    ),
  ];
}

/** Exactly one level above the displayed item/group in the catalogue tree. */
export function evidenceParent(
  f: Pick<
    Family,
    "category" | "character" | "evidenceScope" | "subtype" | "classification"
  >,
): EvidenceScope | null {
  const scope = f.evidenceScope;
  if (scope) {
    if (scope.category === "Everything") return null;
    return scope.group || scope.character
      ? { category: scope.category }
      : { category: "Everything" };
  }
  if (f.category === "Weapons")
    return {
      category: "Weapons",
      group: catalogueGroup(f as Family) as EvidenceScope["group"],
    };
  if (["Class mods", "Artifacts"].includes(f.category) && f.character)
    return { category: f.category, character: f.character };
  return { category: f.category };
}
