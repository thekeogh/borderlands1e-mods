"""BL1E mission/region model; native UI and reward generation need game testing."""

from copy import copy
from pathlib import Path
from types import ModuleType, SimpleNamespace as NS
from unittest.mock import patch
import json
import sys
import unittest
import weakref

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Source/sdk_mods/Playthrough 3"
FIXTURE = json.loads((ROOT / "tests/fixtures/bl1e_missions.json").read_text())


class Object:
    def __init__(self, path):
        self.path = path
        self.ObjectFlags = 0

    def _path_name(self): return self.path
    def _get_address(self): return id(self)


class RegionRow:
    def __init__(self, region):
        self.Region = region
        self.DefaultGameStage = NS(BaseValueConstant=0, BaseValueAttribute=Object("PT3.Stage"),
                                   InitializationDefinition=None, BaseValueScaleConstant=1.0)
        self.DefaultAwesomeLevel = NS(BaseValueConstant=8)
        self.MissionOverrides = [NS(Mission="Sledge", GameStage=0)]

    def __copy__(self):
        # Model the SDK's owned struct copy: UObject references retained,
        # nested structs and arrays copied into independent native memory.
        row = RegionRow(self.Region)
        row.DefaultGameStage = copy(self.DefaultGameStage)
        row.DefaultAwesomeLevel = copy(self.DefaultAwesomeLevel)
        row.MissionOverrides = [copy(value) for value in self.MissionOverrides]
        return row


def load():
    sdk = ModuleType("unrealsdk")
    hooks = ModuleType("unrealsdk.hooks")
    hooks.Type = NS(POST="POST")
    unreal = ModuleType("unrealsdk.unreal")
    unreal.WeakPointer = weakref.ref
    base = ModuleType("mods_base")
    registrations = []
    def hook(path, kind="PRE"):
        registrations.append((path, kind))
        return lambda fn: fn
    base.hook = hook
    base.get_pc = lambda: None
    package = ModuleType("pt3_mission_test")
    package.__path__ = [str(SOURCE)]
    module = ModuleType("pt3_mission_test.missions")
    module.__package__ = package.__name__
    modules = {"unrealsdk": sdk, "unrealsdk.hooks": hooks,
               "unrealsdk.unreal": unreal, "mods_base": base,
               package.__name__: package, module.__name__: module}
    with patch.dict(sys.modules, modules):
        exec(compile((SOURCE / "missions.py").read_text(), "missions.py", "exec"), module.__dict__)
    return module, sdk, registrations


