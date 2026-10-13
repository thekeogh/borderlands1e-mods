# Playthrough 3

**Version 3.0.0 · Author: keogh · Borderlands GOTY Enhanced**

A resettable third playthrough for a **level-69 character**: tougher enemies,
all four DLCs, and level-1 cash prices and rewards.

## Install

Requires the [BL1 PythonSDK mod manager](https://bl-sdk.github.io/willow1-mod-db/).

1. Close the game.
2. Extract `dist/Playthrough3-Level1Economy-BL1E-3.0.0.zip` into your game folder.
   It installs `sdk_mods/Playthrough 3.sdkmod` and
   `WillowGame/CookedPC/Mods/PT3/gd_GameStages_PT3.upk`.
3. Keep **one** PT3 SDK mod. Remove an older unpacked `Playthrough 3` folder from
   `sdk_mods` when replacing it with the archive.
4. Restart, enable **Playthrough 3** and select it in the difficulty menu.

Already have the PT3 UPK installed? Replace only `sdk_mods/Playthrough 3.sdkmod`
with the file in `dist`. Keep the UPK.

PT3 requires playthrough 2 completion. For an older completed save that does not
show PT3, the original mod's unlock procedure is to set **Playthrough 2 Unlocked**
to **2** in WillowTree. Press **R** while highlighting Playthrough 3 in the
difficulty menu to reset PT3; confirming clears its mission progress.

## Settings

**Enemy Max Level** is the only option: **3–5**, default **5**. Maximum ordinary
level is **69 + the setting**, with a fixed minimum of **71**.

| Enemy Max Level | Ordinary levels | 71 | 72 | 73 | 74 | Named/boss | Grenade base damage |
|---|---:|---:|---:|---:|---:|---:|---:|
| 3 | 71–72 | 20% | 80% | — | — | 71 | 700 |
| 4 | 71–73 | 20% | 50% | 30% | — | 71 | 775 |
| **5 (default)** | 71–74 | 20% | 48% | 30% | 2% | 71 | 800 |

Percentages apply independently to supported ordinary spawns, including badasses.
Recognised named enemies/bosses stay at **71**. The same table appears in the
in-game mod description and option description. See [named enemies](NAMED_ENEMIES.txt).

Grenade damage is fixed to the preset and shown on standard grenade-mod cards.
There is no grenade toggle or damage slider. Bonuses, resistances and multiple
hits affect the total damage an enemy receives. Item levels and parts are retained.

## Playing and upgrading

- PT3 starts at **Skags At The Gate**. Its fast-travel unlock follows that mission.
- DLCs use PT3 balance, including Knoxx from its first visit.
- Cash prices, selling, drops and mission payouts use the level-1 economy.
  Your existing wallet balance is retained.
- Upgrading to 3.0.0 starts the new **Enemy Max Level** option at **5**; old spread,
  grenade toggle and spawn-debug settings are ignored. No save reset is required.
- Change the setting for future enemy spawns/restores; reload the map to replace
  enemies already present. Loaded standard grenade mods update with the setting.
- PT1/PT2 and disabling restore native grenade damage. Other playthroughs retain
  their native enemy balance.

Supported population factories are covered; custom/scripted spawn paths can keep
native levels. Intended for solo/host play; co-op is unverified. Use one enemy-level
mod at a time. Optional diagnostics are separate from the normal installation.

## Credits and history

Based on Playthrough 3 by **RedxYeti and Miner Of Worlds**. Named-enemy identifiers
are credited in `NAMED_ENEMIES.txt`. License: GPL-3.0.

Release changes are recorded in [CHANGELOG.md](CHANGELOG.md).
