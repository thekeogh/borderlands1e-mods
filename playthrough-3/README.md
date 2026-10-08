# Playthrough 3: level-1 cash economy

Version 2.0.0. Author: keogh. Private build, based on supplied PT3 v1.1.2
by RedxYeti and Miner Of Worlds.
Pricing changes use the BL1 Enhanced definitions exported from your level-69
character on 7 October 2026. Original custom UPK is unchanged.

## Install on your Windows PC

1. Fully close the game.
2. Replace your original `sdk_mods/Playthrough 3.sdkmod` with
   `dist/Playthrough 3.sdkmod`. If the original is an unpacked `Playthrough 3`
   folder, move that original folder out of `sdk_mods` first. Keep one PT3 copy.
3. Keep the original
   `WillowGame/CookedPC/Mods/PT3/gd_GameStages_PT3.upk` installed.
   Alternatively, extract `dist/Playthrough3-Level1Economy-BL1E-2.0.0.zip` into
   the game root; it contains the replacement, updated diagnostics and unchanged UPK.
4. Restart. Enable **Playthrough 3**, select PT3, and check Zed's shield vendor.
   This replaces the original PT3 mod; do not run both PT3 versions.
5. The diagnostic mod may stay enabled for another F10 export. It only collects
   data and is independent of the PT3 replacement.

No playthrough reset or WillowTree edit is needed. Your current wallet stays as-is.
Existing inventory cash values are recomputed when your character loads.
Vendor price/display/buy/sell callbacks also recompute the relevant item's cash
value before the game reads it. Future native cash calculations confirm PT3.

## Version 2.0.0: load callback fix

The previous build activated at 20:48:46, then restored normal formulas at
20:49:00. Your 20:49:32 export confirms all six original level inputs were back.
The profile-loaded callback previously treated a temporary non-PT3 index during
loading as a reason to restore normal prices. It now preserves the PT3 menu
selection; PT1/PT2 explicitly restore normal prices when selected.

Runtime cash/vendor hooks also confirm the live PT3 index, verify that formula
writes persisted, and refresh cached shop prices before display and transactions.
No item level is temporarily changed. Diagnostics 2.0.0 adds loaded mod versions,
enabled flags, economy state, transition reasons and formula errors to F10 JSON.
Replace the diagnostic SDK mod too if using F10 for another check.

## What changes

- Weapon, shield, class mod, grenade mod and other gear cash formulas use level 1.
  Existing parts, rarity, level requirements and combat stats remain native.
- Native shops use those values for purchase, sale and buyback. Their normal
  markups and quantity handling remain native.
- Cash pickups use level 1 in their **actual credit effect**, including ordinary
  cash, large cash, bobbleheads, skag pearls and Prize Fighter cash using the
  shared formula. Part and pickup-size differences remain.
- Mission cash uses level 1; mission level, XP and equipment rewards remain native.
- Respec costs and the death-fee ceiling use level 1. Death still charges the
  native wallet percentage, bounded by the level-1 ceiling.
- Ammo/healing prices defined as fixed constants remain fixed. Their different
  consumable tiers still have different prices; these had no level inflation.
- PT1/PT2 restore normal cash formulas. Disabling the mod also restores these
  formulas and recomputes cash values for currently loaded inventory.
- Metadata now declares BL1 and BL1E. Two original level-setting callbacks also
  guard against missing player/stage objects while menus or loads are active.

This changes six money-only formula inputs. It does not lower item levels or edit
packed manufacturer grades. It does not scale `AddCurrencyOnHand`, which would
scale sales/refunds and pickups twice. No recurring world scan is added.

## What the supplied export showed

- PT3 index 2, character level 69; many vendor items have internal levels 70/71.
- Gear cash: `CashValueModifierTotal * 1.16^ExpLevel`, before integer conversion.
- Your Zed vendors use a 7x markup. One basic shield's sell value was $1,248,503,
  making its buy price $8,739,521. Other shields exceeded the $9,999,999 display.
  The same shield is expected to sell for $44 and cost $308 with this patch.
- Cash pickup formula grows by `1.12^level`; mission cash has its own 1.12 curve.
- These gear/cash formulas contain no playthrough selector. The data establishes
  level inflation; it does not establish an Enhanced-specific pricing defect.
- Your reported sale arithmetic was correct:
  920,631 + 2,333,627 = 3,254,258.

Baseline values retained in `tests/fixtures/bl1e_economy.json`.
Failed-build export: `../logs/pt3-economy-20261007-204932-272895.json`.
The original readme remains in `ORIGINAL_README.txt`.

## Validation and remaining game checks

32 local tests pass. Economy tests use the actual exported definitions and
function signatures through a mocked SDK. Checks cover level-70 shield pricing,
cash effects, mission cash, respec/death fees, unchanged levels/grades/stats,
fixed consumables, repeated application, restoration and invalid-formula failure.
The regression reproduces PT3 selection followed by a profile callback still
reporting PT1, then verifies PT3 prices persist and explicit PT2 selection restores
normal prices. Vendor tests cover stale caches, display and transaction callbacks.
Two Windows BL1E exports at 21:04:35 and 21:05:03 UTC on 7 October 2026 now
confirm version 2.0.0 by keogh is enabled, the economy remains active, and all
six live formula inputs use constant level 1. Both exports report no errors;
the economy reports no problems or restoration between these captures.

All seven shop shields retain internal level 71 and packed manufacturer grade
4653061. Their native sell values are $44-$160; the recorded 7x vendor markup
gives purchase prices of $308-$1,120. The player reports corrected vendor prices.
The wallet rises from $3,262,489 to $3,262,596, a $107 increase matching the
three logged cash effects of $56, $21 and $30. The $21 pickup supports the
reported chest money of approximately $20.

Evidence: `../logs/pt3-economy-20261007-210435-071730.json` and
`../logs/pt3-economy-20261007-210503-996932.json`. The exporter still reaches its
definition-count limit, but captures all six cash formulas and runtime status.
Completed buy/sell transactions, mission payouts, respec/death charges and PT1/PT2
restoration still need gameplay confirmation. DLC-specific cash overrides, other
mods' direct cash grants and co-op are not verified.

For the gameplay check: buy a shield and complete Fix'er Upper; compare a sale's
displayed value with the wallet increase; collect cash; check mission cash and
PT1/PT2 prices. Another F10 diagnostic export will confirm live formula inputs
and cached cash values. Errors/success messages go to `unrealsdk.log` with the
prefix `[PT3 Economy]`.

Rebuild with `python3 package.py`; run checks with
`python3 -m unittest discover -s tests -v`. Reference hashes remain unchanged.

## Diagnostic export

Copy `dist/PT3EconomyDiagnostics.sdkmod` into the game's `sdk_mods` alongside PT3.
Replace the older diagnostic mod. If it is an unpacked `PT3EconomyDiagnostics`
folder, move that folder out of `sdk_mods` before installing the new SDK archive.
Restart, load PT3, open and close Zed's vendor, then press **F10**. JSON goes to
`sdk_mods/settings/PT3EconomyDiagnostics/` under the normal SDK configuration;
`unrealsdk.log` records the exact path. An export button/key rebind is available
in the diagnostic mod's options. One export may briefly pause the game.

The exporter reads properties and loads packages; it does not assign game
properties, create equipment, adjust currency, save or reset the playthrough.
