import { z } from "zod";

import { Base, Category, SubCategories } from "../shared/index";
import { Array } from "../utils/index"

export const Weapon = Base.extend({
  category: z.object({
    primary: Category.extract(["weapon"]),
    secondary: SubCategories.Weapon
  }),
  stats: z.object({
    damage: Array.DoubleTuple,
    accuracy: Array.DoubleTuple,
    fireRate: Array.DoubleTuple,
    magazine: Array.DoubleTuple,
  })
});

export type Weapon = z.infer<typeof Weapon>;
