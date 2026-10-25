import { PartDefinition, type PublicEntry } from "../shared/models.ts";
import { itemSlug } from "../shared/website.ts";
import { WEBSITE_SCHEMA_VERSION } from "../shared/versions.ts";
import { acquisitionSources } from "../shared/acquisition.ts";
import { cleanPublicEntry } from "../shared/public-cleanup.ts";
import { validateWebsiteDocument } from "../shared/final-document.ts";
/** Assemble exactly the self-contained document consumed by the website. */
export function assembleWebsiteEntry(
  entry: PublicEntry,
  definitions: PartDefinition[],
  slug = itemSlug(entry.name),
  image: string | null = null,
  revision = 1,
) {
  const output = cleanPublicEntry(entry);
  const parts = output.parts.map((ref) => {
    const definition = definitions.find((def) => def.id === ref.partId);
    if (!definition)
      throw new Error("Missing inline part definition: " + ref.partId);
    const { schemaVersion, compilerVersion, ...part } =
      PartDefinition.parse(definition);
    return {
      ...part,
      relationship: ref.relationship,
      familyNotes: ref.notes.trim() || undefined,
    };
  });
  const { references, ...publicOutput } = output;
  return validateWebsiteDocument({
    ...publicOutput,
    sources: acquisitionSources(output.sources),
    levels: {
      ...output.levels,
      notes: output.levels.notes.trim() || undefined,
    },
    stats: output.stats.map((stat) => ({
      ...stat,
      notes: stat.notes.trim() || undefined,
      unit: /^(unspecified|unknown|not specified)$/i.test(stat.unit.trim())
        ? ""
        : stat.unit,
    })),
    schemaVersion: WEBSITE_SCHEMA_VERSION,
    revision,
    slug,
    image,
    parts,
  });
}
