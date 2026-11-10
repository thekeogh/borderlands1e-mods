"""Track native den members and rearm cleared enemy groups after a cooldown.

BL1E does not dispatch observed native spawns through the DoSpawning hook.
Membership polling uses weak references; native rules still perform spawning.
"""

from __future__ import annotations

from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path
import json
import math
import traceback

from mods_base import ButtonOption, SpinnerOption, SETTINGS_DIR, build_mod, get_pc, hook, keybind
import unrealsdk
from unrealsdk import logging
from unrealsdk.hooks import Block, Type, add_hook, remove_hook
from unrealsdk.unreal import WeakPointer

from .policy import DELAYS, Group

_enabled = False
_ready = False
_world_ref = None
_last_time = None
_last_poll = None
_spawn_path = None
_stack = []
_dens = {}
_actors = {}
_errors = []
VERSION = "1.2.10"
_counts = Counter()
_skips = Counter()
_events = deque(maxlen=200)


def trace(kind, **details):
    # Store primitive data only; diagnostics must not keep native actors alive.
    _events.append({"event": kind, "game_time": _last_time, **details})


def object_path(obj):
    try:
        return None if obj is None else obj._path_name()
    except Exception as exc:
        return f"<path unavailable: {exc}>"


def error(exc):
    message = f"{type(exc).__name__}: {exc}"
    frames = traceback.extract_tb(exc.__traceback__)
    if frames:
        frame = frames[-1]
        message += f" [{Path(frame.filename).name}:{frame.lineno} in {frame.name}]"
    if message not in _errors and len(_errors) < 16:
        _errors.append(message)
        logging.error(f"[Enemy Respawn Timer] {message}")


def release_native_guard(entry):
    """Undo the no-respawn flag only if we acquired it from an eligible den."""
    original = entry["original_no_respawn"]
    if original is None:
        return
    den = entry["ref"]()
    if den is not None and bool(den.bNoRespawning):
        den.bNoRespawning = original
    entry["original_no_respawn"] = None


def restore(entry):
    """Restore owned scheduling fields and release our native guard."""
    release_native_guard(entry)
    den = entry["ref"]()
    if den is None:
        return
    if entry["written"] is None and entry.get("original_total") is None:
        return
    data = den.SpawnData
    if entry["written"] is not None and float(data.NextSpawnTime) == entry["written"]:
        data.NextSpawnTime = entry["original"]
    original_total = entry.get("original_total")
    if original_total is not None and int(data.NumTotalActors) == 0:
        data.NumTotalActors = original_total
    den.SpawnData = data
    entry["written"] = None
    entry["original_total"] = None


def reset_session():
    global _world_ref, _last_time, _last_poll
    trace("session_reset", dens=len(_dens), actors=len(_actors))
    for entry in _dens.values():
        try:
            restore(entry)
        except Exception as exc:
            error(exc)
    _dens.clear()
    _actors.clear()
    _stack.clear()
    _world_ref = None
    _last_time = None
    _last_poll = None


def host_clock():
    """Use game time; paused gameplay does not advance cooldowns."""
    global _world_ref, _last_time
    if not _enabled or not _ready:
        _skips["disabled_or_not_ready"] += 1
        return None
    pc = get_pc()
    if pc is None or pc.Pawn is None:
        _skips["no_player_pawn"] += 1
        return None
    world = pc.WorldInfo
    if world is None:
        _skips["missing_player_world"] += 1
        return None
    if world.NetMode == 3:
        _skips["client_world"] += 1
        return None
    now = float(world.TimeSeconds)
    if not math.isfinite(now):
        raise ValueError("Invalid world time")
    old_world = _world_ref() if _world_ref is not None else None
    if (old_world is None or old_world._get_address() != world._get_address()
            or (_last_time is not None and now < _last_time)):
        reset_session()
        _world_ref = WeakPointer(world)
    _last_time = now
    return world, now


def passive_mission_gate(den, aspect):
    """Accept all four-slot Enabled/Disabled tables while the native den is enabled.

    Objective/item payloads and native no-respawn flags remain excluded.
    """
    try:
        if aspect.Class._path_name() != "WillowGame.MissionPopulationAspect" or not den.IsEnabled:
            return False
        objective = aspect.MissionObjective
        items = aspect.MissionItems
        if (objective.MissionDefinition is not None or int(objective.ObjectiveIndex) != -1
                or items.MissionDefinition is not None or items.MissionItemPool is not None):
            return False
        reactions = aspect.MissionReactions
        states = tuple(int(state) for state in reactions.MissionStatusOpportunityReaction)
        # User requested every combination, including configurations not yet seen.
        # Captured enum values: Enabled=0, Disabled=1. Keep unknown layouts native.
        return len(states) == 4 and all(state in (0, 1) for state in states)
    except (AttributeError, TypeError, ValueError):
        return False


