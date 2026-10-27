import { z } from "zod";
export const MANUAL_TEXT_ORIGIN = "https://manual.borderlens.invalid/evidence/";
export const isManualTextUrl = (url?: string | null) =>
  !!url?.startsWith(MANUAL_TEXT_ORIGIN);
export const ManualTextInput = z
  .object({
    label: z.string().trim().max(160).optional(),
    text: z
      .string()
      .trim()
      .min(1, "Paste some evidence text first.")
      .max(100000),
  })
  .strict();
