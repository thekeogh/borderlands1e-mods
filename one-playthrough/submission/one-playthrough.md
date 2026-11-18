---
pyproject_url: https://raw.githubusercontent.com/thekeogh/borderlands1e-mods/main/one-playthrough/Source/sdk_mods/OnePlaythrough/pyproject.toml
mod_categories: gameplay enemy overhaul
---

# One Playthrough

Play Borderlands GOTY Enhanced from level 1 to 69 in one continuous journey,
without restarting the story in another playthrough.

Enemy levels and missions follow your character while keeping their
vanilla minimums: dangerous areas stay dangerous until you catch up. Leave
missions for later and their levels keep pace, even after acceptance or finishing
their objectives. Equipment rewards, XP and cash use the mission level at turn-in,
preserving higher vanilla levels. Gaining a level from that payout does not change
its remaining rewards. Existing unpaid missions adopt this automatically.
Choose Easy, Medium (default), Hard or Very Hard for ordinary enemies. Each keeps native
variety and the higher of your level and the vanilla area level, with different
chances of tougher spawns. New ordinary enemies spawn at least one level above you;
Easy rolls +1/+2 at 40%/60%; Medium rolls +2/+3 at 60%/40%; Hard rolls +3/+4 at 80%/20%, and Very Hard
rolls +3/+4/+5 at 20%/75%/5%, retaining naturally higher ordinary levels. The
choice is saved and affects new spawns only.
Named enemies and bosses have no random roll: exactly your level +2 on Easy/Medium,
+3 on Hard and +4 on Very Hard, overriding higher native levels.
**Adaptive** is an additional saved difficulty: smoothly blend ordinary bonuses
between player-level anchors 5/15/25/35/45/55/65, from +1/+2 at 20%/80% to
+3/+4/+5 at 20%/75%/5%. Small fractional chances are retained. Higher native
ordinary levels remain protected; existing spawns stay unchanged. Adaptive bosses
are fixed at player +2 through level 22, +3 through 52 and +4 from 53. Select
Adaptive and reload the area; Medium remains the default.
An additional **Debug** option for mod testing puts supported hostile enemies,
including bosses and hostile vehicles, at your level minus 30 (minimum 1),
bypassing normal level floors. Reload the area after changing modes. Medium
remains the default; Debug is saved until you change it.
Enemies exactly five levels above you use the native skull warning on their
health bar. This is cosmetic; their levels and combat rules are unchanged.
The optional loot level floor targets new world drops, containers and vendor
stock at least at your level for all equipment (minimum level 1). Rarity and legendary chances stay vanilla. Carried enemy equipment receives the floor when dropped on death. Existing player
equipment stays unchanged; mission rewards follow the mission level at turn-in. Economy follows the game's normal rules.

Scaling covers the main story and all four DLCs: The Zombie Island of Dr. Ned,
Mad Moxxi's Underdome Riot, The Secret Armory of General Knoxx and Claptrap's
New Robot Revolution, without first completing any DLC to enable scaling.
Reaching level 69 depends on how much XP you earn.

## Getting started

1. Install the BL1 PythonSDK mod manager for GOTY Enhanced.
2. Drop `OnePlaythrough.sdkmod` into the game's `sdk_mods` folder.
3. Enable **One Playthrough** in the Mods menu, choose **New Game** and play
   through the full introduction normally.
4. Use **Continue** next time with the mod enabled. Stay in the first playthrough
   to finish remaining missions and DLCs after the story.

For **GOTY Enhanced only**. Designed for solo play; co-op is unverified. Disable
other enemy or mission scaling mods.

Based on the original Playthrough 3 by **RedxYeti and Miner Of Worlds**.
One Playthrough by **keogh**.

[Full instructions and source](https://github.com/thekeogh/borderlands1e-mods/tree/main/one-playthrough)