def den_skip_reason(den, world):
    # These exclusions preserve mission waves, NPCs and one-shot encounters.
    if den is None:
        return "missing_den"
    if world is None:
        return "missing_player_world"
    for field in ("bDeleteMe", "bPendingDelete"):
        if getattr(den, field):
            return field
    if den.bNoRespawning:
        entry = _dens.get(den._get_address())
        if entry is None or entry["original_no_respawn"] is None:
            return "bNoRespawning"
    if str(den.Name).startswith("Default__"):
        return "default_object"
    aspect = getattr(den, "Aspect", None)
    if aspect is not None and not passive_mission_gate(den, aspect):
        return "scripted_aspect"
    den_world = den.WorldInfo
    if den_world is None:
        return "missing_den_world"
    if den_world._get_address() != world._get_address():
        return "different_world"
    data = den.SpawnData
    if str(data.PopulationDefName) in ("", "None"):
        return "no_population_definition"
    if int(data.MaxActiveActors) <= 0:
        return "no_active_actor_capacity"
    return None


def valid_den(den, world):
    return den_skip_reason(den, world) is None


def entry_for(den, world):
    if den is None or world is None:
        _skips["missing_den" if den is None else "missing_player_world"] += 1
        return None
    address = den._get_address()
    entry = _dens.get(address)
    definition = str(den.SpawnData.PopulationDefName)
    if entry is not None and (entry["ref"]() is None or entry["definition"] != definition):
        restore(entry)
        for actor in entry["group"].members:
            _actors.pop(actor, None)
        _dens.pop(address, None)
        entry = None
    reason = den_skip_reason(den, world)
    if reason is not None:
        _skips[reason] += 1
        if _skips[reason] <= 5:
            trace("den_skipped", den=object_path(den), reason=reason)
        # A streamed actor can temporarily have no world. Keep any existing
        # cooldown/owned guard so it can resume when the reference returns.
        if reason == "missing_den_world":
            return None
        if entry is not None:
            restore(entry)
            entry["ignored"] = True
        return None
    if entry is None:
        entry = {"ref": WeakPointer(den), "definition": definition, "group": Group(),
                 "original": None, "written": None, "ignored": False,
                 "released": False, "original_total": None, "suspended": False,
                 "death_evidence": {}, "last_death_at": None,
                 "original_no_respawn": None, "unexpected_spawns": set()}
        _dens[address] = entry
    return None if entry["ignored"] else entry


def set_deadline(entry, choice):
    den = entry["ref"]()
    deadline = entry["group"].deadline(choice)
    if den is None or deadline is None or entry["ignored"]:
        return
    # A native pre-existing no-respawn flag is outside our ownership.
    if entry["original_no_respawn"] is None and den.bNoRespawning:
        return
    data = den.SpawnData
    if entry["written"] is None:
        entry["original"] = float(data.NextSpawnTime)
    data.NextSpawnTime = deadline
    den.SpawnData = data
    # Read back the engine's float32 value for ownership-aware restoration.
    entry["written"] = float(den.SpawnData.NextSpawnTime)
    # Vanilla reset paths can erase NextSpawnTime and NumTotalActors together.
    # Hold the den's native no-respawn flag throughout the actual cooldown.
    if entry["original_no_respawn"] is None:
        entry["original_no_respawn"] = False
    den.bNoRespawning = True


def before_spawning(obj, _args, _ret, _func):
    # A placeholder is necessary even for blocked/skipped calls: the matching
    # unconditional post hook must unwind exactly one frame, including nesting.
    _counts["den_spawn_calls"] += 1
    frame = {"ref": WeakPointer(obj) if obj is not None else None, "entry": None}
    try:
        clock = host_clock()
        if clock is not None:
            world, now = clock
            entry = entry_for(obj, world)
            frame["entry"] = entry
            if entry is not None and entry["group"].cleared_at is not None:
                if entry["group"].blocked(now, respawn_delay.value):
                    set_deadline(entry, respawn_delay.value)
                    _counts["blocked_attempts"] += 1
                    if _counts["blocked_attempts"] <= 10:
                        trace("spawn_blocked", den=object_path(obj),
                              deadline=entry["group"].deadline(respawn_delay.value))
                    _stack.append(frame)
                    return Block
    except Exception as exc:
        frame["entry"] = None
        error(exc)
    _stack.append(frame)
    return None


