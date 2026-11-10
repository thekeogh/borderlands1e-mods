# Consistent Weapon Levels

Borderlands GOTY Enhanced Python SDK mod. Author **keogh**, version **2.0.1**.

Shows the ordinary weapon requirement on item cards, including equipped weapons,
without the proficiency-dependent display reduction. Changes only existing card
text after native rendering. Equip checks, weapon stats, proficiency, generation,
saves and shared definitions stay untouched.

## Install and verify

1. Replace `sdk_mods/ConsistentWeaponLevels.sdkmod` with
   `dist/ConsistentWeaponLevels.sdkmod`.
2. **Fully restart the game** to remove the old version's hooks, then enable
   **Consistent Weapon Levels** in the Mods menu.
3. View the reported weapon in the backpack, then equip it and view its card.
   The supplied exports show internal level 42, native requirement 40 and the
   old mod's incorrect display of 41. The new ordinary display should be **40**.
4. Compare two weapons with different levels using mouse and keyboard. Check
   vendor, bank, pickup and equipped HUD cards if available.
5. Check an actually level-locked weapon remains locked. This mod leaves the
   game's decision alone; displaying an ordinary level does not enforce it.
6. Use **Export level diagnostics** after viewing those cards. Upload the JSON
   from `sdk_mods/settings/ConsistentWeaponLevels/weapon-levels-<timestamp>.json`.

**Version 2.0.1 is confirmed in game for inventory/equipped cards and comparisons.**
The supplied Windows exports show the Static Repeater at 40 both equipped and in
the backpack, and the Volcano corrected from proficiency-reduced 34 to 38.
The latest reviewed export reported zero runtime/export errors, zero unsupported
definitions and zero text-write mismatches. Vendor, bank, pickup and HUD card
coverage has not been individually confirmed; missing fields are skipped.

The user also confirmed overlevel shields and weapons remain unequippable.
Comparison/swap attempts can reject them silently while direct selection shows
an underlevel dialog. That behavior was reproduced with this mod disabled after
reloading the game, for both shields and weapons. No dialog workaround is added.
Shields are outside this mod's display correction and weapon-only diagnostics.

Closing/reopening the inventory rebuilds existing cards after toggling the mod.

## What changed

Version 1 temporarily cleared `PlayerUseLevelBonus.BaseValueAttribute`, then
reran gameplay level queries within card-rendering scopes. That forced a fallback
constant which is not necessarily the actual bonus. Pistol definitions in the
captured data have fallback 1, while their proficiency resolver includes 2.
For internal level 42, forcing fallback 1 produced the misleading level-41 card.
The game's own requirement in both supplied exports was 40.

Version 2 has **no gameplay level-query hooks**, scope counters, definition edits
or level-69 display clamp. After a native card update it:

- Reads the weapon's internal level and existing use-level bonus.
- Reads the supported standard proficiency expression from its existing resolver,
  verifies the skill input and addition operation, then substitutes zero for
  proficiency. The constant operand and scales come from the data; no universal
  offset is assumed. Constant-only definitions use their constant and scale.
- Subtracts the resolved integral bonus from the internal level, with minimum 1.
- Replaces the single number in the existing requirement text. Native labels,
  requirement indicators, colours and usability decisions are preserved.

Version 2.0.0 incorrectly assumed `EvaluateInitializationData(bonus, None)` would
evaluate the proficiency expression at zero. The 14:40 exports show it returned
the pistol fallback of 1 instead, causing the mod to replace native text 40 with
41. Version 2.0.1 removes that call entirely. It reads the verified expression
`proficiency * scale + constant` without resolving a player or changing any data.

Unknown custom/dynamic definitions, math operations, fractional/invalid bonuses,
missing text fields and ambiguous labels stay native. No universal level offset is assumed.
Raw `ExpLevel` is not itself the normal equip requirement.

Only native UI functions are observed. Comparison tracking stores object paths,
not live actors. No polling, timers, package loading or permanent Flash changes.

## Diagnostics

The manual JSON export includes:

- Player level; current and equipped weapon paths; loaded mod versions.
- Weapon names, internal levels, native controller requirements, ordinary display
  levels, resolved bonuses, resolution methods, native level-check results and
  usability checks.
- Definition fallback constants, scales, attribute/context/resolver identities
  and math operation enums.
- Last 40 processed weapon cards, with item identity, text before/after and result.
- Live card text snapshots, hook registration counts, counters and errors.

`missing_text` means a card field was absent or did not contain exactly one number.
`unsupported` means a definition could not be evaluated safely. `write_mismatch`
means the text read back differed from the requested value. `unchanged` is normal
when the game already displayed the correct level. Hook counts show registration,
not proof a particular native update ran.

Exporting reads existing items and native checks; it does not equip, rebuild cards
or edit definitions/saves. Histories contain only primitive values and are bounded.

## Build and checks

```sh
python3 -m unittest discover -s consistent-weapon-levels/tests -v
python3 consistent-weapon-levels/package.py
```

30 checks cover the supplied 42/40/41 regression and the live 2.0.0 failure,
equipped 69-versus-57 example, Lady Finger without artificial capping,
levels 1–69, read-only native definitions,
UI-only hook registration, comparisons, supported card routing, custom/invalid
bonuses, failures, disable/re-enable, localization and diagnostic output.
The null-context fallback model now matches the captured live failure. Production
display calculation makes no native attribute-evaluation calls.

Implementation references: local status-menu UI export for the exact requirement
text field; [native UI mod sources](https://github.com/MOW531/MOW531-BL1-SDK-Mods/tree/main/Custom%20UI%20SDK/Source/sdk_mods/CustomUI)
for card paths and item selection; [SDK hooks](https://github.com/bl-sdk/pyunrealsdk/blob/master/stubgen/templates/unrealsdk/hooks/__init__.pyi.jinja).
No game assets or decompiled scripts are included in the archive.
