import { z } from "zod";

export const DoubleTuple = z.union([
  z.tuple([z.number()]),
  z.tuple([z.number(), z.number()]),
]);