def after_spawning(obj, _args, _ret, _func):
    if not _stack:
        return
    frame = _stack.pop()
    if obj is None or frame["ref"] is None:
        return
    den = frame["ref"]()
    if den is None or den._get_address() != obj._get_address():
        _stack.clear()
        error(RuntimeError("Spawn context mismatch; correlation cleared"))


def record_spawn(obj, _args, pawn, _func):
    _counts["factory_callbacks"] += 1
    if not _enabled or not _ready:
        return
    if pawn is None:
        _skips["factory_returned_none"] += 1
        return
    if not _stack:
        _skips["factory_outside_den"] += 1
        if _skips["factory_outside_den"] <= 10:
            trace("uncorrelated_spawn", factory=object_path(obj), pawn=object_path(pawn))
        return
    entry = _stack[-1]["entry"]
    if entry is None or entry["ignored"]:
        _skips["factory_without_eligible_den"] += 1
        return
    track_spawn(entry, pawn, getattr(obj, "SpawnAllegiance", None))


def track_spawn(entry, pawn, allegiance=None):
    if pawn is None:
        _skips["missing_spawn_actor"] += 1
        return
    if entry["ignored"]:
        return
    try:
        allegiance = allegiance or getattr(pawn, "Allegiance", None)
        path = allegiance._path_name().lower().replace(":", ".") if allegiance is not None else ""
        # Windows bandit captures use gd_allegiance.HumanoidEnemy.BanditAllegiance.
        # Keep exact namespace segments; a broad "enemy" substring is unsafe.
        enemy = (not any(word in path for word in ("friendly", "player", "neutral"))
                 and any(word in path for word in (
                     ".creatureenemy.", ".humanoidenemy.", ".humanenemy.", ".enemy.", ".enemies.")))
        if not enemy:
            # Mixed NPC/enemy dens and unknown allegiances stay native.
            restore(entry)
            entry["ignored"] = True
            entry["ignore_reason"] = "unknown_or_non_enemy_allegiance"
            _skips["unknown_or_non_enemy_allegiance"] += 1
            trace("allegiance_skipped", pawn=object_path(pawn), allegiance=path)
            return
        den = entry["ref"]()
        if den is None:
            return
        address = pawn._get_address()
        if address in entry["group"].members:
            return
        if (entry["group"].cleared_at is not None and _last_time is not None
                and entry["group"].blocked(_last_time, respawn_delay.value)):
            # Never silently replace a live cooldown if a native/script path
            # bypasses it. Retain the evidence so F8 can diagnose that path.
            if address not in entry["unexpected_spawns"]:
                if len(entry["unexpected_spawns"]) < 64:
                    entry["unexpected_spawns"].add(address)
                    trace("spawn_during_cooldown", **den_context(den), pawn=object_path(pawn),
                          native_no_respawn=bool(den.bNoRespawning),
                          deadline=entry["group"].deadline(respawn_delay.value))
                _counts["cooldown_bypasses"] += 1
            return
        if entry["group"].cleared_at is not None:
            release_native_guard(entry)
            entry["unexpected_spawns"].clear()
            # A new native generation now owns its scheduling. Capture a fresh
            # native timestamp if/when this generation is subsequently cleared.
            entry["original"] = None
            entry["written"] = None
            entry["original_total"] = None
            entry["released"] = False
        if not entry["group"].members:
            entry["last_death_at"] = None
        entry["group"].spawned(address)
        _actors[address] = (WeakPointer(pawn), den._get_address())
        _counts["tracked_spawns"] += 1
        trace("spawn_tracked", den=object_path(den), pawn=object_path(pawn), allegiance=path)
    except Exception as exc:
        entry["ignored"] = True
        try:
            restore(entry)
        except Exception as restore_exc:
            error(restore_exc)
        error(exc)


def record_death(obj, _args, _ret, _func):
    _counts["death_callbacks"] += 1
    process_death(obj, native_callback=True, returned=_ret)


