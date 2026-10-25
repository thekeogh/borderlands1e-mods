import type { PublicEntry } from "./models.ts";
/** Remove only notes that repeat their structured value; never rewrite human prose. */
export function redundantStatNote(stat: PublicEntry["stats"][number]) {
  const compact = (s: string) =>
    s
      .trim()
      .toLowerCase()
      .replace(/[−–—]/g, "-")
      .replace(/\s+/g, "")
      .replace(/\+/g, "")
      .replace(/[.;]+$/, "");
  const value =
    stat.minimum === stat.maximum
      ? String(stat.minimum)
      : `${stat.minimum}-${stat.maximum}`;
  if (stat.minimum === null || stat.maximum === null) return false;
  const candidates = [value, value + stat.unit];
  const note = compact(stat.notes);
  return candidates.some(
    (candidate) =>
      note === compact(candidate) ||
      note === compact(stat.name + ":" + candidate),
  );
}
export function cleanPublicEntry(entry: PublicEntry): PublicEntry {
  return {
    ...entry,
    stats: entry.stats.map((stat) => ({
      ...stat,
      notes: redundantStatNote(stat) ? "" : stat.notes,
      context:
        entry.category === "Class mods" &&
        /^(?:team )?ammo(?:unition)? regeneration$/i.test(stat.name.trim()) &&
        !stat.unit.trim() &&
        (!stat.context ||
          /^(?:team bonus|card(?: bonus| rating)?)$/i.test(stat.context.trim()))
          ? "Card bonus"
          : stat.context && /^scale$/i.test(stat.context.trim())
            ? "Multiplier"
            : stat.context,
    })),
  };
}
