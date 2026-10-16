"""Fill omissions in the original PT3 regional balance and repair mission caches.

Only missing base-game regions are added. Existing PT3 entries, mission progress,
reward definitions, money formulas and PT1/PT2 balance are left alone.
"""

from copy import copy

import unrealsdk
from mods_base import get_pc, hook
from unrealsdk.hooks import Type
from unrealsdk.unreal import WeakPointer

from .balance import BASE_LEVEL

KEEP_ALIVE = 0x4000
FAMILIES = ("Arid", "Headlands", "Scrap", "Thor")


class MissionScaling:
    def __init__(self, sdk):
        self.sdk = sdk
        self.enabled = False
        self.prepared = False
        self.regions = set()
        self.additions = {}
        self.pinned = {}
        self.caches = {}
        self.problems = []

    def problem(self, context, exc):
        message = f"{context}: {exc!r}"
        if message not in self.problems and len(self.problems) < 12:
            self.problems.append(message)

    def pin(self, obj):
        address = obj._get_address()
        if address not in self.pinned:
            self.pinned[address] = (obj, bool(obj.ObjectFlags & KEEP_ALIVE))
            obj.ObjectFlags |= KEEP_ALIVE

    def prepare(self):
        if not self.enabled or self.prepared:
            return
        try:
            self.sdk.load_package("gd_GameStages")
            self.sdk.load_package("gd_GameStages_PT3")
            regions = list(self.sdk.find_all("WillowRegionDefinition", exact=False))
            for family in FAMILIES:
                definition = self.sdk.find_object(
                    "GameBalanceDefinition",
                    f"gd_GameStages_PT3.Balance.Balance_P1_{family}",
                )
                if definition is None or not definition.BalanceByRegion:
                    raise ValueError(f"Missing PT3 region balance: {family}")
                rows = definition.BalanceByRegion
                existing = {row.Region._path_name().lower() for row in rows if row.Region is not None}
                # Own this copy before append can reallocate the native array.
                template = copy(rows[0])
                prefix = f"gd_gamestages.{family.lower()}."
                for region in regions:
                    path = region._path_name().lower()
                    if not path.startswith(prefix) or path in existing:
                        continue
                    row = copy(template)
                    row.Region = region
                    row.MissionOverrides.clear()
                    stage = row.DefaultGameStage
                    stage.BaseValueConstant = BASE_LEVEL
                    stage.BaseValueAttribute = None
                    stage.InitializationDefinition = None
                    stage.BaseValueScaleConstant = 1.0
                    self.pin(definition)
                    self.pin(region)
                    rows.append(row)
                    existing.add(path)
                    self.regions.add(path)
                    key = definition._get_address()
                    if key not in self.additions:
                        self.additions[key] = (definition, set())
                    self.additions[key][1].add(path)
            self.prepared = True
        except Exception as exc:
            self.problem("prepare regions", exc)

    def active(self, pc):
        try:
            return (self.enabled and pc is not None and pc.Pawn is not None
                    and pc.WorldInfo.NetMode != 3 and pc.GetCurrentPlaythrough() == 2)
        except Exception:
            return False

    def repair(self, mission, pc):
        if not self.active(pc):
            self.restore_caches()
            return
        if mission is None:
            return
        try:
            region = mission.GameStageRegion
            if region is None or region._path_name().lower() not in self.regions:
                return
            values = {name: getattr(mission, name) for name in ("GameStage", "ExpLevel")}
            if all(value == BASE_LEVEL for value in values.values()):
                return
            address = mission._get_address()
            cached = self.caches.get(address)
            if cached is None or cached[0]() is None:
                self.caches[address] = (WeakPointer(mission), values)
            # Reflected int fields, not level setters or reward-generation calls.
            # RefreshRewardGameStage may have restored a previously cached zero.
            mission.GameStage = BASE_LEVEL
            mission.ExpLevel = BASE_LEVEL
        except Exception as exc:
            self.problem("repair mission", exc)

    def ready(self, pc):
        if not self.active(pc):
            self.restore_caches()
            return
        self.prepare()
        try:
            for mission in self.sdk.find_all("MissionDefinition", exact=False):
                self.repair(mission, pc)
        except Exception as exc:
            self.problem("loaded missions", exc)

    def restore_caches(self):
        for pointer, values in self.caches.values():
            try:
                mission = pointer()
                if mission is not None:
                    for name, value in values.items():
                        if getattr(mission, name) == BASE_LEVEL:
                            setattr(mission, name, value)
            except Exception as exc:
                self.problem("restore mission", exc)
        self.caches.clear()

    def disable(self):
        self.enabled = False
        self.restore_caches()
        for definition, paths in self.additions.values():
            try:
                # Copies survive assignment freeing/reallocating the old array.
                definition.BalanceByRegion = [
                    copy(row) for row in definition.BalanceByRegion
                    if row.Region is None or row.Region._path_name().lower() not in paths
                ]
            except Exception as exc:
                self.problem("restore regions", exc)
        self.additions.clear()
        for obj, was_pinned in self.pinned.values():
            try:
                if not was_pinned:
                    obj.ObjectFlags &= ~KEEP_ALIVE
            except Exception as exc:
                self.problem("restore pin", exc)
        self.pinned.clear()
        self.regions.clear()
        self.prepared = False

    def snapshot(self):
        return {"enabled": self.enabled, "prepared": self.prepared,
                "added_regions": sorted(self.regions), "problems": list(self.problems)}


_scaling = MissionScaling(unrealsdk)


def prepare():
    _scaling.prepare()


def on_enable():
    _scaling.enabled = True
    _scaling.ready(get_pc())


def on_disable():
    _scaling.disable()


def leave_playthrough():
    _scaling.restore_caches()


def snapshot():
    return _scaling.snapshot()


@hook("WillowGame.MissionDefinition:RefreshRewardGameStage", Type.POST)
def refreshed(obj, args, _ret, _func):
    _scaling.repair(obj, args.InWPC)


@hook("WillowGame.MissionDefinition:GetExpLevel")
@hook("WillowGame.MissionDefinition:GetGameStage")
@hook("WillowGame.MissionDefinition:GetExperienceReward")
@hook("WillowGame.MissionDefinition:GetCreditReward")
@hook("WillowGame.MissionDefinition:GetItemRewardForPlayer")
@hook("WillowGame.MissionDefinition:GenerateRewardString")
def reading_mission(obj, args, _ret, _func):
    _scaling.repair(obj, getattr(args, "InWPC", None) or get_pc())


@hook("WillowGame.WillowPlayerController:GrantMissionRewards")
def granting_rewards(obj, args, _ret, _func):
    _scaling.repair(args.InMission, obj)


@hook("WillowGame.WillowPlayerController:ClientSetProfileLoaded", Type.POST)
@hook("WillowGame.WillowPlayerController:OnExpLevelChange", Type.POST)
def player_ready(obj, _args, _ret, _func):
    _scaling.ready(obj)


HOOKS = [refreshed, reading_mission, granting_rewards, player_ready]
