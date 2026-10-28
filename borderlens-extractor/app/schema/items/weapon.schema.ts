import { z } from "zod";

import { Base, Category, SubCategories } from "../shared/index";

export const Weapon = Base.extend({
  category: Category.extract(["weapon"]),
  subCategory: SubCategories.Weapon
})

export type Weapon = z.infer<typeof Weapon>;
