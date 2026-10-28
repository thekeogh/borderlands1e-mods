/** Semantic roles travel with saved facts; they are not additional public fields. */
export const catalogueMeaningInstruction =
  "STRUCTURED INTERPRETATION: Also return structured for each fact when an explicit supported property can be represented: lists of manufacturers/rarities/elements with coverage complete only for an explicit exhaustive/fixed set, partial for confirmed possibilities, maximum_roll for a maximum-roll tier label, or unknown; whole-family level bounds; exact redText; acquisition with canonical label, kindOfSource, real source URL or null, location, acquisition DLC, raw private condition meanings and scoped dropChance; meaningful named variant with distinctions (its actual version name must appear literally in the quote, never invent a heading for ranks or reward groups; unnamed distinctions remain details); or a part with an exact original game path or part identifier only when present literally in the supplied text. The app resolves identifiers only against unique captured candidates; never invent a full path. Use null for structured when uncertain or merely narrative. Acquisition source URLs may be the original saved article URL, never a manual/internal URL. Numeric item facts continue to use stat, with context distinguishing explicit conditions or quantities (Card, While scoped, Team bonus, multiplier, or null when unspecified); do not duplicate them in structured. Do not infer missing level bounds, examples as extrema, a maximum-roll label as exclusive rarity, or parts absent from evidence. Conditions/distinctions here are private facts, not final prose. CATALOGUE MEANING: Every extracted fact has catalogueRole: item_property for an actual family property (including a published family range), general_mechanic for shared damage/skill/system rules, illustrative_example for a sample roll/build/card/price, part_property for a component modifier, progression for ordinal ranks/levels or stronger-replaces-weaker rules alone, descriptive_label for origin/lore/type terminology that establishes no maker. Do not confuse applicability selectors with this presentation role: a rule can apply to this item without being its stat. Classify from the original quote/context, never from a desired output field. Numeric general_mechanic, illustrative_example, part_property and progression facts must not become stats[] or family level bounds; keep useful scoped explanations in details/parts, or omit unhelpful examples with a reason. Only item_property numeric facts become stats[]; preserve genuine published item ranges and all distinct item-specific quantities. Examples cannot establish family minima/maxima. manufacturers means an explicitly established producer, not species/civilization, technology, material, category, loot source or a descriptive adjective. Extract manufacturerNames only for an explicit maker relationship naming the producer in the supporting quote, otherwise []. Extract origin only when this exact item's introduction/content pack is established: Base Game or a canonical expansion, otherwise null. A DLC drop location, equip requirement, page game label or absence of a DLC prefix is not origin proof. Preserve known origins, prefer exact extracted identity facts, and never leave an established Base Game origin null. variants requires meaningful evidenced differences in abilities, fixed configuration, requirements or acquisition; ranks/levels alone or stronger/replaces-lower prose belong together in a progression details section. Do not pad variants with one entry per ordinal step. An individually supported rank-specific acquisition/ability can be explained compactly without inventing a distinct named variant. Always include controls availability, never an obligation to publish every fact. Empty arrays and nulls are correct when unsupported; never fill fields from names alone.";

/** Resolve only like-for-like cross-source disagreements; retain complementary facts. */
export const sourcePriorityInstruction =
  "SOURCE PRIORITY: Use ALL saved sources. When verified Lootlemon and Wiki facts directly contradict each other about the SAME item, edition, attribute, roll scope and conditions, choose Lootlemon. This applies to rarity, stats, timers, mechanics, manufacturers and acquisition. Retain the rejected Wiki fact privately as sourceUsage disposition overridden, with duplicateOf pointing to the exact USED Lootlemon fact ID and reason explaining the same-scope contradiction and priority decision. Do not publish the rejected alternative or source-dispute commentary. Resolved disagreements MUST NOT appear in conflicts[], requiresReview or reviewReason. Do not manufacture conflicts: a maximum-roll Epic label and a supported broader set of legal rarity tiers, card bonuses and actual per-second rates, different player counts, editions, levels and variants may be complementary; retain all applicable scoped facts. Do not discard unrelated Wiki details, mechanics or trivia. Explicit user corrections and captured family identity/restrictions remain authoritative; do not use speculative raw constants to reverse a like-for-like Lootlemon-over-Wiki decision. A conflict within one provider or unsupported identity/edition match remains reviewable. Never invent a preferred fact or treat an unverified page about another item/game as authoritative.";

