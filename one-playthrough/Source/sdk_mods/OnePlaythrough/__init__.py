"""One Playthrough: a continuous, level-scaled journey through Borderlands."""

from __future__ import annotations

from functools import wraps
from pathlib import Path

import unrealsdk
from mods_base import SETTINGS_DIR, BoolOption, ButtonOption, SpinnerOption, build_mod, get_pc, hook, keybind
from unrealsdk import logging
from unrealsdk.hooks import Block, Type, prevent_hooking_direct_calls

from .runtime import Runtime
from .storage import MissionLevels
from .diagnostics import export as export_snapshot
from .reward_encoding import initializer_specs, prepare_definition_data
from .loot import pool_specs
from .loot_trace import specs as loot_trace_specs
from .native_loot import spec as native_loot_spec

SETTINGS = SETTINGS_DIR / "OnePlaythrough"
# The SDK writes mod.json directly when enabling, including from the main menu.
# Create its parent before registration; no character/mission/export is required.
SETTINGS.mkdir(parents=True, exist_ok=True)
runtime = Runtime(unrealsdk, MissionLevels(
    SETTINGS / "mission-levels.json",
    legacy_path=SETTINGS_DIR / "Playthrough3" / "mission-levels.json",
))


enemy_difficulty = SpinnerOption(
    "Enemy difficulty", value="Normal", choices=["Easy", "Normal", "Hard"], wrap_enabled=True,
    description="Ordinary enemies only. Base is always the higher of your level and the vanilla area level. "
                "Ordinary native levels floor at your level +1; extra rolls stop at +3. New spawns only; bosses unchanged.",
)
# Read the saved/live option at spawn time; changing it never edits existing pawns.
runtime.spawns.difficulty = lambda: enemy_difficulty.value

loot_floor = BoolOption(
    "Loot level floor", value=True,
    description="New drops, containers and vendor stock: all equipment at most 2 levels below you. "
                "Rarity chances stay vanilla. Existing gear and mission rewards are unchanged.",
)
runtime.loot.selected = lambda: loot_floor.value


def safe(callback):
    @wraps(callback)
    def wrapped(*args, **kwargs):
        try:
            return callback(*args, **kwargs)
        except Exception as exc:
            runtime.problem(callback.__name__, exc)
            return None
    return wrapped


def on_enable():
    runtime.enabled = True
    runtime.sync(get_pc())


def on_disable():
    runtime.disable()


@hook("WillowGame.WillowPlayerController:ApplyMissionProfileData")
@safe
def applying_profile(obj, args, _ret, _func):
    runtime.sync(obj, profile=args.Profile)


@hook("WillowGame.WillowPlayerController:ApplyMissionProfileData", Type.POST)
@safe
def applied_profile(obj, _args, _ret, _func):
    runtime.sync(obj, loading=True)


@hook("WillowGame.WillowPlayerController:ClientSetProfileLoaded", Type.POST)
@hook("WillowGame.WillowPlayerController:OnExpLevelChange", Type.POST)
@hook("WillowGame.WillowPlayerController:AcceptTrackedMissions", Type.POST)
@hook("WillowGame.WillowPlayerController:SetMissionStatus", Type.POST)
@safe
def player_ready(obj, _args, _ret, _func):
    runtime.sync(obj)


@hook("Engine.WorldInfo:PostBeginPlay", Type.POST)
@safe
def world_ready(obj, _args, _ret, _func):
    pc = get_pc()
    if pc is not None and pc.WorldInfo == obj:
        runtime.sync(pc)


@hook("WillowGame.WillowPlayerController:ClientAddMission")
@safe
def accepting(obj, args, _ret, _func):
    if runtime.ensure(obj) is not None:
        runtime.missions.before_accept(obj, args.InMission)


@hook("WillowGame.WillowPlayerController:ClientAddMission", Type.POST_UNCONDITIONAL)
@safe
def accepted(obj, args, _ret, _func):
    runtime.missions.after_accept(obj, args.InMission)


@hook("WillowGame.WillowPlayerController:GetMissionEligibility")
@safe
def eligibility(obj, args, _ret, _func):
    if runtime.ensure(obj) is not None:
        runtime.missions.apply(args.InMission, obj)


