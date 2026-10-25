import { ImagePath } from "./images.ts";
import { WEBSITE_SCHEMA_VERSION } from "./versions.ts";
import { z } from "zod";
import { PublicEntry, PartDefinition } from "./models.ts";
const Note = z.string().trim().min(1).optional();
export const AcquisitionSource = PublicEntry.shape.sources.element
  .omit({
    dropChance: true,
    notes: true,
  })
  .extend({
    notes: Note,
    label: z.string().trim().min(1),
    conditions: z.array(z.string().trim().min(1)),
    dropChances: z.array(
      z
        .object({
          percent: z.number().min(0).max(100),
          players: z.number().int().min(1).max(4).nullable(),
          conditions: z.array(z.string().min(1)),
        })
        .strict(),
    ),
  })
  .strict();
export const InlinePart = PartDefinition.omit({
  schemaVersion: true,
  compilerVersion: true,
})
  .extend({
    relationship: z.enum(["defining", "required", "possible"]),
    familyNotes: Note,
  })
  .strict();
// Public website format is self-contained. Compiler storage stays normalized.
export const WebsiteEntry = PublicEntry.omit({ references: true })
  .extend({
    schemaVersion: z.literal(WEBSITE_SCHEMA_VERSION),
    revision: z.number().int().positive(),
    image: ImagePath.nullable(),
    slug: z.string().regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/),
    parts: z.array(InlinePart),
    sources: z.array(AcquisitionSource),
    levels: PublicEntry.shape.levels.extend({ notes: Note }),
    stats: z.array(PublicEntry.shape.stats.element.extend({ notes: Note })),
  })
  .strict();
export type WebsiteEntry = z.infer<typeof WebsiteEntry>;
export function itemSlug(name: string) {
  return (
    name
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/['’]/g, "")
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "") || "item"
  );
}
export const categoryFolders = {
  Weapons: "weapons",
  Shields: "shields",
  "Class mods": "class-mods",
  "Grenade mods": "grenade-mods",
  Artifacts: "artifacts",
  "Other equipment": "other-equipment",
} as const;
