import { z } from "zod";

import { String } from "../utils/index"
import { Element } from "./element.schema"

export const SpecialEffects = z.object({
  red: z.object({
    title: String.line,
    description: z.array(String.line),
    self: z.boolean().default(false)
  }).optional().describe("Special red text on unique Borderlands weapons, generally legendary and above. `self` is true when the effect applies to the player, and false when it applies to enemies. Omit when the item has none."),
  elemental: z.array(z.object({
    element: Element.exclude(["none"]),
    description: z.array(String.line).min(1),
    self: z.boolean().default(false)
  })).optional().describe("Elemental effects only, such as splash damage or any other elemental effect that fits. `self` is true when the effect applies to the player, and false when it applies to enemies. Omit when the item has none."),
  status: z.array(z.object({
    title: String.line,
    description: z.array(String.line).min(1),
    self: z.boolean().default(false)
  })).optional().describe("Status effects the item can apply. `self` is true when the effect applies to the player, and false when it applies to enemies. Omit when the item has none."),
  other: z.array(z.object({
    title: String.line,
    description: z.array(String.line).optional(),
    self: z.boolean().default(false)
  })).optional().describe("Other or miscellaneous flavour text, not the red text. For example, the Carnage shotgun's white text: \"Holy crap! It shoots rockets\". `self` is true when the effect applies to the player, and false when it applies to enemies. Omit when the item has none.")
}).optional()