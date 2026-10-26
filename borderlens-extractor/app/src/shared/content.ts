import { z } from "zod";
/** Item origin, independent of where a particular copy can drop. */
export const contentPacks = [
  "Base Game",
  "The Zombie Island of Dr. Ned",
  "Mad Moxxi's Underdome Riot",
  "The Secret Armory of General Knoxx",
  "Claptrap's New Robot Revolution",
] as const;
export const ItemDLC = z.enum(contentPacks).nullable();
export type ItemDLC = z.infer<typeof ItemDLC>;
