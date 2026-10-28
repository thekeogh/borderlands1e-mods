import { consolidateAcquisition } from "./acquisition-outline.ts";
import { coreIdentityConcern } from "./fact-semantics.ts";
import {
  PublicEntry,
  PartDefinition,
  type Draft,
  type Family,
  type Packet,
} from "../shared/models.ts";
import {
  FACT_POLICY,
  type NormalizedFact,
  type ProseDraft,
} from "../shared/factual-build.ts";
import {
  COMPILER_VERSION,
  CATALOGUE_SCHEMA_VERSION,
} from "../shared/versions.ts";
import type { SourceLedger } from "./source-analysis.ts";
import { hash, stable } from "./store.ts";
import { partCandidates } from "./parts.ts";
import { providerForUrl } from "../shared/research.ts";
import { catalogueGroup } from "../shared/taxonomy.ts";
const norm = (s: string) => s.trim().toLowerCase();
const canonicalElement = (s: string) =>
  ({
    fire: "Incendiary",
    incendiary: "Incendiary",
    shock: "Shock",
    electric: "Shock",
    corrosive: "Corrosive",
    explosive: "Explosive",
    none: "Non-elemental",
    "non-elemental": "Non-elemental",
  })[norm(s)];
export type Outline = {
  version: string;
  hash: string;
  fixed: Omit<
    Draft["entry"],
    "summary" | "description" | "details" | "specialEffects" | "notes"
  >;
  parts: Draft["partDefinitions"];
  facts: NormalizedFact[];
  claims: Draft["claims"];
  usage: Draft["sourceUsage"];
  slots: {
    stats: { id: string; factId: string; context: string | null }[];
    sources: {
      id: string;
      factId: string;
      factIds?: string[];
      facts?: {
        id: string;
        detail: string;
        conditions: string[];
        dropConditions: string[];
      }[];
      conditions: string[];
      dropConditions: string[];
    }[];
    variants: { id: string; factId: string; distinctions: string[] }[];
  };
  conflicts: string[];
};
export function playerCondition(text: string) {
  return !/\b(?:not (?:established|verified|specified|confirmed|documented)|(?:missing|insufficient|no) (?:evidence|information)|(?:evidence|source|article|page) (?:does not|doesn't|cannot|can't|fails to)|unknown (?:playthrough|requirement|condition)|requires? (?:verification|confirmation|further research))\b/i.test(
    text,
  );
}
export function factualOutline(
  packet: Packet,
  ledger: SourceLedger[],
  family: Family,
): Outline {
  const fixed: Outline["fixed"] = {
    schemaVersion: CATALOGUE_SCHEMA_VERSION,
    compilerVersion: COMPILER_VERSION,
    id: family.id,
    name: family.name,
    category: family.category,
    weaponType:
      family.classification?.weaponType ||
      (family.category === "Weapons" &&
      catalogueGroup(family) !== "Needs review"
        ? catalogueGroup(family)
        : null),
    ...(family.character ? { character: family.character } : {}),
    dlc: packet.facts.dlc || null,
    manufacturers: [...packet.facts.manufacturers],
    rarities: [...packet.facts.rarities],
    elements: family.element
      ? [family.element]
      : (packet.facts.elements.map(canonicalElement).filter(Boolean) as any),
    redText: packet.facts.redText,
    levels: { minimum: null, maximum: null, notes: "" },
    stats: [],
    sources: [],
    variants: [],
    parts: [],
    references: ledger.map((p) => ({ label: p.url, url: p.url })),
  };
  const result: Outline = {
    version: FACT_POLICY,
    hash: "",
    fixed,
    parts: [],
    facts: [],
    claims: [],
    usage: [],
    slots: { stats: [], sources: [], variants: [] },
    conflicts: [],
  };
  const claim = (
    field: Draft["claims"][number]["field"],
    ids: string[],
    basis: string,
  ) => {
    const existing = result.claims.find((c) => c.field === field);
    if (existing)
      existing.evidenceIds = [...new Set([...existing.evidenceIds, ...ids])];
    else result.claims.push({ field, evidenceIds: [...new Set(ids)], basis });
  };
  const gameIds = packet.evidence
    .filter(
      (e) => e.kind === "game" && (e.value as any).role === "family-defining",
    )
    .map((e) => e.id);
  for (const field of [
    "dlc",
    "manufacturers",
    "rarities",
    "elements",
    "redText",
  ] as const)
    if (
      Array.isArray(fixed[field])
        ? (fixed[field] as any[]).length
        : fixed[field]
    )
      claim(
        field,
        gameIds.length ? gameIds : packet.evidence.slice(0, 1).map((e) => e.id),
        "Verified identity-linked game property.",
      );
  for (const field of [
    "dlc",
    "manufacturers",
    "rarities",
    "elements",
    "redText",
  ] as const) {
    const value = fixed[field];
    if (value == null || (Array.isArray(value) && !value.length)) continue;
    result.facts.push({
      id: "resolved:" + field,
      subject: family.id,
      property: field,
      value,
      role: "item_property",
      conditions: [],
      scope: null,
      status: "accepted",
      reason: "Verified defining game property or authoritative item identity.",
      provenance: gameIds.map((id) => ({
        evidenceId: id,
        factId: "resolved:" + field,
        sourceId: null,
        url: null,
        hash: hash(stable(packet.evidence.find((e) => e.id === id))),
        chunk: null,
        quote: "",
        method: "game",
        policy: FACT_POLICY,
      })),
    });
  }
  const rows = ledger.flatMap((page) =>
    page.chunks.flatMap((chunk) =>
      chunk.facts.map((fact) => ({ page, chunk, fact })),
    ),
  );
  // Resolve equivalent structured quantities by scope/value; Lootlemon takes priority only within the same key.
  const chosen = new Map<
    string,
    {
      value: string;
      provider: string;
      id: string;
      field: string;
      priority: number;
    }
  >();
  const priorities = (url: string) =>
    providerForUrl(url) === "Lootlemon" ? 2 : 1;
  const accept = (
    key: string,
    value: unknown,
    row: (typeof rows)[number],
    field: string,
  ) => {
    const serialized = stable(value),
      previous = chosen.get(key),
      priority = priorities(row.page.url);
    if (previous && previous.value !== serialized) {
      if (priority !== previous.priority) {
        if (priority < previous.priority) {
          const record = result.facts.find((f) => f.id === row.fact.id);
          if (record) {
            record.status = "rejected";
            record.reason =
              "Same-scope verified Lootlemon fact takes precedence.";
          }
          result.usage.push({
            factId: row.fact.id,
            disposition: "overridden",
            fields: [],
            duplicateOf: previous.id,
            reason: "Equivalent scoped field uses verified Lootlemon priority.",
          });
          return false;
        }
        throw Error(
          "Source resolver order must place preferred providers first.",
        );
      }
      const record = result.facts.find((f) => f.id === row.fact.id);
      if (record) {
        record.status = "rejected";
        record.reason =
          "An equally ranked source disagrees; retained the first supported value.";
      }
      result.usage.push({
        factId: row.fact.id,
        disposition: "irrelevant",
        fields: [],
        duplicateOf: null,
        reason:
          "Alternative numerical/property value disagrees with the selected same-scope fact. Kept the first equally ranked supported value.",
      });
      result.conflicts.push(
        "Sources disagree on " +
          field +
          " under the same conditions; kept the first equally ranked supported value.",
      );
      return false;
    }
    if (previous) {
      result.usage.push({
        factId: row.fact.id,
        disposition: "duplicate",
        fields: [],
        duplicateOf: previous.id,
        reason: "Same accepted value and conditions.",
      });
      return false;
    }
    chosen.set(key, {
      value: serialized,
      provider: row.page.url,
      id: row.fact.id,
      field,
      priority,
    });
    return true;
  };
  const ownSubjects = (row: (typeof rows)[number]) => {
    const scope = row.fact.applicabilityScope;
    if (!scope) return true;
    const normalize = (name: string) =>
      name.toLowerCase().replace(/[^a-z0-9]/g, "");
    // Retaining an uncertain fact for reading is not permission to promote it
    // into this item's fixed properties. Respect every explicit scope dimension.
    const overlaps = (values: string[], targets: string[]) =>
      values.some((value) =>
        targets.some((target) => normalize(value) === normalize(target)),
      );
    if (
      scope.categories.length &&
      !overlaps(scope.categories, [family.category])
    )
      return false;
    if (
      scope.characters.length &&
      family.character &&
      !overlaps(scope.characters, [family.character])
    )
      return false;
    const elements = family.element ? [family.element] : packet.facts.elements;
    if (
      scope.elements.length &&
      elements.length &&
      !overlaps(scope.elements, elements)
    )
      return false;
    if (
      scope.weaponTypes.length &&
      (family.category !== "Weapons" ||
        !overlaps(scope.weaponTypes, [
          family.classification?.weaponType || family.subtype,
        ]))
    )
      return false;
    const names = (
      packet.identityNames || [family.name, ...family.aliases]
    ).map(normalize);
    const bound = scope.items.some((name) => names.includes(normalize(name)));
    return !(
      (scope.items.length > 0 && !bound) ||
      (scope.skills.length > 0 && !bound)
    );
  };
  const exhaustive = new Map<
    string,
    { values: string[]; row: (typeof rows)[number]; specificity: number }
  >();
  const specificity = (row: (typeof rows)[number]) =>
    row.fact.catalogueRole === "item_property" ? 2 : 1;
  for (const row of rows) {
    const value = row.fact.structured;
    if (
      !ownSubjects(row) ||
      value?.kind !== "list" ||
      value.coverage !== "complete" ||
      row.fact.excludedReason ||
      row.fact.relevance?.automaticIncluded === false
    )
      continue;
    const previous = exhaustive.get(value.field),
      values = value.values.map((v) =>
        value.field === "elements" ? canonicalElement(v) || v : v,
      );
    const score = specificity(row),
      prior = previous?.specificity || 0;
    if (
      !previous ||
      score > prior ||
      (score === prior &&
        priorities(row.page.url) > priorities(previous.row.page.url))
    )
      exhaustive.set(value.field, { values, row, specificity: score });
    else if (
      score === prior &&
      priorities(row.page.url) === priorities(previous.row.page.url) &&
      stable([...values].sort()) !== stable([...previous.values].sort())
    )
      result.conflicts.push(
        "Conflicting exhaustive " +
          value.field +
          " lists with the same scope and priority.",
      );
  }
  const rejectedListFacts = new Map<
    string,
    { preferred: string; reason: string }
  >();
  const allowedList = (
    field: "manufacturers" | "rarities" | "elements",
    values: string[],
    row: (typeof rows)[number],
  ) => {
    const game =
      field === "elements"
        ? family.element
          ? [family.element]
          : []
        : packet.facts[field] || [];
    const choice = exhaustive.get(field);
    const limit = game.length ? game : choice?.values;
    if (!limit) return values;
    if (values.every((v) => limit.some((allowed) => norm(allowed) === norm(v))))
      return values;
    const record = result.facts.find((f) => f.id === row.fact.id);
    if (game.length || (choice && specificity(row) < choice.specificity)) {
      if (record) {
        record.status = "rejected";
        record.reason =
          "A more specific defining item restriction takes precedence over this broader list.";
      }
      return [];
    }
    if (choice && priorities(choice.row.page.url) > priorities(row.page.url)) {
      result.usage.push({
        factId: row.fact.id,
        disposition: "overridden",
        fields: [],
        duplicateOf: choice.row.fact.id,
        reason:
          "Same-scope exhaustive Lootlemon property list supersedes the conflicting Wiki list.",
      });
      if (record) {
        record.status = "rejected";
        record.reason = "Resolved by same-scope Lootlemon priority.";
      }
      return [];
    }
    if (
      choice &&
      priorities(row.page.url) > priorities(choice.row.page.url) &&
      specificity(row) === choice.specificity
    ) {
      const reason =
        "A verified higher-priority property contradicts the Wiki exhaustive list.";
      rejectedListFacts.set(choice.row.fact.id, {
        preferred: row.fact.id,
        reason,
      });
      result.usage.push({
        factId: choice.row.fact.id,
        disposition: "overridden",
        fields: [],
        duplicateOf: row.fact.id,
        reason,
      });
      exhaustive.delete(field);
      (fixed as any)[field] = [];
      return values;
    }
    result.conflicts.push(
      "A supported " +
        field +
        " value conflicts with an exhaustive list; interpretation requires review.",
    );
    return [];
  };
  for (const [field, choice] of exhaustive) {
    if (
      (field === "elements" && family.element) ||
      (field !== "elements" &&
        (packet.facts[field as "manufacturers" | "rarities"] || []).length)
    )
      continue;
    (fixed as any)[field] = [...choice.values];
  }
  for (const row of [...rows].sort(
    (a, b) => priorities(b.page.url) - priorities(a.page.url),
  )) {
    const { fact, page, chunk } = row,
      provenance = {
        evidenceId: page.sourceId,
        factId: fact.id,
        sourceId: page.sourceId,
        url: page.url,
        hash: page.hash,
        chunk: chunk.index,
        quote: fact.quote,
        method:
          fact.extractionMethod === "parser"
            ? ("parser" as const)
            : ("interpretation" as const),
        policy: FACT_POLICY,
      };
    const normalized: NormalizedFact = {
      id: fact.id,
      subject:
        fact.applicabilityScope?.items.join(" | ") ||
        fact.applicabilityScope?.skills.join(" | ") ||
        family.id,
      property: fact.field,
      value: fact.structured || fact.stat || fact.detail,
      role: fact.catalogueRole || "unclassified",
      conditions:
        fact.structured?.kind === "source"
          ? fact.structured.conditions
          : fact.stat?.context
            ? [fact.stat.context]
            : [],
      scope: fact.applicabilityScope || null,
      status: "candidate",
      reason:
        "Available narrative evidence; not automatically a structured item property.",
      provenance: [provenance],
    };
    result.facts.push(normalized);
    const rejectedList = rejectedListFacts.get(fact.id);
    if (rejectedList) {
      normalized.status = "rejected";
      normalized.reason = rejectedList.reason;
      continue;
    }
    if (fact.excludedReason || fact.relevance?.automaticIncluded === false) {
      normalized.status = "rejected";
      normalized.reason = fact.excludedReason || fact.relevance!.reason;
      continue;
    }
    const fields: string[] = [],
      role = fact.catalogueRole;
    const ownNames = [
      family.name,
      family.rawName,
      ...family.aliases,
      ...(family.nameOverride?.identityAliases || []),
    ]
      .filter(Boolean)
      .map((value) =>
        String(value)
          .toLowerCase()
          .replace(/[^a-z0-9]/g, ""),
      );
    const boundItem = fact.applicabilityScope?.items.some((name) =>
      ownNames.includes(name.toLowerCase().replace(/[^a-z0-9]/g, "")),
    );
    const relatedNumbers =
      !!fact.stat &&
      !!fact.applicabilityScope &&
      ((fact.applicabilityScope.skills.length > 0 && !boundItem) ||
        (fact.applicabilityScope.items.length > 0 && !boundItem));
    const permitted = role === "item_property" && ownSubjects(row);
    if (relatedNumbers)
      normalized.reason =
        "Related ability/other-item numbers stay narrative context, not this item's stats.";
    if (
      permitted &&
      fact.field === "manufacturers" &&
      fact.manufacturerNames?.length
    ) {
      const names = allowedList("manufacturers", fact.manufacturerNames, row);
      for (const name of names)
        if (
          norm(fact.quote).includes(norm(name)) &&
          !fixed.manufacturers.some((n) => norm(n) === norm(name))
        )
          fixed.manufacturers.push(name);
      if (names.length) fields.push("manufacturers");
    }
    if (permitted && fact.field === "dlc" && fact.origin) {
      if (packet.facts.dlc && packet.facts.dlc !== fact.origin) {
        normalized.status = "rejected";
        normalized.reason = "Exact extracted origin remains authoritative.";
        continue;
      }
      if (accept("dlc", fact.origin, row, "dlc")) {
        fixed.dlc = fact.origin;
        fields.push("dlc");
      }
    }
    if (permitted && fact.field === "stats" && fact.stat) {
      const stat = {
        ...fact.stat,
        context: fact.stat.context?.trim() || fact.stat.notes?.trim() || null,
        notes: "",
      };
      const key = stable([
        norm(stat.name),
        stat.context,
        stat.level,
        stat.unit,
      ]);
      if (
        accept(
          "stat:" + key,
          { minimum: stat.minimum, maximum: stat.maximum },
          row,
          "stats",
        )
      ) {
        const id = "stat-" + hash(fact.id).slice(0, 12);
        fixed.stats.push({
          ...stat,
          context:
            fact.stat.context?.trim() ||
            (/^(Card|While scoped|Base bonus|Total bonus|Multiplier)$/i.test(
              fact.stat.notes.trim(),
            )
              ? fact.stat.notes.trim()
              : null),
        });
        result.slots.stats.push({ id, factId: fact.id, context: stat.context });
        fields.push("stats");
      }
    }
    const v = fact.structured;
    if (
      v &&
      ownSubjects(row) &&
      (permitted ||
        (v.kind === "list" &&
          ["rarities", "elements"].includes(v.field) &&
          role === "general_mechanic") ||
        (v.kind === "source" &&
          role === "general_mechanic" &&
          fact.applicabilityScope?.certain &&
          fact.applicabilityScope.categories.includes(family.category)) ||
        (v.kind === "part" && role === "part_property"))
    ) {
      if (v.kind === "list") {
        const values =
          v.field === "manufacturers"
            ? []
            : v.field === "elements"
              ? (v.values.map(canonicalElement).filter(Boolean) as string[])
              : v.values;
        const allowed = allowedList(v.field, values, row);
        for (const value of allowed) {
          if (
            v.field === "elements" &&
            family.element &&
            norm(value) !== norm(family.element)
          )
            continue;
          if (
            !(fixed[v.field] as string[]).some((n) => norm(n) === norm(value))
          )
            (fixed[v.field] as string[]).push(value);
        }
        if (allowed.length) fields.push(v.field);
      } else if (v.kind === "levels" && accept("levels", v, row, "levels")) {
        fixed.levels = { minimum: v.minimum, maximum: v.maximum, notes: "" };
        fields.push("levels");
      } else if (
        v.kind === "redText" &&
        (!packet.facts.redText || packet.facts.redText === v.text) &&
        fact.quote.includes(v.text) &&
        accept("redText", v.text, row, "redText")
      ) {
        fixed.redText = v.text;
        fields.push("redText");
      } else if (v.kind === "source") {
        const source = {
          label: v.label,
          url: page.url.startsWith("https://manual.borderlens.invalid/")
            ? v.url?.startsWith("https://") && fact.quote.includes(v.url)
              ? v.url
              : null
            : page.url,
          kind: v.kindOfSource,
          location: v.location,
          dlc: v.dlc,
          conditions: [],
          notes: "",
          dropChance: v.dropChance ? { ...v.dropChance, conditions: [] } : null,
        };
        const key = stable([
          norm(v.label),
          v.location,
          v.conditions,
          v.dropChance?.players,
          v.dropChance?.conditions,
        ]);
        const accepted = accept(
          "source:" + key,
          { ...source, url: null },
          row,
          "sources",
        );
        const duplicate = result.usage.some(
          (usage) =>
            usage.factId === fact.id && usage.disposition === "duplicate",
        );
        // Equal structured identity does not make complementary reward prose redundant.
        if (accepted || duplicate) {
          const id = "source-" + hash(fact.id).slice(0, 12);
          fixed.sources.push(source);
          result.slots.sources.push({
            id,
            factId: fact.id,
            conditions: v.conditions.filter(playerCondition),
            dropConditions: (v.dropChance?.conditions || []).filter(
              playerCondition,
            ),
          });
          fields.push("sources");
        }
      } else if (
        v.kind === "variant" &&
        accept("variant:" + norm(v.name), v.distinctions, row, "variants")
      ) {
        const id = "variant-" + hash(fact.id).slice(0, 12);
        fixed.variants.push({ name: v.name, description: "", differences: [] });
        result.slots.variants.push({
          id,
          factId: fact.id,
          distinctions: v.distinctions,
        });
        fields.push("variants");
      } else if (v.kind === "part") {
        const candidates = partCandidates(packet).filter(
          (part) =>
            norm(part.path) === norm(v.path) ||
            norm(part.path.split(".").pop() || "") === norm(v.path),
        );
        const candidate = candidates.length === 1 ? candidates[0] : undefined;
        const quoted = norm(fact.quote).includes(norm(v.path));
        const positive = (weight: any) =>
          Number(weight?.BaseValueConstant) > 0 &&
          !weight?.BaseValueAttribute &&
          !weight?.InitializationDefinition;
        const selections = candidate
          ? packet.evidence.filter(
              (e) =>
                /PartListDefinition|InventoryBalanceDefinition/.test(
                  (e.value as any)?.class || "",
                ) &&
                ((e.value as any)?.properties?.WeightedParts || []).some(
                  (rule: any) =>
                    norm(String(rule.Part)) === norm(candidate.path) &&
                    (positive(rule.DefaultWeight) ||
                      (rule.Manufacturers || []).some(
                        (maker: any) =>
                          fixed.manufacturers.some(
                            (name) =>
                              norm(
                                String(maker.Manufacturer).split(".").pop() ||
                                  "",
                              ) === norm(name),
                          ) && positive(maker.DefaultWeight),
                      )),
                ),
            )
          : [];
        const defining =
          candidate?.role === "family-defining" &&
          (candidate.properties?.TitleList || []).some((path: string) =>
            packet.evidence.some(
              (e) =>
                norm(e.path || "") === norm(path) &&
                (e.value as any)?.class?.endsWith("WeaponNamePartDefinition"),
            ),
          );
        const proven =
          v.relationship === "defining"
            ? defining
            : quoted && selections.length > 0;
        if (
          candidate &&
          quoted &&
          proven &&
          !fixed.parts.some((part) => part.partId === candidate.id)
        ) {
          const slot = candidate.path
            .toLowerCase()
            .split(".")
            .map(
              (segment) =>
                segment.match(
                  /^(barrel|body|grip|magazine|accessory|sight|stock|material|action)/,
                )?.[1],
            )
            .find(Boolean) as PartDefinition["slot"] | undefined;
          fixed.parts.push({
            partId: candidate.id,
            relationship: v.relationship,
            notes: "",
          });
          result.parts.push({
            schemaVersion: "1",
            compilerVersion: COMPILER_VERSION,
            id: candidate.id,
            name: v.name,
            slot: slot || v.slot,
            manufacturers: v.manufacturers.filter(
              (name) =>
                fixed.manufacturers.some(
                  (known) => norm(known) === norm(name),
                ) && norm(fact.quote).includes(norm(name)),
            ),
            effects: [],
            notes: [],
          });
          claim(
            "parts",
            [
              candidate.evidenceId,
              page.sourceId,
              ...selections.map((e) => e.id),
            ],
            candidate.id +
              " is supported by the captured title/positive selection rule and the explicit archived part relationship.",
          );
          fields.push("parts");
        }
      }
    }
    if (fields.length) {
      normalized.status = "accepted";
      normalized.reason =
        "Structured fact accepted with original scope and provenance.";
      for (const field of fields)
        claim(field as any, [page.sourceId], "Accepted scoped fact " + fact.id);
      if (!result.usage.some((u) => u.factId === fact.id))
        result.usage.push({
          factId: fact.id,
          disposition: "used",
          fields: [...new Set(fields)],
          duplicateOf: null,
          reason: "Code assembled this supported value.",
        });
    }
  }
  // A direct title relationship is structural identity, not an inferred roll option.
  for (const candidate of partCandidates(packet)) {
    const titles = candidate.properties?.TitleList || [];
    if (
      candidate.role !== "family-defining" ||
      !titles.some((path: string) =>
        packet.evidence.some(
          (e) =>
            e.path?.toLowerCase() === path.toLowerCase() &&
            (e.value as any).class?.endsWith("WeaponNamePartDefinition"),
        ),
      ) ||
      fixed.parts.some((p) => p.partId === candidate.id)
    )
      continue;
    const segment = candidate.path
      .toLowerCase()
      .split(".")
      .find((s) =>
        /^(barrel|body|grip|magazine|accessory|sight|stock|material|action)/.test(
          s,
        ),
      );
    const slot = (segment?.match(
      /^(barrel|body|grip|magazine|accessory|sight|stock|material|action)/,
    )?.[1] || "other") as PartDefinition["slot"];
    fixed.parts.push({
      partId: candidate.id,
      relationship: "defining",
      notes: "",
    });
    result.parts.push({
      schemaVersion: "1",
      compilerVersion: COMPILER_VERSION,
      id: candidate.id,
      name: slot,
      slot,
      manufacturers: [],
      effects: [],
      notes: [],
    });
    claim(
      "parts",
      [candidate.evidenceId],
      candidate.id +
        " directly names this family through its captured title relationship.",
    );
  }
  consolidateAcquisition(result, ledger);
  result.hash = hash(
    stable({
      policy: FACT_POLICY,
      fixed,
      parts: result.parts,
      facts: result.facts,
      corrections: packet.evidence.filter((e) => e.kind === "manual"),
      slots: result.slots,
    }),
  );
  return result;
}
export function assembleProse(outline: Outline, prose: ProseDraft): Draft {
  const warnings = [
    ...outline.conflicts,
    ...prose.uncertainties,
    ...prose.conflicts,
    ...(prose.reviewReason ? [prose.reviewReason] : []),
  ];
  const blockers = [
    ...prose.conflicts,
    ...(prose.reviewReason ? [prose.reviewReason] : []),
  ].filter(coreIdentityConcern);
  const entry = {
    ...structuredClone(outline.fixed),
    summary: prose.entry.summary,
    description: prose.entry.description,
    details: prose.entry.details,
    specialEffects: prose.entry.specialEffects,
    notes: prose.entry.notes,
  };
  entry.levels.notes = prose.entry.levels.notes;
  const quantities = (text: string) =>
    [...text.matchAll(/(?<![A-Za-z])[-+]?\d+(?:\.\d+)?/g)].map((m) =>
      Number(m[0]),
    );
  const sameQuantities = (
    original: string,
    rewritten: string,
    label: string,
  ) => {
    const expected = new Set(quantities(original)),
      actual = new Set(quantities(rewritten));
    if (
      [...expected].some((n) => !actual.has(n)) ||
      [...actual].some((n) => !expected.has(n))
    )
      warnings.push(
        "Numerical wording differs from the saved evidence in " +
          label +
          ". Kept the best available explanation.",
      );
  };
  const checkIds = (
    rows: { id: string }[],
    expected: { id: string }[],
    label: string,
  ) => {
    if (
      rows.some((r) => !expected.some((e) => e.id === r.id)) ||
      new Set(rows.map((r) => r.id)).size !== rows.length
    )
      throw Error(
        "Unexpected or duplicate " +
          label +
          " prose slot. Established facts cannot be changed by the writer.",
      );
  };
  checkIds(prose.entry.stats, outline.slots.stats, "stat");
  checkIds(prose.entry.sources, outline.slots.sources, "source");
  checkIds(prose.entry.variants, outline.slots.variants, "variant");
  outline.slots.stats.forEach((slot, i) => {
    const words = prose.entry.stats.find((r) => r.id === slot.id);
    if (!words)
      throw Error("Missing original stat context/notes slot: " + slot.id);
    entry.stats[i].notes = words.notes;
  });
  outline.slots.sources.forEach((slot, i) => {
    const words = prose.entry.sources.find((r) => r.id === slot.id);
    if (!words) {
      warnings.push(
        "Omitted an optional acquisition source whose wording was unresolved: " +
          entry.sources[i].label,
      );
      return;
    }
    words.conditions.forEach((condition, index) =>
      sameQuantities(slot.conditions[index] || "", condition, slot.id),
    );
    words.dropConditions.forEach((condition, index) =>
      sameQuantities(slot.dropConditions[index] || "", condition, slot.id),
    );
    entry.sources[i].notes = words.notes;
    entry.sources[i].conditions = words.conditions.filter(playerCondition);
    if (entry.sources[i].dropChance)
      entry.sources[i].dropChance!.conditions =
        words.dropConditions.filter(playerCondition);
  });
  outline.slots.variants.forEach((slot, i) => {
    const words = prose.entry.variants.find((r) => r.id === slot.id);
    if (!words || !words.description.trim() || !words.differences.length) {
      warnings.push(
        "Omitted an optional variant whose distinctions were unresolved: " +
          entry.variants[i].name,
      );
      return;
    }
    sameQuantities(
      slot.distinctions.join(" "),
      words.description + " " + words.differences.join(" "),
      slot.id,
    );
    entry.variants[i].description = words.description;
    entry.variants[i].differences = words.differences;
  });
  entry.sources = entry.sources.filter((_, i) =>
    prose.entry.sources.some((row) => row.id === outline.slots.sources[i].id),
  );
  entry.variants = entry.variants.filter((_, i) =>
    prose.entry.variants.some(
      (row) =>
        row.id === outline.slots.variants[i].id &&
        row.description.trim() &&
        row.differences.length,
    ),
  );
  const parts = structuredClone(outline.parts);
  for (const ref of entry.parts) {
    const definition = parts.find((d) => d.id === ref.partId)!;
    const words = prose.partDefinitions.find((d) => d.id === ref.partId);
    if (!words) throw Error("Missing original part prose: " + ref.partId);
    definition.name = words.name;
    definition.effects = words.effects;
    definition.notes = words.notes;
    ref.notes =
      prose.entry.parts.find((p) => p.partId === ref.partId)?.notes || "";
  }
  if (
    prose.partDefinitions.some((d) => !parts.some((p) => p.id === d.id)) ||
    prose.entry.parts.some((d) => !parts.some((p) => p.id === d.partId))
  )
    throw Error("Writer returned an unaccepted part.");
  // Parts/stat/source/variant/level slots contain AI prose too. Retain its
  // citations while the values and relationships remain owned by the outline.
  const proseClaimFields = [
    "summary",
    "description",
    "details",
    "specialEffects",
    "notes",
    "parts",
    "stats",
    "sources",
    "variants",
    "levels",
  ];
  const usage = new Map(prose.sourceUsage.map((u) => [u.factId, u]));
  for (const fixed of outline.usage)
    usage.set(fixed.factId, {
      ...fixed,
      fields: [
        ...new Set([
          ...fixed.fields,
          ...(usage.get(fixed.factId)?.fields || []).filter((f) =>
            proseClaimFields.includes(f),
          ),
        ]),
      ],
    });
  const claims = structuredClone(
    prose.claims.filter((c) => proseClaimFields.includes(c.field)),
  );
  for (const fixed of outline.claims) {
    const existing = claims.find((c) => c.field === fixed.field);
    if (existing)
      existing.evidenceIds = [
        ...new Set([...existing.evidenceIds, ...fixed.evidenceIds]),
      ];
    else claims.push(fixed);
  }
  return {
    entry: PublicEntry.parse(entry),
    partDefinitions: parts.map((p) => PartDefinition.parse(p)),
    claims,
    sourceUsage: [...usage.values()],
    uncertainties: [...new Set(warnings)],
    conflicts: blockers,
    requiresReview: blockers.length > 0,
    reviewReason: blockers[0] || null,
    nameDecision: prose.nameDecision,
    evidenceRequests: prose.evidenceRequests,
  };
}
/** No raw graphs, repeated readings, quotes duplicated as details, or ledger bookkeeping. */
export function writingOutline(
  outline: Outline,
  packet: Packet,
  ledger: SourceLedger[],
) {
  return {
    identity: {
      id: packet.familyId,
      name: packet.name,
      category: packet.category,
      character: packet.character,
      element: packet.element,
    },
    fixed: outline.fixed,
    parts: outline.parts.map((part) => ({
      ...part,
      path: partCandidates(packet).find((p) => p.id === part.id)?.path,
    })),
    slots: outline.slots,
    sources: ledger
      .filter((page) => page.chunks.some((chunk) => chunk.facts.length))
      .map((page) => ({
        sourceId: page.sourceId,
        url: page.url,
        title: packet.evidence.find((e) => e.id === page.sourceId)?.label,
        identityContext: String(
          (packet.evidence.find((e) => e.id === page.sourceId)?.value as any)
            ?.text || "",
        ).slice(0, 350),
        selectedContent: page.selectedContent,
        facts: page.chunks.flatMap((c) =>
          c.facts.map((f) => ({
            id: f.id,
            field: f.field,
            role: f.catalogueRole,
            subject: outline.facts.find((n) => n.id === f.id)?.subject,
            appliesTo: f.applicabilityScope
              ? Object.fromEntries(
                  Object.entries(f.applicabilityScope).filter(
                    ([key, value]) =>
                      key === "certain" ||
                      (Array.isArray(value) && value.length),
                  ),
                )
              : null,
            detail: f.detail,
            stat: f.stat,
            structured: f.structured,
            retrieval: f.retrieval,
            ...(f.retrieval || ["manufacturers", "dlc"].includes(f.field)
              ? { quote: f.quote }
              : {}),
            availability: f.relevance?.forced ? "always" : "selected",
            accountedByCode: outline.usage.some((row) => row.factId === f.id),
            structuredDecision: outline.facts.find((n) => n.id === f.id)
              ?.status,
            decisionReason: outline.facts.find((n) => n.id === f.id)?.reason,
          })),
        ),
      })),
    corrections: packet.evidence
      .filter((e) => e.kind === "manual")
      .map((e) => ({ id: e.id, value: e.value })),
    identityEvidence: packet.evidence
      .filter(
        (e) => e.kind === "game" && (e.value as any).role === "family-defining",
      )
      .map((e) => ({
        id: e.id,
        path: e.path,
        class: (e.value as any).class,
        name: (e.value as any).properties?.PartName || null,
      })),
    conflicts: outline.conflicts,
  };
}
