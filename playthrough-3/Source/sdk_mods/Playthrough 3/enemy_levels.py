"""Weighted PT3 population levels using native initialization data only.

Never call IsEnemy/IsDead on templates or spawning pawns. Never hook/re-enter
level setters or rescale partially initialized actors. The native population
factory performs its complete initialization once at the selected level.
"""

from __future__ import annotations

from collections import Counter
from contextlib import contextmanager, nullcontext
from random import randrange

from mods_base import BoolOption, SliderOption, get_pc, hook
from unrealsdk import logging, find_object
from unrealsdk.hooks import Block, prevent_hooking_direct_calls
from unrealsdk.unreal import WeakPointer
from .named_enemies import NAMED_LEVEL, named_enemy

BASE_LEVEL = 69
WEIGHTS = {
    0: (100,), 1: (65, 35), 2: (50, 35, 15),
    3: (45, 35, 15, 5), 4: (45, 35, 12, 5, 3),
    5: (45, 35, 10, 5, 3, 2),
}
INPUT_FIELDS = ("BaseValueConstant", "BaseValueAttribute",
                "InitializationDefinition", "BaseValueScaleConstant")
KEEP_ALIVE = 0x4000
EXACT_STAGE = "gd_Balance.EnemyLevel.EnemyLevel_GameStage_exact"
spread = SliderOption(
    "Enemy Level Spread", 3, 0, 5, 1, True,
    description=("PT3 enemy populations start at 69, maximum 69 + spread. "
                 "Default 3: 69/70/71/72 at 45/35/15/5%. "
                 "Named enemies/bosses stay at 69. "
                 "Applies when native populations spawn or restore."),
)
spawn_trace = BoolOption(
    "Enemy Spawn Debug Logging", False,
    description=("Log bounded spawn phases for crash troubleshooting. "
                 "Errors and F10 diagnostics remain available when off."),
)
_enabled = False
_counts = Counter()
_ordinary_counts = Counter()
_named_counts = Counter()
_named_definitions = {}
_skipped = Counter()
_targets = {}  # Weak references only; never pin spawned actors.
_problems = []
_traced = set()
_definitions = {}
_pins = {}


def chosen_level(value, ticket=None):
    weights = WEIGHTS[max(0, min(5, int(value)))]
    if ticket is None:
        ticket = randrange(100)
    if not 0 <= ticket < 100:
        raise ValueError("Level ticket must be between 0 and 99")
    for offset, weight in enumerate(weights):
        if ticket < weight:
            return BASE_LEVEL + offset
        ticket -= weight
    raise AssertionError("Weights must sum to 100")


def problem(exc):
    message = f"{type(exc).__name__}: {exc}"
    if message not in _problems and len(_problems) < 12:
        _problems.append(message)
        logging.error(f"[PT3 Enemies] {message}")


def host_player():
    if not _enabled:
        return None
    pc = get_pc()
    if (pc is None or pc.Pawn is None or pc.WorldInfo.NetMode == 3
            or pc.GetCurrentPlaythrough() != 2):
        return None
    return pc


def factory_data(obj, vehicle=False):
    if vehicle:
        return (getattr(obj, "VehicleBalanceDefinition", None),
                getattr(obj, "VehicleArchetype", None))
    definition = obj.PawnBalanceDefinition
    return definition, definition.AIPawnArchetype


def enemy_definition(obj, definition, archetype, known_named=False):
    """Read allegiance/definition identifiers; never execute pawn methods."""
    if archetype is None:
        return False
    allegiance = getattr(obj, "SpawnAllegiance", None) or archetype.Allegiance
    path = allegiance._path_name().lower() if allegiance is not None else ""
    if any(term in path for term in ("friendly", "player", "neutral")):
        return False
    if known_named:
        return True
    if any(term in path for term in (".creatureenemy.", ".humanenemy.", ".enemy.", ".enemies.")):
        return True
    # Unknown definitions remain native rather than probing a template.
    return bool(path) and "_enemies" in definition._path_name().lower()


def pin(obj):
    if obj is not None and obj._get_address() not in _pins:
        _pins[obj._get_address()] = (obj, bool(obj.ObjectFlags & KEEP_ALIVE))
        obj.ObjectFlags |= KEEP_ALIVE


def exact_native_levels(definition):
    """Keep each pawn's experience tied to its own game stage throughout PT3.

    Use the game's exact-stage attribute, not a shared constant that would later
    be overwritten by another spawn. Removing only grade experience offsets
    retains native health/damage/badass bonuses. Restore on PT1/PT2 or disable.
    """
    address = definition._get_address()
    if address in _definitions:
        return
    attribute = find_object("AttributeDefinition", EXACT_STAGE)
    if attribute is None:
        raise ValueError(f"Missing native level attribute: {EXACT_STAGE}")
    values = definition.DefaultExpLevel
    original = {name: getattr(values, name) for name in INPUT_FIELDS}
    offsets = [grade.GradeModifiers.ExpLevel for grade in definition.Grades]
    for obj in (definition, attribute, original["BaseValueAttribute"], original["InitializationDefinition"]):
        pin(obj)
    _definitions[address] = (definition, original, offsets)
    try:
        values.BaseValueConstant = 0.0
        values.BaseValueAttribute = attribute
        values.InitializationDefinition = None
        values.BaseValueScaleConstant = 1.0
        for grade in definition.Grades:
            grade.GradeModifiers.ExpLevel = 0
    except Exception:
        restore_definition(_definitions.pop(address))
        raise


def restore_definition(patch):
    definition, original, offsets = patch
    for name, value in original.items():
        setattr(definition.DefaultExpLevel, name, value)
    for index, offset in enumerate(offsets):
        if index < len(definition.Grades):
            definition.Grades[index].GradeModifiers.ExpLevel = offset


