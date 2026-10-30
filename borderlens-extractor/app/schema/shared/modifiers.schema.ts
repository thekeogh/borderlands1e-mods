import { z } from "zod";

import { Element } from "./element.schema";
import { Array } from "../utils/index"

export const Modifiers = z.object({
  projectileCount: z.object({
    range: Array.DoubleTuple,
  }).optional().describe("Projectile count, including shotgun pellets. Shown beside damage as `x{N}`. Does not always match ammo consumed; Bone Shredder is always x2."),
  elementMultiplier: z.object({
    element: Element.exclude(["none"]),
    range: Array.DoubleTuple,
  }).optional().describe("The weapon's elemental effect rating, linked to the hidden tech system and elemental procs. Shown as `x{N}` next to the elemental effect icon. Usually a minimum of 1 to a maximum of 4.")
}).optional()
