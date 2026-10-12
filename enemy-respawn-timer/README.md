# Enemy Respawn Timer

Private mod for Borderlands GOTY Enhanced. Author: keogh. Version 1.0.0.
First Windows test build; mocked tests cannot verify native timing/correlation.

Copy `dist/EnemyRespawnTimer.sdkmod` to your game's `sdk_mods`, restart and enable
**Enemy Respawn Timer** before loading a map. This is a separate mod: leave
Playthrough 3 enabled. No existing mod, save, reference file or UPK is changed.

## Options

| Respawn Delay | Gameplay seconds after clearing a group |
|---|---:|
| 5 minutes | 300 |
| **15 minutes (default)** | **900** |
| 30 minutes | 1,800 |
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
Forever uses both a session-only guard and a distant native timestamp, never a
saved permanent deletion. Disabling restores timestamps still owned by this mod.
Enable before entering a fresh map: already spawned enemies cannot be correlated
retroactively. Settings persist; enemy timers do not.

Quest/scripted opportunities with an Aspect, native no-respawn flags, friendly
or mixed NPC/enemy groups, unknown allegiances and unsupported layouts stay
native. This protects first encounters, quest NPCs and scripted waves; it means
the mod cannot guarantee every enemy in the game follows your selected timer.
Applies on the host. Co-op behavior is not verified. A manual Reset Enemies mod
can override timestamps/counters, so avoid manually resetting during timer tests.

## Implementation and compatibility

The native declaring function for `PopulationOpportunityDen.DoSpawning` is resolved
at runtime. Its pre/post hooks provide a spawn context, while unconditional
population-factory post hooks correlate completed AI/vehicle spawns to that den.
This also receives the replacement pawn returned by Playthrough 3's blocked
factory hook. Enemy death callbacks remove tracked members and schedule
`SpawnData.NextSpawnTime` when a group becomes empty.

No `IsEnemy`/`IsBoss` template calls, native spawn reinvocations, pawn scans,
health/level changes, quota resets, corpse manipulation or per-frame timer loops.
Data is accessed synchronously; actors/dens/worlds are retained through weak
references only. Only `NextSpawnTime` is assigned; original native no-respawn
flags and spawn totals remain untouched. A missing hook/layout logs an error
and leaves that path native rather than guessing memory fields.

Field names and native reset behavior were checked against
[Reset Enemies source](https://github.com/EerieGoesD/borderlands-1-goty-mods/blob/main/ResetEnemies/__init__.py)
by eeriegoesd ([author site](https://eeriegoesd.com/gaming/mods/)). This implementation
is separate; it does not import that mod's forced spawning or corpse logic.

## First gameplay check

Choose **5 minutes**, then load a fresh map and clear an ordinary bandit/skag
group. Check that it does not return early; leave/revisit its spawn area after
five gameplay minutes. Native spawn eligibility may require leaving its vicinity.
Repeat with **Forever**: the cleared group should stay gone until map reload.
Check that untouched groups and mission encounters still spawn normally.

Use **Export respawn diagnostics** in the mod's options after a spawn/clear.
JSON is written to `sdk_mods/settings/EnemyRespawnTimer/respawn-*.json`.
`Binaries/Win64/Plugins/unrealsdk.log` records the exact path and any errors under
`[Enemy Respawn Timer]`. The export is read-only and includes hook readiness,
tracked spawns, clears, blocked attempts, native timestamps and den schemas.
If tracking/clears remain zero, export for investigation rather than assuming
the delay has taken effect. Windows validation remains pending.

Build: `python3 package.py`. Tests: `python3 -m unittest discover -s tests -v`.