def process_death(obj, native_callback=False, returned=None):
    if obj is None:
        _skips["missing_death_actor"] += 1
        return
    try:
        clock = host_clock()
        if clock is None:
            return
        address = obj._get_address()
        actor = _actors.get(address)
        if not obj.bIsDead:
            _skips["death_callback_not_dead"] += 1
            if native_callback and actor is not None:
                entry = _dens.get(actor[1])
                if entry is not None and not entry["ignored"]:
                    trace("death_callback_without_dead_flag", **den_context(entry["ref"]()),
                          pawn=object_path(obj), returned=str(returned))
                    # An explicit rejected Died return is not death evidence.
                    if returned is not False:
                        entry["death_evidence"][address] = {
                            "time": clock[1], "pawn": object_path(obj), "returned": str(returned)}
            return
        if actor is None or actor[0]() is None:
            _skips["death_not_tracked"] += 1
            return
        entry = _dens.get(actor[1])
        if entry is None or entry["ignored"]:
            return
        trace("death_tracked", pawn=object_path(obj))
        finish_death(address, entry, clock[0], clock[1])
    except Exception as exc:
        error(exc)


def finish_death(address, entry, world, when):
    """Called only for a dead flag or a recent native death plus den removal."""
    _actors.pop(address, None)
    entry["death_evidence"].pop(address, None)
    previous = entry["last_death_at"]
    entry["last_death_at"] = when if previous is None else max(when, previous)
    if entry["group"].died(address, entry["last_death_at"]):
        if entry["suspended"]:
            entry["group"].cleared_at = None
            return
        den = entry["ref"]()
        if den is not None and any(member is None or not member.bIsDead for member in getattr(den, "SpawnedDenMembers", ())):
            entry["group"].cleared_at = None
            return
        if den is not None and valid_den(den, world):
            entry["released"] = False
            set_deadline(entry, respawn_delay.value)
            _counts["cleared_groups"] += 1
            trace("group_cleared", den=object_path(den),
                  deadline=entry["group"].deadline(respawn_delay.value), written=entry["written"])


def den_context(den):
    """Primitive location metadata makes future lifecycle issues reproducible."""
    return {"den": object_path(den),
            "definition": str(den.SpawnData.PopulationDefName) if den is not None else None,
            "location": str(getattr(den, "Location", None))}


