import { z } from "zod";
export const EvidenceRequest = z
  .object({
    topic: z.string().trim().min(1).max(160),
    terms: z.array(z.string().trim().min(2).max(60)).min(1).max(6),
    reason: z.string().trim().min(1).max(400),
  })
  .strict();
export type EvidenceRequest = z.infer<typeof EvidenceRequest>;