@hook("WillowGame.MissionDefinition:GetExpLevel")
@hook("WillowGame.MissionDefinition:GetGameStage")
@safe
def mission_level(obj, _args, _ret, _func):
    pc = get_pc()
    if runtime.ensure(pc) is not None:
        runtime.missions.apply(obj, pc)


@hook("WillowGame.MissionDefinition:RefreshRewardGameStage", Type.POST_UNCONDITIONAL)
@safe
def refreshed_mission(obj, args, _ret, _func):
    pc = args.InWPC or get_pc()
    if runtime.ensure(pc) is not None:
        runtime.missions.apply(obj, pc)


def reward_hooks(path, controller_arg=None):
    stack = []

    @hook(path)
    @safe
    def before(obj, args, _ret, _func):
        token = None
        if controller_arg is None:
            pc, mission = args.InWPC or get_pc(), obj
        else:
            pc = obj
            mission = (args.MStatus.MissionDef if controller_arg == "MStatus"
                       else getattr(args, controller_arg))
        # Push a placeholder even when inactive, so a skipped nested call cannot
        # pop the enclosing call's scope in POST_UNCONDITIONAL.
        stack.append(None)
        if runtime.ensure(pc) is not None:
            token = runtime.missions.enter_reward(mission, pc)
        stack[-1] = token

    @hook(path, Type.POST_UNCONDITIONAL)
    @safe
    def after(_obj, _args, _ret, _func):
        runtime.missions.exit_reward(stack.pop() if stack else None)

    return [before, after]


def reward_initializer_hook(path, parameters, inputs, has_return):
    stack = []

    @hook(path, Type.POST_UNCONDITIONAL)
    @safe
    def after(_obj, _args, _ret, _func):
        if stack:
            runtime.loot.native.exit_definition(stack.pop())

    @hook(path)
    def before(_obj, args, _ret, func):
        stack.append(runtime.loot.native.enter_definition())
        invoked, result = False, None
        runtime.loot.trace.initializer(_obj, args, parameters, inputs)
        try:
            changes = {}
            for parameter in parameters:
                data = prepare_definition_data(runtime, args, parameter)
                if data is None:
                    data = runtime.loot.prepare(getattr(args, parameter))
                if data is not None:
                    changes[parameter] = data
            if not changes:
                return None
            values = {name: getattr(args, name) for name in inputs}
            values.update(changes)
            # SDK hook args are copies. Explicitly invoke native initialization
            # with the encoded struct, then block the original call.
            with prevent_hooking_direct_calls():
                invoked = True
                result = func(**values)
            return (Block, result) if has_return else Block
        except Exception as exc:
            runtime.problem("reward item initialization", exc)
            # Retrying an initializer after invocation risks duplicate effects.
            if invoked:
                return (Block, result) if has_return else Block
            return None
    return before, after


def native_loot_hook(path, inputs, has_return):
    @hook(path)
    def before(obj, args, _ret, func):
        invoked, assigned, result, original = False, False, None, None
        try:
            plan = runtime.loot.native.plan(obj, args, get_pc())
            if plan is None:
                return None
            original, encoded = plan
            values = {name: getattr(args, name) for name in inputs}
            values["InGradeIndex"] = encoded.ManufacturerGradeIndex
            # Fresh native inventory only, before its first stat initialization.
            # Persist the level in both native inputs and copied definition data.
            assigned = True
            obj.DefinitionData = encoded
            with prevent_hooking_direct_calls():
                invoked = True
                result = func(**values)
            return (Block, result) if has_return else Block
        except Exception as exc:
            runtime.problem("native loot initialization", exc)
            if invoked:
                return (Block, result) if has_return else Block
            if assigned:
                try:
                    obj.DefinitionData = original
                except Exception as restore_error:
                    runtime.problem("restore uninitialized loot data", restore_error)
            return None
    return before


