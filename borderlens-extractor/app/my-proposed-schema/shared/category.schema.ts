import { z } from "zod";

export const Category = z.enum([
  "artifacts",
  "class-mods",
  "grenade-mods",
  "shields",
  "weapons",
  "other"
]);
