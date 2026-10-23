import { hash } from "./store.ts";
import type { Packet, Draft } from "../shared/models.ts";
export const partId = (path: string) =>
  "part-" + hash(path.toLowerCase()).slice(0, 16);
export function partCandidates(packet: Packet) {
  return packet.evidence
    .filter(
      (e) =>
        e.kind === "game" &&
        (e.value as any)?.class?.endsWith("WeaponPartDefinition"),
    )
    .map((e) => ({
      id: partId(e.path!),
      evidenceId: e.id,
      path: e.path!,
      role: (e.value as any).role,
      properties: (e.value as any).properties,
    }));
}
export function validateParts(draft: Draft, packet: Packet) {
  const candidates = new Map(partCandidates(packet).map((p) => [p.id, p]));
  const defs = new Map(draft.partDefinitions.map((p) => [p.id, p]));
  if (defs.size !== draft.partDefinitions.length)
    throw new Error("Duplicate shared part definition.");
  const refs = new Set(draft.entry.parts.map((p) => p.partId));
  if (refs.size !== draft.entry.parts.length)
    throw new Error("Duplicate family part reference.");
  if ([...defs.keys()].some((id) => !refs.has(id)))
    throw new Error(
      "Part definitions must correspond to this entry’s referenced parts.",
    );
  for (const ref of draft.entry.parts) {
    const candidate = candidates.get(ref.partId);
    if (!candidate || !defs.has(ref.partId))
      throw new Error(
        "Part reference lacks a captured definition or matching shared part entry: " +
          ref.partId,
      );
    const claims = draft.claims.filter(
      (c) =>
        c.field === "parts" && c.evidenceIds.includes(candidate.evidenceId),
    );
    if (!claims.length)
      throw new Error(
        "Parts claim must cite the actual captured part: " + ref.partId,
      );
    if (ref.relationship === "defining") {
      const titles = candidate.properties?.TitleList || [];
      if (
        candidate.role !== "family-defining" ||
        !titles.some((path: string) =>
          packet.evidence.some(
            (e) =>
              e.path?.toLowerCase() === String(path).toLowerCase() &&
              (e.value as any)?.class?.endsWith("WeaponNamePartDefinition"),
          ),
        )
      )
        throw new Error(
          "Defining part requires a direct captured title relationship: " +
            ref.partId,
        );
    } else {
      const cited = new Set(claims.flatMap((c) => c.evidenceIds));
      const selection = packet.evidence.some(
        (e) =>
          cited.has(e.id) &&
          /PartListDefinition|InventoryBalanceDefinition/.test(
            (e.value as any)?.class || "",
          ) &&
          JSON.stringify((e.value as any).properties)
            .toLowerCase()
            .includes(candidate.path.toLowerCase()),
      );
      const page = packet.evidence.some(
        (e) => cited.has(e.id) && e.kind === "page",
      );
      if (
        !selection ||
        !page ||
        !claims.some((c) => c.basis.includes(ref.partId))
      )
        throw new Error(
          "Required/possible part compatibility needs both a cited selection rule referencing this part and supporting page evidence; otherwise omit the option: " +
            ref.partId,
        );
    }
  }
}