def restore_definitions():
    for patch in _definitions.values():
        restore_definition(patch)
    _definitions.clear()
    for obj, was_pinned in _pins.values():
        if not was_pinned:
            obj.ObjectFlags &= ~KEEP_ALIVE
    _pins.clear()


@contextmanager
def native_level_data(definition, natural_stage, target):
    """Widen grade eligibility only for this call, then restore its ranges."""
    grades = [(grade.GameStageRequirement,
               grade.GameStageRequirement.MinGameStage,
               grade.GameStageRequirement.MaxGameStage) for grade in definition.Grades]
    exact_native_levels(definition)
    try:
        for req, low, high in grades:
            if low <= natural_stage <= high:
                req.MinGameStage = min(low, target)
                req.MaxGameStage = max(high, target)
        yield
    finally:
        for req, low, high in reversed(grades):
            req.MinGameStage = low
            req.MaxGameStage = high


def spawn(obj, args, func, *, restore=False, vehicle=False):
    invoked = False
    pawn = None
    trace = False
    try:
        if host_player() is None:
            return None
        definition, archetype = factory_data(obj, vehicle)
        name = named_enemy(definition, archetype)
        if definition is None and (not vehicle or name is None):
            _skipped["missing vehicle balance definition"] += 1
            return None
        path = (definition if definition is not None else archetype)._path_name()
        if not enemy_definition(obj, definition, archetype, name is not None):
            _skipped[path] += 1
            return None
        target = NAMED_LEVEL if name is not None else chosen_level(spread.value)
        key = (path, target, restore, vehicle)
        if spawn_trace.value and key not in _traced and len(_traced) < 64:
            _traced.add(key)
            trace = True
            logging.info(f"[PT3 Enemies] Preparing {path}; level {target}; restore={restore}.")
        call_args = [args.Master, args.SpawnLocationContextObject,
                     args.SpawnLocation, args.SpawnRotation, target, args.AwesomeLevel]
        if restore:
            call_args.append(args.AIPawnMemento)
        # Named vehicles may have only an archetype. Their existing native
        # factory receives stage 69; never invent AI balance data or rescale.
        level_data = (native_level_data(definition, args.GameStage, target)
                      if definition is not None else nullcontext())
        with level_data:
            if trace:
                logging.info(f"[PT3 Enemies] Calling native factory: {path}; level {target}.")
            with prevent_hooking_direct_calls():
                invoked = True
                pawn = func(*call_args)
            if trace:
                logging.info(f"[PT3 Enemies] Native factory returned; spawned={pawn is not None}.")
        if trace:
            logging.info("[PT3 Enemies] Grade ranges restored.")
        if pawn is not None:
            _counts[target] += 1
            if name is not None:
                _named_counts[name] += 1
                _named_definitions[path] = name
            else:
                _ordinary_counts[target] += 1
            _targets[pawn._get_address()] = (WeakPointer(pawn), target, path)
            if sum(_counts.values()) % 128 == 0:
                for address, (ref, _, _) in list(_targets.items()):
                    if ref() is None:
                        _targets.pop(address, None)
        return Block, pawn
    except Exception as exc:
        problem(exc)
        # Never duplicate a spawn or its mission side effects after invocation.
        return (Block, pawn) if invoked else None


@hook("WillowGame.PopulationFactoryBalancedAIPawn:CreatePopulationActor")
def create_pawn(obj, args, _ret, func):
    return spawn(obj, args, func)


@hook("WillowGame.PopulationFactoryBalancedAIPawn:RestorePopulatedAIPawn")
def restore_pawn(obj, args, _ret, func):
    return spawn(obj, args, func, restore=True)


@hook("WillowGame.PopulationFactoryWillowVehicle:CreatePopulationActor")
def create_vehicle(obj, args, _ret, func):
    return spawn(obj, args, func, vehicle=True)


def on_enable():
    global _enabled
    _enabled = True
    _counts.clear()
    _ordinary_counts.clear()
    _named_counts.clear()
    _named_definitions.clear()
    _skipped.clear()
    _targets.clear()
    _problems.clear()
    _traced.clear()
    logging.info(f"[PT3 Enemies] Native factory policy enabled; spread {int(spread.value)}.")
    logging.info(f"[PT3 Enemies] Listed named enemies/bosses use level {NAMED_LEVEL}.")


def on_disable():
    global _enabled
    _enabled = False
    restore_definitions()
    _targets.clear()


def snapshot(_pc):
    """Inspect only completed, tracked spawns when the user requests F10."""
    result = {"policy": "native_factory_data", "enabled": _enabled,
              "spread": int(spread.value), "minimum": 69,
              "maximum": 69 + int(spread.value),
              "weights": WEIGHTS[max(0, min(5, int(spread.value)))],
              "assigned_counts": dict(_counts), "skipped_definitions": dict(_skipped),
              "ordinary_assigned_counts": dict(_ordinary_counts),
              "named_enemy_level": NAMED_LEVEL, "named_enemy_counts": dict(_named_counts),
              "named_definitions": dict(_named_definitions),
              "patched_definitions": len(_definitions),
              "problems": list(_problems), "tracked_enemies": []}
    for ref, target, definition in list(_targets.values()):
        pawn = ref()
        if pawn is None:
            continue
        try:
            result["tracked_enemies"].append({
                "pawn": pawn._path_name(), "definition": definition,
                "named_enemy": _named_definitions.get(definition),
                "assigned_level": target, "game_stage": pawn.GetGameStage(),
                "exp_level": pawn.GetExpLevel(),
            })
        except Exception as exc:
            result.setdefault("read_errors", []).append(str(exc))
        if len(result["tracked_enemies"]) >= 200:
            break
    return result


HOOKS = [create_pawn, restore_pawn, create_vehicle]
