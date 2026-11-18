# One Playthrough

**5.0.0 · keogh · Borderlands GOTY Enhanced**

Play from level **1 to 69** in one continuous journey through Pandora. Enemies
and missions scale with you across the main story and all four DLCs,
without restarting the story in another playthrough.

Higher-level areas and missions keep their vanilla minimums. Once you outlevel
them, they scale with you—including every DLC, without first completing it.
Missions keep following your level after acceptance, including completed objectives
awaiting turn-in. Equipment rewards, XP and cash use the mission level when you
turn it in, preserving higher vanilla mission levels. A level gained from that
payout does not change its remaining rewards; SDU upgrades keep their native behaviour.

Choose **Enemy difficulty** in the mod options. **Medium** is the default;
the setting is saved and applies to new spawns.

**Debug** is an extra option for testing mods and travelling through fights quickly.
It sets supported hostile enemies—including named enemies, bosses and hostile
vehicles—to **max(1, your level − 30)**, ignoring their normal level floors and
offsets. At level 40, enemies spawn at level 10; at levels 1–31 they spawn at level 1.
Choose Debug, then reload the area for fresh enemies. Switch back to a play
difficulty and reload again when finished testing. Debug is saved like the other
settings; Medium remains the default. It changes enemy levels, not mission
progress, reward rules or your existing gear.


| Ordinary-enemy roll | Easy | Medium | Hard | Very Hard |
| --- | ---: | ---: | ---: | ---: |
| Native, minimum your level +1 | 0% | 0% | 0% | 0% |
| At least +1 | 40% | 0% | 0% | 0% |
| At least +2 | 60% | 60% | 0% | 0% |
| At least +3 | 0% | 40% | 80% | 20% |
| At least +4 | 0% | 0% | 20% | 75% |
| At least +5 | 0% | 0% | 0% | 5% |

Ordinary enemies use **max(your level, vanilla area level)** as their base,
retaining naturally higher levels without stacking bonuses. Easy rolls +1/+2 at **40%/60%**, with no native/on-level roll. Medium rolls +2/+3 at **60%/40%**. Hard rolls +3/+4 at **80%/20%**; Very Hard rolls
+3/+4/+5 at **20%/75%/5%**. Existing spawned enemies keep their levels.

Named enemies and bosses do not roll: **Easy and Medium fix them at your level +2**,
**Hard fixes them at your level +3**;
**Very Hard fixes them at your level +4**, overriding higher native level inputs.
This includes supported named hostile vehicles. Native grade-selection
bands, identities and combat modifiers are preserved in every mode.

**Adaptive** is an additional saved option. It gradually raises ordinary-enemy
bonuses as you level. Each row below is reached at its **anchor level**; weights
blend every level between anchors. Levels 1–5 keep the first row and levels 65+
keep the last. Bracket names are guides, not abrupt cutoffs: a small chance of
an adjacent bracket's enemy levels appears during the transition.

| Target bracket | Anchor level | Base +1 | Base +2 | Base +3 | Base +4 | Base +5 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1–10 | 5 | 20% | 80% | 0% | 0% | 0% |
| 11–20 | 15 | 0% | 80% | 20% | 0% | 0% |
| 21–30 | 25 | 0% | 40% | 60% | 0% | 0% |
| 31–40 | 35 | 0% | 20% | 70% | 10% | 0% |
| 41–50 | 45 | 0% | 0% | 70% | 30% | 0% |
| 51–60 | 55 | 0% | 0% | 45% | 52% | 3% |
| 61–69 | 65 | 0% | 0% | 20% | 75% | 5% |

For example, at level 30 the ordinary rolls are +2 **30%**, +3 **65%** and +4
**5%**. Adaptive still uses the higher of your level and the native area level as
the spawn base and retains naturally higher ordinary enemies. Your character
level determines the percentages, even when visiting a higher-level area.

Adaptive named enemies/bosses, including supported named hostile vehicles,
remain fixed and receive their increases two levels after the bracket boundary:

| Player level | Fixed named/boss level |
| --- | --- |
| 1–22 | Player +2 |
| 23–52 | Player +3 |
| 53+ | Player +4 |

Select **Adaptive** in Enemy difficulty, then reload the area for fresh spawns.
Existing enemies keep their levels. Medium remains the default; all existing
presets retain their rules. F10 reports your current Adaptive weights and boss
offset. This mode follows character level, not equipment strength or deaths.

Enemies exactly **five levels above you** show the native skull beside their
health bar. This changes only the HUD warning icon; +6-or-higher native skulls,
enemy stats and damage rules remain native. Disabling the mod restores its owned
icon override. The new visual change needs an in-game check.

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
