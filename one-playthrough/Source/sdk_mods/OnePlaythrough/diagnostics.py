"""Manual, bounded, read-only snapshots for Windows gameplay verification."""

from datetime import datetime, timezone
from itertools import islice
import json
import math

from .economy_diagnostics import collect as collect_economy
from .rewards import describe as describe_rewards
from .spawns import hostile


def serialize(value, depth=0, on_reference=None):
    if isinstance(value, float) and not math.isfinite(value):
        return {"nonfinite": str(value)}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): serialize(item, depth + 1, on_reference) for key, item in value.items()}
    if hasattr(value, "_path_name"):
        if on_reference is not None:
            on_reference(value)
        return value._path_name()
    if depth >= 6:
        return "depth limit"
    # WrappedArray also has _type, but it describes the element PROPERTY.
    # It is not a WrappedStruct's UScriptStruct and has no _properties().
    if isinstance(value, (list, tuple)) or type(value).__name__ == "WrappedArray":
        return [serialize(value[i], depth + 1, on_reference) for i in range(min(len(value), 300))]
    if hasattr(value, "_type"):
        fields = {}
        for prop in value._type._properties():
            name = str(prop.Name)
            try:
                fields[name] = serialize(getattr(value, name), depth + 1, on_reference)
            except Exception as exc:
                fields[name] = {"error": repr(exc)}
        return fields
    return str(value)


def initialization(value):
    return {name: (item._path_name() if hasattr(item, "_path_name") else item)
            for name in ("BaseValueConstant", "BaseValueAttribute", "InitializationDefinition", "BaseValueScaleConstant")
            for item in (getattr(value, name),)}


def live_enemy_combat(sdk, pc, read):
    """Read the captured BL1E HUD stat fields from live pawns on manual export."""
    if pc is None or getattr(pc, "Pawn", None) is None:
        return []
    world = pc.WorldInfo
    samples = []
    pawns = read("find live AI pawns", lambda: sdk.find_all("WillowAIPawn", exact=False), [])
    for pawn in islice(pawns, 500):
        def sample():
            path = pawn._path_name()
            if (getattr(pawn, "WorldInfo", None) != world or "default__" in path.lower()
                    or any(getattr(pawn, flag, False)
                           for flag in ("bDeleteMe", "bPendingDelete", "bIsDead", "bPlayedDeath"))):
                return None
            state = getattr(pawn, "BalanceDefinitionState", None)
            definition = getattr(state, "BalanceDefinition", None)
            if definition is None or not hostile(pawn, definition, pawn):
                return None
            health = getattr(pawn, "HealthMaxVar", None)
            if health is None or health <= 0:
                return None  # The HUD fields may not be initialized yet.
            return {"pawn": path, "name": str(getattr(pawn, "AIPawnName", "")),
                    "balance": definition._path_name(), "grade": getattr(state, "GradeIndex", None),
                    "level": pawn.ExpLevel, "max_health": health,
                    "max_shield": getattr(pawn, "ShieldMaxVar", None),
                    "has_shield": getattr(pawn, "bHasShieldVar", None)}

        record = read("live AI combat fields", sample)
        if record is not None:
            samples.append(record)
            if len(samples) == 80:
                break
    return samples


def export(runtime, pc, directory, version="unknown"):
    snapshot = serialize(runtime.snapshot())
    snapshot.update({"captured_utc": datetime.now(timezone.utc).isoformat(), "version": version,
                     "export_complete": False, "partial": True, "export_errors": [],
                     "missions": [], "enemy_definitions": []})
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    path = directory / f"one-playthrough-{stamp}.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(snapshot, stream, indent=2, allow_nan=False)
        stream.write("\n")
    # A policy report now exists before any optional Unreal reflection reads.
    # Even an interrupted collection leaves useful enabled/scaling/error state.
    def read(label, getter, default=None):
        try:
            return getter()
        except Exception as exc:
            if len(snapshot["export_errors"]) < 100:
                snapshot["export_errors"].append({"context": label, "error": repr(exc)})
            return default

    snapshot["regions"]["region_levels"] = read("native regional floors", runtime.regions.levels_snapshot, [])
    for mission in read("find missions", lambda: list(runtime.sdk.find_all("MissionDefinition", exact=False)), []):
        if len(snapshot["missions"]) >= 600:
            break
        name = read("mission path", mission._path_name, "unreadable mission")
        if "default__" in str(name).lower():
            continue
        record = {"path": name}
        for field, attr in (("level", "ExpLevel"), ("stage", "GameStage"), ("minimum", "MinimumLevel")):
            record[field] = read(f"{name}.{attr}", lambda attr=attr: getattr(mission, attr))
        record["region"] = read(f"{name}.GameStageRegion", lambda: serialize(mission.GameStageRegion))
        if str(name).lower() in runtime.missions.levels:
            record["item_rewards"] = read(f"{name} item reward inheritance",
                lambda: describe_rewards(mission, runtime.missions.levels[str(name).lower()]), [])
        snapshot["missions"].append(record)
    for definition in read("find enemy definitions", lambda: list(runtime.sdk.find_all("AIPawnBalanceDefinition", exact=False)), []):
        if len(snapshot["enemy_definitions"]) >= 600:
            break
        name = read("enemy definition path", definition._path_name, "unreadable enemy definition")
        if "default__" in str(name).lower():
            continue
        record = {"path": name, "grades": []}
        record["default_level"] = read(f"{name}.DefaultExpLevel", lambda: initialization(definition.DefaultExpLevel))
        for i, grade in enumerate(read(f"{name}.Grades", lambda: list(definition.Grades), [])):
            if i >= 300:
                break
            record["grades"].append(read(f"{name}.Grades[{i}]", lambda: {
                "min": grade.GameStageRequirement.MinGameStage,
                "max": grade.GameStageRequirement.MaxGameStage,
                "level_modifier": grade.GradeModifiers.ExpLevel,
                "display_name": str(getattr(grade.GradeModifiers, "DisplayName", "")),
            }))
        snapshot["enemy_definitions"].append(record)
    if pc is not None:
        for name, getter in (
            ("playthrough_index", lambda: pc.GetCurrentPlaythrough()),
            ("map", lambda: pc.WorldInfo.GetMapName()),
            ("mission_progress", lambda: serialize(pc.MissionPlaythroughData)),
            ("unaccepted_mission_data", lambda: serialize(getattr(pc, "NonStartedMissionData", []))),
            ("save_file_id", lambda: pc.SaveGameFileId),
        ):
            snapshot[name] = read(name, getter)
    snapshot["live_enemy_combat"] = read(
        "live enemy combat", lambda: live_enemy_combat(runtime.sdk, pc, read), [])
    snapshot["economy"] = read("economy", lambda: collect_economy(runtime.sdk, pc, serialize, read), {})
    snapshot["export_complete"] = True
    snapshot["partial"] = bool(snapshot["export_errors"])
    temporary = path.with_suffix(".tmp")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(serialize(snapshot), stream, indent=2, allow_nan=False)
            stream.write("\n")
        temporary.replace(path)
    except Exception as exc:
        raise RuntimeError(f"Basic report saved to {path}; full export failed: {exc!r}") from exc
    return path
