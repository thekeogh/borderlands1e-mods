"""Player-relative regions using the game's existing first-playthrough data."""

from __future__ import annotations

from contextlib import contextmanager
import math

from .patches import Patches, resolve

INPUT_FIELDS = ("BaseValueConstant", "BaseValueAttribute", "InitializationDefinition",
                "BaseValueScaleConstant")

PACKAGES = ("gd_globals", "gd_GameStages", "dlc1_PackageDefinition",
            "dlc2_packagedefinition", "dlc3_PackageDefinition", "dlc4_PackageDefinition")
GLOBALS = ("gd_globals.general.globals", "dlc1_packagedefinition.customglobals",
           "dlc2_packagedefinition.customglobals", "dlc3_packagedefinition.customglobals",
           "dlc4_packagedefinition.customglobals")


def player_level(pc, profile=None):
    """Only solo/host PT1. Profile fallback prepares levels before pawn creation."""
    if pc is None or pc.WorldInfo.NetMode == 3 or pc.GetCurrentPlaythrough() != 0:
        return None
    if profile is not None:
        value = int(profile.ExpLevel)
    elif pc.Pawn is not None:
        value = int(pc.Pawn.GetExpLevel())
    else:
        profile = getattr(pc, "LastLoadedProfile", None)
        if profile is None:
            return None
        value = int(profile.ExpLevel)
    return max(1, min(69, value))


def character_key(pc):
    """Native save slot and class, not the editable character display name."""
    profile = getattr(pc, "LastLoadedProfile", None)
    file_name = str(getattr(pc, "SaveGameFileName", "") or "").replace("\\", "/").lower()
    # The assigned file id works before the first save has a file name.
    file_id = getattr(pc, "SaveGameFileId", -1)
    if profile is not None:
        file_id = getattr(profile, "SaveGameId", file_id)
    if isinstance(file_id, int) and file_id >= 0:
        slot = f"slot:{file_id}"
    elif file_name:
        slot = f"file:{file_name}"
    else:
        return None
    cls = getattr(pc, "PlayerClass", None)
    return slot + ":" + (cls._path_name().lower() if cls is not None else "unknown-class")


