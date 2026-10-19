# One Playthrough changelog

All release changes are recorded here. README.md is the player guide.

## 4.0.4 — 2026-10-19

- Shortened the in-game description to under half its previous length.
- Fixed enabled-state persistence on installations where the OnePlaythrough
  settings directory does not yet exist. The SDK writes mod.json directly after
  enabling, but does not create its parent directory. Enabling from the main menu
  could therefore appear successful while no enabled state was saved for restart.
- Create `sdk_mods/settings/OnePlaythrough/` before registering the mod, so the
  SDK can save `mod.json` without loading a character, accepting a mission or
  exporting diagnostics first. Existing settings are not replaced. Manual
  disabling is still remembered; auto-enable is not forced over a saved choice.
- Validation: reproduced the missing-directory failure with a model of the SDK's
  settings lifecycle, then passed 65 local tests after the fix, including enabling
  at the menu and restoring on restart, persisting manual disable, and preserving
  saved keybinds/mission data. Windows restart confirmation remains pending.
- Scaling, economy, mission levels and legacy acceptance-level migration are
  unchanged. Continue with existing characters after enabling the updated mod.

## 4.0.3 — 2026-10-19

- Renamed the active mod to One Playthrough, including the repository directory
  (`one-playthrough`), SDK module/archive (`OnePlaythrough`), download ZIP,
  in-game name and description, diagnostic keybind, log messages and export names.
- Rewrote the README as a short player guide: one continuous level-1-to-69
  playthrough, main game and all DLCs, installation, New Game, Continue and credits.
- Clarified that available missions follow your level until you accept them,
  highlighting the benefit of leaving missions for later.
- Settings and diagnostics now use `sdk_mods/settings/OnePlaythrough/`. Valid
  mission acceptance levels are copied automatically from the old Playthrough3
  settings when the new file does not exist. Existing new settings take priority;
  legacy files are preserved, and invalid data is not silently overwritten.
- Existing v4 characters can Continue after removing the old Playthrough 3 SDK
  archive/unpacked folder. Do not enable both versions together. Replaced the
  obsolete generated packages in the active distribution folder.
- Gameplay scaling, native economy, enemy variety and mission reward rules are
  unchanged. Historical release names and original-author attribution remain.
- Validation: 62 local tests passed, including seven upgrade cases covering
  accepted-level preservation, multiple characters, new-file precedence, one-time
  migration, corrupt/invalid files and a fresh installation. Renamed archives and
  source/doc contents verified; reference/ and the older mods remain unchanged.

## 4.0.2 — 2026-10-19

- Diagnostic-only release for the reported Fix'er Upper vendor: a level-3
  character saw no regular shields and could only buy a level-4 Item of the Day
  for approximately $940. The cause is not established; no stock, level or price
  changes have been applied to gameplay.
- Manual exports now include reflected vendor stock, generation/price inputs,
  runtime inventory and native required-level queries. Loaded shield balances
  (including Intro/Stock), item pools, pricing definitions and referenced data
  resolvers are captured even if stock generation produced no shield.
- Include available character XP/currency fields. Data collection is bounded,
  follows data definitions only and does not generate inventory, refresh vendors,
  change prices, load extra packages or grant rewards.
- Fixed the two mission-progress export errors observed in Windows reports:
  WrappedArray also exposes `_type`, but it describes an element property rather
  than a struct schema. Arrays are now serialized before inspecting struct fields.
- Gameplay source and acceptance metadata are unchanged. Existing characters can
  Continue; no reset or New Game required. Restarting may regenerate vendor stock.
- Validation: 55 local tests passed, including modeled SDK array/struct layouts,
  empty stock, shield grade restrictions, native item queries, partial field/class
  failures, definition cycles/limits and unchanged objects after export. Windows
  vendor export and the underlying stock issue still require gameplay evidence.

## 4.0.1 — 2026-10-19

- Fixed silent diagnostic failures: manual F10 exports now log a request and
  either the saved path or the actual error. The previous general-purpose safe
  wrapper swallowed export exceptions, hiding why no report was produced.
- Added an Export diagnostics button as a fallback for keybind/enablement issues.
  The startup version line also reports whether the runtime was enabled at load.
- Write a basic policy/status report before optional Unreal reflection. Collect
  optional properties independently, skip class defaults and retain readable
  partial reports when a definition, field or class cannot be read.
- Serialize nonfinite native floats safely. Atomically replace the basic report
  after collection; preserve its path if final writing fails.
- Automatic gameplay logging remains quiet. Scaling, spawning, mission locks,
  native economy and save data are unchanged; no new character/reset required.
- Validation: 48 local tests passed, including actual registered keybind/menu
  callbacks, unreadable fields, missing classes, nonfinite values and disk errors.
  Windows export confirmation pending; the original failing field is not known
  without a report or visible failure message from the affected game session.

## 4.0.0 — 2026-10-19

