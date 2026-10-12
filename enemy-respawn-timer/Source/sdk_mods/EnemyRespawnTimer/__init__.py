"""Delay repeat enemy populations without recreating actors or resetting quests.

First Windows build: native field names are supported by Reset Enemies' BL1E
source, while spawn/death correlation needs in-game verification. Every native
spawn executes normally once; this mod never calls DoSpawning itself.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import math

from mods_base import ButtonOption, SpinnerOption, SETTINGS_DIR, build_mod, get_pc, hook
import unrealsdk
from unrealsdk import logging
from unrealsdk.hooks import Block, Type, add_hook, remove_hook
from unrealsdk.unreal import WeakPointer

from .policy import DELAYS, Group

_enabled = False
_ready = False
_world_ref = None
_last_time = None
_spawn_path = None
_stack = []
_dens = {}
_actors = {}
_errors = []
_counts = {"tracked_spawns": 0, "cleared_groups": 0, "blocked_attempts": 0}


def error(exc):
    message = f"{type(exc).__name__}: {exc}"
    if message not in _errors and len(_errors) < 16:
        _errors.append(message)
        logging.error(f"[Enemy Respawn Timer] {message}")


def restore(entry):
    """Restore only our timestamp, never another mod's subsequent edit."""
    den = entry["ref"]()
    written = entry["written"]
    if den is None or written is None:
        return
    data = den.SpawnData
    if float(data.NextSpawnTime) == written:
        data.NextSpawnTime = entry["original"]
        den.SpawnData = data
    entry["written"] = None


def reset_session():
    global _world_ref, _last_time
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


def host_clock():
    """Use game time; paused gameplay does not advance cooldowns."""
    global _world_ref, _last_time
    if not _enabled or not _ready:
        return None
    pc = get_pc()
    if pc is None or pc.Pawn is None:
        return None
    world = pc.WorldInfo
    if world.NetMode == 3:
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


def valid_den(den, world):
    # Aspected/one-shot opportunities can drive mission waves or scripted fights.
    # Preserve their native behavior rather than stalling a quest.
    if (str(den.Name).startswith("Default__") or den.bDeleteMe or den.bPendingDelete
            or den.bNoRespawning or getattr(den, "Aspect", None) is not None):
        return False
    if den.WorldInfo._get_address() != world._get_address():
        return False
    data = den.SpawnData
    return (str(data.PopulationDefName) not in ("", "None")
            and int(data.MaxActiveActors) > 0)


def entry_for(den, world):
    address = den._get_address()
    entry = _dens.get(address)
    definition = str(den.SpawnData.PopulationDefName)
    if entry is not None and (entry["ref"]() is None or entry["definition"] != definition):
        restore(entry)
        for actor in entry["group"].members:
            _actors.pop(actor, None)
        _dens.pop(address, None)
        entry = None
    if not valid_den(den, world):
        if entry is not None:
            restore(entry)
            entry["ignored"] = True
        return None
    if entry is None:
        entry = {"ref": WeakPointer(den), "definition": definition, "group": Group(),
                 "original": None, "written": None, "ignored": False}
        _dens[address] = entry
    return None if entry["ignored"] else entry


def set_deadline(entry, choice):
    den = entry["ref"]()
    deadline = entry["group"].deadline(choice)
    if den is None or deadline is None or entry["ignored"]:
        return
    data = den.SpawnData
    if entry["written"] is None:
        entry["original"] = float(data.NextSpawnTime)
    data.NextSpawnTime = deadline
    den.SpawnData = data
    # Read back the engine's float32 value for ownership-aware restoration.
    entry["written"] = float(den.SpawnData.NextSpawnTime)


def before_spawning(obj, _args, _ret, _func):
    # A placeholder is necessary even for blocked/skipped calls: the matching
    # unconditional post hook must unwind exactly one frame, including nesting.
    frame = {"ref": WeakPointer(obj), "entry": None}
    try:
        clock = host_clock()
        if clock is not None:
            world, now = clock
            entry = entry_for(obj, world)
            frame["entry"] = entry
            if entry is not None and entry["group"].cleared_at is not None:
                set_deadline(entry, respawn_delay.value)
                if entry["group"].blocked(now, respawn_delay.value):
                    _counts["blocked_attempts"] += 1
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
    den = frame["ref"]()
    if den is None or den._get_address() != obj._get_address():
        _stack.clear()
        error(RuntimeError("Spawn context mismatch; correlation cleared"))


