import { sourceKey, type InheritedEvidence } from "./research";
import { storedTextBytes } from "./source-size";
export function evidenceSizeTotals(
  direct: { url: string; text: string }[],
  inherited: InheritedEvidence[],
  pendingUrls: string[] = [],
) {
  const included = { bytes: 0, count: 0, missing: 0 },
    auto = { bytes: 0, count: 0, missing: 0 },
    seen = new Set<string>();
  for (const row of inherited) {
    const key = sourceKey(row.url);
    if (seen.has(key)) continue;
    seen.add(key);
    const mode = row.inclusionMode || (row.alwaysInclude ? "always" : "auto");
    if (mode === "never") continue;
    const total = mode === "always" ? included : auto;
    total.count++;
    if (row.textBytes == null) total.missing++;
    else total.bytes += row.textBytes;
  }
  for (const row of direct) {
    const key = sourceKey(row.url);
    if (seen.has(key)) continue;
    seen.add(key);
    included.count++;
    included.bytes += storedTextBytes(row.text);
  }
  for (const url of pendingUrls) {
    const key = sourceKey(url);
    if (seen.has(key)) continue;
    seen.add(key);
    included.count++;
    included.missing++;
  }
  return { included, auto };
}
