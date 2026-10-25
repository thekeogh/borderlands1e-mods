import { assembleWebsiteEntry } from "./final-entry.ts";
import { serializeWebsiteDocument } from "../shared/final-document.ts";
import AdmZip from "adm-zip";
import { Store, HttpError } from "./store.ts";
import { PublicEntry, PartDefinition, type Family } from "../shared/models.ts";
import { WebsiteEntry, itemSlug, categoryFolders } from "../shared/website.ts";
import { catalogueGroup } from "../shared/taxonomy.ts";
function readyItems(store: Store) {
  return store.state.families.filter(
    (f) =>
      !f.supersededBy &&
      f.status === "done" &&
      PublicEntry.safeParse(store.get(f.id, "output")).success,
  );
}
function exportSlugs(items: Family[]) {
  const result = new Map<string, string>(),
    used = new Set<string>();
  for (const f of items) {
    const folder = categoryFolders[f.category],
      base = itemSlug(f.name);
    const group = items.filter(
      (other) => other.category === f.category && itemSlug(other.name) === base,
    );
    let slug = base;
    if (group.length > 1) {
      slug += "-" + itemSlug(f.character || catalogueGroup(f));
      if (
        group.filter(
          (other) =>
            (other.character || catalogueGroup(other)) ===
            (f.character || catalogueGroup(f)),
        ).length > 1
      )
        slug += "-" + f.id.slice(-6);
    }
    if (used.has(folder + "/" + slug)) slug = base + "-" + f.id;
    let suffix = 2;
    const initial = slug;
    while (used.has(folder + "/" + slug)) slug = initial + "-" + suffix++;
    used.add(folder + "/" + slug);
    result.set(f.id, slug);
  }
  return result;
}
export function websiteEntry(
  store: Store,
  f: Family,
  slug = exportSlugs(readyItems(store)).get(f.id) || itemSlug(f.name),
  refreshImages = true,
): WebsiteEntry | null {
  if (refreshImages) store.images.refresh();
  const parsed = PublicEntry.safeParse(store.get(f.id, "output"));
  if (!parsed.success) return null;
  const output = parsed.data,
    local = store.get<PartDefinition[]>(f.id, "parts") || [];
  const definitions = output.parts
    .map(
      (ref) =>
        local.find((part) => part.id === ref.partId) ||
        store.get<any>("_parts", ref.partId)?.definition,
    )
    .filter(Boolean);
  try {
    return assembleWebsiteEntry(
      output,
      definitions,
      slug,
      store.images.match(f).image,
      Math.max(1, f.revision),
    );
  } catch (error: any) {
    throw new HttpError(
      409,
      "Final JSON validation failed for " + f.name + ": " + error.message,
    );
  }
}
export function websiteZip(store: Store) {
  const ready = readyItems(store);
  if (!ready.length)
    throw new HttpError(
      409,
      "No completed current-schema items are ready to export. Build an item first.",
    );
  store.images.refresh();
  const zip = new AdmZip(),
    slugs = exportSlugs(ready);
  for (const f of ready) {
    const slug = slugs.get(f.id)!;
    const filename = categoryFolders[f.category] + "/" + slug + ".json";
    zip.addFile(
      filename,
      Buffer.from(
        serializeWebsiteDocument(websiteEntry(store, f, slug, false)),
      ),
    );
  }
  return zip.toBuffer();
}
