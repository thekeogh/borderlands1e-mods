import { z } from "zod";

export const DoubleTuple = z.union([
  z.tuple([z.int()]),
  z.tuple([z.int(), z.int()]),
]);