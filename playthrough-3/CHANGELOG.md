# Changelog

All release changes are recorded here. README.md describes installation and current play.

## 3.0.0 — 2026-10-13

- Replaced Enemy Level Spread with **Enemy Max Level**, range **3–5**, default **5**.
- Ordinary enemies start at **71**. Max 3: 71/72 at **20/80%**; max 4:
  71/72/73 at **20/50/30%**; max 5: 71/72/73/74 at **20/48/30/2%**.
- Recognised named enemies/bosses remain fixed at **71**, at every setting.
- Standard grenade mods use exact base card damage **700 / 775 / 800** for
  settings 3 / 4 / 5. Removed the grenade toggle and relative damage multipliers.
- Retained grenade levels, parts and native definitions. Original damage slots
  restore on PT1/PT2 selection or disable, including dropped and natively copied
  items. Slot updates wait for native initialization to finish; they do not
  reinitialize items, intercept damage events or compound the boost.
- Retained the Continue/load activation fix from 2.5.1.
- Removed Enemy Spawn Debug Logging and all PT3 runtime log messages except the
  loading/version line. Optional manual diagnostics retain bounded error details.
- Generated the in-game preset table from the same constants used by gameplay.
- Rewrote README.md for players; consolidated release history here. Included the
  README, changelog and named-enemy reference in the SDK archive.
- Normal installation no longer automatically installs diagnostics. The companion
  remains an optional separate artifact.
- Preserved native enemy initialization, DLC setup, UPK, level-1 cash calculations,
  save reset behavior and named-enemy identifiers.
- The new setting identifier starts upgrades at max 5; removed settings are ignored.
- Validation: 94 local tests passed, including every probability ticket, native
  factory arguments/restoration, exact grenade targets, Continue transitions,
  copied/reinitialized slots, silent runtime behavior and unchanged cash results.
  Archive integrity, source contents, table consistency and reference hashes checked.
  New presets and exact grenade targets still require Windows gameplay confirmation.

## 2.5.1

- Fixed grenade activation when continuing a save without a difficulty-selection
  callback. The supplied export showed PT3 active and the toggle on, but multiplier
  1 and zero updated slots.
- Detected the live playthrough at profile/level-ready events, item initialization
  and damage reads; preserved explicit choices during transient old controllers.
- Added startup grenade logging and pending-selection diagnostic status.
- Retained the 2.5.0 multipliers, enemy policy and economy. Gameplay subsequently
  confirmed the updated card and increased grenade damage.

## 2.5.0

- Added Boost Grenade Damage, enabled by default in PT3.
- Used 5x at spread 3; weighted mean enemy level gently adjusted other spreads,
  including 5.26x at spread 5 and 5.34x at spread 6.
- Updated native grenade card/damage slots without changing the shared projectile
  formula, item levels or parts. Added option callbacks and native restoration.
- Diagnostics 2.2.0 added grenade state and cached damage to F10 exports.

## 2.4.0

- Added spread 6, reaching level 75.
- Reduced level-69 chance to 2% in spreads 5 and 6; moved the freed 3% to level 72.
- Spread 5: 69–74 at 2/10/45/33/7/3%.
- Spread 6: 69–75 at 2/10/40/33/8/5/2%.
- Updated in-game descriptions, diagnostics and README; preserved default spread 3.

## 2.3.0

- Rebalanced ordinary enemy probabilities; default spread 3 became
  69/70/71/72 at 5/20/55/20%.
- Set recognised named enemies/bosses to 71 at every spread.
- Included all configured odds in the in-game description and option description.
- Preserved the existing spawn hooks, mission/region baseline and economy.

## 2.2.0

- Added fixed level-69 named enemies/bosses using 71 named entities and 146 exact
  balance/archetype identifiers, including DLCs and known Underdome variants.
- Kept generic enemies/badasses on the weighted policy; excluded friendly/player/
  neutral spawns and name-substring guessing.
- Included a named-enemy list, source attribution, diagnostic counters and native
  stage forwarding for Mad Mel/Krom's turret.

## 2.1.2

- Disabled spawn phase logging by default after initial gameplay confirmation.
- Applied the 200-enemy diagnostic limit after skipping expired weak references.
- Kept existing probabilities, native initialization and economy.

## 2.1.1

- Replaced the crashing 2.1.0 spawn path with native population-factory initialization.
- Removed unsafe template/pawn hostility and death queries, level-setter hooks,
  post-initialization rescaling and load/enable actor scans.
- Used the native exact-stage level attribute and zeroed grade experience offsets;
  retained health/damage bonuses and restored temporary grade eligibility ranges.
- Added guarded fresh/restored AI and supported vehicle spawning, weak tracking,
  diagnostic counts and bounded phase logging without duplicate spawn retries.
- Retained the working level-1 economy. Initial Windows gameplay confirmed 69–72
  enemies without another crash; complete spawn-path coverage was not established.

## 2.1.0

- Introduced Enemy Level Spread, minimum 69 and a weighted upper range.
- Fixed the shared PT3 mission/region baseline at 69.
- Added enemy-level diagnostics. This build crashed on the first enemy encounter
  in Enhanced and was superseded by 2.1.1.

## 2.0.0

- Fixed early profile callbacks restoring normal cash formulas during PT3 loading.
- Kept the PT3 menu selection until an explicit PT1/PT2 choice.
- Confirmed formulas and refreshed cached cash values at native vendor/display/
  buy/sell operations; preserved wallet transactions and item/mission levels.
- Added loaded mod versions, runtime cash state and expanded read-only diagnostics.
- Changed author to keogh and began the private 2.x version series.

## 1.2.0

- Introduced the level-1 PT3 cash economy for gear prices, cash pickup effects,
  mission payouts, respec costs and the death-fee ceiling.
- Retained item levels, packed manufacturer grades, rarity, combat stats, fixed
  consumable prices, vendor markups and native wallet transaction handling.
- Recomputed cached inventory cash values and restored native formulas on PT1/PT2
  selection or disable. Did not multiply AddCurrencyOnHand or scan every frame.
- Declared BL1/BL1E support and guarded original level callbacks against missing
  player/stage objects during loading.
- Included the unchanged original UPK and supplied-export-based cash validation.
  The activation/loading problem was subsequently fixed in 2.0.0.

## Original mod — RedxYeti and Miner Of Worlds

- **1.1.2:** fixed DLC 3 and 4 scaling.
- **1.1.1:** fixed the fast-travel list not updating.
- **1.1.0:** started PT3 at Skags At The Gate and used PT2 ammo pickup amounts.

Original notes remain in `ORIGINAL_README.txt`. Named-enemy identifier sources
are recorded in `NAMED_ENEMIES.txt`.
