import { z } from "zod";

export const Versions = z.object({
  schema: z.int().positive(),
  compiler: z.stringFormat("semver", /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/),
  revision: z.int().positive().default(1),
})