def loot_pool_hooks(path, context, inputs=()):
    stack = []

    @hook(path)
    @safe
    def before(_obj, args, _ret, _func):
        runtime.loot.trace.event(path, _obj, args, inputs)
        stack.append(None)
        source = getattr(args, context) if context is not None else None
        stack[-1] = runtime.loot.enter(source, get_pc())

    @hook(path, Type.POST_UNCONDITIONAL)
    @safe
    def after(_obj, _args, _ret, _func):
        token = stack.pop() if stack else None
        if token is not None:
            runtime.loot.exit(token)

    return [before, after]


def loot_trace_hook(path, inputs):
    @hook(path)
    def observe(obj, args, _ret, _func):
        runtime.loot.trace.event(path, obj, args, inputs)
        return None
    return observe


def loot_death_hooks(path):
    stack = []

    @hook(path)
    @safe
    def before(obj, _args, _ret, _func):
        stack.append(None)
        if runtime.enabled and runtime.loot.selected():
            runtime.loot.native.boss_trace.death(obj, "before")
            stack[-1] = runtime.loot.dying(obj)

    @hook(path, Type.POST_UNCONDITIONAL)
    @safe
    def after(_obj, _args, _ret, _func):
        runtime.loot.native.boss_trace.death(_obj, "after")
        token = stack.pop() if stack else None
        if token is not None:
            try:
                runtime.loot.carried.commit(token)
            finally:
                runtime.loot.end_death(token)

    return [before, after]


def carried_drop_hooks(path):
    stack = []

    @hook(path)
    @safe
    def before(obj, args, _ret, _func):
        stack.append(None)
        runtime.loot.native.boss_trace.drop(obj, "before")
        stack[-1] = runtime.loot.carried.prepare(obj, args, get_pc())

    @hook(path, Type.POST_UNCONDITIONAL)
    @safe
    def after(obj, _args, _ret, _func):
        runtime.loot.native.boss_trace.drop(obj, "after")
        plan = stack.pop() if stack else None
        runtime.loot.carried.finish_drop(obj, plan, get_pc())

    return before, after


def native_spawn(obj, args, func, restore=False, vehicle=False):
    if runtime.spawns.active:
        return None
    invoked = False
    pawn = None
    original_definition = None
    swapped = False
    field = "VehicleBalanceDefinition" if vehicle else "PawnBalanceDefinition"
    try:
        level = runtime.ensure(get_pc())
        if level is None:
            return None
        level, definition = runtime.spawns.plan(obj, level, args.GameStage, vehicle)
        if args.GameStage == level and definition is None:
            return None
        if definition is not None:
            original_definition = getattr(obj, field)
            setattr(obj, field, definition)
            swapped = True
        values = [args.Master, args.SpawnLocationContextObject, args.SpawnLocation,
                  args.SpawnRotation, level, args.AwesomeLevel]
        if restore:
            values.append(args.AIPawnMemento)
        # The original factory initializes attributes once. A private definition
        # supplies rare exact levels without changing shared native definitions.
        runtime.spawns.active = True
        with prevent_hooking_direct_calls():
            invoked = True
            pawn = func(*values)
        return Block, pawn
    except Exception as exc:
        runtime.problem("native population", exc)
        # Never retry after invocation: that can duplicate enemies/quest events.
        return (Block, pawn) if invoked else None
    finally:
        runtime.spawns.active = False
        if swapped:
            try:
                setattr(obj, field, original_definition)
            except Exception as exc:
                runtime.problem("restore native factory", exc)


@hook("WillowGame.PopulationFactoryBalancedAIPawn:CreatePopulationActor")
def create_pawn(obj, args, _ret, func):
    return native_spawn(obj, args, func)


@hook("WillowGame.PopulationFactoryBalancedAIPawn:RestorePopulatedAIPawn")
def restore_pawn(obj, args, _ret, func):
    return native_spawn(obj, args, func, restore=True)


@hook("WillowGame.PopulationFactoryWillowVehicle:CreatePopulationActor")
def create_vehicle(obj, args, _ret, func):
    return native_spawn(obj, args, func, vehicle=True)


@hook("Engine.BaseBalanceDefinition:IsGameStageSupported")
@hook("Engine.BaseBalanceDefinition:SelectGradeIndex")
@hook("WillowGame.PopulationFactoryBalancedAIPawn:GetSpawnProbabilityAtThisGameStage")
@safe
def grade_boundary(obj, _args, _ret, _func):
    if runtime.ensure(get_pc()) is None:
        return
    definition = getattr(obj, "PawnBalanceDefinition", None)
    if definition is None and getattr(obj, "DefaultExpLevel", None) is not None:
        definition = obj
    if definition is not None:
        runtime.grades.prepare(definition)


