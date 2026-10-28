import { z } from "zod";

export const Sources = z.object({
  lootlemon: z.url().optional(),
  wiki: z.url().optional(),
})