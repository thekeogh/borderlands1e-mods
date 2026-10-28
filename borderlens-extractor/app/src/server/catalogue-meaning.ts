import { familyStat } from "./fact-semantics.ts";
import type { Draft, Packet } from "../shared/models.ts";
import type { SourceLedger, SourceReading } from "./source-analysis.ts";
const normalize = (value: string) => value.trim().toLowerCase();
/** Reject malformed attribution while the source reader can still repair its reading. */
export function validateFactMeaning(fact: SourceReading["facts"][number]) {
  const structured = fact.structured;
  if (structured) {
    const field =
      structured.kind === "list"
        ? structured.field
        : (
            {
              levels: "levels",
              redText: "redText",
              source: "sources",
              variant: "variants",
              part: "parts",
            } as const
          )[structured.kind];
    if (
      structured.kind === "list" &&
      structured.field === "manufacturers" &&
      structured.values.some(
        (name) =>
          !(fact.manufacturerNames || []).some(
            (known) => normalize(known) === normalize(name),
          ),
      )
    )
      throw Error(
        "Structured manufacturer lists must use only explicitly attributed producer names from this same fact.",
      );
    if (
      structured.kind === "list" &&
      structured.field === "elements" &&
      structured.values.some(
        (value) =>
          !/^(Non-elemental|Incendiary|Shock|Corrosive|Explosive)$/i.test(
            value,
          ),
      )
    )
      throw Error(
        "Use canonical supported element labels; unrelated-game elements and unknown labels are not this item's properties.",
      );
    if (
      structured.kind === "part" &&
      !normalize(fact.quote).includes(normalize(structured.path))
    )
      throw Error(
        "Part identifiers must appear literally in the supporting source quote. Return structured null when no captured identifier can be established; never invent a path.",
      );
    if (
      structured.kind === "variant" &&
      !normalize(fact.quote).includes(normalize(structured.name))
    )
      throw Error(
        "A structured variant requires its actual version name in the supporting quote. Do not invent names for progression/reward groups; keep useful distinctions in details instead.",
      );
    if (field !== fact.field)
      throw Error(
        "Structured fact payload must match its quoted fact field; do not mix acquisition, variants, levels or property lists.",
      );
    if (
      structured.kind === "levels" &&
      structured.minimum !== null &&
      structured.maximum !== null &&
      structured.minimum > structured.maximum
    )
      throw Error("Structured level bounds are reversed.");
    if (
      ["illustrative_example", "progression", "descriptive_label"].includes(
        fact.catalogueRole || "",
      )
    )
      throw Error(
        "Examples, progression and labels are narrative evidence; structured must be null rather than a family-wide property.",
      );
  }
  if (
    fact.manufacturerNames?.length &&
    (fact.field !== "manufacturers" ||
      fact.catalogueRole !== "item_property" ||
      fact.manufacturerNames.some(
        (name) => !normalize(fact.quote).includes(normalize(name)),
      ))
  )
    throw Error(
      "manufacturerNames requires an item_property manufacturer fact whose exact quote names each explicit producer; labels and unrelated names are not maker evidence.",
    );
  if (
    fact.origin &&
    (fact.field !== "dlc" || fact.catalogueRole !== "item_property")
  )
    throw Error(
      "origin belongs only to an item_property dlc fact establishing item introduction, never a drop-location or general-rule fact.",
    );
}
/** Validate semantic placement, never guess or silently rewrite public values. */
export function validateCatalogueMeaning(
  draft: Draft,
  ledger: SourceLedger[],
  packet: Packet,
  warn?: (message: string) => void,
) {
  const advisory = (error: Error) => {
    if (warn) warn(error.message);
    else throw error;
  };
  for (const page of ledger)
    for (const chunk of page.chunks)
      for (const fact of chunk.facts) validateFactMeaning(fact);
  const used = ledger.flatMap((page) =>
    page.chunks.flatMap((chunk) =>
      chunk.facts.flatMap((fact) => {
        const usage = draft.sourceUsage.find(
          (row) => row.factId === fact.id && row.disposition === "used",
        );
        return usage ? [{ fact, usage, sourceId: page.sourceId }] : [];
      }),
    ),
  );
  const itemFacts = used.filter(
    ({ fact }) => fact.catalogueRole === "item_property",
  );
  const makerClaimIds = new Set(
    draft.claims
      .filter((claim) => claim.field === "manufacturers")
      .flatMap((claim) => claim.evidenceIds),
  );
  const supportedMakers = new Set(
    (packet.facts?.manufacturers || []).map(normalize),
  );
  for (const { fact, usage, sourceId } of itemFacts) {
    if (
      fact.field !== "manufacturers" ||
      !usage.fields.includes("manufacturers") ||
      !makerClaimIds.has(sourceId)
    )
      continue;
    for (const name of fact.manufacturerNames || []) {
      if (!normalize(fact.quote).includes(normalize(name)))
        throw Error(
          "Manufacturer attribution must name its producer in the original supporting quote.",
        );
      supportedMakers.add(normalize(name));
    }
  }
  for (const name of draft.entry.manufacturers || []) {
    // Explicit user corrections remain authoritative; an unrelated raw/page claim does not.
    const manual = packet.evidence.some(
      (e) =>
        e.kind === "manual" &&
        makerClaimIds.has(e.id) &&
        normalize(JSON.stringify(e.value)).includes(normalize(name)),
    );
    if (!supportedMakers.has(normalize(name)) && !manual)
      throw Error(
        "Manufacturer needs an explicit producer relationship in an item-property source fact or defining game data; descriptive labels are not manufacturers. Leave unsupported manufacturers empty.",
      );
  }
  const origins = new Set(
    itemFacts
      .filter(({ fact }) => fact.field === "dlc" && fact.origin)
      .map(({ fact }) => fact.origin!),
  );
  const expectedOrigin =
    packet.facts?.dlc || (origins.size === 1 ? [...origins][0] : null);
  const manualOrigin = packet.evidence.some(
    (e) =>
      e.kind === "manual" &&
      draft.claims.some(
        (claim) => claim.field === "dlc" && claim.evidenceIds.includes(e.id),
      ) &&
      draft.entry.dlc &&
      normalize(JSON.stringify(e.value)).includes(normalize(draft.entry.dlc)),
  );
  if (draft.entry.dlc && !expectedOrigin && !manualOrigin && origins.size === 0)
    throw Error(
      "Item origin needs an explicit item-origin source fact or exact extracted origin. A game label or DLC acquisition source is not proof; leave origin null when unknown.",
    );
  if (expectedOrigin && draft.entry.dlc !== expectedOrigin)
    throw Error(
      "An established item origin must be preserved, including Base Game. Use exact extracted origin first, then the explicitly supported item-origin fact; drop locations do not change origin.",
    );
  if (origins.size > 1 && !packet.facts?.dlc)
    advisory(
      new Error(
        "Conflicting item origins require source-priority resolution before publication.",
      ),
    );
  for (const { fact, usage } of used) {
    if (!fact.catalogueRole) continue; // Historical test/manual ledgers; new compiler readings always carry roles.
    if (!familyStat(fact, packet) && fact.stat) {
      if (usage.fields.some((field) => field === "stats" || field === "levels"))
        throw Error(
          "General mechanics, examples, component values and progression must not become item stats or level bounds. Explain useful scoped facts in details/parts instead.",
        );
      const promoted = (draft.entry.stats || []).some(
        (stat) =>
          normalize(stat.name) === normalize(fact.stat!.name) &&
          stat.minimum === fact.stat!.minimum &&
          stat.maximum === fact.stat!.maximum &&
          stat.unit === fact.stat!.unit &&
          stat.level === fact.stat!.level,
      );
      const supported = itemFacts.some(
        ({ fact: other }) =>
          other.stat &&
          normalize(other.stat.name) === normalize(fact.stat!.name) &&
          other.stat.minimum === fact.stat!.minimum &&
          other.stat.maximum === fact.stat!.maximum &&
          other.stat.unit === fact.stat!.unit &&
          other.stat.level === fact.stat!.level,
      );
      if (promoted && !supported)
        throw Error(
          "A non-item numeric fact was promoted to an item stat. Keep its original scope in explanatory text.",
        );
    }
    if (
      ["progression", "illustrative_example", "descriptive_label"].includes(
        fact.catalogueRole,
      ) &&
      usage.fields.includes("variants")
    )
      advisory(
        new Error(
          "Ordinal progression, examples and labels alone do not establish meaningful variants. Combine progression into a details section; retain variants only for evidenced substantive differences.",
        ),
      );
    if (
      fact.catalogueRole !== "item_property" &&
      usage.fields.includes("manufacturers")
    )
      throw Error(
        "Descriptive/general/example terminology cannot establish an item manufacturer.",
      );
  }
}