def poll_dens(world, now):
    """Read native membership; DoSpawning is not dispatched through our hook on BL1E."""
    _counts["den_polls"] += 1
    for den in unrealsdk.find_all("PopulationOpportunityDen"):
        try:
            if den is None:
                _skips["missing_den"] += 1
                continue
            if str(den.Name).startswith("Default__"):
                continue
            entry = entry_for(den, world)
            if entry is None:
                continue
            raw_members = list(den.SpawnedDenMembers)
            null_members = sum(pawn is None for pawn in raw_members)
            if null_members:
                _skips["null_native_members"] += null_members
                # An unresolved slot is not evidence of death or removal.
                continue
            native_members = raw_members
            # Register all living members before processing any missed deaths.
            for pawn in native_members:
                if not pawn.bIsDead:
                    track_spawn(entry, pawn)
            if entry["ignored"]:
                continue
            native_addresses = {pawn._get_address() for pawn in native_members}
            live_addresses = {pawn._get_address() for pawn in native_members if not pawn.bIsDead}
            # Death callbacks can arrive while the turret's dead flag stays false.
            # Confirm only after native membership and active count also agree.
            for address, evidence in sorted(list(entry["death_evidence"].items()),
                                            key=lambda pair: pair[1]["time"]):
                age = now - evidence["time"]
                if age > 2.0 or age < 0:
                    entry["death_evidence"].pop(address, None)
                    trace("death_evidence_expired", **den_context(den), pawn=evidence["pawn"])
                elif (address not in native_addresses
                      and int(den.SpawnData.NumActiveActors) == len(live_addresses)):
                    trace("death_confirmed_by_native_removal", **den_context(den),
                          pawn=evidence["pawn"], death_time=evidence["time"])
                    _counts["deaths_confirmed_by_native_removal"] += 1
                    finish_death(address, entry, world, evidence["time"])
            missing = []
            dead = []
            for address in list(entry["group"].members):
                actor = _actors.get(address)
                pawn = actor[0]() if actor is not None else None
                if pawn is not None and pawn.bIsDead:
                    dead.append(pawn)
                elif pawn is None or address not in live_addresses:
                    # Native membership can change without a Died callback.
                    # Discard obsolete members without counting them as kills.
                    _actors.pop(address, None)
                    entry["group"].members.discard(address)
                    missing.append(address)
            if missing:
                entry["suspended"] = True
                _counts["lost_members"] += len(missing)
                trace("tracking_suspended", **den_context(den), missing_count=len(missing),
                      native_alive=int(den.SpawnData.NumActiveActors))
            if (entry["suspended"] and live_addresses
                    and int(den.SpawnData.NumActiveActors) == len(live_addresses)):
                # A complete native living list is a new reliable baseline.
                entry["suspended"] = False
                _counts["recovered_groups"] += 1
                trace("tracking_recovered", **den_context(den), native_alive=len(live_addresses))
            for pawn in dead:
                _counts["polled_deaths"] += 1
                process_death(pawn)
            if entry["suspended"]:
                continue
            if entry["ignored"] or entry["group"].cleared_at is None:
                continue
            if entry["group"].blocked(now, respawn_delay.value):
                set_deadline(entry, respawn_delay.value)
            elif not entry["released"]:
                # Logs show NumTotalActors == MaxTotalActors after the clear.
                # Expiring NextSpawnTime alone cannot make that den eligible.
                if int(den.SpawnData.NumActiveActors) != 0 or any(not p.bIsDead for p in native_members):
                    continue
                release_native_guard(entry)
                data = den.SpawnData
                entry["original_total"] = int(data.NumTotalActors)
                data.NumTotalActors = 0
                data.NextSpawnTime = 0.0
                den.SpawnData = data
                entry["written"] = float(den.SpawnData.NextSpawnTime)
                entry["released"] = True
                _counts["rearmed_groups"] += 1
                trace("group_rearmed", den=object_path(den), original_total=entry["original_total"])
        except Exception as exc:
            error(exc)
    # Drop expired native references after streamed-out dens disappear.
    for address, entry in list(_dens.items()):
        if entry["ref"]() is None:
            for actor in entry["group"].members:
                _actors.pop(actor, None)
            _dens.pop(address, None)


@hook("Engine.GameViewportClient:PostRender", Type.POST_UNCONDITIONAL)
def poll_tick(_obj, _args, _ret, _func):
    global _last_poll
    try:
        clock = host_clock()
        if clock is None:
            return
        world, now = clock
        if _last_poll is not None and now - _last_poll < 0.5:
            return
        _last_poll = now
        poll_dens(world, now)
    except Exception as exc:
        error(exc)


def change_delay(_option, value):
    try:
        if host_clock() is None:
            return
        for entry in _dens.values():
            if entry["released"]:
                restore(entry)
                entry["released"] = False
            set_deadline(entry, value)
        logging.info(f"[Enemy Respawn Timer] Delay: {value}.")
    except Exception as exc:
        error(exc)


respawn_delay = SpinnerOption(
    "Respawn Delay", "30 minutes", list(DELAYS),
    description=("Wait after the last enemy in a tracked group dies: 1/30 minutes, "
                 "1/3 hours, or Forever until map reload. Uses gameplay time. "
                 "Native proximity/mission rules still decide whether a group can spawn."),
    on_change_while_enabled=change_delay,
)


def spawn_hook_path(function):
    # SDK paths may already use ':' before the function. Splitting only on '.'
    # turned WillowGame.PopulationOpportunityDen:DoSpawning into the invalid
    # WillowGame:PopulationOpportunityDen:DoSpawning seen in the Windows logs.
    path = function._path_name().replace(":", ".")
    owner, _, name = path.rpartition(".")
    return owner + ":" + name


def resolve_spawn_function():
    # Resolve the actual native declaring class instead of trusting a guessed
    # hook package. Unknown layouts remain native and appear in diagnostics.
    for owner in ("GearboxFramework.PopulationOpportunityDen", "WillowGame.PopulationOpportunityDen"):
        try:
            function = unrealsdk.find_object("Function", owner + ".DoSpawning")
        except ValueError:
            # The SDK raises for missing objects; try the next declaring class.
            continue
        if function is not None:
            return spawn_hook_path(function)
    for function in unrealsdk.find_all("Function"):
        path = spawn_hook_path(function)
        if path.endswith(".PopulationOpportunityDen:DoSpawning"):
            return path
    raise RuntimeError("Native PopulationOpportunityDen.DoSpawning not found; export diagnostics")


