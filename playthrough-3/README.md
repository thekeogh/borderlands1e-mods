# Playthrough 3: weighted enemies and level-1 cash economy

Version 2.3.0. Author: keogh. Private build, based on supplied PT3 v1.1.2
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
   Alternatively, extract `dist/Playthrough3-Level1Economy-BL1E-2.3.0.zip` into
   the game root; it contains the replacement, updated diagnostics and unchanged UPK.
4. Restart. Enable **Playthrough 3**, select PT3, and check **Enemy Level Spread**
   defaults to **3**. Ordinary new enemies should show levels 69–72; listed named enemies 71.
   This replaces the original PT3 mod; do not run both PT3 versions.
5. The diagnostic mod may stay enabled for another F10 export. It only collects
   data and is independent of the PT3 replacement.

No playthrough reset or WillowTree edit is needed. Your current wallet stays as-is.
Existing inventory cash values are recomputed when your character loads.
Vendor price/display/buy/sell callbacks also recompute the relevant item's cash
value before the game reads it. Future native cash calculations confirm PT3.

## Version 2.3.0: harder spread and named enemies at 71

Default spread 3 now gives **69: 5%, 70: 20%, 71: 55%, 72: 20%**. All listed
named enemies/bosses now use **71**, independent of spread, including spread 0.
The approved odds for every spread are in the table below. Default remains 3;
your saved spread setting remains in place. Economy and mission/region baseline
remain unchanged, and the existing spawn hooks and initialization stay in place.

Open the mod's in-game **Description** (`[...]`) to see all six spreads as
`level: chance` pairs. The **Enemy Level Spread** option description also lists
them. Both descriptions are generated from the live policy constants, so their
numbers stay in sync with actual spawning. This is the configured distribution,
not a guarantee that a small encounter will match the percentages exactly.

## Named-enemy recognition (introduced in 2.2.0)

71 named entities are recognised through 146 exact balance/archetype IDs. Every
matched enemy now uses **71**, independent of spread (2.2.0 originally used 69).
Ordinary enemies and ordinary
badasses keep the same weighted spread. Economy, mission/region baseline, grade
stat bonuses, settings identifiers and the three existing hooks stay unchanged.

The complete list and exact IDs are in [NAMED_ENEMIES.txt](NAMED_ENEMIES.txt),
also included as `PT3-Named-Enemies.txt` in the installation ZIP. Includes base
game and DLC bosses, named quest enemies, the five named Knoxx loot midgets,
and known Underdome variants. Generic Royal Guards, Badass Devastators, Loot Goons,
bloated rakks and Skag Rapparees retain the ordinary policy.

