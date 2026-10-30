import { z } from "zod";

export const Game = z.enum([
  "borderlands",
  "borderlands-goty",
  "borderlands-goty-enhanced",
]).describe("Borderlands 1 release this item belongs to: original, GOTY, or GOTY Enhanced. Other games in the series will be supported later.");
