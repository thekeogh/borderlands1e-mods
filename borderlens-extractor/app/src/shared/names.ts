import { z } from "zod";
export const NameDecision = z
  .object({
    name: z.string().trim().min(1).max(160),
    identityVerified: z.boolean(),
    availability: z.enum(["obtainable", "cut", "unknown"]),
    identityPaths: z.array(z.string()).max(8),
    reason: z.string().min(1),
    conflicts: z.array(z.string()),
    evidence: z
      .array(
        z
          .object({ id: z.string(), quote: z.string().min(8).max(600) })
          .strict(),
      )
      .min(1)
      .max(5),
    corroboration: z
      .array(
        z
          .object({
            kind: z.enum([
              "weaponType",
              "manufacturer",
              "element",
              "character",
              "definingPart",
            ]),
            id: z.string(),
            quote: z.string().min(8).max(600),
          })
          .strict(),
      )
      .min(1)
      .max(5),
  })
  .strict();
export type NameDecision = z.infer<typeof NameDecision>;
export const ManualItemName = z
  .string()
  .trim()
  .min(1)
  .max(160)
  .refine(
    (value) => !/[\u0000-\u001f\u007f]/.test(value),
    "Enter a single-line item name.",
  );
export const NameOverride = z
  .object({
    origin: z.enum(["manual", "research"]).default("research"),
    identityName: z.string().optional(),
    identityAliases: z.array(z.string()).optional(),
    corroboration: z.array(NameDecision.shape.corroboration.element),
    name: z.string().trim().min(1).max(160),
    originalName: z.string(),
    reason: z.string(),
    verifiedAt: z.string(),
    evidence: z.array(
      z
        .object({
          id: z.string(),
          url: z.string(),
          quote: z.string(),
          hash: z.string(),
        })
        .strict(),
    ),
    identityPaths: z.array(z.string()),
  })
  .strict()
  .refine(
    (value) => value.origin === "manual" || value.corroboration.length > 0,
    "Research names need corroborating evidence.",
  );
export type NameOverride = z.infer<typeof NameOverride>;
export const NameFile = z
  .object({
    schemaVersion: z.literal(1),
    entries: z.record(z.string(), NameOverride),
  })
  .strict();
