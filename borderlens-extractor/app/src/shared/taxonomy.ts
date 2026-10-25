import type { Family } from "./models.ts";

export const weaponTypes = [
  "Combat rifles",
  "Eridian weapons",
  "Repeater pistols",
  "Revolvers",
  "Rocket launchers",
  "Shotguns",
  "SMGs",
  "Sniper rifles",
] as const;
// Presentation groups never replace captured engine types or stable family IDs.
export function catalogueGroup(
  f: Pick<
    Family,
    "category" | "subtype" | "classification" | "classificationReview"
  >,
): string {
  if (f.category !== "Weapons") return f.subtype;
  if (f.classification?.weaponType) return f.classification.weaponType;
  switch (f.subtype) {
    case "Machine guns":
      return "Combat rifles";
    case "Machine pistols":
      return "Repeater pistols";
    case "Other weapons":
    case "Grenade launchers":
      return "Needs review";
    default:
      return f.subtype;
  }
}
export function classificationNote(
  f: Pick<
    Family,
    "category" | "subtype" | "classification" | "classificationReview"
  >,
): string | null {
  if (f.category !== "Weapons" || f.classification) return null;
  if (f.classificationReview) return f.classificationReview;
  if (f.subtype === "Grenade launchers")
    return "Internal grenade-launcher candidates. Verify released-game availability before treating these as catalogue items.";
  if (f.subtype === "Other weapons")
    return "Weapon type unresolved. This group includes DLC titles and shared naming definitions; a raw title is not proof of a separate item family.";
  return null;
}
export function catalogueOrder(a: Family, b: Family) {
  return (
    a.category.localeCompare(b.category) ||
    Number(catalogueGroup(a) === "Needs review") -
      Number(catalogueGroup(b) === "Needs review") ||
    catalogueGroup(a).localeCompare(catalogueGroup(b)) ||
    (a.character || "").localeCompare(b.character || "") ||
    a.name.localeCompare(b.name) ||
    a.id.localeCompare(b.id)
  );
}