def on_enable():
    global _enabled, _ready, _spawn_path
    reset_session()
    _errors.clear()
    _counts.clear()
    _counts.update(tracked_spawns=0, cleared_groups=0, blocked_attempts=0,
                   den_spawn_calls=0, factory_callbacks=0, death_callbacks=0)
    _skips.clear()
    _events.clear()
    # Old releases offered 5/15 minutes; fall back if saved settings retain them.
    if respawn_delay.value not in DELAYS:
        respawn_delay.value = "30 minutes"
    _enabled = True
    _ready = False
    try:
        _spawn_path = resolve_spawn_function()
        if not add_hook(_spawn_path, Type.PRE, "EnemyRespawnTimer.Pre", before_spawning):
            raise RuntimeError("Could not install respawn pre hook")
        if not add_hook(_spawn_path, Type.POST_UNCONDITIONAL, "EnemyRespawnTimer.Post", after_spawning):
            raise RuntimeError("Could not install respawn post hook")
        _ready = True
        logging.info(f"[Enemy Respawn Timer] Enabled; {respawn_delay.value}; {_spawn_path}.")
    except Exception as exc:
        if _spawn_path is not None:
            remove_hook(_spawn_path, Type.PRE, "EnemyRespawnTimer.Pre")
            remove_hook(_spawn_path, Type.POST_UNCONDITIONAL, "EnemyRespawnTimer.Post")
        error(exc)
        # Membership polling is independent of this optional spawn observer.
        _ready = True


def on_disable():
    global _enabled, _ready
    _enabled = False
    _ready = False
    if _spawn_path is not None:
        remove_hook(_spawn_path, Type.PRE, "EnemyRespawnTimer.Pre")
        remove_hook(_spawn_path, Type.POST_UNCONDITIONAL, "EnemyRespawnTimer.Post")
    reset_session()
    logging.info("[Enemy Respawn Timer] Disabled; owned native timestamps restored.")


@hook("WillowGame.WillowGameInfo:PreCommitMapChange", Type.PRE)
def map_change(_obj, _args, _ret, _func):
    reset_session()


def snapshot():
    pc = get_pc()
    result = {"version": VERSION, "captured_utc": datetime.now(timezone.utc).isoformat(), "enabled": _enabled, "ready": _ready,
              "delay": respawn_delay.value, "spawn_hook": _spawn_path,
              "tracking_mode": "native_den_members", "last_poll": _last_poll,
              "counts": dict(_counts), "skip_counts": dict(_skips),
              "recent_events": list(_events), "stack_depth": len(_stack),
              "errors": list(_errors), "dens": []}
    try:
        if pc is not None:
            result["game_time"] = float(pc.WorldInfo.TimeSeconds)
            result["net_mode"] = int(pc.WorldInfo.NetMode)
            result["world"] = object_path(pc.WorldInfo)
            result["player_pawn"] = object_path(pc.Pawn)
    except Exception as exc:
        result.setdefault("read_errors", []).append(str(exc))
    for entry in _dens.values():
        den = entry["ref"]()
        if den is None:
            continue
        try:
            result["dens"].append({"den": den._path_name(), "definition": entry["definition"],
                                   "ignored": entry["ignored"], "ignore_reason": entry.get("ignore_reason"),
                                   "released": entry["released"], "tracking_suspended": entry["suspended"],
                                   "pending_death_evidence": list(entry["death_evidence"].values()),
                                   "owns_no_respawn_guard": entry["original_no_respawn"] is not None,
                                   "original_no_respawn": entry["original_no_respawn"],
                                   "native_no_respawn": bool(den.bNoRespawning),
                                   "alive_tracked": len(entry["group"].members),
                                   "actors": [actor_snapshot(address) for address in entry["group"].members],
                                   "original_next_spawn": entry["original"],
                                   "written_next_spawn": entry["written"],
                                   "cleared_at": entry["group"].cleared_at,
                                   "deadline": entry["group"].deadline(respawn_delay.value),
                                   "native_next_spawn": float(den.SpawnData.NextSpawnTime)})
        except Exception as exc:
            result.setdefault("read_errors", []).append(str(exc))
    # Explicit read-only inventory also works when no spawn context was observed.
    result["native_dens"] = []
    try:
        for den in unrealsdk.find_all("PopulationOpportunityDen"):
            if den is None:
                continue
            if len(result["native_dens"]) >= 300:
                result["native_dens_truncated"] = True
                break
            if str(den.Name).startswith("Default__"):
                continue
            row = {"den": object_path(den)}
            result["native_dens"].append(row)
            try:
                row["tracked"] = den._get_address() in _dens
                row["fields"] = read_fields(den, (
                    "bNoRespawning", "bDeleteMe", "bPendingDelete", "Aspect",
                    "MaxTotalActors", "RespawnDelay", "RespawnDelayAfterDeath",
                    "DenSpawningState", "IsEnabled", "Location", "SpawnedDenMembers"))
                row["spawn_data"] = read_fields(den.SpawnData, (
                    "PopulationDefName", "NextSpawnTime", "MaxActiveActors", "NumActiveActors",
                    "NumTotalActors"))
                row["aspect"] = aspect_snapshot(getattr(den, "Aspect", None))
                row["skip_reason"] = den_skip_reason(den, pc.WorldInfo) if pc else "no_player"
            except Exception as exc:
                row["error"] = str(exc)
    except Exception as exc:
        result.setdefault("read_errors", []).append(str(exc))
    result["observer_hooks"] = {}
    for index, observer in enumerate([map_change, poll_tick, *spawn_hooks, *death_hooks]):
        try:
            result["observer_hooks"][f"{index}:{observer.hook_identifier}"] = observer.get_active_count()
        except Exception as exc:
            result.setdefault("read_errors", []).append(str(exc))
    return result


