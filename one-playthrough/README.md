# One Playthrough

**6.2.0 · keogh · Borderlands GOTY Enhanced**

Play from level **1 to 69** in one continuous journey through Pandora. Enemies
and missions scale with you across the main story and all four DLCs,
without restarting the story in another playthrough.

Higher-level areas and missions keep their vanilla minimums. Once you outlevel
them, they scale with you—including every DLC, without first completing it.
Missions keep following your level after acceptance, including completed objectives
awaiting turn-in. Equipment rewards, XP and cash use the mission level when you
turn it in, preserving higher vanilla mission levels. A level gained from that
payout does not change its remaining rewards; SDU upgrades keep their native behaviour.

Enemy factories use their native level offsets and grade rules at the higher of
your level and the original area stage. Named enemies and bosses use their own
native rules. Enemy names follow the grade the game selects at the scaled stage.

The mod applies the captured Playthrough 2 combat formula inputs from level 1.
The standard enemy health and Guardian shield multipliers are 2.0×, and the
enemy damage formula uses 1.15× (vanilla PT1 uses 0.75×). The Vault boss formula
uses its PT2 health exponent. Special encounters retain their own formulas.
This recreates verified parts of PT2.5 combat within the first campaign. The
original post-story game logic and every encounter have yet to be verified.

Enemies exactly **five levels above you** show the native skull beside their
health bar. This changes only the HUD warning icon; +6-or-higher native skulls,
enemy stats and damage rules remain native. Disabling the mod restores its owned
icon override.

New equipment from world drops, containers (including chests and skag piles)
and vending-machine stock targets at least **your level** whenever the mod is
enabled. Higher-level equipment stays higher. Rarity and legendary chances
follow vanilla rules.

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
Historical named-enemy identifiers reference RedxYeti's Dedicated Drops and
[-Ry's Boss Bars](https://github.com/Ry0511/my_bl1_sdk_mods/tree/main/src/py/boss_bars).
