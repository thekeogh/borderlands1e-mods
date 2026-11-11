# One Playthrough

**4.7.1 · keogh · Borderlands GOTY Enhanced**

Play from level **1 to 69** in one continuous journey through Pandora. Enemies
and missions scale with you across the main story and all four DLCs,
without restarting the story in another playthrough.

Higher-level areas and missions keep their vanilla minimums. Once you outlevel
them, they scale with you—including every DLC, without first completing it.
Missions keep following your level after acceptance, including completed objectives
awaiting turn-in. Equipment rewards, XP and cash use the mission level when you
turn it in, preserving higher vanilla mission levels. A level gained from that
payout does not change its remaining rewards; SDU upgrades keep their native behaviour.

Choose **Enemy difficulty** in the mod options. **Normal** is the default;
the setting is saved and applies to new spawns.

| Ordinary-enemy roll | Easy | Normal | Hard | Very Hard |
| --- | ---: | ---: | ---: | ---: |
| Native, minimum your level +1 | 70% | 50% | 20% | 0% |
| At least +1 | 20% | 20% | 5% | 0% |
| At least +2 | 9% | 25% | 55% | 0% |
| At least +3 | 1% | 5% | 20% | 40% |
| At least +4 | 0% | 0% | 0% | 59% |
| At least +5 | 0% | 0% | 0% | 1% |

The base remains **max(your level, vanilla area level)** in every difficulty.
New ordinary spawns also floor native level variation at **your level +1**. The mod's
extra boosts stop at +3 for Easy, Normal and Hard. **Very Hard** rolls +3/+4/+5
at **40%/59%/1%**, with no native, +1 or +2 roll. Naturally higher enemies and
higher-level areas can still exceed these boosts. Existing spawned enemies keep their levels.
Native and +1 rolls now share a +1 minimum. Around your level, their combined
chances are Easy **90%**, Normal **70%**, Hard **25%**; naturally higher enemies
and areas retain their higher levels.
Naturally stronger enemies keep their strength; bonuses do not stack. Named
enemies and bosses keep their native levels and offsets, with a minimum of
**your level +3 in every difficulty** and no random bonus. This is a floor, not
a cap: at player level 5, a native level-10 boss stays 10; a level-6 boss becomes 8.

**Loot level floor** is enabled by default. New equipment from world drops,
containers (including chests and skag piles) and vending-machine stock targets
at least **your level for all equipment**,
never below level 1. Higher-level equipment stays higher; rarity and legendary
chances stay vanilla. Toggle it off in the
mod options for native loot levels.

The floor applies when equipment is generated, and when carried enemy equipment
drops on death. Existing player inventory and player-drop copies keep their levels.
Mission rewards use the mission level at turn-in. Existing vendor stock needs to refresh before
the floor can affect it; money and pricing formulas stay native.

Designed for solo play; reaching level 69 depends on how much you play.

## Install and play

1. Install the [BL1 PythonSDK mod manager](https://bl-sdk.github.io/willow1-mod-db/).
2. Close the game. Copy [OnePlaythrough.sdkmod](dist/OnePlaythrough.sdkmod) into
   the game's `sdk_mods` folder.
3. Launch the game and enable **One Playthrough** in **Mods**. Disable other
   enemy or mission scaling mods.
4. Choose **New Game**, create your character and enjoy the full introduction.
5. Play normally. Next time, choose **Continue** with the mod enabled. Stay in
   the first playthrough to finish remaining missions and DLCs after the story.

**Upgrading from Playthrough 3 v4?** Remove its old SDK archive or unpacked mod
folder before installing this one. Choose **Continue** with your existing
character; saved mission records transfer automatically. Unpaid missions follow
your level immediately, including missions accepted in older versions.

For troubleshooting, **F10** exports a report to
`sdk_mods/settings/OnePlaythrough/diagnostics/`.

## Credits

Based on the original **Playthrough 3** by
[RedxYeti](https://github.com/RedxYeti/Yeti-BL1-SDK-Mods) and
[Miner Of Worlds](https://github.com/MOW531/MOW531-BL1-SDK-Mods).
One Playthrough by **keogh**. [GPL-3.0](LICENSE) · [Changelog](CHANGELOG.md).
Named-enemy identifiers reference RedxYeti's Dedicated Drops and
[-Ry's Boss Bars](https://github.com/Ry0511/my_bl1_sdk_mods/tree/main/src/py/boss_bars).
