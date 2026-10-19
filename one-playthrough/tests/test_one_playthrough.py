"""Native-data regression models. These tests do not execute the Windows engine."""

from contextlib import nullcontext
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace as NS
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Source/sdk_mods/OnePlaythrough"
NATIVE = json.loads((ROOT / "tests/fixtures/native.json").read_text())


class Object:
    def __init__(self, path):
        self.path = path
        self.ObjectFlags = 0

    def _path_name(self): return self.path
    def _get_address(self): return id(self)


def value(data):
    if isinstance(data, dict):
        if "ref" in data: return Object(data["ref"])
        return NS(**{k: value(v) for k, v in data.items()})
    if isinstance(data, list): return [value(v) for v in data]
    return data


def aid(level):
    return NS(BaseValueConstant=level, BaseValueAttribute=None,
              InitializationDefinition=None, BaseValueScaleConstant=1.0)


class Harness:
    def __init__(self, directory, *, registration_factory=None, in_menu=False):
        self.pc = Object("World.PlayerController")
        self.pc.WorldInfo = NS(NetMode=0, GetMapName=lambda: "Arid_Badlands_P")
        self.pc.pt = 0
        self.pc.level = 1
        self.pc.Pawn = NS(GetExpLevel=lambda: self.pc.level)
        self.pc.GetCurrentPlaythrough = lambda: self.pc.pt
        self.pc.SaveGameFileId = 1
        self.pc.SaveGameFileName = "Save0001.sav"
        self.pc.PlayerClass = Object("gd_PlayerClassId.Soldier")
        self.pc.LastLoadedProfile = Object("Profile.One")
        self.pc.LastLoadedProfile.ExpLevel = 1
        self.pc.LastLoadedProfile.SaveGameId = 1
        self.pc.MissionPlaythroughData = [NS(MissionList=[])]
        self.mission = Object("Z0_Missions.Missions.M_Scavenger1")
        self.mission.GameStageRegion = Object("gd_GameStages.Arid.Arid__C")
        self.mission.GameStage = self.mission.ExpLevel = 0
        self.mission.MinimumLevel = 12
        self.mission.ItemRewards = [Object("Native.Reward.Rifle")]
        self.mission.ExperienceRewardMultiplier = aid(1.15)
        self.mission.CreditRewardMultiplier = aid(1.0)
        self.missions = [self.mission]
        self.sdk = ModuleType("unrealsdk")
        self.messages = []
        self.sdk.logging = NS(info=self.messages.append, error=self.messages.append)
        self.loads = []
        self.sdk.load_package = self.loads.append
        self.scans = []
        self.globals = []
        self.definitions = []
        self.vendors = []
        self.inventory = []
        self.economy_definitions = {}
        base = Object("gd_globals.General.Globals")
        balances = []
        for path, rows in NATIVE["balances"].items():
            definition = Object(path)
            definition.BalanceByRegion = value(rows)
            balances.append(definition)
        base.RegionBalanceData = [NS(PlayThroughNumber=1, BalanceDefinitions=balances),
                                  NS(PlayThroughNumber=2, BalanceDefinitions=[self.unused_balance()])]
        self.globals.append(base)
        # DLC row layout is the same reflected structure; region names below
        # come from the original PT3 UPK imports. These are modeled DLC tables.
        for n, region in enumerate(("DLC1_Jakobs_Cove", "DLC2_Colleseum", "DLC3_Craw", "DLC4_Beginning"), 1):
            root = Object(f"dlc{n}_PackageDefinition.CustomGlobals")
            definition = Object(f"dlc{n}_PackageDefinition.Balance.P1")
            definition.BalanceByRegion = [NS(Region=Object(f"dlc{n}_PackageDefinition.DLC{n}.{region}"),
                DefaultGameStage=aid(35), DefaultAwesomeLevel=aid(3),
                MissionOverrides=[NS(Mission=Object("Native.DLC.Finale"), GameStage=aid(61), AwesomeLevel=aid(4))])]
            root.RegionBalanceData = [NS(PlayThroughNumber=1, BalanceDefinitions=[definition]),
                                      NS(PlayThroughNumber=2, BalanceDefinitions=[self.unused_balance()])]
            self.globals.append(root)
        def find_all(cls, exact=False):
            self.scans.append(cls)
            return {"GlobalsDefinition": self.globals, "MissionDefinition": self.missions,
                    "AIPawnBalanceDefinition": self.definitions,
                    "WillowVendingMachine": self.vendors, "WillowInventory": self.inventory,
                    **self.economy_definitions}.get(cls, [])
        self.sdk.find_all = find_all
        self.callbacks = {}
        hooks = ModuleType("unrealsdk.hooks")
        hooks.Type = NS(POST="POST", POST_UNCONDITIONAL="POST_UNCONDITIONAL")
        hooks.Block = object()
        hooks.prevent_hooking_direct_calls = nullcontext
        base_mod = ModuleType("mods_base")
        def hook(path, kind="PRE"):
            def decorate(fn):
                self.callbacks[(path, kind)] = fn
                return fn
            return decorate
        base_mod.hook = hook
        base_mod.keybind = lambda identifier, key: lambda fn: NS(identifier=identifier, key=key, callback=fn)
        base_mod.ButtonOption = lambda identifier, **kw: NS(identifier=identifier, **kw)
        base_mod.get_pc = lambda: None if in_menu else self.pc
        base_mod.SETTINGS_DIR = Path(directory)
        def build_mod(**kwargs):
            self.registration = kwargs
            if registration_factory is not None:
                self.registered_mod = registration_factory(**kwargs)
                return self.registered_mod
        base_mod.build_mod = build_mod
        self.modules = {"unrealsdk": self.sdk, "unrealsdk.hooks": hooks, "mods_base": base_mod}
        name = "oneplaythrough_test"
        spec = importlib.util.spec_from_file_location(name, SOURCE / "__init__.py",
                                                    submodule_search_locations=[str(SOURCE)])
        module = importlib.util.module_from_spec(spec)
        module.__version__, module.__version_info__ = "4.0.4", (4, 0, 4)
        self.modules[name] = module
        with patch.dict(sys.modules, self.modules):
            spec.loader.exec_module(module)
        self.mod = module
        self.runtime = module.runtime

    def unused_balance(self):
        definition = Object("Native.PT2.Balance")
        definition.BalanceByRegion = [NS(Region=Object("Native.PT2.Region"),
            DefaultGameStage=aid(37), DefaultAwesomeLevel=aid(4), MissionOverrides=[])]
        return definition

    def enable(self, level=1):
        self.pc.level = level
        self.mod.on_enable()

    def rows(self):
        return [row for root in self.globals for pt in root.RegionBalanceData
                if pt.PlayThroughNumber == 1 for definition in pt.BalanceDefinitions
                for row in definition.BalanceByRegion]

    def row(self):
        return next(r for r in self.rows() if r.Region.path.lower() == self.mission.GameStageRegion.path.lower())

    def state(self, status=1):
        self.pc.MissionPlaythroughData[0].MissionList = [NS(MissionDef=self.mission, Status=status, Objectives=[4, 7])]

    def accept(self):
        self.mod.accepting(self.pc, NS(InMission=self.mission), None, None)
        self.state()
        self.mod.accepted(self.pc, NS(InMission=self.mission), True, None)

    def reward(self, name="GetItemRewardForPlayer", native=None):
        path = "WillowGame.MissionDefinition:" + name
        args = NS(InWPC=self.pc)
        self.callbacks[(path, "PRE")](self.mission, args, None, None)
        try:
            # Model a DIRECT C++ refresh bypassing all Python mission hooks.
            self.mission.GameStage = int(self.row().DefaultGameStage.BaseValueConstant)
            self.mission.ExpLevel = self.mission.GameStage
            return native() if native else self.mission.GameStage
        finally:
            self.callbacks[(path, "POST_UNCONDITIONAL")](self.mission, args, None, None)


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.h = Harness(self.tmp.name)

    def test_new_game_has_no_menu_intro_story_reset_or_save_edit_hooks(self):
        h = self.h
        h.enable()
        self.assertEqual([o.identifier for o in h.registration["options"]], ["Export diagnostics"])
        self.assertTrue(all(not any(x in path for x in ("GFxLobby", "PressStart", "LaunchNewGame"))
                            for path, _ in h.callbacks))
        self.assertEqual(h.pc.pt, 0)
        self.assertEqual(h.pc.MissionPlaythroughData[0].MissionList, [])
        self.assertFalse(any("PT3" in p for p in h.loads))

    def test_real_native_regions_and_all_dlc_scale_from_one_to_69(self):
        h = self.h
        for level in (1, 10, 30, 50, 69):
            h.enable(level)
            self.assertEqual(len(h.runtime.regions.counts), 5)
            self.assertEqual(h.runtime.regions.snapshot()["missing_globals"], [])
            for row in h.rows():
                self.assertEqual(row.DefaultGameStage.BaseValueConstant, level)
                for override in row.MissionOverrides:
                    self.assertEqual(override.GameStage.BaseValueConstant, level)

    def test_native_loot_quality_story_dependencies_and_pt2_tables_preserved(self):
        h = self.h
        before = [(row.DefaultAwesomeLevel.BaseValueConstant,
                   [(o.Mission, o.AwesomeLevel.BaseValueConstant) for o in row.MissionOverrides]) for row in h.rows()]
        h.enable(30)
        self.assertEqual(before, [(row.DefaultAwesomeLevel.BaseValueConstant,
                    [(o.Mission, o.AwesomeLevel.BaseValueConstant) for o in row.MissionOverrides]) for row in h.rows()])
        for root in h.globals:
            self.assertEqual(root.RegionBalanceData[1].BalanceDefinitions[0].BalanceByRegion[0].DefaultGameStage.BaseValueConstant, 37)

    def test_offer_tracks_player_until_acceptance_then_locks(self):
        h = self.h
        h.enable(20)
        self.assertEqual(h.mission.ExpLevel, 20)
        h.pc.level = 30
        h.mod.mission_level(h.mission, NS(), None, None)
        self.assertEqual(h.mission.ExpLevel, 30)
        h.accept()
        h.pc.level = 40
        h.mod.player_ready(h.pc, NS(), None, None)
        self.assertEqual((h.mission.GameStage, h.mission.ExpLevel), (30, 30))
        self.assertEqual(h.row().DefaultGameStage.BaseValueConstant, 40)

    def test_all_native_reward_entry_points_use_locked_level(self):
        h = self.h
        h.enable(20)
        h.accept()
        h.pc.level = 30
        h.runtime.sync(h.pc)
        for method in ("GetExperienceReward", "GetCreditReward", "GetItemRewardForPlayer", "GenerateRewardString"):
            self.assertEqual(h.reward(method), 20)
            self.assertEqual(h.row().DefaultGameStage.BaseValueConstant, 30)
        self.assertEqual(h.runtime.missions.scopes, [])

    def test_xp_multiplier_reward_definition_and_native_price_calculation_preserved(self):
        h = self.h
        rewards = h.mission.ItemRewards[:]
        multiplier = h.mission.ExperienceRewardMultiplier
        credits = h.mission.CreditRewardMultiplier
        h.enable(20)
        h.accept()
        h.pc.level = 30
        result = h.reward("GetExperienceReward", lambda: multiplier.BaseValueConstant * h.mission.GameStage ** 2)
        self.assertAlmostEqual(result, 1.15 * 20 ** 2)
        self.assertEqual(h.mission.ItemRewards, rewards)
        self.assertIs(h.mission.ExperienceRewardMultiplier, multiplier)
        self.assertIs(h.mission.CreditRewardMultiplier, credits)
        self.assertFalse(any("CashValue" in p or "Vending" in p for p, _ in h.callbacks))

    def test_level_up_inside_reward_reapplies_latest_world_level(self):
        h = self.h
        h.enable(20)
        h.accept()
        h.pc.level = 30
        def native():
            h.pc.level = 31
            h.mod.player_ready(h.pc, NS(), None, None)
            self.assertEqual(h.row().DefaultGameStage.BaseValueConstant, 20)
        h.reward("GetExperienceReward", native)
        self.assertEqual(h.row().DefaultGameStage.BaseValueConstant, 31)

    def test_nested_and_exceptional_native_rewards_restore_scopes(self):
        h = self.h
        h.enable(20)
        h.accept()
        h.pc.level = 30
        def outer():
            self.assertEqual(h.reward("GetExperienceReward"), 20)
            self.assertEqual(h.row().DefaultGameStage.BaseValueConstant, 20)
            raise RuntimeError("modeled native failure")
        with self.assertRaises(RuntimeError): h.reward(native=outer)
        self.assertEqual(h.row().DefaultGameStage.BaseValueConstant, 30)
        self.assertEqual(h.runtime.missions.scopes, [])

    def test_acceptance_survives_full_reload_and_characters_are_isolated(self):
        h = self.h
        h.enable(20)
        h.accept()
        second = Harness(self.tmp.name)
        second.pc.level = 30
        second.state()
        second.enable(30)
        self.assertEqual(second.mission.ExpLevel, 20)
        second.pc.SaveGameFileId = second.pc.LastLoadedProfile.SaveGameId = 2
        second.runtime.sync(second.pc)
        self.assertEqual(second.mission.ExpLevel, 30)

    def test_declining_or_blocking_acceptance_does_not_lock_offer(self):
        h = self.h
        h.enable(20)
        h.mod.accepting(h.pc, NS(InMission=h.mission), None, None)
        h.mod.accepted(h.pc, NS(InMission=h.mission), False, None)
        h.pc.level = 30
        h.mod.mission_level(h.mission, NS(), None, None)
        self.assertEqual(h.mission.ExpLevel, 30)
        self.assertEqual(h.runtime.missions.levels, {})

    def test_abandoned_unsaved_acceptance_does_not_poison_next_offer(self):
        h = self.h
        h.enable(20)
        h.accept()
        h.pc.MissionPlaythroughData[0].MissionList = []  # Load an earlier native save.
        h.pc.level = 30
        h.runtime.sync(h.pc)
        self.assertEqual(h.mission.ExpLevel, 30)
        h.accept()
        self.assertEqual(h.runtime.missions.levels[h.mission.path.lower()], 30)

    def test_fresh_character_reusing_slot_does_not_inherit_old_locks(self):
        h = self.h
        h.enable(20)
        h.accept()
        fresh = Harness(self.tmp.name)
        fresh.runtime.enabled = True
        fresh.runtime.sync(fresh.pc, loading=True)
        self.assertEqual(fresh.runtime.missions.levels, {})

    def test_volatile_acceptance_migrates_when_new_character_gets_save_id(self):
        h = self.h
        h.pc.SaveGameFileName = ""
        h.pc.SaveGameFileId = h.pc.LastLoadedProfile.SaveGameId = -1
        h.enable(1)
        h.accept()
        h.pc.SaveGameFileId = h.pc.LastLoadedProfile.SaveGameId = 5
        h.pc.level = 5
        h.runtime.sync(h.pc)
        self.assertEqual(h.mission.ExpLevel, 1)
        self.assertIsNotNone(h.runtime.missions.key)
        self.assertTrue(h.runtime.store.path.exists())

    def test_quest_progress_and_original_mission_minimum_restored_on_disable(self):
        h = self.h
        h.state()
        progress = deepcopy(h.pc.MissionPlaythroughData)
        h.enable(20)
        self.assertEqual(h.mission.MinimumLevel, 0)
        h.mod.on_disable()
        self.assertEqual((h.mission.ExpLevel, h.mission.GameStage, h.mission.MinimumLevel), (0, 0, 12))
        self.assertEqual(h.pc.MissionPlaythroughData[0].MissionList[0].Objectives,
                         progress[0].MissionList[0].Objectives)
        self.assertEqual(h.pc.MissionPlaythroughData[0].MissionList[0].Status, 1)

    def test_other_playthrough_or_client_restores_all_native_region_values(self):
        h = self.h
        original = [r.DefaultGameStage.BaseValueConstant for r in h.rows()]
        h.enable(30)
        h.pc.pt = 1
        h.runtime.sync(h.pc)
        self.assertEqual(original, [r.DefaultGameStage.BaseValueConstant for r in h.rows()])
        h.pc.pt = 0
        h.pc.WorldInfo.NetMode = 3
        h.runtime.sync(h.pc)
        self.assertEqual(original, [r.DefaultGameStage.BaseValueConstant for r in h.rows()])

    def test_profile_prepares_region_scaling_before_player_pawn_exists(self):
        h = self.h
        h.runtime.enabled = True
        h.pc.Pawn = None
        h.mod.applying_profile(h.pc, NS(Profile=NS(ExpLevel=40)), None, None)
        self.assertTrue(all(r.DefaultGameStage.BaseValueConstant == 40 for r in h.rows()))

    def test_late_dlc_globals_are_discovered_on_next_world_ready(self):
        h = self.h
        dlc = h.globals.pop()
        h.enable(20)
        self.assertEqual(len(h.runtime.regions.snapshot()["missing_globals"]), 1)
        h.globals.append(dlc)
        h.mod.world_ready(h.pc.WorldInfo, NS(), None, None)
        self.assertEqual(h.runtime.regions.snapshot()["missing_globals"], [])

    def test_repeated_level_changes_do_not_duplicate_native_rows(self):
        h = self.h
        count = len(h.rows())
        for level in (1, 20, 40, 69, 1): h.enable(level)
        self.assertEqual(len(h.rows()), count)
        self.assertEqual(len(h.loads), 6)

    def test_corrupt_acceptance_file_is_preserved_and_scaling_still_operates(self):
        h = self.h
        p = h.runtime.store.path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("corrupt")
        h.enable(20)
        h.accept()
        self.assertEqual(p.read_text(), "corrupt")
        self.assertIsNotNone(h.runtime.store.error)
        self.assertEqual(h.mission.ExpLevel, 20)

    def test_diagnostics_do_not_change_runtime_data(self):
        h = self.h
        h.enable(20)
        h.accept()
        before = [r.DefaultGameStage.BaseValueConstant for r in h.rows()]
        h.mod.export_diagnostics()
        paths = list((Path(self.tmp.name) / "OnePlaythrough/diagnostics").glob("*.json"))
        self.assertEqual(len(paths), 1)
        json.loads(paths[0].read_text())
        self.assertEqual(before, [r.DefaultGameStage.BaseValueConstant for r in h.rows()])
        self.assertEqual(len(h.messages), 3)  # Loading line, manual request, saved path.

    def test_native_autoaccepted_story_mission_locks_without_manual_accept(self):
        h = self.h
        h.enable(20)
        h.state(1)
        h.mod.player_ready(h.pc, NS(), None, None)
        h.pc.level = 30
        h.runtime.sync(h.pc)
        self.assertEqual(h.mission.ExpLevel, 20)

    def test_reward_without_explicit_controller_uses_local_player(self):
        h = self.h
        h.enable(20)
        h.accept()
        h.pc.level = 30
        path = "WillowGame.MissionDefinition:GetExperienceReward"
        args = NS(InWPC=None)
        h.callbacks[(path, "PRE")](h.mission, args, None, None)
        self.assertEqual(h.row().DefaultGameStage.BaseValueConstant, 20)
        h.callbacks[(path, "POST_UNCONDITIONAL")](h.mission, args, None, None)
        self.assertEqual(h.row().DefaultGameStage.BaseValueConstant, 30)

    def test_original_resolver_objects_are_pinned_and_restored_with_flags(self):
        h = self.h
        row = h.row()
        original = Object("Native.OriginalStageResolver")
        row.DefaultGameStage.BaseValueAttribute = original
        h.enable(30)
        self.assertIsNone(row.DefaultGameStage.BaseValueAttribute)
        self.assertNotEqual(original.ObjectFlags, 0)
        h.mod.on_disable()
        self.assertIs(row.DefaultGameStage.BaseValueAttribute, original)
        self.assertEqual(original.ObjectFlags, 0)

    def test_restoration_preserves_an_external_change_to_a_patched_field(self):
        h = self.h
        h.enable(20)
        h.row().DefaultGameStage.BaseValueConstant = 99
        h.mod.on_disable()
        self.assertEqual(h.row().DefaultGameStage.BaseValueConstant, 99)

    def test_unknown_metadata_format_is_never_overwritten(self):
        h = self.h
        p = h.runtime.store.path
        p.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps({"format_version": 999, "characters": {}})
        p.write_text(text)
        h.enable(20)
        h.accept()
        self.assertEqual(p.read_text(), text)
        self.assertIsNotNone(h.runtime.store.error)

    def test_temporary_acceptance_does_not_migrate_between_profiles(self):
        h = self.h
        h.pc.SaveGameFileName = ""
        h.pc.SaveGameFileId = h.pc.LastLoadedProfile.SaveGameId = -1
        h.enable(20)
        h.accept()
        h.pc.LastLoadedProfile = Object("Profile.Other")
        h.pc.LastLoadedProfile.SaveGameId = 6
        h.pc.MissionPlaythroughData[0].MissionList = []
        h.pc.level = 30
        h.runtime.sync(h.pc)
        self.assertEqual(h.runtime.missions.levels, {})
        self.assertEqual(h.mission.ExpLevel, 30)

    def test_preloaded_dlc_globals_stay_alive_until_scaling_disabled(self):
        h = self.h
        h.enable(20)
        self.assertTrue(all(root.ObjectFlags != 0 for root in h.globals))
        h.mod.on_disable()
        self.assertTrue(all(root.ObjectFlags == 0 for root in h.globals))


class SpawnTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.h = Harness(self.tmp.name)
        self.h.enable(20)
        self.definition = Object("Native.Enemy.BossOrOrdinary")
        self.attribute = Object("gd_Balance.EnemyLevel.EnemyLevel_GameStage_plus2")
        self.definition.DefaultExpLevel = NS(BaseValueConstant=0, BaseValueAttribute=self.attribute,
                                            InitializationDefinition=None, BaseValueScaleConstant=1)
        self.definition.Grades = [NS(GameStageRequirement=NS(MinGameStage=30, MaxGameStage=50),
                                     GradeModifiers=NS(ExpLevel=1, HealthMultiplier=3, DamageMultiplier=2))]
        self.h.definitions.append(self.definition)
        self.factory = NS(PawnBalanceDefinition=self.definition)
        self.args = NS(Master=object(), SpawnLocationContextObject=object(), SpawnLocation=object(),
                       SpawnRotation=object(), GameStage=35, AwesomeLevel=8, AIPawnMemento=object())
        self.calls = []
        self.pawn = Object("World.SpawnedPawn")

    def native(self, *args):
        self.calls.append(args)
        stage = args[4]
        grade = self.definition.Grades[0]
        self.assertLessEqual(grade.GameStageRequirement.MinGameStage, stage)
        self.assertGreaterEqual(grade.GameStageRequirement.MaxGameStage, stage)
        self.assertIs(self.definition.DefaultExpLevel.BaseValueAttribute, self.attribute)
        self.pawn.level = stage + 2 + grade.GradeModifiers.ExpLevel
        self.pawn.health = self.pawn.level ** 3 * grade.GradeModifiers.HealthMultiplier
        return self.pawn

    def test_native_offsets_and_grade_bonuses_remain_at_player_relative_base(self):
        result = self.h.mod.create_pawn(self.factory, self.args, None, self.native)
        self.assertIs(result[1], self.pawn)
        self.assertEqual(self.pawn.level, 23)
        self.assertEqual(self.pawn.health, 23 ** 3 * 3)
        self.assertEqual(self.definition.Grades[0].GradeModifiers.DamageMultiplier, 2)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0][:4], (self.args.Master, self.args.SpawnLocationContextObject,
                                           self.args.SpawnLocation, self.args.SpawnRotation))
        self.assertEqual(self.calls[0][5], 8)
        self.assertEqual(self.pawn.ObjectFlags, 0)  # Never pin a spawned actor.

    def test_native_lower_equal_and_higher_offsets_not_weighted_or_fixed_bosses(self):
        for offset in (-2, -1, 0, 1, 2, 3):
            self.definition.Grades[0].GradeModifiers.ExpLevel = offset
            self.h.mod.create_pawn(self.factory, self.args, None, self.native)
            self.assertEqual(self.pawn.level, 22 + offset)

    def test_level_one_and_69_use_native_initialization_and_keep_offsets(self):
        for level in (1, 69):
            self.h.pc.level = level
            self.h.mod.create_pawn(self.factory, self.args, None, self.native)
            self.assertEqual(self.pawn.level, level + 3)

    def test_matching_native_stage_is_not_reinvoked(self):
        self.args.GameStage = 20
        self.assertIsNone(self.h.mod.create_pawn(self.factory, self.args, None, self.native))
        self.assertEqual(self.calls, [])  # SDK continues its original native call.

    def test_restore_forwards_original_memento_once(self):
        self.h.mod.restore_pawn(self.factory, self.args, None, self.native)
        self.assertEqual(self.calls[0][-1], self.args.AIPawnMemento)
        self.assertEqual(len(self.calls), 1)

    def test_vehicle_uses_native_stage_without_inventing_balance_data(self):
        factory = NS(VehicleBalanceDefinition=None)
        self.h.mod.create_vehicle(factory, self.args, None, self.native)
        self.assertEqual(self.calls[0][4], 20)

    def test_failed_native_invocation_never_retries_or_duplicates(self):
        def fail(*args):
            self.calls.append(args)
            raise RuntimeError("modeled engine error")
        result = self.h.mod.create_pawn(self.factory, self.args, None, fail)
        self.assertIsNone(result[1])
        self.assertEqual(len(self.calls), 1)

    def test_grade_boundary_changes_restore_on_disable(self):
        self.h.mod.create_pawn(self.factory, self.args, None, self.native)
        self.h.mod.on_disable()
        req = self.definition.Grades[0].GameStageRequirement
        self.assertEqual((req.MinGameStage, req.MaxGameStage), (30, 50))
        self.assertIs(self.definition.DefaultExpLevel.BaseValueAttribute, self.attribute)
        self.assertEqual(self.definition.ObjectFlags, 0)

    def test_grade_end_bands_preserve_intermediate_bands_and_selection_data(self):
        first = self.definition.Grades[0]
        first.GameStageRequirement.MaxGameStage = 40
        middle, last = deepcopy(first), deepcopy(first)
        middle.GameStageRequirement = NS(MinGameStage=41, MaxGameStage=50)
        last.GameStageRequirement = NS(MinGameStage=51, MaxGameStage=69)
        self.definition.Grades = [first, middle, last]
        self.h.runtime.grades.prepare(self.definition)
        self.assertEqual([(g.GameStageRequirement.MinGameStage, g.GameStageRequirement.MaxGameStage)
                          for g in self.definition.Grades], [(1, 40), (41, 50), (51, 100)])
        self.assertEqual([g.GradeModifiers.ExpLevel for g in self.definition.Grades], [1, 1, 1])

    def test_new_native_hook_argument_names_match_live_bl1e_export(self):
        for name, kind in self.h.callbacks:
            if name in NATIVE["functions"]:
                params = NATIVE["functions"][name]
                if name.endswith(":CreatePopulationActor"):
                    self.assertEqual(params[:6], ["Master", "SpawnLocationContextObject", "SpawnLocation",
                                                 "SpawnRotation", "GameStage", "AwesomeLevel"])
                if name.endswith(":RestorePopulatedAIPawn"):
                    self.assertEqual(params[-1], "AIPawnMemento")
                if name.endswith(":RefreshRewardGameStage"):
                    self.assertEqual(params, ["InWPC"])
                if name.endswith(":ClientAddMission"):
                    self.assertEqual(params[0], "InMission")

    def test_disabled_other_playthrough_and_network_client_do_not_intercept_spawn(self):
        for mode in (1, 2):
            self.h.pc.pt = mode
            self.assertIsNone(self.h.mod.create_pawn(self.factory, self.args, None, self.native))
        self.h.pc.pt = 0
        self.h.pc.WorldInfo.NetMode = 3
        self.assertIsNone(self.h.mod.create_pawn(self.factory, self.args, None, self.native))
        self.h.pc.WorldInfo.NetMode = 0
        self.h.mod.on_disable()
        self.assertIsNone(self.h.mod.create_pawn(self.factory, self.args, None, self.native))
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
