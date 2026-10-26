import { z } from "zod";
import { weaponTypes } from "./taxonomy.ts";
export const equipmentTypes = [
  "Shields",
  "Class mods",
  "Grenade mods",
  "Artifacts",
  "Other equipment",
] as const;
export const ManualType = z
  .enum([...weaponTypes, ...equipmentTypes])
  .nullable();
export type ManualType = z.infer<typeof ManualType>;
