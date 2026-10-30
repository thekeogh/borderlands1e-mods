import { z } from "zod";

export const Rarity = z.enum([
  "common",
  "uncommon",
  "rare",
  "epic",
  "legendary",
  "pearlescent",
]);