/** Shared-site tips are not item-family catalogue facts. Keep raw captures intact. */
export const catalogueScopeInstruction =
  "Applicable category-wide equipment rules (for example legal rarity tiers and skill-bonus combinations) are relevant to this family; retain them with their scope and check family-specific exceptions. Include only facts specific to this item family: properties, mechanics, meaningful strengths/tradeoffs, variants, parts, acquisition requirements and item-specific quirks. EXCLUDE generic farming guides, suggested routes, fast-travel/respawn instructions, timing runs, movement/kill-speed advice, general loot-quality/luck explanations, navigation, ads and repeated site-wide tips. Do not rewrite those tips into item notes, descriptions or details. Notes describe this item's own quirks, not a how-to guide. Item-specific drop locations, drop probabilities and acquisition conditions remain useful. Mark already-extracted generic advice irrelevant in sourceUsage; full-source reading never means publishing every piece of boilerplate.";
export const catalogueQualityInstruction =
  "PUBLIC QUALITY: Use natural player language everywhere, including parts and stat notes. Do not publish raw part/material identifiers (such as sight4_Jakobs_Bessie or acc4_Heavy), numbered engine scope labels, Zoom End FOV constants, or title-link/extraction explanations. Explain stronger magnification plainly; keep the raw constant privately. Preserve useful human-facing modifier numbers and signs in the relevant part.effects as well as mechanics: for example a scope's +30% damage belongs on that scope, never as a weapon-card damage range. Do not reuse a known part definition if its effects omit supported numeric modifiers; enrich it with cited facts. Differentiate card and scoped stats with stats[].context (for example Card or While scoped), keeping the stat name/range intact. Use units only when established by the evidence; never assume an accuracy rating is a percentage. Use rounds for an established magazine round count and rounds/second only if firing-rate units are established. Keep unknown units empty and unknown contexts null. elements MUST use the canonical labels Non-elemental, Incendiary, Shock, Corrosive, Explosive (or an empty array when unknown); never use None, fire or lowercase aliases. Stat notes must add factual context, not repeat the structured numbers/units. Use clear contexts such as Scope multiplier instead of scale. Do not use vague phrases such as standard scopes compared with it; say the supported property plainly without inventing a baseline. Do not repeat edition conditions at source and rate levels, or textual player counts already represented by players. Acquisition rates must keep edition, player-count and other conditions separate; dropChance.players is 1–4 only when explicitly established, otherwise null. Do not choose the highest probability or collapse solo and multiplayer values. Resolve conflicting rates with identical conditions privately, never arbitrarily. Avoid repeating whole sentences/facts across description, details and notes; summary and short specialEffects may recap key abilities. Put detailed arithmetic in mechanics, practical identity in description, and unique quirks in notes. Omit vague numerical damage/one-shot benchmarks whose character, skills, class mod or target requirements cannot be specified from evidence; account for those facts privately as irrelevant with the precise missing setup. Do not replace missing setup with phrases like 'with a suitable build'. Unknown bounds stay null; leave absent optional note text empty rather than adding filler. For class mods, a Lootlemon Epic label does not prove Epic is the only available rarity: combine supported generic class-mod rarity rules with the actual family selection rules and respect fixed-rarity exceptions. Preserve all supported obtainable tiers. Distinguish an ammo-regeneration card bonus with no per-second unit (context Card bonus) from weapon-specific per-second rates. If a source says displayed rates are maxima, label those contexts Team [weapon type] (maximum rate) and do not present them as guaranteed values. Describe solo and team benefits without implying that team bonuses exclude the wearer or that ammo regeneration is useless alone. All human-readable sentences must be original AI wording, never copied or assembled from source sentences.";

