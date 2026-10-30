import { z } from "zod";

import { Aliases } from "./aliases.schema";
import { Content } from "./content.schema";
import { Game } from "./game.schema";
import { Sources } from "./sources.schema";
import { Versions } from "./versions.schema";
import { Manufacturer } from "./manufacturer.schema";
import { Rarity } from "./rarity.schema";
import { Element } from "./element.schema";
import { SpecialEffects } from "./special-effects.schema";
import { Modifiers } from "./modifiers.schema";
import { String } from "../utils/index"

export const Base = z.object({
  versions: Versions,
  id: z.string(),
  game: z.array(Game).min(1),
  content: Content,
  sources: Sources,
  aliases: Aliases,
  tags: z.array(z.string()).describe("Search keywords only. Indexed by the search engine (Fuse.js initially), not shown as item content."),
  name: z.string(),
  summary: String.line.describe("Brief one-line prose summary of the item."),
  description: z.array(String.line).min(1).describe("Full prose description of the item. One or more lines, no length limit."),
  slug: z.stringFormat("slug", /^[a-z0-9]+(?:-[a-z0-9]+)*$/).describe("Slug of this item's name only. Do not include numbers, ids, types, or other qualifiers. Duplicates are fine; the app also uses type and game to disambiguate."),
  manufacturers: z.array(Manufacturer).min(1),
  rarities: z.array(Rarity).min(1),
  elements: z.array(Element).describe("[] never spawns with an element. Include 'None' when it can spawn without one."),
  specialEffects: SpecialEffects,
  modifiers: Modifiers
})
