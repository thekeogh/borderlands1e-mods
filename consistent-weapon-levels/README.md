# Consistent Weapon Levels

Private Borderlands GOTY Enhanced Python SDK mod. Author **keogh**, version **1.0.0**.

Corrects the proficiency-dependent level on equipped weapon cards. Intended result:
a weapon shown as level 69 in the backpack remains level 69 when equipped.
Uses the native level calculation with the weapon definition's ordinary fallback
bonus, rather than displaying its internal `ExpLevel` directly.

## Install

1. Copy `dist/ConsistentWeaponLevels.sdkmod` to the Windows game's `sdk_mods/` folder.
2. Restart the game. Enable **Consistent Weapon Levels** in the Mods menu.
3. Run alongside your Playthrough 3 and AutopickupBL1E mods.

Existing cards may need rebuilding: close/reopen the inventory or change selection.
Disable the mod to restore the original card behavior.

## How it works

Your BL1E diagnostic exports contain the weapon level-bonus attributes. Their
resolvers use weapon proficiency scaled by 0.25, plus a constant of 2. Weapon
definitions also provide a fallback constant; this varies between definitions.
That data supports the proficiency explanation. It does not establish why the
original developers retained the calculation.

Paired PRE/POST_UNCONDITIONAL hooks track native item-card rendering in inventory,
comparisons, vendors, the bank, pickup comparisons, equipped HUD cards and rewards.
During those calls only, hooks on both native required-level query wrappers
recalculate a weapon's level with its definition's proficiency attribute reference
temporarily cleared. The reference is restored synchronously in `finally`, including
on errors. The game handles its own rounding, lower bounds and level caps.

Outside card rendering, level queries pass through unchanged. The mod does not
edit proficiency skills, weapon stats, saves, weapon generation or persistent
definitions. Unknown custom level attributes and custom initializers are left alone.
No polling or timers. The original game UI is expected to render on its game thread.

## Verify in game

- Compare the same weapon in backpack and equipped slots, with keyboard and mouse.
- Repeat with a pistol and another weapon type; compare two weapons too.
- Check vendor and pickup comparison cards. Low-proficiency weapons should agree too.
- Check an actually too-high-level weapon still cannot be equipped.

**Native Windows verification remains pending.** The regression suite models SDK
callbacks; it cannot prove BL1E's UI dispatches every level query through those hooks.
If a card still differs, use the mod's **Export level diagnostics** button after
viewing it. Export location:

```text
sdk_mods/settings/ConsistentWeaponLevels/weapon-levels-<timestamp>.json
```

The export includes UI/query counts, registered-hook counts, exceptions and native
versus corrected levels for up to 100 weapons owned by your loaded character.
`card_calls > 0` with `corrected_queries == 0` indicates the expected level-query
path was not intercepted, or the viewed weapon has an unsupported custom definition.
Hook counts show registration, not proof that a particular native function ran.
Normal activation/error/export messages also appear in `Binaries/Win64/Plugins/unrealsdk.log`.
Exporting restores the definition after each query and does not edit your save.

## Build and checks

```sh
python3 -m unittest discover -s consistent-weapon-levels/tests -v
python3 consistent-weapon-levels/package.py
```

21 regression checks cover the 69-versus-57 example, exported definition-specific
fallbacks, native clamping, nested and blocked UI calls, thread-specific scopes,
both query signatures, non-weapons/custom definitions, recursion and exception
cleanup, disable/re-enable, gameplay boundaries and diagnostic restoration.
The small fixture is extracted from `logs/pt3-economy-20261007-210503-996932.json`;
it contains only level definitions and function schemas, not your save.

Implementation references: local BL1/BL1E GearScore and Custom UI sources for UI
entry points; [SDK hook API](https://github.com/bl-sdk/pyunrealsdk/blob/master/stubgen/templates/unrealsdk/hooks/__init__.pyi.jinja)
and [mods_base hooks](https://github.com/bl-sdk/mods_base/blob/master/hook.py).
The existing Unofficial Patch's proficiency change was studied; no code copied.
All files under `reference/` remain unchanged.
