import { NameDecision, type NameOverride } from "./names.ts";
import { ItemDLC } from "./content.ts";
import { DiscoveryClassification } from "./discovery-classification.ts";
import { EvidenceRequest } from "./evidence-requests.ts";
import type { EvidenceScope } from "./evidence-scopes.ts";
import { CATALOGUE_SCHEMA_VERSION, COMPILER_VERSION } from "./versions.ts";
import type { EffectiveClassification } from "./classification.ts";
import { z } from "zod";
export const Stage = z.enum([
  "evidence",
  "sources",
  "draft",
  "validate",
  "complete",
]);
export type Stage = z.infer<typeof Stage>;
export const stages: Stage[] = [
  "evidence",
  "sources",
  "draft",
  "validate",
  "complete",
];
export const Category = z.enum([
  "Weapons",
  "Shields",
  "Grenade mods",
  "Class mods",
  "Artifacts",
  "Other equipment",
]);
export type Category = z.infer<typeof Category>;
export const PartDefinition = z
  .object({
    schemaVersion: z.literal("1"),
    compilerVersion: z.literal(COMPILER_VERSION),
    id: z.string().regex(/^part-[a-f0-9]{16}$/),
    name: z.string().min(1),
    slot: z.enum([
      "barrel",
      "body",
      "grip",
      "magazine",
      "accessory",
      "sight",
      "stock",
      "material",
      "action",
      "other",
    ]),
    manufacturers: z.array(z.string()),
    effects: z.array(z.string()),
    notes: z.array(z.string()),
  })
  .strict();
export type PartDefinition = z.infer<typeof PartDefinition>;
export const Element = z.enum([
  "Non-elemental",
  "Incendiary",
  "Shock",
  "Corrosive",
  "Explosive",
]);
export const PublicEntry = z
  .object({
    schemaVersion: z.literal(CATALOGUE_SCHEMA_VERSION),
    compilerVersion: z.literal(COMPILER_VERSION),
    id: z.string(),
    name: z.string().min(1),
    dlc: ItemDLC.default(null),
    category: Category,
    weaponType: z.string().nullable(),
    character: z.enum(["Roland", "Lilith", "Mordecai", "Brick"]).optional(),
    summary: z.string().min(15).max(200),
    description: z.array(z.string().min(20).max(6000)).min(1).max(30),
    details: z
      .array(
        z
          .object({
            heading: z.string().min(1),
            paragraphs: z.array(z.string().min(1)).min(1),
          })
          .strict(),
      )
      .default([]),
    variants: z.array(
      z
        .object({
          name: z.string().min(1),
          description: z.string().min(1),
          differences: z.array(z.string()),
        })
        .strict(),
    ),
    parts: z.array(
      z
        .object({
          partId: z.string().regex(/^part-[a-f0-9]{16}$/),
          relationship: z.enum(["defining", "required", "possible"]),
          notes: z.string(),
        })
        .strict(),
    ),
    manufacturers: z.array(z.string()),
    rarities: z.array(z.string()),
    elements: z.array(Element),
    redText: z.string().nullable(),
    specialEffects: z.array(z.string()),
    levels: z.object({
      minimum: z.number().int().positive().nullable(),
      maximum: z.number().int().positive().nullable(),
      notes: z.string(),
    }),
    stats: z.array(
      z.object({
        name: z.string().trim().min(1),
        context: z.string().min(1).nullable().default(null),
        minimum: z.number().nullable(),
        maximum: z.number().nullable(),
        unit: z.string(),
        level: z.number().int().positive().nullable(),
        notes: z.string(),
      }),
    ),
    sources: z.array(
      z.object({
        label: z.string(),
        url: z.string().nullable(),
        kind: z.enum(["world_drop", "vendor", "quest", "enemy", "other"]),
        notes: z.string(),
        location: z.string().nullable(),
        dlc: z.string().nullable(),
        conditions: z.array(z.string()),
        dropChance: z
          .object({
            percent: z.number().min(0).max(100),
            players: z.number().int().min(1).max(4).nullable().default(null),
            conditions: z.array(z.string().min(1)),
          })
          .strict()
          .nullable(),
      }),
    ),
    notes: z.array(z.string()),
    references: z.array(
      z.object({ label: z.string(), url: z.string() }).strict(),
    ),
  })
  .strict();
