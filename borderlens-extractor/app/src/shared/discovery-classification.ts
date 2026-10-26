import { z } from "zod";
import { weaponTypes } from "./taxonomy.ts";
export const DiscoveryClassification = z
  .object({
    weaponType: z.enum(weaponTypes).nullable(),
    identityVerified: z.boolean(),
    availability: z.enum(["obtainable", "cut", "unknown"]),
    identityPaths: z.array(z.string()).max(8),
    reason: z.string().min(1),
    evidence: z
      .array(
        z
          .object({
            url: z.string(),
            title: z.string(),
            quote: z.string().min(8).max(600),
          })
          .strict(),
      )
      .max(5),
    conflicts: z.array(z.string()),
  })
  .strict();
export type DiscoveryClassification = z.infer<typeof DiscoveryClassification>;