def export_diagnostics(_option=None):
    # Manual diagnostics must remain available even if gameplay hooks fail.
    # Do not wrap this in safe(): that would hide the reason no file was saved.
    logging.info("[One Playthrough Diagnostics] Export requested.")
    try:
        path = export_snapshot(runtime, get_pc(), SETTINGS / "diagnostics", version=__version__)
    except Exception as exc:
        runtime.problem("export diagnostics", exc)
        logging.error(f"[One Playthrough Diagnostics] Export failed: {exc!r}")
        return None
    logging.info(f"[One Playthrough Diagnostics] Exported to {path}")
    return path


@keybind("Export One Playthrough diagnostics", "F10")
def export_key():
    export_diagnostics()


HOOKS = [applying_profile, applied_profile, player_ready, world_ready, accepting, accepted,
         eligibility, mission_level, refreshed_mission, create_pawn, restore_pawn,
         create_vehicle, grade_boundary]
try:
    specs = initializer_specs(unrealsdk)
    runtime.loot.trace.initializer_signatures = [
        {"path": path, "data": parameters, "inputs": inputs, "returns_value": has_return}
        for path, parameters, inputs, has_return in specs]
    runtime.missions.item_encoding["initializer_hooks"] = [spec[0] for spec in specs]
    runtime.loot.carried.configure(specs)
    HOOKS.extend(callback for spec in specs for callback in reward_initializer_hook(*spec))
    if not specs:
        runtime.problem("reward item encoding", ValueError("No compatible native item initializer found"))
except Exception as exc:
    runtime.problem("reward initializer discovery", exc)

try:
    specs = pool_specs(unrealsdk)
    runtime.loot.hooks = [{"path": path, "context": context, "parameters": inputs}
                          for path, context, inputs in specs]
    for path, context, _inputs in specs:
        if context is not None:
            HOOKS.extend(loot_pool_hooks(path, context, _inputs))
    if not specs or any(context is None for _, context, _ in specs):
        runtime.problem("loot pool discovery", ValueError("No compatible context for one or more native loot pool functions"))
except Exception as exc:
    runtime.problem("loot pool discovery", exc)
for name in ("WillowPawn", "WillowVehicle"):
    HOOKS.extend(loot_death_hooks(f"WillowGame.{name}:Died"))
for name in ("WillowWeapon", "WillowItem"):
    HOOKS.extend(carried_drop_hooks(f"WillowGame.{name}:DropFrom"))

try:
    spec = native_loot_spec(unrealsdk)
    path, inputs, has_return = spec
    runtime.loot.native.signature = {"path": path, "inputs": inputs, "returns_value": has_return}
    HOOKS.append(native_loot_hook(*spec))
except Exception as exc:
    runtime.problem("native loot initializer discovery", exc)

for name in ("GetExperienceReward", "GetCreditReward", "GetItemRewardForPlayer", "GenerateRewardString"):
    HOOKS.extend(reward_hooks("WillowGame.MissionDefinition:" + name))
HOOKS.extend(reward_hooks("WillowGame.WillowPlayerController:GrantMissionRewards", "InMission"))
HOOKS.extend(reward_hooks("WillowGame.WillowPlayerController:GetMissionDescriptionForUI", "MissionDef"))
HOOKS.extend(reward_hooks("WillowGame.WillowPlayerController:PopulateMissionDataFromStatus", "MStatus"))

__version__: str
__version_info__: tuple[int, ...]

build_mod(hooks=HOOKS, options=[enemy_difficulty, loot_floor,
                              ButtonOption("Export diagnostics", on_press=export_diagnostics)],
          keybinds=[export_key], on_enable=on_enable,
          on_disable=on_disable, settings_file=Path(SETTINGS / "mod.json"))
logging.info(f"One Playthrough Loaded: {__version__}, {__version_info__}; enabled={runtime.enabled}")
