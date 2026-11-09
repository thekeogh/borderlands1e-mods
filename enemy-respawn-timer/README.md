# Enemy Respawn Timer

Private mod for Borderlands GOTY Enhanced. Author: keogh. Version 1.2.8.
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

The timer starts when the last tracked enemy in a spawn group dies, rather than
one global timer for the whole map. First encounters spawn normally. After expiry,
the group is eligible to respawn; native distance, visibility, population quotas
and mission conditions still apply. This mod does not forcibly summon enemies
at the instant a timer ends or make normally non-respawning bosses respawn.
Native default respawn timing is not established here; it can vary by opportunity.

Paused game time does not count. Changing the option updates cleared groups from
their original clear time. Entering a different map or reloading clears tracking.
Forever uses both a session-only guard and a native timestamp 999,999,999 seconds
after the clear time, never a saved permanent deletion. Disabling restores owned
timestamps and any reset tally still at zero (before a new native generation).
Native member lists also allow tracking enemies already alive when enabled.
Use a fresh map for repeatable tests. Settings persist; enemy timers do not.

Quest objective/item opportunities, unknown scripted aspects, native no-respawn
flags, friendly or mixed NPC/enemy groups, unknown allegiances and unsupported
layouts stay native. Enabled MissionPopulationAspect gates are allowed only when
they have no objective or item payload and their reaction table contains four
Enabled/Disabled slots. All 16 combinations are accepted, including combinations
not yet seen in-game. Native activation is preserved. This protects first encounters, quest NPCs and scripted waves; it means
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
or quest flag changes. Native no-respawn flags remain untouched. Missing layouts
are logged and skipped. All native object reads occur synchronously.

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