def record_spawn(obj, _args, pawn, _func):
    if not _enabled or not _ready or pawn is None or not _stack:
        return
    entry = _stack[-1]["entry"]
    if entry is None or entry["ignored"]:
        return
    try:
        allegiance = getattr(obj, "SpawnAllegiance", None) or getattr(pawn, "Allegiance", None)
        path = allegiance._path_name().lower() if allegiance is not None else ""
        enemy = (not any(word in path for word in ("friendly", "player", "neutral"))
                 and any(word in path for word in (".creatureenemy.", ".humanenemy.", ".enemy.", ".enemies.")))
        if not enemy:
            # Mixed NPC/enemy dens and unknown allegiances stay native.
            restore(entry)
            entry["ignored"] = True
            return
        den = entry["ref"]()
        if den is None:
            return
        address = pawn._get_address()
        if entry["group"].cleared_at is not None:
            # A new native generation now owns its scheduling. Capture a fresh
            # native timestamp if/when this generation is subsequently cleared.
            entry["original"] = None
            entry["written"] = None
        entry["group"].spawned(address)
        _actors[address] = (WeakPointer(pawn), den._get_address())
        _counts["tracked_spawns"] += 1
    except Exception as exc:
        entry["ignored"] = True
        try:
            restore(entry)
        except Exception as restore_exc:
            error(restore_exc)
        error(exc)


def record_death(obj, _args, _ret, _func):
    try:
        clock = host_clock()
        if clock is None or not obj.bIsDead:
            return
        address = obj._get_address()
        actor = _actors.pop(address, None)
        if actor is None or actor[0]() is None:
            return
        entry = _dens.get(actor[1])
        if entry is None or entry["ignored"]:
            return
        if entry["group"].died(address, clock[1]):
            den = entry["ref"]()
            if den is not None and valid_den(den, clock[0]):
                set_deadline(entry, respawn_delay.value)
                _counts["cleared_groups"] += 1
    except Exception as exc:
        error(exc)


def change_delay(_option, value):
    try:
        if host_clock() is None:
            return
        for entry in _dens.values():
            set_deadline(entry, value)
        logging.info(f"[Enemy Respawn Timer] Delay: {value}.")
    except Exception as exc:
        error(exc)


respawn_delay = SpinnerOption(
    "Respawn Delay", "15 minutes", list(DELAYS),
    description=("Wait after the last enemy in a tracked group dies: 5/15/30 minutes, "
                 "1/3 hours, or Forever until map reload. Uses gameplay time. "
                 "Native proximity/mission rules still decide whether a group can spawn."),
    on_change_while_enabled=change_delay,
)


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
            path = function._path_name()
            owner, _, name = path.rpartition(".")
            return owner + ":" + name
    for function in unrealsdk.find_all("Function"):
        path = function._path_name()
        if path.endswith(".PopulationOpportunityDen.DoSpawning"):
            owner, _, name = path.rpartition(".")
            return owner + ":" + name
    raise RuntimeError("Native PopulationOpportunityDen.DoSpawning not found; export diagnostics")


def on_enable():
    global _enabled, _ready, _spawn_path
    reset_session()
    _errors.clear()
    for key in _counts:
        _counts[key] = 0
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
    result = {"version": "1.0.0", "enabled": _enabled, "ready": _ready,
              "delay": respawn_delay.value, "spawn_hook": _spawn_path,
              "counts": dict(_counts), "errors": list(_errors), "dens": []}
    if pc is not None:
        result["game_time"] = float(pc.WorldInfo.TimeSeconds)
        result["net_mode"] = int(pc.WorldInfo.NetMode)
    for entry in _dens.values():
        den = entry["ref"]()
        if den is None:
            continue
        try:
            result["dens"].append({"den": den._path_name(), "definition": entry["definition"],
                                   "ignored": entry["ignored"], "alive_tracked": len(entry["group"].members),
                                   "cleared_at": entry["group"].cleared_at,
                                   "deadline": entry["group"].deadline(respawn_delay.value),
                                   "native_next_spawn": float(den.SpawnData.NextSpawnTime)})
        except Exception as exc:
            result.setdefault("read_errors", []).append(str(exc))
    # Explicit user export only: read class schemas to resolve BL1E differences.
    result["schemas"] = {}
    for name in ("PopulationOpportunityDen", "WillowPopulationMaster", "PopulationFactoryBalancedAIPawn"):
        try:
            cls = unrealsdk.find_class(name)
            if cls is not None:
                result["schemas"][name] = {"path": cls._path_name(), "fields": [str(prop.Name) for prop in cls._properties()]}
        except Exception as exc:
            result.setdefault("read_errors", []).append(str(exc))
    return result


def export_diagnostics(_option=None):
    try:
        folder = SETTINGS_DIR / "EnemyRespawnTimer"
        folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
        path = folder / f"respawn-{stamp}.json"
        path.write_text(json.dumps(snapshot(), indent=2, allow_nan=False))
        logging.info(f"[Enemy Respawn Timer] Exported to {path}")
    except Exception as exc:
        error(exc)


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
    hooks=[map_change, *spawn_hooks, *death_hooks],
    settings_file=Path(SETTINGS_DIR) / "EnemyRespawnTimer.json",
    on_enable=on_enable,
    on_disable=on_disable,
)