export class UnclearPublicProse extends Error {
  constructor(
    public passage: string,
    public instruction: string,
  ) {
    super(instruction);
  }
}
export function publicQualityIssue(text: string): string | null {
  if (
    /\b(?:scopes?|optics?)\b.{0,60}\bcompared (?:with|to|against) it\b/i.test(
      text,
    )
  )
    return "Vague comparison: describe the supported scope property plainly; omit the unnamed comparison baseline rather than inventing one.";
  if (
    /\bon the (?:Enhanced|original)(?: edition)? listing\b|\blisted original-game\b/i.test(
      text,
    )
  )
    return "Research wording: state the item fact and its edition directly; omit references to listings or compilation.";
  if (
    /\b(?:sight|acc|barrel|body|stock|mag|grip)\d+_[\w]+|\bMaterial_[\w]+|\b[\w]+_Material\b|\b(?:sight|scope)[45]\b|Zoom End FOV|\btitles the .{0,60}family\b/i.test(
      text,
    )
  )
    return "Replace internal part names, scope constants and title-link wording with player-facing descriptions; retain technical evidence privately.";
  if (
    /(?:suitable|appropriate|right|certain) (?:character|skills?|class mod|build)|with (?:some|enough|the right) (?:skills?|bonuses|gear)/i.test(
      text,
    ) &&
    /\d[\d,]*\s*(?:damage|%|percent)|one[ -]shot|single (?:shot|hit)/i.test(
      text,
    )
  )
    return "Numerical/one-shot benchmark lacks explicit build requirements; specify the evidenced setup or omit the benchmark.";
  return null;
}
export function sourceExclusionReason(text: string): string | null {
  return (
    genericAdviceReason(text) ||
    (/Zoom End FOV/i.test(text)
      ? "Internal field-of-view constant; keep privately, describe magnification in player language."
      : null) ||
    (publicQualityIssue(text)?.startsWith("Numerical/")
      ? "Damage benchmark lacks reproducible build requirements."
      : null)
  );
}
export function genericAdviceReason(text: string): string | null {
  const value = text.replace(/\s+/g, " ").toLowerCase();
  if (
    /(?:last|recently|most recent).{0,100}fast[ -]?travel.{0,120}(?:spawn|respawn)|fast[ -]?travel.{0,100}(?:set|determin|restart|respawn|spawn point)/i.test(
      value,
    )
  )
    return "Generic fast-travel/respawn advice";
  if (
    /combin\w* nearby loot|(?:time|timing|timed|compar\w*).{0,35}(?:routes?|runs?)|(?:farm\w*|loot).{0,50}(?:routes?|per session)|(?:shortcuts?).{0,100}(?:faster kills|kill\w* faster|travel.{0,15}combat|farming|loot opportunities)|movement speed.{0,100}(?:farming|loot opportunities)|(?:reduc\w*|minimi\w*).{0,30}(?:travel|combat) time/.test(
      value,
    )
  )
    return "Generic farming/route optimisation advice";
  if (
    /(?:loot sources?|loot quality|rarity).{0,80}awesome level|awesome level.{0,90}of (?:loot|higher-rarity)|catalyst.{0,12}scavenger.{0,100}(?:class mods?|awesome level)/.test(
      value,
    )
  )
    return "Generic loot-quality advice";
  return null;
}
export function publicPassages(value: unknown): string[] {
  if (typeof value === "string") return [value];
  if (Array.isArray(value)) return value.flatMap(publicPassages);
  if (value && typeof value === "object")
    return Object.entries(value)
      .filter(([key]) => !["references", "redText"].includes(key))
      .flatMap(([, value]) => publicPassages(value));
  return [];
}