class MissionTests(unittest.TestCase):
    def setUp(self):
        self.mod, self.sdk, self.registrations = load()
        self.pc = NS(Pawn=Object("World.Player"), WorldInfo=NS(NetMode=0),
                     GetCurrentPlaythrough=lambda: 2,
                     MissionPlaythroughData=["PT1 progress", "PT2 progress", "PT3 progress"])
        self.mod.get_pc = lambda: self.pc
        self.regions = {}
        self.definitions = {}
        for family in self.mod.FAMILIES:
            region = self.region(f"gd_GameStages.{family}.{family}__A")
            obj = Object(f"gd_GameStages_PT3.Balance.Balance_P1_{family}")
            obj.BalanceByRegion = [RegionRow(region)]
            self.definitions[obj.path] = obj
        arid = self.definitions["gd_GameStages_PT3.Balance.Balance_P1_Arid"]
        arid.BalanceByRegion.append(RegionRow(self.region("gd_GameStages.Arid.Arid_Mines")))
        self.missions = []
        for path, fields in FIXTURE["missions"].items():
            mission = Object(path)
            mission.GameStageRegion = self.region(fields["GameStageRegion"]["ref"])
            mission.GameStage = mission.ExpLevel = 0
            mission.ExperienceRewardMultiplier = fields["ExperienceRewardMultiplier"]
            mission.ItemRewards = fields["ItemRewards"]
            self.missions.append(mission)
        self.foreign = self.region("OtherMod.Arid.Arid__C")
        self.packages = []
        self.scans = []
        self.sdk.load_package = self.packages.append
        self.sdk.find_object = lambda cls, path: self.definitions.get(path)
        def find_all(cls, exact=False):
            self.scans.append(cls)
            if cls == "WillowRegionDefinition": return list(self.regions.values())
            if cls == "MissionDefinition": return self.missions
            raise AssertionError(f"Unexpected world scan: {cls}")
        self.sdk.find_all = find_all
        self.policy = self.mod._scaling
        self.policy.enabled = True

    def region(self, path):
        if path not in self.regions:
            self.regions[path] = Object(path)
        return self.regions[path]

    def mission(self, suffix):
        return next(m for m in self.missions if m.path.endswith(suffix))

    def test_missing_regions_get_69_and_no_story_override(self):
        self.policy.prepare()
        for definition in self.definitions.values():
            for row in definition.BalanceByRegion:
                if row.Region.path.lower() in self.policy.regions:
                    stage = row.DefaultGameStage
                    self.assertEqual((stage.BaseValueConstant, stage.BaseValueAttribute,
                                      stage.InitializationDefinition, stage.BaseValueScaleConstant),
                                     (69, None, None, 1.0))
                    self.assertEqual(row.MissionOverrides, [])
                    self.assertEqual(row.DefaultAwesomeLevel.BaseValueConstant, 8)
        self.assertIn("gd_gamestages.arid.arid__c", self.policy.regions)
        self.assertIn("gd_gamestages.arid.arid__c_difficult", self.policy.regions)
        self.assertIn("gd_gamestages.headlands.headlands__b", self.policy.regions)
        self.assertIn("gd_gamestages.scrap.scrap_newhaven_b", self.policy.regions)
        self.assertNotIn(self.foreign.path.lower(), self.policy.regions)
        self.assertEqual(self.policy.problems, [])

    def test_existing_regions_templates_and_other_playthroughs_untouched(self):
        originals = [(row, row.DefaultGameStage.BaseValueAttribute,
                      list(row.MissionOverrides)) for obj in self.definitions.values()
                     for row in obj.BalanceByRegion]
        self.policy.prepare()
        for row, attribute, overrides in originals:
            self.assertIs(row.DefaultGameStage.BaseValueAttribute, attribute)
            self.assertEqual(row.DefaultGameStage.BaseValueConstant, 0)
            self.assertEqual(row.MissionOverrides, overrides)
        self.assertEqual(self.pc.MissionPlaythroughData,
                         ["PT1 progress", "PT2 progress", "PT3 progress"])

    def test_repeated_preparation_does_not_duplicate_rows_or_loads(self):
        self.policy.prepare()
        counts = [len(obj.BalanceByRegion) for obj in self.definitions.values()]
        self.policy.prepare()
        self.assertEqual(counts, [len(obj.BalanceByRegion) for obj in self.definitions.values()])
        self.assertEqual(self.packages, ["gd_GameStages", "gd_GameStages_PT3"])

    def test_accepted_and_unaccepted_missions_repaired_before_native_reads(self):
        self.policy.prepare()
        for suffix in ("M_RakkDebris", "M_Scavenger1"):
            mission = self.mission(suffix)
            self.assertIsNone(self.mod.reading_mission(mission, NS(InWPC=self.pc), None, None))
            # The game reads the corrected fields to label the mission and
            # compute XP/item level. Neither reward definitions nor progress change.
            self.assertEqual((mission.ExpLevel, mission.GameStage), (69, 69))
            fields = FIXTURE["missions"][mission.path]
            self.assertEqual(mission.ExperienceRewardMultiplier, fields["ExperienceRewardMultiplier"])
            self.assertEqual(mission.ItemRewards, fields["ItemRewards"])

    def test_native_refresh_overwriting_with_cached_zero_is_repaired_again(self):
        self.policy.prepare()
        mission = self.mission("M_Scavenger1")
        self.mod.reading_mission(mission, NS(), None, None)
        mission.GameStage = mission.ExpLevel = 0  # Native cache/profile refresh.
        self.mod.refreshed(mission, NS(InWPC=self.pc), False, None)
        self.assertEqual((mission.GameStage, mission.ExpLevel), (69, 69))

    def test_turn_in_uses_69_before_native_grant_without_granting_twice(self):
        self.policy.prepare()
        mission = self.mission("M_Scavenger1")
        self.assertIsNone(self.mod.granting_rewards(self.pc, NS(InMission=mission), None, None))
        self.assertEqual((mission.GameStage, mission.ExpLevel), (69, 69))
        self.assertEqual(self.scans, ["WillowRegionDefinition"])

    def test_existing_valid_main_mission_is_not_changed(self):
        self.policy.prepare()
        mission = self.mission("M_KillSledge2")
        mission.GameStage, mission.ExpLevel = 69, 69
        self.policy.repair(mission, self.pc)
        self.assertNotIn(mission._get_address(), self.policy.caches)
        self.assertEqual((mission.GameStage, mission.ExpLevel), (69, 69))

    def test_other_missing_region_missions_repaired(self):
        self.policy.ready(self.pc)
        for mission in self.missions:
            self.assertEqual((mission.GameStage, mission.ExpLevel),
                             (0, 0) if mission.path.endswith("M_KillSledge2") else (69, 69))

    def test_pt1_pt2_clients_no_controller_and_disabled_skip(self):
        self.policy.prepare()
        mission = self.mission("M_RakkDebris")
        for pt in (0, 1):
            self.pc.GetCurrentPlaythrough = lambda: pt
            self.policy.repair(mission, self.pc)
            self.assertEqual((mission.GameStage, mission.ExpLevel), (0, 0))
        self.pc.GetCurrentPlaythrough = lambda: 2
        self.pc.WorldInfo.NetMode = 3
        self.policy.repair(mission, self.pc)
        self.pc.WorldInfo.NetMode = 0
        self.policy.repair(mission, None)
        self.policy.enabled = False
        self.policy.repair(mission, self.pc)
        self.assertEqual((mission.GameStage, mission.ExpLevel), (0, 0))

    def test_disable_restores_rows_fields_and_pin_flags_and_reenable_works(self):
        first = next(iter(self.definitions.values()))
        first.ObjectFlags = self.mod.KEEP_ALIVE
        counts = [len(obj.BalanceByRegion) for obj in self.definitions.values()]
        self.policy.ready(self.pc)
        self.policy.disable()
        self.assertEqual(counts, [len(obj.BalanceByRegion) for obj in self.definitions.values()])
        self.assertEqual(first.ObjectFlags, self.mod.KEEP_ALIVE)
        for region in self.regions.values(): self.assertEqual(region.ObjectFlags, 0)
        for mission in self.missions: self.assertEqual((mission.GameStage, mission.ExpLevel), (0, 0))
        self.mod.on_enable()
        self.assertTrue(self.policy.prepared)
        self.assertEqual(self.mission("M_RakkDebris").ExpLevel, 69)

    def test_leaving_pt3_restores_only_our_cached_fields(self):
        self.policy.ready(self.pc)
        mission = self.mission("M_RakkDebris")
        mission.GameStage = 20  # Another native calculation must survive restoration.
        self.mod.leave_playthrough()
        self.assertEqual((mission.GameStage, mission.ExpLevel), (20, 0))
        self.assertEqual(self.policy.caches, {})

    def test_disable_preserves_unrelated_rows_added_later(self):
        self.policy.prepare()
        definition = next(iter(self.definitions.values()))
        row = RegionRow(self.foreign)
        definition.BalanceByRegion.append(row)
        self.policy.disable()
        self.assertTrue(any(r.Region is self.foreign for r in definition.BalanceByRegion))

    def test_partial_prepare_failure_can_retry_without_duplicates(self):
        path = "gd_GameStages_PT3.Balance.Balance_P1_Headlands"
        missing = self.definitions.pop(path)
        self.policy.prepare()
        self.assertFalse(self.policy.prepared)
        arid = next(iter(self.definitions.values()))
        count = len(arid.BalanceByRegion)
        self.definitions[path] = missing
        self.policy.prepare()
        self.assertTrue(self.policy.prepared)
        self.assertEqual(len(arid.BalanceByRegion), count)
        self.assertEqual(len(self.policy.problems), 1)

    def test_late_mission_load_uses_prepared_region_without_world_scan(self):
        self.policy.prepare()
        mission = Object("Z0_Missions.Missions.NewLateMission")
        mission.GameStageRegion = self.region("gd_GameStages.Arid.Arid__C")
        mission.GameStage = mission.ExpLevel = 0
        self.mod.reading_mission(mission, NS(), None, None)
        self.assertEqual((mission.GameStage, mission.ExpLevel), (69, 69))
        self.assertEqual(self.scans, ["WillowRegionDefinition"])

    def test_deleted_missions_do_not_break_disable(self):
        self.policy.prepare()
        mission = self.mission("M_RakkDebris")
        self.policy.repair(mission, self.pc)
        self.missions.remove(mission)
        del mission
        self.policy.disable()
        self.assertEqual(self.policy.problems, [])

    def test_menu_prepare_then_continue_repairs_previously_accepted_missions(self):
        self.mod.get_pc = lambda: None
        self.mod.on_enable()
        self.assertEqual(self.packages, [])
        self.mod.prepare()  # Called after the original PressStart setup.
        self.assertTrue(self.policy.prepared)
        self.mod.player_ready(self.pc, NS(), None, None)
        self.assertEqual(self.mission("M_Scavenger1").ExpLevel, 69)

    def test_loading_another_playthrough_restores_transient_mission_cache(self):
        self.policy.ready(self.pc)
        mission = self.mission("M_Scavenger1")
        self.assertEqual(mission.ExpLevel, 69)
        self.pc.GetCurrentPlaythrough = lambda: 1
        self.mod.player_ready(self.pc, NS(), None, None)
        self.assertEqual((mission.GameStage, mission.ExpLevel), (0, 0))
        self.assertEqual(self.pc.MissionPlaythroughData,
                         ["PT1 progress", "PT2 progress", "PT3 progress"])

    def test_hooks_match_live_signatures_and_never_block_native_calls(self):
        params = FIXTURE["function_parameters"]
        for path, kind in self.registrations:
            if path.endswith(":ClientSetProfileLoaded"):
                # Existing PT3 lifecycle hook; the old export filtered this out.
                self.assertEqual(kind, "POST")
                continue
            self.assertIn(path, params)
            if path.endswith(":RefreshRewardGameStage"):
                self.assertEqual((kind, params[path]), ("POST", ["InWPC"]))
            if path.endswith(":GrantMissionRewards"):
                self.assertEqual((kind, params[path]), ("PRE", ["InMission"]))
        self.assertEqual(len(self.registrations), 10)

    def test_snapshot_json_safe_read_only_and_no_runtime_logging(self):
        self.policy.prepare()
        before = [len(obj.BalanceByRegion) for obj in self.definitions.values()]
        json.dumps(self.policy.snapshot())
        self.assertEqual(before, [len(obj.BalanceByRegion) for obj in self.definitions.values()])
        self.assertFalse(hasattr(self.sdk, "logging"))


if __name__ == "__main__":
    unittest.main()
