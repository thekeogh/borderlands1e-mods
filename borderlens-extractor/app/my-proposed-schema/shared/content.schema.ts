import { z } from "zod";

export const Content = z.enum([
  "Base Game",
  "The Zombie Island of Dr. Ned",
  "Mad Moxxi's Underdome Riot",
  "The Secret Armory of General Knoxx",
  "Claptrap's New Robot Revolution"
]);