export type PublicEntry = z.infer<typeof PublicEntry>;
export const Draft = z
  .object({
    nameDecision: NameDecision.nullable().optional(),
    evidenceRequests: z.array(EvidenceRequest).max(3).optional(),
    entry: PublicEntry,
    partDefinitions: z.array(PartDefinition),
    claims: z.array(
      z
        .object({
          field: z.enum([
            "dlc",
            "summary",
            "description",
            "details",
            "variants",
            "parts",
            "manufacturers",
            "rarities",
            "elements",
            "redText",
            "specialEffects",
            "levels",
            "stats",
            "sources",
            "notes",
          ]),
          evidenceIds: z.array(z.string()).min(1),
          basis: z.string().min(1),
        })
        .strict(),
    ),
    sourceUsage: z
      .array(
        z
          .object({
            factId: z
              .string()
              .describe(
                "Exact extracted PAGE FACT id from ALL SOURCE FACTS; never a game:, manual: or page-level evidence id.",
              ),
            disposition: z.enum([
              "used",
              "duplicate",
              "overridden",
              "irrelevant",
              "conflict",
            ]),
            fields: z.array(z.string()),
            reason: z.string().min(1),
            duplicateOf: z
              .string()
              .nullable()
              .describe(
                "For duplicate: used equivalent fact ID. For overridden: used Lootlemon fact ID that supersedes the contradictory Wiki fact. Otherwise null.",
              ),
          })
          .strict(),
      )
      .default([]),
    uncertainties: z.array(z.string()),
    conflicts: z.array(z.string()),
    requiresReview: z.boolean(),
    reviewReason: z.string().nullable(),
  })
  .strict();
export type Draft = z.infer<typeof Draft>;
// Model-facing structured outputs require every object property. The compiler
// supplies the authoritative character; older saved/public entries may omit it.
export const WriterDraft = Draft.extend({
  nameDecision: NameDecision.nullable().default(null),
  evidenceRequests: Draft.shape.evidenceRequests.unwrap().default([]),
  entry: PublicEntry.extend({
    character: PublicEntry.shape.character.unwrap().nullable().default(null),
  }),
});
export const SourceMatches = z
  .object({
    classification: DiscoveryClassification.nullable().default(null),
    matches: z
      .array(
        z
          .object({
            url: z.string(),
            title: z.string(),
            gameEvidence: z.string(),
            reason: z.string(),
          })
          .strict(),
      )
      .max(4),
    notFoundReason: z.string().nullable(),
  })
  .strict();
