import { z } from "zod";
import { PublicEntry, PartDefinition, Draft } from "./models.ts";
import { NameDecision } from "./names.ts";
import { EvidenceRequest } from "./evidence-requests.ts";
import { ItemDLC } from "./content.ts";
/** Version independently of the public website document. */
export const FACT_POLICY = "5";
export const ApplicabilityScope = z
  .object({
    certain: z.boolean(),
    categories: z.array(z.string()),
    characters: z.array(z.string()),
    elements: z.array(z.string()),
    weaponTypes: z.array(z.string()),
    items: z.array(z.string()),
    skills: z.array(z.string()),
  })
  .strict();
export const StructuredFact = z.discriminatedUnion("kind", [
  z
    .object({
      kind: z.literal("list"),
      field: z.enum(["manufacturers", "rarities", "elements"]),
      values: z.array(z.string().min(1)),
      coverage: z
        .enum(["complete", "partial", "maximum_roll", "unknown"])
        .default("unknown"),
    })
    .strict(),
  z
    .object({
      kind: z.literal("levels"),
      minimum: z.number().int().positive().nullable(),
      maximum: z.number().int().positive().nullable(),
    })
    .strict(),
  z.object({ kind: z.literal("redText"), text: z.string().min(1) }).strict(),
  z
    .object({
      kind: z.literal("source"),
      label: z.string().min(1),
      url: z.string().nullable(),
      kindOfSource: PublicEntry.shape.sources.element.shape.kind,
      location: z.string().nullable(),
      dlc: ItemDLC,
      conditions: z.array(z.string()),
      dropChance: PublicEntry.shape.sources.element.shape.dropChance,
    })
    .strict(),
  z
    .object({
      kind: z.literal("variant"),
      name: z.string().min(1),
      distinctions: z.array(z.string().min(1)).min(1),
    })
    .strict(),
  z
    .object({
      kind: z.literal("part"),
      path: z.string().min(1),
      relationship: PublicEntry.shape.parts.element.shape.relationship,
      name: z.string().min(1),
      slot: PartDefinition.shape.slot,
      manufacturers: z.array(z.string()),
    })
    .strict(),
]);
export type StructuredFact = z.infer<typeof StructuredFact>;
export const FactProvenance = z
  .object({
    evidenceId: z.string(),
    factId: z.string(),
    sourceId: z.string().nullable(),
    url: z.string().nullable(),
    hash: z.string(),
    chunk: z.number().int().nullable(),
    quote: z.string(),
    method: z.enum(["game", "parser", "interpretation", "manual"]),
    policy: z.string(),
  })
  .strict();
export const NormalizedFact = z
  .object({
    id: z.string(),
    subject: z.string(),
    property: z.string(),
    value: z.union([
      StructuredFact,
      z
        .object({
          name: z.string(),
          context: z.string().nullable().optional(),
          minimum: z.number().nullable(),
          maximum: z.number().nullable(),
          unit: z.string(),
          level: z.number().nullable(),
          notes: z.string(),
        })
        .strict(),
      z.string(),
      z.number(),
      z.array(z.string()),
      z.null(),
    ]),
    role: z.string(),
    conditions: z.array(z.string()),
    scope: ApplicabilityScope.nullable(),
    status: z.enum(["candidate", "accepted", "rejected", "conflict"]),
    reason: z.string(),
    provenance: z.array(FactProvenance).min(1),
  })
  .strict();
export type NormalizedFact = z.infer<typeof NormalizedFact>;
/** Only prose and private requests/usage can be returned by the writing model. */
export const ProseDraft = z.object({
  entry: PublicEntry.pick({
    summary: true,
    description: true,
    details: true,
    specialEffects: true,
    notes: true,
  })
    .extend({
      levels: z.object({ notes: z.string() }).default({ notes: "" }),
      stats: z
        .array(
          z.object({
            id: z.string().default(""),
            notes: z.string().default(""),
          }),
        )
        .default([]),
      sources: z
        .array(
          z.object({
            id: z.string().default(""),
            notes: z.string(),
            conditions: z.array(z.string()),
            dropConditions: z.array(z.string()).default([]),
          }),
        )
        .default([]),
      variants: z
        .array(
          z.object({
            id: z.string().default(""),
            description: z.string(),
            differences: z.array(z.string()),
          }),
        )
        .default([]),
      parts: z
        .array(z.object({ partId: z.string(), notes: z.string() }))
        .default([]),
    })
    .strip(),
  partDefinitions: z
    .array(
      z.object({
        id: z.string(),
        name: z.string(),
        effects: z.array(z.string()),
        notes: z.array(z.string()),
      }),
    )
    .default([]),
  claims: Draft.shape.claims.default([]),
  sourceUsage: Draft.shape.sourceUsage,
  nameDecision: NameDecision.nullable().default(null),
  evidenceRequests: z.array(EvidenceRequest).max(3).default([]),
  uncertainties: z.array(z.string()),
  conflicts: z.array(z.string()),
  requiresReview: z.boolean(),
  reviewReason: z.string().nullable(),
});
export type ProseDraft = z.infer<typeof ProseDraft>;
/** Null means unchanged. Corrections cannot return structured item fields. */
export const ProsePatch = z.object({
  entry: z.object(
    Object.fromEntries(
      Object.entries(ProseDraft.shape.entry.shape).map(([name, schema]) => [
        name,
        (schema as z.ZodType).nullable().default(null),
      ]),
    ),
  ),
  partDefinitions: ProseDraft.shape.partDefinitions.nullable().default(null),
  claims: ProseDraft.shape.claims.nullable().default(null),
  sourceUsage: ProseDraft.shape.sourceUsage.nullable().default(null),
  uncertainties: ProseDraft.shape.uncertainties.nullable().default(null),
  conflicts: ProseDraft.shape.conflicts.nullable().default(null),
  requiresReview: z.boolean().nullable().default(null),
  reviewReason: z.string().nullable().default(null),
});
