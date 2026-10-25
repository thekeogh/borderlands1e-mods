import type { Family, Source } from "../shared/models.ts";
import type { ClassificationOverride } from "../shared/classification.ts";
import { itemSlug } from "../shared/website.ts";
import { providerForUrl } from "../shared/research.ts";
const clean = (s: string) =>
  s
    .normalize("NFKD")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
/** An item-specific BL1 route AND matching typed title establish category;
 * navigation text, search results and generic source pages cannot. */
export function equipmentCategoryCandidate(
  f: Family,
  pages: Source[],
): ClassificationOverride | null {
  if (
    f.category !== "Other equipment" ||
    f.status === "excluded" ||
    f.supersededBy ||
    f.classification?.origin === "manual"
  )
    return null;
  const candidates: ClassificationOverride[] = [];
  for (const page of pages) {
    if (providerForUrl(page.url) !== "Lootlemon") continue;
    const path = new URL(page.url).pathname.replace(/\/$/, "");
    const route = /^\/(shield|grenade-mod)\/([^/]+)-bl1$/i.exec(path);
    if (
      !route ||
      ![f.name, ...f.aliases].some(
        (name) => itemSlug(name) === route[2].toLowerCase(),
      )
    )
      continue;
    const category =
      route[1].toLowerCase() === "shield" ? "Shields" : "Grenade mods";
    const title = clean(page.title),
      term = category === "Shields" ? "shield" : "grenade";
    if (
      !/\bbl1\b/.test(title) ||
      !new RegExp(`\\b${term}\\b`).test(title) ||
      ![f.name, ...f.aliases].some((name) =>
        title.startsWith(clean(name) + " "),
      )
    )
      continue;
    candidates.push({
      name: f.name,
      category,
      weaponType: null,
      reason: `The saved item-specific BL1 Lootlemon route and matching article title identify this family as ${category.toLowerCase()}.`,
      verifiedAt: new Date().toISOString(),
      evidence: [
        {
          id: page.id,
          url: page.url,
          title: page.title,
          quote: page.title,
          hash: page.hash,
        },
      ],
    });
  }
  if (new Set(candidates.map((c) => c.category)).size !== 1) return null;
  return candidates[0] || null;
}
