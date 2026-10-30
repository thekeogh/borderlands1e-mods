import { z } from "zod";

import { Base, Category, SubCategories } from "../shared/index";

export const Weapon = Base.extend({
  category: z.object({
    primary: Category.extract(["weapon"]),
    secondary: SubCategories.Weapon
  })
})

export type Weapon = z.infer<typeof Weapon>;
