import { z } from "zod";

export const Character = z.enum([
  "brick",
  "lilith",
  "mordecai",
  "roland",
]);
