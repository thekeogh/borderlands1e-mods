import { z } from "zod";

const Id = z.enum([
  "damage",
  "fire-rate",
  "recoil",
  "elemental-level",
  "accuracy",
  "max-accuracy",
  "max-inaccuracy",
  "spread",
  "reload-speed",
  "equip-speed",
  "mag-size",
  "swap-speed"
])

const Modifier = z.object({
  id: Id,
  type: z.enum(["string", "number"]),
  name: z.string(),
  value: z.number(),
})

export const Parts = (z.object({
  body: z.array(z.object({
    name: z.string(),
    modifiers: z.array(Modifier)
  }))
})