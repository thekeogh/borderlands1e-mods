import { z } from "zod";

import { Content } from "./shared/content.schema";
import { Game } from "./shared/game.schema";
import { Category } from "./shared/category.schema";
import { SubCategory } from "./shared/sub-category.schema";
import { Sources } from "./shared/sources.schema";

export const Base = z.object({
  versions: z.object({
    schema: z.int().positive(),
    compiler: z.stringFormat("semver", /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/),
    revision: z.int().positive().default(1),
  }),
  sources: Sources,
  id: z.string(),
  game: Game,
  content: Content,
  category: Category,
  subCategory: SubCategory,
  name: z.string(),
  slug: z.stringFormat("slug", /^[a-z0-9]+(?:-[a-z0-9]+)*$/),
})