import { z } from "zod";

export const Category = z.enum([
  "artifact",
  "class-mod",
  "grenade-mod",
  "shield",
  "weapon",
  "other"
]);