export type Raw = {
  id: string;
  record_type: string;
  path: string;
  class?: string;
  name?: string;
  properties?: Record<string, unknown>;
  [key: string]: unknown;
};
export type History = { at: string; stage: string; message: string };
export type Family = {
  evidenceScope?: EvidenceScope;
  urlDiscovery?: {
    status: "complete" | "failed";
    at: string;
    issue: string | null;
  };
  id: string;
  name: string;
  rawName?: string;
  nameOverride?: NameOverride;
  category: Category;
  subtype: string;
  rawCategory?: Category;
  rawSubtype?: string;
  character?: "Roland" | "Lilith" | "Mordecai" | "Brick";
  element?: z.infer<typeof Element>;
  discoveryVersion?: number;
  supersededBy?: string[];
  classification?: EffectiveClassification;
  classificationReview?: string;
  aliases: string[];
  roots: string[];
  status: "queued" | "running" | "blocked" | "done" | "excluded";
  stage: Stage;
  inputHash: string;
  issue: string | null;
  notes: string;
  gameOnly: boolean;
  sourceUrls: string[];
  history: History[];
  updatedAt: string;
  manualOutput: boolean;
  revision: number;
  compiledSchemaVersion?: string;
  compiledCompilerVersion?: string;
};
export type Capture = {
  id: string;
  name: string;
  version: string;
  importedAt: string;
  objects: number;
  manifest: Record<string, unknown>;
};
export type Source = {
  manualText?: boolean;
  selectedContent?: { boxes: number; warnings: number };
  inheritedFrom?: { id: string; name: string };
  reusedFrom?: { id: string; name: string };
  id: string;
  familyId: string;
  url: string;
  title: string;
  fetchedAt: string;
  hash: string;
  text: string;
  filename: string;
  imported: boolean;
  captureMethod?: "chrome";
  error?: string;
  contentVersion?: number;
  sections?: { heading: string; text: string }[];
  tables?: { caption: string; headers: string[]; rows: string[][] }[];
};
export type Evidence = {
  id: string;
  kind: "game" | "page" | "manual";
  label: string;
  path?: string;
  value: unknown;
};
export type Packet = {
  character?: Family["character"];
  element?: Family["element"];
  familyId: string;
  name: string;
  category: Category;
  subtype: string;
  evidence: Evidence[];
  warnings: string[];
  facts: {
    dlc?: import("./content.ts").ItemDLC;
    redText: string | null;
    manufacturers: string[];
    rarities: string[];
    elements: string[];
  };
};
export type CoverageEntry = {
  key: string;
  name: string;
  category: string;
  url: string;
  source: string;
  game: string;
  status: "matched" | "missing_extraction" | "ambiguous" | "excluded";
  familyIds: string[];
  reason: string;
};
export type BatchSourceMode = "saved" | "fresh" | "auto";
export type Run = {
  cancelRequested?: boolean;
  mode?: "build" | "discover";
  scope?: EvidenceScope;
  rebuildAll?: boolean;
  continueOnError?: boolean;
  sourceMode: BatchSourceMode;
  sourcePrepared: string[];
  status: "idle" | "running" | "pausing" | "paused" | "blocked" | "complete";
  queue: string[];
  index: number;
  currentId: string | null;
  message: string;
  startedAt: string | null;
  deferred: string[];
  pendingFrom: string | null;
  pauseRequested: boolean;
};
export type Settings = {
  agent: "grok" | "codex";
  model: string;
  writingStyle: string;
  research: boolean;
  maxItems: number;
};
export type Project = {
  evidenceStats?: import("./evidence-stats.ts").EvidenceStats;
  identitySync?: import("./identity-sync.ts").IdentitySyncState | null;
  schemaVersion: 1;
  revision: number;
  families: Family[];
  captures: Capture[];
  run: Run;
  buildCheckpoint?: Run;
  sharedScopes?: Family[];
  settings: Settings;
  coverage: {
    status: "idle" | "running" | "complete" | "partial" | "failed";
    message: string;
    updatedAt: string | null;
    entries: CoverageEntry[];
    errors: string[];
  };
  activity: History[];
};
export const now = () => new Date().toISOString();
export const initial = (): Project => ({
  schemaVersion: 1,
  revision: 0,
  families: [],
  captures: [],
  run: {
    sourceMode: "saved",
    sourcePrepared: [],
    status: "idle",
    queue: [],
    index: 0,
    currentId: null,
    message: "Import an extractor ZIP to begin.",
    startedAt: null,
    deferred: [],
    pendingFrom: null,
    pauseRequested: false,
  },
  settings: {
    agent: "grok",
    model: "",
    writingStyle:
      "Clear, concise player reference. Explain what makes the item useful and its tradeoffs. Natural original prose, no hype or engine jargon.",
    research: true,
    maxItems: 10000,
  },
  coverage: {
    status: "idle",
    message: "No external inventory scanned yet.",
    updatedAt: null,
    entries: [],
    errors: [],
  },
  activity: [],
});

export {
  researchProviders,
  providerForUrl,
  type ResearchProvider,
  type ResearchReport,
} from "./research.ts";
