import type { DiscoveryClassification } from "../shared/discovery-classification.ts";
import type { Family } from "../shared/models.ts";
import { catalogueGroup } from "../shared/taxonomy.ts";
import { sourceKey } from "../shared/research.ts";
import { sourceQuoteMatches } from "./source-analysis.ts";
import { sourceUrl } from "./research.ts";
import { Store, hash } from "./store.ts";
const key = (value: string) => value.toLowerCase().replace(/[^a-z0-9]+/g, "");
const typeWords: Record<string, RegExp> = {
  "Combat rifles": /combat rifles?|assault rifles?|support machine guns?/i,
  "Repeater pistols":
    /repeater pistols?|machine pistols?|semi.automatic pistols?/i,
  Revolvers: /revolvers?/i,
  "Rocket launchers": /rocket launchers?/i,
  Shotguns: /shotguns?/i,
  SMGs: /submachine guns?|\bsmgs?\b/i,
  "Sniper rifles": /sniper rifles?/i,
  "Eridian weapons": /eridian (?:weapons?|guns?)/i,
};
export function applyDiscoveryClassification(
  store: Store,
  f: Family,
  result: {
    classification: DiscoveryClassification | null;
    matches: {
      url: string;
      title: string;
      gameEvidence: string;
      reason: string;
    }[];
  },
) {
  const decision = result.classification;
  if (
    !decision ||
    f.category !== "Weapons" ||
    catalogueGroup(f) !== "Needs review" ||
    store.classifications.data.entries[f.id]?.manual
  )
    return false;
  store.put(f.id, "discoveryClassification", decision);
  const reject = (reason: string) => {
    f.classificationReview = reason;
    store.save();
    return false;
  };
  if (
    !f.roots.length ||
    f.roots.every((root) => /gd_weap_names_shared\./i.test(root))
  )
    return reject(
      "Shared naming modifiers are not verified standalone item families.",
    );
  if (
    f.roots.some((root) =>
      /prototype|(?:^|[._:/-])(?:unused|cut|beta|test)(?:[._:/-]|$)/i.test(
        root,
      ),
    )
  )
    return reject(
      "This extracted identity may be a test, cut or prototype definition; inspect it before classification.",
    );
  if (
    !decision.identityVerified ||
    decision.availability !== "obtainable" ||
    !decision.weaponType ||
    decision.conflicts.length
  )
    return reject([decision.reason, ...decision.conflicts].join(" "));
  const roots = new Set(f.roots.map((root) => root.toLowerCase()));
  if (!decision.identityPaths.some((path) => roots.has(path.toLowerCase())))
    return reject(
      "Discovery did not corroborate an extracted identity for this exact candidate.",
    );
  const names = [f.name, ...f.aliases].map(key).filter(Boolean),
    citations = [];
  for (const citation of decision.evidence) {
    const match = result.matches.find(
      (match) => sourceKey(match.url) === sourceKey(citation.url),
    );
    if (
      !match ||
      store.isSourceExcluded(f.id, citation.url) ||
      store.sourceInclusionMode(f.id, citation.url) === "never"
    )
      continue;
    let decodedUrl: string;
    try {
      sourceUrl(citation.url);
      decodedUrl = decodeURIComponent(citation.url);
    } catch {
      continue;
    }
    if (
      /borderlands[_\s-]*[234](?!\d)|-bl[234]\b|pre.?sequel|wonderlands/i.test(
        decodedUrl + " " + citation.title + " " + match.gameEvidence,
      )
    )
      continue;
    if (
      !names.some((name) =>
        key(citation.title + " " + citation.quote).includes(name),
      ) ||
      !typeWords[decision.weaponType]?.test(citation.quote)
    )
      continue;
    if (
      /\bis (?:an? )?(?:cut|unused|unobtainable|prototype)|not obtainable|cannot be obtained|removed from/i.test(
        citation.quote,
      )
    )
      continue;
    const saved = store.cachedSource(citation.url);
    if (saved && !sourceQuoteMatches(saved.text, citation.quote)) continue;
    citations.push({
      id:
        "discovery:" +
        hash(sourceKey(citation.url) + "|" + citation.quote).slice(0, 20),
      url: citation.url,
      title: citation.title,
      quote: citation.quote,
      hash: hash(citation.quote),
    });
  }
  if (!citations.length)
    return reject(
      "No verified BL1 item-page quotation establishes this candidate's identity and weapon type.",
    );
  store.classifications.set(f.id, "research", {
    name: f.name,
    category: "Weapons",
    weaponType: decision.weaponType,
    reason: decision.reason,
    verifiedAt: new Date().toISOString(),
    verification: "discovery",
    evidence: citations,
  });
  delete f.classificationReview;
  store.save();
  return true;
}
