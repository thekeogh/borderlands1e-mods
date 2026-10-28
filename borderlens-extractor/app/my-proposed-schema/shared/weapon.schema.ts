import { z } from "zod";

export const Weapon = z.enum([
  "combat-rifle",
  "eridian-weapon",
  "repeater-pistol",
  "revolver",
  "rocket-launcher",
  "shotgun",
  "smg",
  "sniper-rifle",
]);
