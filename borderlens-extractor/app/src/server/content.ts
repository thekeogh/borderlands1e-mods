import basePackages from "./base-content-packages.json";
import { contentPacks, type ItemDLC } from "../shared/content.ts";
import type { Family, Raw } from "../shared/models.ts";
const baseContentPackages = new Set(basePackages);
/** Only this family's original identity roots establish package origin. Linked loot graphs don't. */
export function extractedContent(
  f: Pick<Family, "roots">,
  records: Map<string, Raw>,
): { dlc: ItemDLC; paths: string[] } {
  const origins = new Map<ItemDLC, string[]>();
  for (const root of f.roots) {
    const record = records.get(root.toLowerCase());
    if (!record || !/Definition$/.test(record.class || ""))
      return { dlc: null, paths: [] };
    const match = /^dlc([1-4])_/i.exec(record.path);
    const packageName = record.path.split(".")[0].toLowerCase();
    const dlc = match
      ? contentPacks[Number(match[1])]
      : baseContentPackages.has(packageName)
        ? "Base Game"
        : null;
    // Unknown/mod packages never become Base Game merely because they lack DLC prefixes.
    if (!dlc) return { dlc: null, paths: [] };
    origins.set(dlc, [...(origins.get(dlc) || []), root]);
  }
  if (origins.size !== 1) return { dlc: null, paths: [] };
  const [dlc, paths] = [...origins][0];
  return { dlc, paths };
}