def aspect_snapshot(aspect):
    """Read metadata only: an attached aspect does not establish quest status."""
    if aspect is None:
        return None
    result = {"object": object_path(aspect)}
    try:
        cls = aspect.Class
        result["class"] = object_path(cls)
        # Keep useful mission conditions; omit exploratory UObject/memory dumps.
        result["fields"] = read_fields(aspect, (
            "MissionReactions", "MissionItems", "MissionObjective"))
    except Exception as exc:
        result["read_error"] = str(exc)
    return result


def actor_snapshot(address):
    actor = _actors.get(address)
    pawn = actor[0]() if actor is not None else None
    if pawn is None:
        return {"address": address, "valid": False}
    return {"pawn": object_path(pawn), "valid": True,
            "fields": read_fields(pawn, ("bIsDead", "bDeleteMe", "bPendingDelete"))}


def read_fields(obj, names):
    result = {}
    for name in names:
        try:
            value = getattr(obj, name)
            result[name] = value if value is None or isinstance(value, (str, int, float, bool)) else str(value)
        except Exception as exc:
            result[name] = {"read_error": str(exc)}
    return result


def export_diagnostics(_option=None):
    logging.info("[Enemy Respawn Timer] Diagnostics requested.")
    try:
        folder = SETTINGS_DIR / "EnemyRespawnTimer"
        folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
        path = folder / f"respawn-{stamp}.json"
        path.write_text(json.dumps(snapshot(), indent=2, allow_nan=False), encoding="utf-8")
        logging.info(f"[Enemy Respawn Timer] Exported to {path}")
        return path
    except Exception as exc:
        error(exc)
        logging.error(f"[Enemy Respawn Timer] Diagnostics export failed: {exc}")
        return None


@keybind("Export respawn diagnostics", "F8")
def export_key():
    export_diagnostics()


def post_hook(path, callback):
    return hook(path, Type.POST_UNCONDITIONAL)(callback)


spawn_hooks = [post_hook(path, record_spawn) for path in (
    "WillowGame.PopulationFactoryBalancedAIPawn:CreatePopulationActor",
    "WillowGame.PopulationFactoryBalancedAIPawn:RestorePopulatedAIPawn",
    "WillowGame.PopulationFactoryWillowVehicle:CreatePopulationActor",
)]
death_hooks = [post_hook(path, record_death) for path in (
    "WillowGame.WillowAIPawn:Died", "WillowGame.WillowVehicle:Died",
)]

build_mod(
    options=[respawn_delay, ButtonOption("Export respawn diagnostics", on_press=export_diagnostics,
                                        description="Write current timers, counters and native fields to SDK settings.")],
    hooks=[map_change, poll_tick, *spawn_hooks, *death_hooks],
    keybinds=[export_key],
    settings_file=Path(SETTINGS_DIR) / "EnemyRespawnTimer.json",
    on_enable=on_enable,
    on_disable=on_disable,
)
