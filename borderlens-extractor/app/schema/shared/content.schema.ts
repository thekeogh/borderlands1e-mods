import { z } from "zod";

export const Content = z.enum([
  "base",
  "bl-zombie-dlc",
  "bl-moxxis-underdome-dlc",
  "bl-knoxx-dlc",
  "bl-robot-revolution-dlc"
]).describe("Content pack the item comes from: the base game or a named DLC.");