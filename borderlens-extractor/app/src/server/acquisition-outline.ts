import type { Outline } from "./factual-outline.ts";
import type { SourceLedger } from "./source-analysis.ts";
const normalize = (value: string) =>
  value.trim().toLowerCase().replace(/\s+/g, " ");
const escaped = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const unique = (values: string[]) => [
  ...new Map(values.map((v) => [normalize(v), v])).values(),
];
/** Identity matching is exact, or backed by an explicit alias statement in a captured quote. */
export function consolidateAcquisition(
  outline: Outline,
  ledger: SourceLedger[],
) {
  const facts = ledger
    .flatMap((page) => page.chunks.flatMap((chunk) => chunk.facts))
    .filter(
      (f) => !f.excludedReason && f.relevance?.automaticIncluded !== false,
    );
  const labels = outline.fixed.sources.map((source) => source.label);
  const parent = new Map(
    labels.map((label) => [normalize(label), normalize(label)]),
  );
  const root = (key: string): string =>
    parent.get(key) === key ? key : root(parent.get(key)!);
  const alias = (a: string, b: string) =>
    new RegExp(
      `(?:^|\\b)${escaped(a)}\\s*(?:\\(\\s*)?(?:(?:is|was)\\s+)?(?:also\\s+(?:known\\s+as|called|spelled)|a\\.?k\\.?a\\.?|alternatively\\s+(?:known\\s+as|spelled)|an?\\s+alternate\\s+spelling\\s+of)\\s+["']?${escaped(b)}(?=$|[\\s).,;"'])`,
      "i",
    );
  for (let i = 0; i < labels.length; i++)
    for (let j = i + 1; j < labels.length; j++) {
      const a = labels[i],
        b = labels[j];
      if (normalize(a) === normalize(b)) continue;
      if (
        facts.some(
          (f) => alias(a, b).test(f.quote) || alias(b, a).test(f.quote),
        )
      )
        parent.set(root(normalize(b)), root(normalize(a)));
    }
  const canonicalNames = new Map<string, string>();
  for (const label of labels) {
    const identity = root(normalize(label));
    if (!canonicalNames.has(identity)) canonicalNames.set(identity, label);
  }
  const detail = new Map(facts.map((f) => [f.id, f.detail]));
  const groups: {
    source: Outline["fixed"]["sources"][number];
    slot: Outline["slots"]["sources"][number];
    key: string;
  }[] = [];
  outline.fixed.sources.forEach((original, i) => {
    const source = structuredClone(original),
      slot = structuredClone(outline.slots.sources[i]);
    source.label = canonicalNames.get(root(normalize(source.label)))!;
    slot.factIds = [slot.factId];
    slot.facts = [
      {
        id: slot.factId,
        detail: detail.get(slot.factId) || "",
        conditions: [...slot.conditions],
        dropConditions: [...slot.dropConditions],
      },
    ];
    const key = root(normalize(source.label)) + ":" + source.kind;
    const compatible = (a: string | null, b: string | null) =>
      !a || !b || normalize(a) === normalize(b);
    const knownLocations = new Set(
      outline.fixed.sources
        .filter(
          (other) => root(normalize(other.label)) + ":" + other.kind === key,
        )
        .map((other) => (other.location ? normalize(other.location) : ""))
        .filter(Boolean),
    );
    const matches = groups.filter(
      (g) =>
        g.key === key &&
        !(
          knownLocations.size > 1 &&
          Boolean(g.source.location) !== Boolean(source.location)
        ) &&
        compatible(g.source.location, source.location) &&
        compatible(g.source.dlc, source.dlc) &&
        JSON.stringify(g.source.dropChance) ===
          JSON.stringify(source.dropChance) &&
        (!source.dropChance ||
          (JSON.stringify(g.slot.conditions) ===
            JSON.stringify(slot.conditions) &&
            JSON.stringify(g.slot.dropConditions) ===
              JSON.stringify(slot.dropConditions))),
    );
    if (matches.length !== 1) {
      groups.push({ source, slot, key });
      return;
    }
    const group = matches[0];
    // Prefer an entity's own page to a generic overview; all original pages remain in claims/provenance.
    const direct = (url: string | null, label: string) => {
      try {
        return (
          decodeURIComponent(new URL(url!).pathname.split("/").at(-1)!)
            .replace(/[^a-z0-9]/gi, "")
            .toLowerCase() === label.replace(/[^a-z0-9]/gi, "").toLowerCase()
        );
      } catch {
        return false;
      }
    };
    if (
      direct(source.url, source.label) &&
      !direct(group.source.url, group.source.label)
    )
      group.source.url = source.url;
    group.source.location ||= source.location;
    group.source.dlc ||= source.dlc;
    group.slot.conditions = unique([
      ...group.slot.conditions,
      ...slot.conditions,
    ]);
    group.slot.dropConditions = unique([
      ...group.slot.dropConditions,
      ...slot.dropConditions,
    ]);
    group.slot.factIds = unique([...group.slot.factIds!, slot.factId]);
    group.slot.facts!.push(...slot.facts);
  });
  outline.fixed.sources = groups.map((g) => g.source);
  outline.slots.sources = groups.map((g) => g.slot);
}
