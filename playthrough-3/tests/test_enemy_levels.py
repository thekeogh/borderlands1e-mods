"""Native factory model; this cannot reproduce an engine protection fault."""

from collections import Counter
from contextlib import nullcontext
from pathlib import Path
from types import ModuleType, SimpleNamespace as NS
from unittest.mock import patch
import sys
import json
import unittest
import weakref

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Source/sdk_mods/Playthrough 3"


class Object:
    def __init__(self, path="TheWorld.Enemy"):
        self.path = path
        self.ObjectFlags = 0

    def _path_name(self): return self.path
    def _get_address(self): return id(self)


class Template(Object):
    def __init__(self, allegiance):
        super().__init__("gd_GenericPawn.Character.Pawn")
        self.Allegiance = Object(allegiance) if allegiance else None

    def __getattr__(self, name):
        raise AssertionError(f"Do not invoke native template methods: {name}")


class Pawn(Object):
    def __init__(self):
        super().__init__()
        self.stage = self.level = None
        self.health = None

    def GetGameStage(self): return self.stage
    def GetExpLevel(self): return self.level

    def IsEnemy(self, other): raise AssertionError("Do not probe spawning pawn hostility")
    def IsDead(self): raise AssertionError("Do not probe spawning pawn health")
    def SetGameStage(self, value): raise AssertionError("Do not rescale initialized enemy")
    def SetExpLevel(self, value): raise AssertionError("Do not re-enter level setter")


def load():
    sdk = ModuleType("unrealsdk")
    messages = []
    sdk.logging = NS(info=messages.append, error=messages.append)
    sdk.find_all = lambda *a, **kw: (_ for _ in ()).throw(AssertionError("No actor scans"))
    sdk.find_object = lambda cls, path: Object(path)
    hooks = ModuleType("unrealsdk.hooks")
    hooks.Block = object()
    hooks.Type = NS(PRE="PRE", POST="POST")
    hooks.prevent_hooking_direct_calls = nullcontext
    hooks.add_hook = hooks.remove_hook = lambda *args: None
    unreal = ModuleType("unrealsdk.unreal")
    unreal.WeakPointer = weakref.ref
    unreal.UObject = unreal.WrappedStruct = unreal.BoundFunction = object
    base = ModuleType("mods_base")
    registrations = []
    def hook(path=None, *a, **kw):
        path = path or kw["hook_func"]
        registrations.append(path)
        return lambda fn: fn
    base.hook = hook
    base.SliderOption = lambda name, value, low, high, step, integer, **kw: NS(
        identifier=name, value=value, min_value=low, max_value=high, step=step,
        is_integer=integer, **kw)
    base.BoolOption = lambda name, value, **kw: NS(identifier=name, value=value, **kw)
    base.SETTINGS_DIR = ROOT / "unused-settings"
    base.get_pc = lambda: None
    base.build_mod = lambda **kw: None
    options = ModuleType("mods_base.options")
    options.BaseOption = options.BoolOption = object
    package = ModuleType("pt3_level_test")
    package.__path__ = [str(SOURCE)]
    module = ModuleType("pt3_level_test.enemy_levels")
    module.__package__ = package.__name__
    modules = {"unrealsdk": sdk, "unrealsdk.hooks": hooks, "unrealsdk.unreal": unreal,
               "mods_base": base, "mods_base.options": options, package.__name__: package,
               module.__name__: module}
    with patch.dict(sys.modules, modules):
        exec(compile((SOURCE / "enemy_levels.py").read_text(), "enemy_levels.py", "exec"), module.__dict__)
    pc = NS(Pawn=Object(), WorldInfo=NS(NetMode=0), GetCurrentPlaythrough=lambda: 2)
    module.get_pc = lambda: pc
    module.on_enable()
    module.messages, module.registrations = messages, registrations
    return module, pc, modules


