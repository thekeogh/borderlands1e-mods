import { NameDecision } from "./names.ts";
import { z } from "zod";
import { Category } from "./models.ts";
import { weaponTypes } from "./taxonomy.ts";
export const TypeSyncDecision = z
  .object({
    category: Category.nullable(),
    weaponType: z.enum(weaponTypes).nullable(),
    identityVerified: z.boolean(),
    availability: z.enum(["obtainable", "cut", "unknown"]),
    confidence: z.enum(["high", "uncertain"]),
    identityPaths: z.array(z.string()).max(8),
    reason: z.string().min(1),
    conflicts: z.array(z.string()),
    contextNotes: z.array(z.string()).default([]),
    evidence: z
      .array(
        z
          .object({ id: z.string(), quote: z.string().min(8).max(600) })
          .strict(),
      )
      .max(5),
  })
  .strict();
export type IdentitySyncState = {
  familyId: string;
  target: "type" | "name";
  message: string;
};
export type IdentitySyncResult = { changed: boolean; message: string };

export const NameSyncResponse = z
  .object({ decision: NameDecision.nullable() })
  .strict();
