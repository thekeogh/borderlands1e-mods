# Enemy Respawn Timer

Private mod for Borderlands GOTY Enhanced. Author: keogh. Version 1.3.1.
Validated in selected BL1E encounters: bandits, skags, spiderants/spiderantlings
and gatling turrets at 1 minute; Rust Commons West bandits and spiderantlings
stayed cleared for over 35 minutes on Forever. Map travel reset tracking as intended.

Copy `dist/EnemyRespawnTimer.sdkmod` to your game's `sdk_mods`, restart and enable
**Enemy Respawn Timer** before loading a map. This is a separate mod: leave
Playthrough 3 enabled. No existing mod, save, reference file or UPK is changed.

## Options

| Respawn Delay | Gameplay seconds after clearing a group |
|---|---:|
| 1 minute (testing) | 60 |
| **30 minutes (default)** | **1,800** |
| 1 hour | 3,600 |
| 3 hours | 10,800 |
| Forever (until reload) | Blocked for the current loaded map session |

For ordinary groups, the timer starts when the last tracked enemy in that group
dies. Recognized named enemies start their den's timer on their own confirmed kill,
even if existing grunts from that den are still alive. First encounters spawn normally. After expiry,
the group is eligible to respawn; native distance, visibility, population quotas
and mission conditions still apply. This mod does not forcibly summon enemies
at the instant a timer ends. Named enemies are also suppressed after confirmed
kills; their initial native spawn and mission death handling still execute.
Native default respawn timing is not established here; it can vary by opportunity.

Paused game time does not count. Changing the option updates cleared groups from
their original clear time. Entering a different map or reloading clears tracking.
During cooldown the mod holds the den's native no-respawn flag and temporarily
disables ordinary spawn opportunities, persistent payload-free mission gates, and
recognized named-enemy dens after a confirmed named kill.
The no-respawn flag alone did not prevent the recorded rakk bypass. Forever uses
a timestamp 999,999,999 seconds after clearing and keeps these native guards until
map reload or disable. Finite delays release the guards at expiry. Disabling
restores owned flags, activation, timestamps and any reset tally still at zero
(before a new generation). Staged mission disable/respawn patterns retain native
activation control.
Native member lists also allow tracking enemies already alive when enabled.
Use a fresh map for repeatable tests. Settings persist; enemy timers do not.

For ordinary groups, quest objective/item opportunities, unknown scripted aspects,
native no-respawn flags, friendly/mixed groups, unknown allegiances and unsupported
layouts stay native. Recognized named-enemy dens are an explicit exception to the
mission/no-respawn exclusions: they are observed normally and guarded only after
a confirmed named kill. Native no-respawn flags are restored to their original
values, including True, on cleanup. Enabled MissionPopulationAspect gates are allowed only when
they have no objective or item payload and their four-slot reaction table uses
known values: Enabled, Disabled, Respawn50Percent or Respawn100Percent. All 256
combinations of those four values are accepted, including combinations not yet
seen in-game. Native activation is preserved. This protects first encounters, quest NPCs and scripted waves; it means
the mod cannot guarantee every enemy in the game follows your selected timer.
Applies on the host. Co-op behavior is not verified. A manual Reset Enemies mod
can override timestamps/counters, so avoid manually resetting during timer tests.

## Implementation and compatibility

A render hook checks the host's native `PopulationOpportunityDen.SpawnedDenMembers`
lists at most twice per gameplay second. Living enemy members are tracked through
weak references. Death callbacks start the timer after the last member dies;
polling also catches missed callbacks when the dead pawn still exists. A native
death callback with a false dead flag can be confirmed by removal from the den
within two gameplay seconds, provided the native active count agrees with the
remaining living member list. An explicit false death return is rejected.
Expired references alone never count as kills. Obsolete members are removed without counting
kills; ambiguous empty groups suspend tracking until a complete native living
member list is available again. They are not permanently excluded. Confirmed
cooldowns remain active. Friendly/mixed/unknown groups stay native.

On expiry, an empty cleared den's `SpawnData.NumTotalActors` is reset to zero and
`NextSpawnTime` to zero once. This releases its exhausted lifetime spawn allowance
for native scheduling. Finite cooldowns keep the deadline until then; Forever
never releases the tally. New native generations get a new cooldown after clearing.
The DoSpawning/factory hooks remain supplementary observers; tracking does not
depend on them firing or installing successfully.