class SpawnTests(unittest.TestCase):
    def setUp(self):
        self.mod, self.pc, self.modules = load()
        self.mod.randrange = lambda total: 99  # 72 at default spread
        self.attribute, self.initializer = Object("attribute"), Object("initializer")
        self.requirement = NS(MinGameStage=1, MaxGameStage=69)
        self.grade = NS(GameStageRequirement=self.requirement,
                        GradeModifiers=NS(ExpLevel=-2, HealthMultiplier=2, DamageMultiplier=3))
        self.definition = Object("gd_Balance_Enemies_Humans.Bandits.Balance")
        self.definition.AIPawnArchetype = Template("gd_allegiance.HumanEnemy.BanditAllegiance")
        self.definition.DefaultExpLevel = NS(BaseValueConstant=0, BaseValueAttribute=self.attribute,
                                            InitializationDefinition=self.initializer,
                                            BaseValueScaleConstant=1)
        self.definition.Grades = [self.grade]
        self.factory = NS(PawnBalanceDefinition=self.definition)
        self.args = NS(Master=object(), SpawnLocationContextObject=object(),
                       SpawnLocation=object(), SpawnRotation=object(), GameStage=69,
                       AwesomeLevel=8, AIPawnMemento=object())
        self.pawn = Pawn()
        self.calls = []

    def original_data(self):
        return (dict(vars(self.definition.DefaultExpLevel)), dict(vars(self.requirement)),
                dict(vars(self.grade.GradeModifiers)), self.definition.ObjectFlags,
                self.attribute.ObjectFlags, self.initializer.ObjectFlags)

    def native_spawn(self, *args):
        self.calls.append(args)
        stage = args[4]
        self.assertTrue(self.requirement.MinGameStage <= stage <= self.requirement.MaxGameStage)
        data = self.definition.DefaultExpLevel
        self.assertEqual(data.BaseValueAttribute.path, self.mod.EXACT_STAGE)
        self.assertIsNone(data.InitializationDefinition)
        self.assertTrue(self.attribute.ObjectFlags & self.mod.KEEP_ALIVE)
        # Native factory model: initialization calculates real level/stats once.
        self.pawn.stage = stage
        self.pawn.level = stage + self.grade.GradeModifiers.ExpLevel
        self.pawn.health = self.pawn.level ** 3 * self.grade.GradeModifiers.HealthMultiplier
        return self.pawn

    def test_exact_ticket_counts_for_all_spreads(self):
        expected = {0: (100,), 1: (30, 70), 2: (10, 35, 55),
                    3: (5, 20, 55, 20), 4: (5, 15, 50, 25, 5),
                    5: (5, 10, 45, 30, 7, 3)}
        for spread, weights in expected.items():
            counts = Counter(self.mod.chosen_level(spread, ticket) for ticket in range(100))
            self.assertEqual(counts, {69 + offset: count for offset, count in enumerate(weights)})

    def test_default_and_setting_identifier_preserved(self):
        self.assertEqual(self.mod.spread.value, 3)
        self.assertEqual(self.mod.spread.identifier, "Enemy Level Spread")
        self.assertEqual((self.mod.spread.min_value, self.mod.spread.max_value), (0, 5))

    def test_spawn_has_matching_real_level_and_native_stats_without_setters(self):
        original = self.original_data()
        result = self.mod.create_pawn(self.factory, self.args, None, self.native_spawn)
        self.assertEqual(result, (self.mod.Block, self.pawn))
        self.assertEqual((self.pawn.stage, self.pawn.level, self.pawn.health), (72, 72, 2 * 72 ** 3))
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0][:4], tuple(getattr(self.args, name) for name in
                          ("Master", "SpawnLocationContextObject", "SpawnLocation", "SpawnRotation")))
        self.assertEqual(self.calls[0][4:], (72, 8))
        self.assertEqual(self.requirement.MaxGameStage, 69)
        self.mod.on_disable()
        self.assertEqual(self.original_data(), original)

    def test_restore_forwards_memento_without_second_spawn(self):
        self.mod.restore_pawn(self.factory, self.args, None, self.native_spawn)
        self.assertEqual(self.calls[0][6], self.args.AIPawnMemento)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.pawn.level, 72)

    def test_unsafe_archetype_queries_absent_even_for_unknown_allegiance(self):
        self.definition.path = "CustomBalance.Enemy"
        self.definition.AIPawnArchetype = Template("custom.UnknownAllegiance")
        self.assertIsNone(self.mod.create_pawn(self.factory, self.args, None, self.native_spawn))
        self.assertEqual(self.calls, [])
        self.assertEqual(self.mod._skipped[self.definition.path], 1)

    def test_enemy_balance_package_can_classify_other_named_allegiance(self):
        self.definition.AIPawnArchetype = Template("gd_allegiance.Humans.Bandit")
        self.mod.create_pawn(self.factory, self.args, None, self.native_spawn)
        self.assertEqual(self.pawn.level, 72)

    def test_no_level_setter_population_post_or_load_scan_hooks(self):
        self.assertEqual(set(self.mod.registrations), {
            "WillowGame.PopulationFactoryBalancedAIPawn:CreatePopulationActor",
            "WillowGame.PopulationFactoryBalancedAIPawn:RestorePopulatedAIPawn",
            "WillowGame.PopulationFactoryWillowVehicle:CreatePopulationActor"})
        self.mod.on_enable()  # find_all stub throws if scanned
        self.assertEqual(self.mod._targets, {})

    def test_friendly_player_neutral_and_missing_allegiance_skip(self):
        original = self.original_data()
        for path in ("gd_allegiance.Friendly.NPC", "gd_allegiance.Player.Team",
                     "gd_allegiance.Neutral.NPC", None):
            self.definition.AIPawnArchetype = Template(path)
            self.assertIsNone(self.mod.create_pawn(self.factory, self.args, None, self.native_spawn))
        self.assertEqual(self.calls, [])
        self.assertEqual(self.original_data(), original)

    def test_spawn_allegiance_override_takes_precedence(self):
        self.factory.SpawnAllegiance = Object("gd_allegiance.Friendly.NPC")
        self.assertIsNone(self.mod.create_pawn(self.factory, self.args, None, self.native_spawn))

    def test_clients_other_playthroughs_and_disabled_mod_skip(self):
        self.pc.WorldInfo.NetMode = 3
        self.assertIsNone(self.mod.create_pawn(self.factory, self.args, None, self.native_spawn))
        self.pc.WorldInfo.NetMode = 0
        for pt in (0, 1):
            self.pc.GetCurrentPlaythrough = lambda: pt
            self.assertIsNone(self.mod.create_pawn(self.factory, self.args, None, self.native_spawn))
        self.pc.GetCurrentPlaythrough = lambda: 2
        self.mod.on_disable()
        self.assertIsNone(self.mod.create_pawn(self.factory, self.args, None, self.native_spawn))
        self.assertEqual(self.calls, [])

    def test_spread_five_supports_74_without_permanent_grade_changes(self):
        original = self.original_data()
        self.mod.spread.value = 5
        self.mod.create_pawn(self.factory, self.args, None, self.native_spawn)
        self.assertEqual((self.pawn.stage, self.pawn.level), (74, 74))
        self.mod.on_disable()
        self.assertEqual(self.original_data(), original)

    def test_failure_restores_ranges_and_disable_restores_data_without_duplicate_spawn(self):
        original = self.original_data()
        def fail(*args):
            self.calls.append(args)
            raise RuntimeError("native failure")
        self.assertEqual(self.mod.create_pawn(self.factory, self.args, None, fail), (self.mod.Block, None))
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.requirement.MaxGameStage, 69)
        self.mod.on_disable()
        self.assertEqual(self.original_data(), original)

    def test_preexisting_pin_flags_are_preserved(self):
        self.attribute.ObjectFlags = self.mod.KEEP_ALIVE | 16
        self.mod.create_pawn(self.factory, self.args, None, self.native_spawn)
        self.mod.on_disable()
        self.assertEqual(self.attribute.ObjectFlags, self.mod.KEEP_ALIVE | 16)

    def test_missing_data_layout_delegates_to_original_before_invocation(self):
        del self.definition.DefaultExpLevel
        self.assertIsNone(self.mod.create_pawn(self.factory, self.args, None, self.native_spawn))
        self.assertEqual(self.calls, [])
        self.assertTrue(self.mod._problems)

    def test_collision_failure_not_retried(self):
        original = self.original_data()
        self.assertEqual(self.mod.create_pawn(self.factory, self.args, None, lambda *a: None),
                         (self.mod.Block, None))
        self.mod.on_disable()
        self.assertEqual(self.original_data(), original)
        self.assertEqual(self.mod._counts, {})

    def test_nested_same_definition_restores_outer_then_original_data(self):
        original = self.original_data()
        with self.mod.native_level_data(self.definition, 69, 70):
            with self.mod.native_level_data(self.definition, 70, 72):
                self.assertEqual(self.definition.DefaultExpLevel.BaseValueAttribute.path, self.mod.EXACT_STAGE)
                self.assertEqual(self.requirement.MaxGameStage, 72)
            self.assertEqual(self.requirement.MaxGameStage, 70)
            self.assertEqual(self.grade.GradeModifiers.ExpLevel, 0)
        self.mod.restore_definitions()
        self.assertEqual(self.original_data(), original)

    def test_vehicle_factory_supported_layout_uses_same_native_policy(self):
        factory = NS(VehicleBalanceDefinition=self.definition,
                     VehicleArchetype=self.definition.AIPawnArchetype)
        self.mod.create_vehicle(factory, self.args, None, self.native_spawn)
        self.assertEqual(self.pawn.level, 72)

    def test_unsupported_vehicle_factory_stays_native(self):
        self.assertIsNone(self.mod.create_vehicle(NS(), self.args, None, self.native_spawn))
        self.assertEqual(self.calls, [])
        self.assertTrue(self.mod._skipped)

    def test_phase_logs_bracket_native_call_and_restoration(self):
        self.mod.spawn_trace.value = True
        self.mod.create_pawn(self.factory, self.args, None, self.native_spawn)
        messages = "\n".join(self.mod.messages)
        self.assertLess(messages.index("Calling native factory"), messages.index("Native factory returned"))
        self.assertLess(messages.index("Native factory returned"), messages.index("Grade ranges restored"))

    def test_spawn_trace_off_keeps_counts_and_errors_without_phase_messages(self):
        self.assertFalse(self.mod.spawn_trace.value)
        self.mod.create_pawn(self.factory, self.args, None, self.native_spawn)
        self.assertEqual(self.mod._counts, {72: 1})
        self.assertEqual(self.mod._traced, set())
        self.assertFalse(any("Calling native factory" in message for message in self.mod.messages))
        self.assertEqual(len(self.mod.messages), 2)  # Policy enable notices only.
        self.mod.problem(ValueError("diagnostic error"))
        self.assertIn("diagnostic error", self.mod.messages[-1])

    def test_snapshot_limits_live_rows_after_skipping_dead_references(self):
        self.mod._targets = {index: (lambda: None, 69, "expired") for index in range(200)}
        pawns = [Pawn() for _ in range(201)]
        for pawn in pawns:
            pawn.stage = pawn.level = 69
            self.mod._targets[pawn._get_address()] = (weakref.ref(pawn), 69, "live")
        before = dict(self.mod._targets)
        rows = self.mod.snapshot(self.pc)["tracked_enemies"]
        self.assertEqual(len(rows), 200)
        self.assertTrue(all(row["exp_level"] == 69 for row in rows))
        self.assertEqual(self.mod._targets, before)

    def test_completed_spawn_snapshot_is_read_only(self):
        self.mod.create_pawn(self.factory, self.args, None, self.native_spawn)
        before = self.original_data(), dict(self.mod._counts), self.pawn.level
        result = self.mod.snapshot(self.pc)
        self.assertEqual(result["tracked_enemies"][0]["exp_level"], 72)
        self.assertEqual(result["assigned_counts"], {72: 1})
        self.assertEqual((self.original_data(), dict(self.mod._counts), self.pawn.level), before)

    def test_two_enemies_share_definition_but_keep_different_levels(self):
        self.mod.create_pawn(self.factory, self.args, None, self.native_spawn)
        first = self.pawn
        self.pawn = Pawn()
        self.mod.randrange = lambda total: 0
        self.mod.create_pawn(self.factory, self.args, None, self.native_spawn)
        self.assertEqual((first.level, self.pawn.level), (72, 69))
        self.assertEqual(self.definition.DefaultExpLevel.BaseValueAttribute.path, self.mod.EXACT_STAGE)
        self.assertEqual(self.mod._counts, {72: 1, 69: 1})

    def test_missing_exact_stage_attribute_skips_before_native_call(self):
        original = self.original_data()
        self.mod.find_object = lambda *args: None
        self.assertIsNone(self.mod.create_pawn(self.factory, self.args, None, self.native_spawn))
        self.assertEqual(self.calls, [])
        self.assertEqual(self.original_data(), original)

    def test_main_mod_retains_fixed_baseline_economy_and_settings(self):
        package = self.modules["pt3_level_test"]
        economy = ModuleType("pt3_level_test.economy")
        economy.HOOKS = []
        events = []
        economy.on_enable = lambda: events.append("economy enabled")
        economy.on_disable = lambda: events.append("economy disabled")
        package.economy, package.enemy_levels = economy, self.mod
        main = ModuleType("pt3_level_test.main")
        main.__package__ = package.__name__
        main.__version__, main.__version_info__ = "2.3.0", (2, 3, 0)
        self.modules["mods_base"].build_mod = lambda **kw: setattr(main, "registration", kw)
        self.modules[economy.__name__] = economy
        with patch.dict(sys.modules, self.modules):
            exec(compile((SOURCE / "__init__.py").read_text(), "main.py", "exec"), main.__dict__)
        main.GlobalGameStage = NS(ValueResolverChain=[NS(ConstantValue=84)])
        main.on_enable()
        self.assertEqual(main.GlobalGameStage.ValueResolverChain[0].ConstantValue, 69)
        self.assertEqual(main.registration["options"], [self.mod.spread, self.mod.spawn_trace])
        self.assertEqual(main.registration["description"], self.mod.MOD_DESCRIPTION)
        self.assertEqual(main.registration["settings_file"].name, "PT3.json")
        original = self.original_data()
        self.mod.create_pawn(self.factory, self.args, None, self.native_spawn)
        economy.set_mode = lambda *a, **kw: None
        self.modules["unrealsdk"].load_package = lambda *a: None
        main.GlobalsDef = NS()
        main.OnButtonClicked(NS(DialogResult="Dif1"), None, None, None)
        self.assertEqual(self.original_data(), original)
        main.on_disable()
        self.assertEqual(events, ["economy enabled", "economy disabled"])

    def test_all_sourced_named_ids_spawn_at_71_for_every_spread_fresh_and_restored(self):
        fixture = json.loads((ROOT / "tests/fixtures/bl1_named_enemies.json").read_text())
        self.mod.randrange = lambda *a: self.fail("Named spawns must not roll a random level")
        for kind in ("balances", "archetypes"):
            for path, name in fixture[kind].items():
                # Native archetype-only vehicles are exercised separately.
                if "vehicle" in path and kind == "archetypes":
                    continue
                self.definition.path = path.upper() if kind == "balances" else "gd_Balance_Enemies_Humans.Generic"
                self.definition.AIPawnArchetype.path = path.upper() if kind == "archetypes" else "gd_GenericPawn.Character.Pawn"
                for spread in range(6):
                    self.mod.spread.value = spread
                    for hook in (self.mod.create_pawn, self.mod.restore_pawn):
                        with self.subTest(kind=kind, path=path, spread=spread, hook=hook.__name__):
                            self.calls.clear()
                            result = hook(self.factory, self.args, None, self.native_spawn)
                            self.assertEqual(result, (self.mod.Block, self.pawn))
                            self.assertEqual((self.pawn.stage, self.pawn.level), (71, 71))
                            self.assertEqual(self.pawn.health, 2 * 71 ** 3)
                            self.assertEqual(len(self.calls), 1)
                            self.assertEqual(self.mod._named_definitions[self.definition.path], name)

    def test_named_rule_does_not_match_substrings_display_labels_or_generic_badasses(self):
        self.grade.GradeModifiers.DisplayName = "Sledge"
        for path in ("gd_Balance_Enemies_Humans.Bandits.Badass",
                     "gd_Balance_Enemies_Humans.Bandits.Named.Pawn_Balance_Sledge_Minions",
                     "Custom.Sledge", "dlc3_gd_balance_enemies.CrimsonLance.Pawn_Balance_BadassDevastator"):
            self.definition.path = path
            self.mod.spread.value = 5
            self.mod.create_pawn(self.factory, self.args, None, self.native_spawn)
            self.assertEqual(self.pawn.level, 74)
        self.assertEqual(self.mod._named_counts, {})
        self.assertEqual(self.mod._ordinary_counts, {74: 4})

    def test_known_named_id_still_excludes_friendly_player_neutral_and_clients(self):
        self.definition.path = "gd_Balance_Enemies_Humans.Bandits.Named.Pawn_Balance_Sledge"
        for path in ("gd_allegiance.Friendly.NPC", "gd_allegiance.Player.Team", "gd_allegiance.Neutral.NPC"):
            self.factory.SpawnAllegiance = Object(path)
            self.assertIsNone(self.mod.create_pawn(self.factory, self.args, None, self.native_spawn))
        del self.factory.SpawnAllegiance
        self.pc.WorldInfo.NetMode = 3
        self.assertIsNone(self.mod.create_pawn(self.factory, self.args, None, self.native_spawn))
        self.assertEqual(self.calls, [])
        self.assertEqual(self.mod._named_counts, {})

    def test_known_named_id_handles_unrecognised_allegiance_without_pawn_queries(self):
        self.definition.path = "gd_VaultBoss_Main.population.Pawn_Balance_VaultBoss_Main"
        self.definition.AIPawnArchetype.Allegiance = None
        self.mod.create_pawn(self.factory, self.args, None, self.native_spawn)
        self.assertEqual(self.pawn.level, 71)

    def test_named_enemy_restores_definition_and_pins_on_disable(self):
        self.definition.path = "gd_Balance_Enemies_Humans.Bandits.Named.Pawn_Balance_Sledge"
        original = self.original_data()
        self.mod.create_pawn(self.factory, self.args, None, self.native_spawn)
        self.mod.on_disable()
        self.assertEqual(self.original_data(), original)

    def test_named_and_ordinary_spawn_counts_export_separately(self):
        ordinary_path = self.definition.path
        self.mod.create_pawn(self.factory, self.args, None, self.native_spawn)
        self.pawn = Pawn()
        self.definition.path = "gd_Balance_Enemies_Humans.Bandits.Named.Pawn_Balance_Sledge"
        self.mod.create_pawn(self.factory, self.args, None, self.native_spawn)
        result = self.mod.snapshot(self.pc)
        self.assertEqual(result["assigned_counts"], {71: 1, 72: 1})
        self.assertEqual(result["ordinary_assigned_counts"], {72: 1})
        self.assertEqual(result["named_enemy_counts"], {"Sledge": 1})
        self.assertEqual(result["named_enemy_level"], 71)
        self.assertEqual(result["tracked_enemies"][-1]["named_enemy"], "Sledge")
        self.definition.path = ordinary_path
        self.mod.on_enable()
        self.assertEqual(self.mod._named_counts, {})
        self.assertEqual(self.mod._named_definitions, {})
        self.assertEqual(self.mod._ordinary_counts, {})

    def test_named_vehicle_archetypes_pass_native_stage_71_without_ai_data(self):
        for path in ("gd_CheetahsPaw.VehicleArchetype.Mad_Mel", "gd_banditkromboss.Vehicle.Krom_Turret_Archetype"):
            vehicle = Object(path)
            vehicle.Allegiance = None
            factory = NS(VehicleArchetype=vehicle)
            before = self.original_data()
            self.mod.spread.value = 5
            def native_vehicle(*args):
                self.calls.append(args)
                self.pawn.stage = self.pawn.level = args[4]
                return self.pawn
            self.calls.clear()
            self.assertEqual(self.mod.create_vehicle(factory, self.args, None, native_vehicle), (self.mod.Block, self.pawn))
            self.assertEqual(self.calls[0][4:], (71, 8))
            self.assertEqual(len(self.calls), 1)
            self.assertEqual(self.original_data(), before)

    def test_named_vehicle_failure_never_retries_and_friendly_vehicle_stays_native(self):
        vehicle = Object("gd_CheetahsPaw.VehicleArchetype.Mad_Mel")
        vehicle.Allegiance = None
        factory = NS(VehicleArchetype=vehicle)
        def fail(*args):
            self.calls.append(args)
            raise RuntimeError("vehicle failure")
        self.assertEqual(self.mod.create_vehicle(factory, self.args, None, fail), (self.mod.Block, None))
        self.assertEqual(len(self.calls), 1)
        factory.SpawnAllegiance = Object("gd_allegiance.Player.Team")
        self.assertIsNone(self.mod.create_vehicle(factory, self.args, None, fail))
        self.assertEqual(len(self.calls), 1)


if __name__ == "__main__":
    unittest.main()
