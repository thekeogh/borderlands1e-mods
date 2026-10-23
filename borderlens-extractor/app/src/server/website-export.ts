import AdmZip from "adm-zip";
import { Store, HttpError } from "./store.ts";
import { PublicEntry, PartDefinition, type Family } from "../shared/models.ts";
import { WebsiteEntry, itemSlug, categoryFolders } from "../shared/website.ts";
import { catalogueGroup } from "../shared/taxonomy.ts";
function readyItems(store: Store) {
  return store.state.families.filter(
    (f) =>
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
      slug += "-" + itemSlug(catalogueGroup(f));
      if (
        group.filter((other) => catalogueGroup(other) === catalogueGroup(f))
          .length > 1
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
): WebsiteEntry | null {
  const parsed = PublicEntry.safeParse(store.get(f.id, "output"));
  if (!parsed.success) return null;
  const output = parsed.data,
    local = store.get<PartDefinition[]>(f.id, "parts") || [];
  const parts = output.parts.map((ref) => {
    const definition =
      local.find((part) => part.id === ref.partId) ||
      store.get<any>("_parts", ref.partId)?.definition;
    if (!definition)
      throw new HttpError(
        409,
        "Missing part data; rebuild " + f.name + " before exporting.",
      );
    const { schemaVersion, compilerVersion, ...part } =
      PartDefinition.parse(definition);
    return { ...part, relationship: ref.relationship, familyNotes: ref.notes };
  });
  return WebsiteEntry.parse({ ...output, schemaVersion: "3", slug, parts });
}
export function websiteZip(store: Store) {
  const ready = readyItems(store);
  if (!ready.length)
    throw new HttpError(
      409,
      "No completed current-schema items are ready to export. Build an item first.",
    );
  const zip = new AdmZip(),
    slugs = exportSlugs(ready);
  for (const f of ready) {
    const slug = slugs.get(f.id)!;
    const filename = categoryFolders[f.category] + "/" + slug + ".json";
    zip.addFile(
      filename,
      Buffer.from(JSON.stringify(websiteEntry(store, f, slug), null, 2) + "\n"),
    );
  }
  return zip.toBuffer();
}
