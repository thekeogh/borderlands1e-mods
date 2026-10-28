import { z } from "zod";
export const BackupUI = z
  .object({
    selection: z.string().max(500),
    groups: z.record(z.string(), z.boolean()),
    tab: z.enum(["preview", "game-data", "sources", "history", "json"]),
    view: z.enum(["catalogue", "coverage", "activity"]),
    query: z.string().max(1000),
    filter: z.string().max(100),
  })
  .strict();
export type BackupUI = z.infer<typeof BackupUI>;
export const backupFilename = (date = new Date()) => {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}_${pad(date.getHours())}-${pad(date.getMinutes())}.zip`;
};