- Clean implementation in a separate directory; v3 and reference/ are unchanged.
- Uses the normal first-playthrough progress slot, New Game, character creation,
  full introduction, starting equipment and Continue. No PT2-completion gate,
  third-slot creation, quest resets, completion flags or intro skips.
- Native first-playthrough regional defaults and story-stage overrides follow
  character level 1–69 in the main game and all four DLC globals. Native region
  coverage includes Arid__C and other regions missing from the original PT3 UPK.
- No custom UPK is needed. Native loot-quality values and story dependencies are
  retained; only regional level inputs are replaced.
- Population factories receive the player-relative base before native spawning;
  the game retains DefaultExpLevel, grade offsets, native random choices and
  health/damage calculations. No actor level setters, post-spawn rescaling,
  weighted levels, named-enemy list or fixed boss level.
- Extended the first/last native AI grade eligibility bands to cover low-level
  DLC entry and levels through the cap. Intermediate bands and modifiers remain.
- Mission offers follow the player. Acceptance levels persist per save slot/class
  in SDK settings, including across Continue and game restarts. Native .sav files
  are not rewritten. Actual acceptance is distinguished from preview/tracking.
- Native reward entry points use the locked level, including synchronous regional
  overrides for internal C++ refreshes that bypass Python hooks. Nested scopes,
  early exits and level-ups during reward grants restore the latest world base.
- Removed mission minimum-level gates while retaining quest dependencies, story
  unlocks and objective progress. Existing accepted missions on an imported save
  can only be locked at the level first observed by v4; fresh characters intended.
- Native money formulas, wallet transactions, XP multipliers, reward definitions,
  ammo amounts, grenade damage and first-playthrough combat multipliers remain.
- Removed v3 settings and all automatic difficulty switching. PT2, old PT3 slots
  and network clients are excluded; co-op is not verified.
- Read-only F10 diagnostic exports include regional coverage, acceptance levels,
  native enemy definition inputs and bounded errors. Only the version logs normally.
- New concise player README covers installation, New Game, intro and Continue.
- Validation: 38 local tests passed. Real exported BL1E base-game regional rows
  were exercised at levels 1, 10, 30, 50 and 69. Tests also cover modeled DLC
  tables, acceptance/reload isolation, native C++-style reward refreshes, nested
  cleanup, level-ups during rewards, native spawn offsets and one-call spawning.
- Package/source integrity, unchanged v3 files and reference hashes checked.
  Local models cannot execute the Windows engine; low-level DLCs, scripted
  spawns, special boss floors and the full New Game flow need in-game confirmation.

## 3.0.2 — 2026-10-16

- Fixed missing base-game regions in the original PT3 balance, including
  `Arid__C`, `Arid__C_Difficult`, `Headlands__B` and `Scrap_NewHaven_B`.
  Missing loaded regions are added to the matching PT3 balance at level 69.
  Existing entries and their story overrides are preserved.
- Corrected affected mission GameStage and ExpLevel before native UI, XP and
  item-reward reads, and after native reward-stage refreshes. This covers offered
  and accepted missions, including What Hit The Fan and Scavenger: Combat Rifle.
- Retained quest progress, reward definitions, XP multipliers, enemy presets,
  named-enemy levels, level-1 cash formulas and native grenade damage. No rewards
  are reissued and already granted items are not changed.
- Applied the fix through the SDK mod; the original UPK remains unchanged.
  Fully restart after replacing the SDK mod. No quest or playthrough reset needed.
- Restore added regional entries and edited transient mission fields on disable;
  restore mission fields when leaving PT3. PT1/PT2 and clients are excluded.
- Optional diagnostics 2.2.2 includes missing-region policy status and bounded
  errors. Normal runtime logging remains limited to the loading/version line.
- Validation: 85 local tests passed, including region omissions, accepted/offered
  mission reads, native refresh overwrites, turn-in preparation, Continue/load,
  restoration, client/PT1/PT2 exclusions and existing enemy/cash regressions.
  Original UPK row layouts checked. Windows UI, XP and item rewards need gameplay
  confirmation; local models do not execute the game's native reward code.

## 3.0.1 — 2026-10-14

- Removed all grenade damage adjustments, card overrides, hooks and callbacks.
  Grenade damage and damage cards now use native game values at every setting.
- Removed the grenade preset column from the in-game table and README, along
  with the damage module, its tests and its diagnostic status export.
- Optional diagnostics updated to 2.2.1; normal installation remains separate.
- Enemy levels, probabilities, named/boss level 71, default max 5, level-1 economy
  and the original PT3 assets and mission setup are unchanged.
- Fully restart the game after replacing the SDK mod to clear previous runtime
  damage changes. Existing settings and saves are retained.
- Validation: 66 local tests passed; archive contents, unchanged enemy/economy
  code, original UPK and 95 reference hashes verified. Windows gameplay pending.

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

The earlier Playthrough 3 distribution retains its original notes and
named-enemy sources. These historical features are not part of One Playthrough.
