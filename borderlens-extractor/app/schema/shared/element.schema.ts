import { z } from "zod";

export const Element = z.enum([
  "none",
  "incendiary",
  "corrosive",
  "shock",
  "explosive",
]);
