import { z } from "zod";

import { Base } from "./base.schema";

export const Weapon = Base.extend({

})

export type Weapon = z.infer<typeof Weapon>;