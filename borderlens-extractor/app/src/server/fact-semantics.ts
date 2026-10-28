import type { Packet } from "../shared/models.ts";
/** Applicability is broader than ownership: a related skill's baseline is not an item stat. */
export function familyStat(
  fact: {
    catalogueRole?: string;
    stat?: unknown;
    applicabilityScope?: { items: string[]; skills: string[] } | null;
  },
  packet: Pick<Packet, "name" | "identityNames">,
) {
  if (fact.catalogueRole && fact.catalogueRole !== "item_property")
    return false;
  const scope = fact.applicabilityScope;
  if (!scope) return true;
  const norm = (name: string) => name.toLowerCase().replace(/[^a-z0-9]/g, "");
  const names = [packet.name, ...(packet.identityNames || [])]
    .filter(Boolean)
    .map(norm);
  const bound = scope.items.some((name) => names.includes(norm(name)));
  return !(
    (scope.skills.length > 0 && !bound) ||
    (scope.items.length > 0 && !bound)
  );
}
/** Optional source names/progression are advisory; explicit wrong-family evidence remains blocking. */
export function coreIdentityConcern(message: string) {
  return /\b(?:unresolved|unverified|unknown|wrong|different|mismatched)\s+(?:(?:family|item)\s+)?identity\b|\b(?:family|item) identity\b.*\b(?:unresolved|unverified|unknown|wrong|mismatch)\b|\b(?:different|wrong) (?:item family|game|game edition)\b/i.test(
    message,
  );
}