The ID tables were cross-checked against
[Dedicated Drops SDK](https://github.com/RedxYeti/Yeti-BL1-SDK-Mods/blob/315f9ea9d0b8b419bf45a0873721fc54c5bb0444/DedicatedDropsSDK/enemies.py)
and [Boss Bars](https://github.com/Ry0511/my_bl1_sdk_mods/blob/a70761d52b5586292a85d4c1b5edd253810fdd13/src/py/boss_bars/constants.py).
This uses identifiers, not English display-label matching, broad substrings or
native `IsBoss`/`IsEnemy` calls. Friendly/player/neutral allegiances still skip.

Matched AI enemies use the existing exact-stage initialization. Mad Mel and
Krom's turret can have only vehicle archetypes; their existing native factory
receives stage 71 without inventing AI balance fields. Ordinary unsupported
vehicles still follow their native behavior. Vehicle displayed levels and native
boss-specific overrides need Windows gameplay verification. Scripted paths
outside these factories remain outside coverage; listing a name cannot guarantee
every version of its encounter follows these hooks.

F10 adds `named_enemy_level`, `named_enemy_counts`, matched `named_definitions`
and a `named_enemy` label on tracked rows. `ordinary_assigned_counts` excludes
named enemies so their guaranteed 71s do not distort the spread check; existing
`assigned_counts` still includes all successful supported spawns. The diagnostic
companion remains 2.1.1 and already reads the expanded snapshot.

Restart when replacing the SDK mod. No reset or save edit required. Enemies
already present receive the new rule only on a new spawn/restore. In Windows,
check Nine-Toes/Pinky/Digit, Sledge or Bone Head at spread 5, then bosses in DLCs
and Mad Mel/Krom's turret. They should show 71; ordinary enemies can reach 74.

## Version 2.1.2: cleanup after gameplay testing

On 9 October 2026, you reported playing 2.1.1 without another crash: enemies at
69, 70, 71 and one 72, none outside that range. This is initial gameplay
confirmation; it does not establish coverage of every spawn path.

2.1.2 keeps the same native spawn behavior, level probabilities and economy.
**Enemy Spawn Debug Logging** now defaults off to reduce log noise; enable it
for bounded phase messages if troubleshooting another crash. Error messages,
counts and F10 exports remain active. F10's 200-enemy limit now applies after
skipping expired weak references, so older unloaded enemies cannot hide current
ones. The diagnostic companion remains version 2.1.1.

## Version 2.1.1: spawn crash revision

**2.1.0 crashed on the first enemy encounter in Windows BL1E. Do not use that
build.** The supplied SDK log stops after economy activation and does not identify
the faulting native call. Therefore the precise crash cause remains unconfirmed.

2.1.1 removes the risky path: no `IsEnemy`/`IsDead` calls on pawn templates or
spawning actors; no native level-setter hooks, spawn-completion rescaling or actor
scans on loading/enabling. Population classification reads data identifiers only.
The engine creates each supported enemy once using its normal initialization.
Initial Windows BL1E gameplay confirmation is recorded above.

Supported definitions use the game's `EnemyLevel_GameStage_exact` attribute for
`DefaultExpLevel`, with grade experience offsets zeroed. Each enemy therefore
reads its own game stage, rather than a shared constant overwritten by the next
spawn. The chosen game stage is passed to the native factory. Other grade stat
modifiers remain intact. These level inputs remain in place during PT3 so later
native recalculations agree, and restore on PT1/PT2 selection or mod disable.
Temporary grade eligibility ranges restore in `finally`, including on exceptions.
Data references are pinned against GC until the original inputs are restored.
This avoids changing an already initialized pawn's displayed level after its stats
have been calculated. The field names and factory call pattern were checked against
the local BL1 EnemyRandomizer source; broader native coverage still needs testing.

Fresh/restored balanced AI populations are supported. Vehicle populations use the
same policy when their factory exposes compatible balance data. Unknown allegiances,
unsupported data layouts and scripted paths outside these factories stay native;
**their levels are not yet guaranteed to obey the range**. These skips are reported
in F10 diagnostics rather than executing unsafe template methods to guess hostility.

When debug logging is enabled, bounded `[PT3 Enemies]` phase messages bracket definition preparation, the
native factory call, its return and restoration. If the game still crashes, the
last phase helps identify the failing operation. The final message confirms
grade-range restoration; it does not mean the PT3 level policy was removed.
F10 inspects only tracked,
completed spawns; it no longer scans pawns or invokes hostility/death predicates.
The previously working level-1 economy and custom UPK remain unchanged.

## Enemy level spread

Replaces **Playthrough 3 Base Level** with **Enemy Level Spread**, range 0–5,
default **3**. Ordinary enemies have a minimum of **69**, maximum **69 + spread**, independent
of character level. This is intended for your level-69 PT3 run. The old offset's
saved setting has a different identifier and is ignored; upgrading starts at 3.
Your enabled state and other PT3 settings stay in the same `PT3.json` file.

| Spread | Level 69 | Level 70 | Level 71 | Level 72 | Level 73 | Level 74 |
|---|---:|---:|---:|---:|---:|---:|
| 0 | 100% | — | — | — | — | — |
| 1 | 30% | 70% | — | — | — | — |
| 2 | 10% | 35% | 55% | — | — | — |
| **3 (default)** | **5%** | **20%** | **55%** | **20%** | — | — |
| 4 | 5% | 15% | 50% | 25% | 5% | — |
| 5 | 5% | 10% | 45% | 30% | 7% | 3% |

These are per-ordinary-enemy probabilities, not quotas per encounter. Each supported enemy
spawn gets one choice, shared by its game stage and experience initialization. Native enemy types,
badass/boss grade bonuses and abilities remain; a boss can still be much tougher
than an ordinary enemy of the same level. Recognised named enemies and bosses
use 71 instead of rolling this table, even at spreads 0 or 1. Explicit friendly,
player and neutral allegiances and PT1/PT2 are excluded. Changes run on the host.

Native grades available at the original stage have their eligibility widened
only during the call, so a grade ending at 69 can still spawn at 72. Grade
archetypes, selection weights, health, damage and ability bonuses remain native.
Tracking uses weak UObject references, never pinned enemy actors. Restored actors
get a fresh choice. Changing spread affects new spawns; existing enemies retain
their levels until replaced. Restart/reload when upgrading from the crashing build.

The shared PT3 mission/region baseline is now **69**, independent of spread. Enemy
level changes are separate from it. The level-1 economy code is unchanged.

Further Windows checks: normal enemies, badasses,
bosses, scripted encounters, restored areas and enemy vehicles. At default spread
3, 72s have a 20% chance; supported ordinary spawns should stay within 69–72,
while recognised named enemies use 71.
Do not also enable another mod that overrides enemy levels.

Replace **PT3EconomyDiagnostics.sdkmod** too for diagnostics **2.1.1**. F10 now
adds `pt3_enemies`: chosen-level counts, actual tracked enemy game stages/displayed
levels, skipped definitions and any errors. It also captures
reflected enemy/population function signatures for native troubleshooting.
Exports still go to `sdk_mods/settings/PT3EconomyDiagnostics/`. After a few fights,
the counters help verify the distribution; a small sample need not match it exactly.

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

The economy changes six money-only formula inputs. It does not lower item levels or edit
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

65 local tests pass: 32 economy/export tests plus 33 enemy-level regression tests.
Named-enemy tests exercise sourced IDs at all six spreads on fresh/restored AI
spawns, case-insensitive exact matching, excluded generic/substrings/display
labels, friendly/client exclusion, native vehicle stage forwarding, separate
diagnostic counts, disable restoration and native failure without retries.
Enemy tests check every probability ticket, native initialization inputs, fresh and
restored signatures, nested data restoration, narrow grades at 74, preserved stat
bonuses, independent levels on shared definitions, PT1/disable and GC pin
restoration, NPC/client exclusions, unsupported data fallback,
read-only diagnostics, live-row export limits, optional phase logging and exception handling without duplicate
spawns. Template/pawn methods intentionally raise if the policy attempts unsafe
queries or rescaling, and actor scans are forbidden by the test stub. These tests
cannot reproduce an engine protection fault; gameplay testing remains necessary.
Economy tests use the actual exported definitions and
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
You subsequently reported broader testing and a completed mission with the correct
wallet increase. Respec/death charges and PT1/PT2 restoration still need gameplay
confirmation. DLC-specific cash overrides, other
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