No native spawn calls, pawn-wide scans, health/level changes, corpse manipulation,
or quest flag changes. Ordinary pre-existing native no-respawn dens stay native.
Eligible cleared dens acquire a temporary flag owned by the mod. Missing
layouts are logged and skipped. Named kills may acquire a guard over a native
no-respawn flag already set to True; that original True is preserved on cleanup.
All native object reads occur synchronously.

Field names and native reset behavior were checked against
[Reset Enemies source](https://github.com/EerieGoesD/borderlands-1-goty-mods/blob/main/ResetEnemies/__init__.py)
by eeriegoesd ([author site](https://eeriegoesd.com/gaming/mods/)). This implementation
is separate; it does not import that mod's forced spawning or corpse logic.

## Diagnostic test

1. Install the updated SDKMOD, restart the game, enable the mod, select **1 minute**.
2. Load a fresh map. Press **F8** before approaching an ordinary bandit/skag group.
3. Clear the whole group. Press **F8** again immediately after the last kill.
4. Stay on the same map. Move away, let at least 60 seconds of unpaused gameplay
   pass, then revisit the spawn area. Press **F8** again, whether it respawned or not.
5. Send all three JSON files, the area/enemy names, and what happened.

F8 is rebindable in the mod's keybinds. **Export respawn diagnostics** in options
exports the same report. Avoid map travel, save/quit and manual Reset Enemies
commands during this test: those reset or interfere with tracked timers.
Native proximity/mission rules still govern whether an eligible group spawns.

Reports: `sdk_mods/settings/EnemyRespawnTimer/respawn-*.json`.
`Binaries/Win64/Plugins/unrealsdk.log` records the exact export path and any errors
under `[Enemy Respawn Timer]`. If no JSON appears, send that log.

Exports are read-only. They include hook readiness/observer activation, callback
counts, skip reasons, the last 200 events, tracked pawns (including expired weak
references), clear/deadline/native timestamps, a bounded native den inventory even
when nothing was tracked, and relevant mission conditions. Counters/events cover the current
mod-enabled session; map changes clear timers but leave diagnostic history.
Exports include poll counts, tracking mode, and `group_rearmed` events to distinguish
tracking failures, pending cooldowns and native scheduling after quota release.
Export remains available when the mod's respawn hook setup fails.
Other enemy encounters, co-op and longer finite delays have not been verified in-game.

Build: `python3 package.py`. Tests: `python3 -m unittest discover -s tests -v`.

## 1.2.0 diagnostic finding

The corrected DoSpawning path still received zero callbacks in the second Krom's
Canyon test. The two-enemy den (`PopulationOpportunityDen_31`) went from two living
members to none, but its lifetime tally stayed at 2 against `MaxTotalActors = 2`.
No tracking or cooldown occurred in 1.1.1. Membership polling replaces reliance on
that callback, and expiry now resets the exhausted tally. Allegiance paths also
normalize the SDK's colon separator before enemy classification.
Repeat the same test with this build; native scheduling after rearming still needs
in-game verification. Keep the original diagnostics for comparison.

## 1.2.1 diagnostic finding

The 1.2.0 bridge captures show polling working (301 polls by 151.834 gameplay
seconds), but bandits were rejected as unknown allegiance. The actual captured
path is `gd_allegiance.humanoidenemy.banditallegiance`; the filter only included
`humanenemy`, omitting `humanoidenemy`. The filter now recognizes that exact
namespace segment while preserving friendly/player/neutral exclusions. Polling
regressions now use the captured bandit allegiance, including a replay of the
recorded two-member clear and timer expiry. In-game spawning after rearming
remains unverified; repeat the same F8 test on a fresh map.

## 1.2.2 Fyrestone diagnostics

The Fyrestone capture shows five untracked deaths and an empty skag den 25 with
five total spawns. That den carries a `MissionPopulationAspect` and is excluded
by the current blanket aspect rule. Other skag dens were recognized and still
had living tracked members. The exports do not establish whether den 25's mission
is active or complete. F8 now includes each attached aspect's class and up to 96
reflected field values, plus its class schema, to investigate that restriction.
This build changes diagnostics only; mission-linked dens remain excluded.

## 1.2.3 Fyrestone mission gate

The new capture identifies den 25's gate as
`Z0_Missions.Missions.M_RepairClapTrap_02`, with reaction values
Disabled/Disabled/Disabled/Enabled, no mission item/objective payload, and
`IsEnabled = true`. The blanket aspect exclusion rejected this native-enabled
spawn. That exact gate pattern is now eligible while enabled. Unconditional
mission aspects without payloads are also eligible. Active-mission patterns,
objective/item payloads, unknown layouts, disabled gates and native no-respawn
flags remain excluded. No mission status, reaction table or activation flag is
changed. Retest the five skags with 1 minute; actual respawning remains unverified.

## 1.2.4 Rust Commons West tracking recovery

The restored `respawn-20261109-153814-498517.json` identifies five bandit dens and
one gatling turret den losing old actor references. These were not spiderants.
Some dens later contained replacement native actors, while the mod still kept
them ignored. The user identified the displayed map as **Rust Commons West**.
Coordinates are native den positions, not named landmarks:

| Package / den ID | Enemies | X | Y | Z |
|---|---|---:|---:|---:|
| Scrap_POI / 2 | Bandits | -3519 | -46482 | 3847 |
| scrap_p / 32 | Bandits | -32516 | -8450 | 2532 |
| scrap_p / 29 | Bandits | -33406 | -2538 | 2738 |
| Scrap_POI / 3 | Bandits | -19341 | 1343 | 1982 |
| Scrap_POI / 8 | Gatling turret | -19483 | 388 | 1974 |
| Scrap_POI / 4 | Bandits | -19635 | -14257 | 2051 |

Polling now drops obsolete members, reconciles current native membership, and
resumes tracking when the living list matches the native active count. Empty or
incomplete uncertain groups wait for a reliable baseline; disappearance alone
never starts a cooldown. It cannot reconstruct the time of an unobserved kill.
Confirmed finite/Forever cooldowns are preserved. Recovery diagnostics include
`tracking_suspended` / `tracking_recovered`, definition, location and active count.

Retest in Rust Commons West: F8 near the bandit/turret group, move away within the
same map, return and F8, clear the group and F8, wait a minute then return and F8.
Look for recovered tracking followed by an ordinary clear/rearm/respawn cycle.
Recovery is covered by mocked regressions; in-game validation remains pending.

## 1.2.5 Aqueduct turrets

The 1.2.3 captures `respawn-20261109-154430-810984.json` through
`respawn-20261109-154709-640038.json` show
`Trash_Aquaduct.PopulationOpportunityDen_7` (`AutoTurret_Gatling`) going from two
living members to zero, then remaining empty beyond a minute. No timer started:
the gate for `Z1_Missions.Missions.M_JaynisCleaningUp` was excluded. Its reaction
pattern is Disabled/Enabled/Enabled/Enabled; it is currently enabled and has no
objective/item payload. The gate rule now permits Disabled prefixes followed by
Enabled suffixes, while rejecting any pattern that disables again. Disabled dens,
objective/item payloads and native no-respawn flags remain protected.

This build includes 1.2.4 tracking recovery. Retest the same two turrets at 1 minute
with F8 before kills, after both die, and after returning. In-game respawning for
this turret den remains unverified.

## 1.2.6 All mission-gate combinations

At the user's request, all 16 combinations of four Enabled/Disabled reaction slots
are accepted. This includes gates that disable again and hypothetical patterns.
The den must still be currently enabled; the mod does not change mission reaction
tables or enable disabled dens. Mission objective/item payloads, native no-respawn
flags, unknown aspect classes and invalid table shapes/values remain excluded.
Tests exercise tracking, clearing and rearming for all 16 patterns, both with and
without a linked mission, and verify that the other exclusions still apply.
This expands coverage to staged gates without objective/item payloads; their
in-game behavior remains unverified. Includes 1.2.4 tracking recovery.

## 1.2.7 Turret death evidence

The latest captures report version 1.2.5. Aqueduct den 7 passed the mission gate
and tracked both turrets, then suspended at 60.306 and 101.998 gameplay seconds as
the native active count dropped from two to one to zero. No clear or cooldown
was recorded. The session also logged three rejected death callbacks with a false
`bIsDead` flag; those callbacks were not correlated in the old diagnostics, so
attributing them specifically to the turrets remains an inference.

A tracked native death callback now records bounded evidence when the dead flag
is false, unless its native result is explicitly false. It is accepted only if
the same actor leaves the native den within two gameplay seconds and native
active counts match the remaining living list. Disappearance without a recent
callback still suspends tracking. Confirmed deaths use the latest kill's gameplay
time, even when callbacks are confirmed out of order. The mod does not write the
pawn's dead flag. F8 records callback return values, pending evidence, and
`death_confirmed_by_native_removal` events for verification.

Includes all 16 gate combinations and tracking recovery. Repeat the turret test
with F8 before kills, immediately after each turret dies, and after waiting/returning.
Actual turret death handling and respawning remain unverified in-game.

## 1.2.8 Normal-play cleanup

Respawn behavior, timing options, tracking recovery and the accepted handling of
despawned survivors are unchanged. Removed exploratory class schemas, raw UObject
memory/property dumps and the invalid pawn Health field probe from exports.
F8 and the options export button remain available, including timers, native den
state, relevant mission conditions, counters, errors and the last 200 events.
Normal play writes no diagnostic files automatically. The in-memory event buffer
is bounded; lifecycle/error console messages remain useful for troubleshooting.
Saved settings persist, including Forever. Install the updated SDKMOD and restart.

## 1.2.9 Native reset bypass of Forever

The capture `respawn-20261109-211258-389217.json` retains a complete failure:
Aqueduct gatling den 7 cleared at 670.637 gameplay seconds and received its
Forever deadline. Two new turrets appeared at 1631.006 seconds, about 16 minutes
later, with no intervening map reset or mod rearm. Bandit den 15 also respawned
later. This proves the timestamp-only approach can be bypassed; the export does
not identify the exact native reset caller. Previous shorter Forever successes
did not establish coverage for this reset path.

Eligible cleared dens now hold `bNoRespawning = true` throughout their cooldown,
in addition to the existing timestamp. The original eligible value is restored
at finite expiry, disable or map reset. Pre-existing no-respawn dens are still
excluded; the mod recognizes its own flag so it can continue managing cooldowns.
Unexpected enemy spawns during an active cooldown no longer silently erase that
cooldown; F8 records `spawn_during_cooldown` events and guard ownership/state.
No actors are deleted if a bypass occurs. No survivor-restoration calls were added.

69 mocked tests pass, including the recorded turret timeline, late scheduling
resets, expiry/cleanup, existing native flags, and unexpected spawns. In-game
validation of the native guard is pending. Install this build, restart, clear the
gatling turrets and bandits on Forever, F8 after clearing, and F8 again on return
after at least 20 minutes of gameplay in the same map. Map travel still resets
Forever, as requested.

## 1.2.10 Missing native references

A reported `NoneType ... _get_address` error pointed only to the shared logger,
so the exact caller could not be established from that line. Known null-access
paths are now guarded: missing player/den world references, missing callback
targets and null native member/inventory slots. Transient missing worlds skip
processing without marking the den ignored, clearing its timer or releasing its
native no-respawn guard. Unresolved member slots do not count as kills/removal.
Future caught errors include their original source function and line.

74 mocked tests pass, including missing-world cooldown preservation, recovery
when references return, null actor slots/callbacks and contextual error reporting.
Includes the 1.2.9 native no-respawn guard; its longer in-game verification is
still separate from this null-reference fix. F8 and saved settings are retained.

## 1.2.11 Skag Gully reaction values

`respawn-20261111-130628-239917.json` shows three cleared Skag Gully skag dens
(10, 11 and 22) still guarded on Forever, with no recorded cooldown bypass. It
also shows den 7 containing two live skags while excluded as `scripted_aspect`.
Dens 7 and 8 use reaction table (0,0,3,0), with 3 named Respawn100Percent; den 9
uses (0,0,2,0), with 2 named Respawn50Percent. These ordinary skag dens carry no
mission objective/item payload. The previous filter accepted only 0 and 1, so
they were outside the timer's coverage. The capture cannot associate their earlier
untracked deaths with particular dens, so the player's complete respawn sequence
is not independently established.

The filter now accepts all 256 four-slot combinations of the four observed enum
values. Disabled dens, objective/item payloads, native no-respawn flags and unknown
values/layouts remain excluded. Mission tables are not rewritten. Regressions
cover all 256 combinations plus the three actual captured Skag Gully tables.
Install/restart and reclear the previously respawned group on Forever; F8 after
clearing and on returning. Coverage of these reaction values is newly implemented;
in-game validation is pending.

## 1.2.12 Rakk activation guard

The 1.2.11 captures show all six original rakk from Skag Gully den 25 killed by
569.535 gameplay seconds, with one new rakk at 1529.803 seconds. The distant
NextSpawnTime and bNoRespawning guard were both still set. This is a confirmed
native spawn bypass, not a leftover original rakk. The actual native caller is
not established by the export.

Cleared ordinary dens (Aspect is None) now additionally hold IsEnabled = false
throughout the cooldown. Only activation acquired from an enabled den is restored
at finite expiry, map reset or disable. A native re-enable is corrected on the
next poll while the owned cooldown remains active. Pre-existing disabled values
are preserved. Mission aspects are excluded from this activation override so
quest-controlled activation remains native. The existing timestamp/no-respawn
guards, mission objective/item exclusions and bypass diagnostics remain in place.
No native spawn calls, survivor restoration or actor deletion were added.

F8 now reports native_enabled, original_enabled and owns_activation_guard, and
includes native activation in bypass events. 79 mocked tests pass, including the
recorded rakk timeline, activation reassertion, finite/map/disable restoration,
pre-existing disabled activation and preservation of mission-linked activation.
The stronger guard still requires in-game verification. Install on the next
restart, continue playing with Forever, and export after a clear and if anything
returns in the same loaded map session. Map travel still clears the cooldown.

## 1.2.13 Persistent mission-gate activation

The 1.2.12 Fyrestone captures show skag den 25 cleared at 177.547 gameplay seconds,
then a new skag at 1138.066 seconds (16 minutes later). Its timestamp/no-respawn
guard remained set, but owns_activation_guard was false: the 1.2.12 activation
hold intentionally excluded every mission aspect. The attached gate is for
`Z0_Missions.Missions.M_RepairClapTrap_02`, has reaction table (1,1,1,0), and no
mission objective or item payload. This exposes an activation-guard coverage gap.

Activation ownership now also applies to eligible mission gates with an Enabled
suffix: (0,0,0,0), (1,0,0,0), (1,1,0,0), (1,1,1,0). Once natively enabled, these
gates remain enabled through subsequent mission stages. Eligibility recognizes
the mod's owned disabled state, preventing the next poll from dropping its own
guard. Staged disable/respawn reactions keep native activation. Objective/item
payloads and native no-respawn exclusions remain intact. Mission tables/statuses
are never changed. Owned activation is restored on expiry, disable and map reset.

82 mocked tests pass, including the recorded Fyrestone sequence, persistent gate
cleanup and preservation of staged mission activation. In-game verification is
pending. Restart with this build and reclear that group on Forever; export after
clearing and if anything returns. No map travel is needed for the retest.

## 1.3.0 Named-enemy cooldowns

At the user's request, recognized named enemies are covered even when their dens
carry native no-respawn flags or mission objectives. Bone Head and the other
previously observed named population aliases are recognized before spawning.
A standalone catalogue of exact native balance/archetype IDs covers base-game and
DLC named enemies; it is bundled locally and does not require another mod. Factory
balance observations and native pawn archetypes identify names without display-name
substring guesses or native IsBoss calls. The identity data reuses this repository's
verified named catalogue, with its pinned Dedicated Drops SDK/Boss Bars sources
retained in `named_enemies.py`. Unknown named identities and scripted spawns outside
the native den system cannot be guaranteed; F8 remains available for those cases.

Nothing is disabled merely because a named enemy exists. The first native spawn,
fight, loot and mission death callbacks run normally. On a confirmed named kill,
its den gets the selected cooldown and activation guard. A named kill in a mixed
den starts the timer immediately; later grunt deaths do not restart it. Existing
living grunts are not deleted. The mod does not accept/complete/reset missions or
edit saved mission states. Named disappearance alone is not a kill.

With Forever, guards last until map reload, travel or disable. Finite expiry
restores native activation/no-respawn settings; it never forces a one-shot boss to
respawn. Leaving and returning allows whatever fresh native spawns that map and
mission state normally permit. Guards and named kill history are session-only.

89 mocked tests pass, including Bone Head's initial spawn/mission objective,
original True no-respawn ownership, confirmed kill/Forever, finite expiry and map
reset; DLC archetype/factory identification; exact catalogue matches; mixed-den
kills; and disappearance handling. In-game named-boss and scripted multi-phase
behavior still require verification. Install/restart, select Forever, kill Bone
Head, F8, then F8 if he returns without map travel. Map exit/re-entry is the reset.

## 1.3.1 Diagnostic cleanup

Removed routine enable/disable/delay status logging, the redundant diagnostics
request line and duplicate export-failure logging. Successful manual exports still
log their file path; genuine errors remain deduplicated and bounded to 16 entries.
Expected factory callbacks outside the optional DoSpawning observer no longer
occupy the event buffer; their counter remains available in F8 reports.

F8/the export button, the last 200 in-memory events, counters and native inventory
remain available. No automatic diagnostic file writes were present or added.
Respawn scheduling, native guards, hooks and polling are unchanged from 1.3.0.
91 mocked tests pass, including quiet gameplay with retained clear history,
explicit F8/button exports and a failed export preserving the respawn guard.