class Regions:
    def __init__(self, sdk):
        self.sdk = sdk
        self.patches = Patches()
        self.loaded = set()
        self.counts = {}
        self.problems = []
        self.level = None
        self.rows = {}
        self.overrides = {}

    def problem(self, context, exc):
        message = f"{context}: {exc!r}"
        if message not in self.problems and len(self.problems) < 16:
            self.problems.append(message)

    def update(self, level):
        for name in PACKAGES:
            if name in self.loaded:
                continue
            try:
                self.sdk.load_package(name)
                self.loaded.add(name)
            except Exception as exc:
                self.problem(name, exc)
        counts = {}
        rows = {}
        for root in self.sdk.find_all("GlobalsDefinition", exact=False):
            path = root._path_name().lower()
            if path not in GLOBALS:
                continue
            # Keep preloaded DLC globals alive so their first map/vendor load
            # sees the scaled data rather than a freshly reloaded vanilla table.
            self.patches.pin(root)
            count = 0
            for playthrough in root.RegionBalanceData:
                if playthrough.PlayThroughNumber != 1:
                    continue
                for definition in playthrough.BalanceDefinitions:
                    if definition is None:
                        continue
                    for i, row in enumerate(definition.BalanceByRegion):
                        if row.Region is not None:
                            name = row.Region._path_name().lower()
                            pair = (definition, i)
                            if pair not in rows.setdefault(name, []):
                                rows[name].append(pair)
                        count += 1
            counts[path] = count
        self.counts = counts
        self.rows = rows
        self.level = level
        for name in self.rows:
            self.apply(name)

    def apply(self, name):
        if self.level is None:
            return
        for definition, i in self.rows.get(name, []):
            row = definition.BalanceByRegion[i]
            self.floor(definition, ("BalanceByRegion", i, "DefaultGameStage"), name)
            for j, _override in enumerate(row.MissionOverrides):
                self.floor(definition, ("BalanceByRegion", i, "MissionOverrides", j, "GameStage"), name)

    def floor(self, definition, path, name):
        # Scope rewards to their acceptance level, including below an area floor.
        if name in self.overrides:
            self.patches.stage(definition, path, self.overrides[name])
            return
        values = {field: self.patches.original(definition, (*path, field)) for field in INPUT_FIELDS}
        if values["BaseValueAttribute"] is not None or values["InitializationDefinition"] is not None:
            # Never flatten an unfamiliar dynamic formula to its constant term.
            # The factory still floors its resolved native GameStage at spawn.
            self.problem(name, ValueError("Dynamic regional stage retained for native evaluation"))
            for field, value in values.items():
                self.patches.set(definition, (*path, field), value)
            return
        native = float(values["BaseValueConstant"]) * float(values["BaseValueScaleConstant"])
        if not math.isfinite(native):
            raise ValueError(f"Non-finite native regional stage: {name}")
        self.patches.stage(definition, path, max(self.level, native))

    @contextmanager
    def native(self, name):
        """Let native mission code select its own original story-dependent floor."""
        saved = []
        try:
            for definition, i in self.rows.get(name, []):
                row = definition.BalanceByRegion[i]
                paths = [("BalanceByRegion", i, "DefaultGameStage")]
                paths.extend(("BalanceByRegion", i, "MissionOverrides", j, "GameStage")
                             for j in range(len(row.MissionOverrides)))
                for path in paths:
                    data = resolve(definition, path)
                    for field in INPUT_FIELDS:
                        saved.append((data, field, getattr(data, field)))
                        setattr(data, field, self.patches.original(definition, (*path, field)))
            yield
        finally:
            for data, field, value in reversed(saved):
                setattr(data, field, value)

    def override(self, name, level=None):
        if level is None:
            self.overrides.pop(name, None)
        else:
            self.overrides[name] = level
        self.apply(name)

    def restore(self):
        for error in self.patches.restore():
            self.problem("restore regions", error)
        self.counts.clear()
        self.rows.clear()
        self.overrides.clear()
        self.level = None

    def snapshot(self):
        return {"region_counts": dict(self.counts),
                "missing_globals": [name for name in GLOBALS if not self.counts.get(name)],
                "level_rule": "max(player, native regional stage); story overrides remain separate",
                "problems": list(self.problems)}

    def levels_snapshot(self):
        """Optional manual reflection, after the basic diagnostic report exists."""
        return [
                    {"region": name, "source": definition._path_name(),
                     "native_default": {field: self.patches.original(
                         definition, ("BalanceByRegion", i, "DefaultGameStage", field))
                         for field in INPUT_FIELDS},
                     "current_default": row.DefaultGameStage.BaseValueConstant,
                     "mission_overrides": [
                         {"mission": override.Mission,
                          "native_stage": {field: self.patches.original(
                              definition, ("BalanceByRegion", i, "MissionOverrides", j, "GameStage", field))
                              for field in INPUT_FIELDS},
                          "current_stage": override.GameStage.BaseValueConstant}
                         for j, override in enumerate(row.MissionOverrides)]}
                    for name, definitions in self.rows.items() for definition, i in definitions
                    for row in (definition.BalanceByRegion[i],)]


class Grades:
    """Extend only the end bands; retain native offsets and grade probabilities."""
    def __init__(self):
        self.patches = Patches()

    def prepare(self, definition):
        grades = definition.Grades
        if not grades:
            return
        lows = [g.GameStageRequirement.MinGameStage for g in grades]
        highs = [g.GameStageRequirement.MaxGameStage for g in grades]
        for i in range(len(grades)):
            base = ("Grades", i, "GameStageRequirement")
            if lows[i] == min(lows) and lows[i] > 1:
                self.patches.set(definition, (*base, "MinGameStage"), 1)
            if highs[i] == max(highs) and highs[i] < 100:
                self.patches.set(definition, (*base, "MaxGameStage"), 100)

    def restore(self):
        return self.patches.restore()
