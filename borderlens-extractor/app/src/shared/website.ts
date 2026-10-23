import { z } from "zod";
import { PublicEntry, PartDefinition } from "./models.ts";
export const InlinePart = PartDefinition.omit({
  schemaVersion: true,
  compilerVersion: true,
})
  .extend({
    relationship: z.enum(["defining", "required", "possible"]),
    familyNotes: z.string(),
  })
  .strict();
// Public website format is self-contained. Compiler storage stays normalized v2.
export const WebsiteEntry = PublicEntry.extend({
  schemaVersion: z.literal("3"),
  slug: z.string().regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/),
  parts: z.array(InlinePart),
}).strict();
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
