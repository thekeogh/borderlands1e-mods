import { z } from "zod";

import { Aliases } from "./aliases.schema";
import { Content } from "./content.schema";
import { Game } from "./game.schema";
import { Sources } from "./sources.schema";
import { Versions } from "./versions.schema";
import { Manufacturer } from "./manufacturer.schema";
import { Rarity } from "./rarity.schema";

export const Base = z.object({
  versions: Versions,
  id: z.string(),
  game: Game,
  content: Content,
  sources: Sources,
  name: z.string(),
  slug: z.stringFormat("slug", /^[a-z0-9]+(?:-[a-z0-9]+)*$/),
  alias: Aliases,
  tags: z.array(z.string()),
  manufacturers: z.array(Manufacturer),
  rarities: z.array(Rarity),
})
