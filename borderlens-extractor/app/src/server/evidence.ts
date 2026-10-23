import {
  type Family,
  type Raw,
  type Packet,
  type Evidence,
} from "../shared/models.ts";
import { Store, hash, stable } from "./store.ts";
import { unpack } from "./importer.ts";
export const evidenceId = (path: string) =>
  "game:" + hash(path.toLowerCase()).slice(0, 16);
export function rawRefs(v: unknown): string[] {
  const result: string[] = [];
  const visit = (x: any) => {
    if (!x || typeof x !== "object") return;
    if (x.$ref) {
      result.push(x.$ref);
      return;
    }
    for (const [k, y] of Object.entries(x))
      if (k !== "ObjectArchetype")
        if (Array.isArray(y)) y.forEach(visit);
        else visit(y);
  };
  visit(v);
  return result;
}
export function buildPacket(store: Store, f: Family): Packet {
  const records = store.records;
  const chosen = new Map<string, Raw>();
  const queue = [...f.roots];
  const roots = new Set(f.roots.map((p) => p.toLowerCase()));
  // Include defining parts and associated types; a generic type alone is not identity.
  for (const r of records.values()) {
    if (!r.class?.match(/(?:Weapon|Item)(?:Part|Type)?Definition$/)) continue;
    const p = unpack(r.properties);
    if ((p?.TitleList || []).some((p: string) => roots.has(p.toLowerCase())))
      queue.push(r.path);
  }
  const defining = queue.map((p) => p.toLowerCase());
  const partLists = new Set<string>();
  for (const r of records.values())
    if (
      r.class?.endsWith("PartListDefinition") &&
      rawRefs(r.properties).some((p) => defining.includes(p.toLowerCase()))
    ) {
      partLists.add(r.path.toLowerCase());
      queue.push(r.path);
    }
  for (const r of records.values())
    if (
      r.class?.endsWith("WeaponTypeDefinition") &&
      rawRefs(r.properties).some((p) => partLists.has(p.toLowerCase()))
    )
      queue.push(r.path);
  const typeRoots = new Set(queue.map((p) => p.toLowerCase()));
  for (const r of records.values())
    if (r.class?.endsWith("InventoryBalanceDefinition")) {
      const p = unpack(r.properties);
      if (
        typeRoots.has(String(p?.InventoryDefinition).toLowerCase()) &&
        !p?.BaseDefinition
      )
        queue.push(r.path);
    }
  const warnings: string[] = [];
  let budget = 0;
  const seen = new Set<string>();
  while (queue.length && budget < 180) {
    const p = queue.shift()!.toLowerCase();
    if (seen.has(p)) continue;
    seen.add(p);
    const r = records.get(p);
    if (!r) continue;
    if (!r.class?.match(/Definition$|Resolver$|Expression|Behavior|PartList/))
      continue;
    chosen.set(p, r);
    budget++;
    for (const target of rawRefs(r.properties))
      if (!seen.has(target.toLowerCase())) queue.push(target);
  }
  if (queue.length)
    warnings.push(
      "The reference graph was bounded; this packet is not proof of complete source or stat coverage.",
    );
  const identity = new Set(defining);
  const identityRefs = new Set<string>();
  for (const key of identity) {
    const row = records.get(key);
    if (row)
      for (const ref of rawRefs(row.properties))
        identityRefs.add(ref.toLowerCase());
  }
  const facts: Packet["facts"] = {
    redText: null,
    manufacturers: [],
    rarities: [],
    elements: [],
  };
  for (const r of chosen.values()) {
    const p = unpack(r.properties);
    if (
      identityRefs.has(r.path.toLowerCase()) &&
      r.class?.endsWith("AttributePresentationDefinition") &&
      p.bDontDisplayNumber &&
      p.NoConstraintText
    )
      facts.redText ||= p.NoConstraintText;
    if (
      identity.has(r.path.toLowerCase()) &&
      r.class?.endsWith("WeaponPartDefinition") &&
      p.CustomDamageTypeDefinition
    ) {
      const match = String(p.CustomDamageTypeDefinition).match(
        /gd_(Incendiary|Corrosive|Shock|Explosive)\./i,
      );
      if (match) facts.elements.push(match[1].toLowerCase());
    }
    if (
      roots.has(r.path.toLowerCase()) &&
      String(p?.Rarity?.BaseValueAttribute).includes("Legendary")
    )
      facts.rarities.push("Legendary");
  }
  // Manufacturer claims require the defining part's rule; do not infer from filename.
  for (const list of chosen.values()) {
    const p = unpack(list.properties);
    for (const rule of p?.WeightedParts || []) {
      if (!defining.includes(String(rule.Part).toLowerCase())) continue;
      const fallback = rule.DefaultWeight;
      if (
        fallback?.BaseValueConstant !== 0 ||
        fallback?.BaseValueAttribute ||
        fallback?.InitializationDefinition
      )
        continue;
      for (const row of rule.Manufacturers || []) {
        const weight = row.DefaultWeight;
        if (
          row.Manufacturer &&
          (weight?.BaseValueConstant > 0 ||
            weight?.InitializationDefinition ||
            weight?.BaseValueAttribute)
        ) {
          const name = String(row.Manufacturer).split(".").pop()!;
          facts.manufacturers.push(name);
        }
      }
    }
  }
  for (const k of ["manufacturers", "rarities", "elements"] as const)
    facts[k] = [...new Set(facts[k])];
  const evidence: Evidence[] = [...chosen.values()].map((r) => ({
    id: evidenceId(r.path),
    kind: "game",
    label: r.path,
    path: r.path,
    value: {
      role: identity.has(r.path.toLowerCase())
        ? "family-defining"
        : "shared context; not necessarily valid for this family",
      class: r.class,
      properties: unpack(r.properties),
      complete: r.complete,
      issues: r.issues,
    },
  }));
  for (const s of store.sources(f.id))
    evidence.push({
      id: s.id,
      kind: "page",
      label: s.title || s.url,
      value: {
        url: s.url,
        hash: s.hash,
        retrievedAt: s.fetchedAt,
        text: s.text.slice(0, 30000),
        imported: s.imported,
        sections: s.sections || [],
        tables: s.tables || [],
      },
    });
  if (f.manualOutput) {
    const output = store.get(f.id, "output");
    if (output)
      evidence.push({
        id: "manual:reviewed-output",
        kind: "manual",
        label: "Manually reviewed public entry",
        value: output,
      });
  }
  if (f.notes)
    evidence.push({
      id: "manual:" + hash(f.notes).slice(0, 16),
      kind: "manual",
      label: "Saved user correction",
      value: f.notes,
    });
  warnings.push(
    "Shared context includes alternative parts and other families. Presence in this graph does not establish compatibility; follow explicit selection and title rules.",
    "Spawn stage, internal item level and use requirement are distinct. Shared defaults are not final roll ranges.",
    "Only captured definitions and saved pages are evidence; unresolved fields must stay unknown.",
  );
  return {
    familyId: f.id,
    name: f.name,
    category: f.category,
    subtype: f.subtype,
    evidence,
    warnings,
    facts,
  };
}
export function packetHash(p: Packet) {
  return hash(stable(p));
}
export function validateDraft(draft: any, p: Packet) {
  if (
    draft.entry.id !== p.familyId ||
    draft.entry.name !== p.name ||
    draft.entry.category !== p.category
  )
    throw new Error("Generated identity does not match this family.");
  const ids = new Set(p.evidence.map((e) => e.id));
  for (const claim of draft.claims) {
    for (const id of claim.evidenceIds)
      if (!ids.has(id))
        throw new Error(`Claim cites unavailable evidence: ${id}`);
    if (!claim.basis.trim())
      throw new Error("Claim is missing its supporting basis.");
  }
  const publicText = [
    draft.entry.summary,
    ...(draft.entry.description || []),
    ...(draft.entry.variants || []).flatMap((v: any) => [
      v.name,
      v.description,
      ...v.differences,
    ]),
    ...(draft.partDefinitions || []).flatMap((p: any) => [
      p.name,
      ...p.effects,
      ...p.notes,
    ]),
    ...(draft.entry.parts || []).map((p: any) => p.notes),
    ...draft.entry.specialEffects,
    ...draft.entry.notes,
    ...draft.entry.stats.map((s: any) => s.notes),
    ...draft.entry.sources.map((s: any) => s.notes),
  ].join("\n");
  if (
    /\bgd_[\w]|WillowGame\.|BaseValueAttribute|ManufacturerGradeIndex|resolver chain|\bUObject\b/i.test(
      publicText,
    )
  )
    throw new Error(
      "Player-facing text contains engine/debug language. Rebuild or edit the draft.",
    );
  // Catch substantial verbatim copying while allowing names, red text and short labels.
  const words = (text: string) =>
    text
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, " ")
      .trim()
      .split(/\s+/);
  const sourcePhrases = new Set<string>();
  for (const page of p.evidence.filter((e) => e.kind === "page")) {
    const tokens = words(String((page.value as any).text || ""));
    for (let i = 0; i + 12 <= tokens.length; i++)
      sourcePhrases.add(tokens.slice(i, i + 12).join(" "));
  }
  for (const passage of [
    draft.entry.summary,
    ...(draft.entry.description || []),
    ...draft.entry.specialEffects,
    ...draft.entry.notes,
    ...(draft.entry.variants || []).flatMap((v: any) => [
      v.description,
      ...v.differences,
    ]),
    ...(draft.partDefinitions || []).flatMap((part: any) => [
      ...part.effects,
      ...part.notes,
    ]),
  ]) {
    const tokens = words(passage);
    for (let i = 0; i + 12 <= tokens.length; i++)
      if (sourcePhrases.has(tokens.slice(i, i + 12).join(" ")))
        throw new Error(
          "Public prose repeats a substantial source passage verbatim. Rewrite in original wording; preserve only names, red text and necessary labels.",
        );
  }
  const effects = draft.entry.specialEffects as string[];
  if (
    effects.length > 2 ||
    effects.join(" ").trim().split(/\s+/).filter(Boolean).length > 45
  )
    throw new Error(
      "Special-effect explanation must be at most two short entries and 45 words total. Rewrite the saved article explanation in plain gameplay language.",
    );
  if (
    /tech[- ]consuming|tech levels?|defining accessory|accessory adds|ordinary incendiary accessory/i.test(
      [draft.entry.summary, ...effects].join(" "),
    )
  )
    throw new Error(
      "Effect explanation is too technical. Explain the player-visible ability in plain language, using the saved articles.",
    );
  if (
    draft.entry.notes.some((note: string) =>
      /not established|not verified|captured definitions|extraction limitation/i.test(
        note,
      ),
    )
  )
    throw new Error(
      "Move evidence limitations into uncertainties; public notes should contain gameplay tips.",
    );
  if (effects.length && p.evidence.some((e) => e.kind === "page")) {
    const pages = new Set(
      p.evidence
        .filter((e) => e.kind === "page" || e.kind === "manual")
        .map((e) => e.id),
    );
    if (
      !draft.claims.some(
        (claim: any) =>
          claim.field === "specialEffects" &&
          claim.evidenceIds.some((id: string) => pages.has(id)),
      )
    )
      throw new Error(
        "Special effects must cite the saved wiki/Lootlemon article explanation (or an explicit manual review), not only raw game internals.",
      );
  }
  const claimed = new Set(draft.claims.map((c: any) => c.field));
  const required = [
    "summary",
    "description",
    ...(draft.entry.variants?.length ? ["variants"] : []),
    ...(draft.entry.parts?.length ? ["parts"] : []),
    ...(["manufacturers", "rarities", "elements", "notes"] as const).filter(
      (k) => draft.entry[k].length,
    ),
    ...(draft.entry.redText ? ["redText"] : []),
    ...(draft.entry.specialEffects.length ? ["specialEffects"] : []),
    ...(draft.entry.stats.length ? ["stats"] : []),
    ...(draft.entry.sources.length ? ["sources"] : []),
    ...(draft.entry.levels.minimum !== null ||
    draft.entry.levels.maximum !== null
      ? ["levels"]
      : []),
  ];
  for (const field of required)
    if (
      ![...claimed].some((p: any) => p === field || p.startsWith(field + "."))
    )
      throw new Error(`Missing evidence claim for ${field}.`);
  const bounds = [draft.entry.levels, ...draft.entry.stats];
  for (const b of bounds)
    if (b.minimum !== null && b.maximum !== null && b.minimum > b.maximum)
      throw new Error("Minimum exceeds maximum in generated statistics.");
  if (p.facts.redText && draft.entry.redText !== p.facts.redText)
    throw new Error(
      "Generated red flavour text differs from the captured text.",
    );
  if (draft.requiresReview || draft.conflicts.length)
    throw new Error(
      draft.reviewReason ||
        draft.conflicts[0] ||
        "This entry needs review before export.",
    );
}
