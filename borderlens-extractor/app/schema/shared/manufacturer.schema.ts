import { z } from "zod";

export const Manufacturer = z.enum([
  "anshin",
  "atlas",
  "dahl",
  "eridian",
  "gearbox",
  "hyperion",
  "jakobs",
  "maliwan",
  "pangolin",
  "ss-munitions",
  "tediore",
  "torgue",
  "vladof",
]);
