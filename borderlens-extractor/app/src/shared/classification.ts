import { z } from "zod";
import { weaponTypes } from "./taxonomy.ts";
export const ClassificationEvidence = z
  .object({
    id: z.string(),
    url: z.string(),
    title: z.string(),
    quote: z.string(),
    hash: z.string(),
  })
  .strict();
export const ClassificationOverride = z
  .object({
    name: z.string(),
    weaponType: z.enum(weaponTypes),
    reason: z.string().min(1),
    verifiedAt: z.string(),
    evidence: z.array(ClassificationEvidence),
  })
  .strict();
export type ClassificationOverride = z.infer<typeof ClassificationOverride>;
export type EffectiveClassification = ClassificationOverride & {
  origin: "manual" | "research";
};
export const ClassificationFile = z
  .object({
    schemaVersion: z.literal(1),
    entries: z.record(
      z.string(),
      z
        .object({
          manual: ClassificationOverride.optional(),
          research: ClassificationOverride.optional(),
        })
        .strict(),
    ),
  })
  .strict();
export type ClassificationFile = z.infer<typeof ClassificationFile>;
export const ClassificationDecision = z
  .object({
    weaponType: z.enum(weaponTypes).nullable(),
    identityVerified: z.boolean(),
    availability: z.enum(["obtainable", "cut", "unknown"]),
    reason: z.string().min(1),
    evidence: z
      .array(
        z
          .object({ id: z.string(), quote: z.string().min(8).max(600) })
          .strict(),
      )
      .max(5),
    conflicts: z.array(z.string()),
  })
  .strict();
