"""4.1 policy regressions; native calls and DLC data are explicitly modeled."""

from copy import deepcopy
from types import SimpleNamespace as NS
import tempfile
import unittest

from test_one_playthrough import Harness, Object, aid


class Floors(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.h = Harness(self.tmp.name)

    def test_region_floor_is_reversible_and_does_not_stick_at_previous_player_level(self):
        h = self.h
        h.enable(8)
        self.assertEqual(h.row().DefaultGameStage.BaseValueConstant, 16)
        h.enable(30)
        self.assertEqual(h.row().DefaultGameStage.BaseValueConstant, 30)
        h.enable(5)
        self.assertEqual(h.row().DefaultGameStage.BaseValueConstant, 16)
        h.mod.on_disable()
        self.assertEqual(h.row().DefaultGameStage.BaseValueConstant, 16)

    def test_each_story_override_keeps_its_own_floor_not_final_story_maximum(self):
        h = self.h
        row = h.rows()[0]  # Actual captured Fyrestone 3, then 4/5/12.
        h.enable(1)
        self.assertEqual(row.DefaultGameStage.BaseValueConstant, 3)
        self.assertEqual([o.GameStage.BaseValueConstant for o in row.MissionOverrides], [4, 5, 12])
        h.enable(8)
        self.assertEqual(row.DefaultGameStage.BaseValueConstant, 8)
        self.assertEqual([o.GameStage.BaseValueConstant for o in row.MissionOverrides], [8, 8, 12])

    def test_every_dlc_scales_before_completion_without_changing_story_flags(self):
        h = self.h
        h.enable(1)
        for root in h.globals[1:]:
            row = root.RegionBalanceData[0].BalanceDefinitions[0].BalanceByRegion[0]
            self.assertEqual(row.DefaultGameStage.BaseValueConstant, 35)
            self.assertEqual(row.MissionOverrides[0].GameStage.BaseValueConstant, 61)
        h.enable(50)
        for root in h.globals[1:]:
            row = root.RegionBalanceData[0].BalanceDefinitions[0].BalanceByRegion[0]
            self.assertEqual(row.DefaultGameStage.BaseValueConstant, 50)
            self.assertEqual(row.MissionOverrides[0].GameStage.BaseValueConstant, 61)
        self.assertEqual(h.pc.MissionPlaythroughData[0].MissionList, [])
        self.assertEqual(h.pc.pt, 0)

    def test_offer_below_vanilla_level_stays_high_then_tracks_player_and_locks(self):
        h = self.h
        h.enable(5)
        self.assertEqual(h.mission.ExpLevel, 16)
        h.enable(20)
        self.assertEqual(h.mission.ExpLevel, 20)
        h.accept()
        h.enable(30)
        self.assertEqual(h.mission.ExpLevel, 20)

    def test_accepting_high_level_offer_locks_offer_level_not_player_level(self):
        h = self.h
        h.enable(5)
        h.accept()
        self.assertEqual(h.runtime.missions.levels[h.mission.path.lower()], 16)
        h.enable(30)
        self.assertEqual(h.reward(), 16)

    def test_dlc_offers_keep_floor_then_scale_before_any_dlc_completion(self):
        for n in range(1, 5):
            with self.subTest(dlc=n):
                h = Harness(self.tmp.name + f"/dlc{n}")
                row = h.globals[n].RegionBalanceData[0].BalanceDefinitions[0].BalanceByRegion[0]
                h.mission.GameStageRegion = row.Region
                h.enable(1)
                self.assertEqual(h.mission.ExpLevel, 35)
                h.enable(50)
                self.assertEqual(h.mission.ExpLevel, 50)
                h.accept()
                h.enable(69)
                self.assertEqual(h.reward(), 50)
                self.assertEqual(row.DefaultGameStage.BaseValueConstant, 69)

    def test_native_mission_refresh_selects_current_story_override(self):
        h = self.h
        h.mission.GameStageRegion = h.rows()[0].Region
        h.enable(1)
        self.assertEqual(h.mission.ExpLevel, 3)
        override = h.rows()[0].MissionOverrides[1]
        h.pc.MissionPlaythroughData[0].MissionList.append(NS(MissionDef=override.Mission, Status=4))
        h.runtime.sync(h.pc)
        self.assertEqual(h.mission.ExpLevel, 5)
        self.assertNotEqual(h.mission.ExpLevel, 12)

    def test_legacy_accepted_level_below_new_floor_still_rewards_at_saved_level(self):
        h = self.h
        h.state()
        h.runtime.store.levels("slot:1:gd_playerclassid.soldier")[h.mission.path.lower()] = 7
        h.runtime.store.save()
        h.enable(10)
        self.assertEqual(h.mission.ExpLevel, 7)
        self.assertEqual(h.reward(), 7)
        self.assertEqual(h.row().DefaultGameStage.BaseValueConstant, 16)

    def test_exception_during_native_floor_query_restores_all_live_fields(self):
        h = self.h
        h.enable(30)
        before = (h.row().DefaultGameStage.BaseValueConstant, h.mission.GameStage, h.mission.ExpLevel)
        h.runtime.missions.floors.clear()
        def fail(_pc):
            self.assertEqual(h.row().DefaultGameStage.BaseValueConstant, 16)
            raise RuntimeError("modeled native refresh error")
        h.mission.RefreshRewardGameStage = fail
        with self.assertRaises(RuntimeError): h.runtime.missions.apply(h.mission, h.pc)
        self.assertEqual(before, (h.row().DefaultGameStage.BaseValueConstant, h.mission.GameStage, h.mission.ExpLevel))
        self.assertFalse(h.runtime.missions.reading_native)


class Rare(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.h = Harness(self.tmp.name)
        h = self.h
        self.definition = Object("gd_Balance_Enemies_Humans.Bandits.Basic.Pawn_Balance_Grunt")
        self.definition.DefaultExpLevel = aid(0)
        self.definition.DefaultExpLevel.BaseValueAttribute = Object("gd_Balance.EnemyLevel.EnemyLevel_GameStage_minus1")
        self.definition.Grades = [NS(GameStageRequirement=NS(MinGameStage=1, MaxGameStage=100),
                                     GradeModifiers=NS(ExpLevel=0, HealthMultiplier=3, DamageMultiplier=2))]
        self.definition.AIPawnArchetype = Object("gd_Bandits.Archetypes.BasicGrunt")
        self.definition.AIPawnArchetype.Allegiance = Object("gd_Allegiance.HumanEnemy.Bandit")
        self.definition.Class = Object("WillowGame.AIPawnBalanceDefinition")
        self.definition.Outer = Object("gd_Balance_Enemies_Humans.Bandits.Basic")
        self.factory = NS(PawnBalanceDefinition=self.definition)
        self.args = NS(Master=object(), SpawnLocationContextObject=object(), SpawnLocation=object(),
                       SpawnRotation=object(), GameStage=20, AwesomeLevel=8, AIPawnMemento=object())
        self.exact = Object("gd_Balance.EnemyLevel.EnemyLevel_GameStage_exact")
        h.sdk.find_object = lambda cls, path: self.exact
        self.created = []
        def construct(cls, outer, name, template_obj):
            self.assertIs(template_obj, self.definition)
            clone = Object(outer.path + "." + name)
            clone.DefaultExpLevel = NS(**vars(template_obj.DefaultExpLevel))
            clone.Grades = deepcopy(template_obj.Grades)
            self.created.append(clone)
            return clone
        h.sdk.construct_object = construct
        h.enable(20)
        self.calls = []

    def native(self, *args):
        self.calls.append(args)
        definition = self.factory.PawnBalanceDefinition
        estimate = self.h.runtime.spawns.plan.__globals__["native_level"](definition.DefaultExpLevel, args[4])
        modifier = definition.Grades[0].GradeModifiers.ExpLevel
        return NS(level=modifier if modifier > 0 else estimate + modifier,
                  definition=definition, health_multiplier=definition.Grades[0].GradeModifiers.HealthMultiplier)

    def spawn(self, ticket=0, restore=False):
        self.h.runtime.spawns.roll = lambda: ticket
        callback = self.h.mod.restore_pawn if restore else self.h.mod.create_pawn
        result = callback(self.factory, self.args, None, self.native)
        if result is None:
            return self.native(self.args.Master, self.args.SpawnLocationContextObject, self.args.SpawnLocation,
                               self.args.SpawnRotation, self.args.GameStage, self.args.AwesomeLevel)
        return result[1]

    def test_all_100_tickets_produce_exact_50_20_25_5_distribution(self):
        levels = [self.spawn(ticket).level for ticket in range(100)]
        self.assertEqual({level: levels.count(level) for level in set(levels)}, {20: 50, 21: 20, 22: 25, 23: 5})

    def test_all_presets_produce_exact_weighted_levels(self):
        expected = {
            "Easy": {20: 70, 21: 20, 22: 9, 23: 1},
            "Normal": {20: 50, 21: 20, 22: 25, 23: 5},
            "Hard": {20: 20, 21: 5, 22: 55, 23: 20},
        }
        for difficulty, counts in expected.items():
            with self.subTest(difficulty=difficulty):
                self.h.mod.enemy_difficulty.value = difficulty
                levels = [self.spawn(ticket).level for ticket in range(100)]
                self.assertEqual({level: levels.count(level) for level in set(levels)}, counts)
                report = self.h.runtime.spawns.snapshot()
                self.assertEqual(report["difficulty"], difficulty)
                self.assertEqual(sum(report["ordinary_tickets"].values()), 100)

    def test_every_preset_keeps_max_player_vanilla_area_as_spawn_base(self):
        policies = {"Easy": (70, 20, 9, 1), "Normal": (50, 20, 25, 5),
                    "Hard": (20, 5, 55, 20)}
        for difficulty, weights in policies.items():
            self.h.mod.enemy_difficulty.value = difficulty
            for player, area in ((8, 30), (40, 12)):
                self.h.enable(player)
                self.args.GameStage = area
                ticket = 0
                for extra, count in enumerate(weights):
                    for _ in range(count):
                        spawned = self.spawn(ticket)
                        expected = max(player, max(player, area) + (extra if extra else -1))
                        self.assertEqual(spawned.level, expected, (difficulty, player, area, ticket))
                        self.assertEqual(self.calls[-1][4], max(player, area) + extra)
                        ticket += 1

    def test_difficulty_change_affects_new_spawns_without_mutating_old_ones(self):
        self.h.mod.enemy_difficulty.value = "Easy"
        first = self.spawn(85)
        self.h.mod.enemy_difficulty.value = "Hard"
        second = self.spawn(95)
        self.assertEqual((first.level, second.level), (21, 23))
        self.assertEqual(first.definition.DefaultExpLevel.BaseValueConstant, 0)
        self.assertIs(first.definition.DefaultExpLevel.BaseValueAttribute, self.exact)
        self.assertIs(self.factory.PawnBalanceDefinition, self.definition)

    def test_all_presets_keep_naturally_higher_levels_without_stacking(self):
        self.definition.DefaultExpLevel.BaseValueAttribute = Object("gd_Balance.EnemyLevel.EnemyLevel_GameStage_plus5")
        for difficulty in ("Easy", "Normal", "Hard"):
            self.h.mod.enemy_difficulty.value = difficulty
            self.assertTrue(all(self.spawn(t).level == 25 for t in range(100)))

    def test_invalid_difficulty_falls_back_to_normal(self):
        self.h.mod.enemy_difficulty.value = "Invalid saved value"
        self.assertEqual(self.h.runtime.spawns.snapshot()["difficulty"], "Normal")
        self.assertEqual(self.spawn(90).level, 22)

    def test_native_floor_preserves_area_stage_and_native_grade_selection_bands(self):
        self.h.enable(20)
        self.args.GameStage = 30
        grade = self.definition.Grades[0]
        grade.GradeModifiers.ExpLevel = 3
        grade.GameStageRequirement.MinGameStage = 25
        grade.GameStageRequirement.MaxGameStage = 40
        lower, upper = deepcopy(grade), deepcopy(grade)
        lower.GameStageRequirement.MinGameStage, lower.GameStageRequirement.MaxGameStage = 1, 24
        upper.GameStageRequirement.MinGameStage, upper.GameStageRequirement.MaxGameStage = 41, 100
        self.definition.Grades.extend((lower, upper))
        before = deepcopy(self.definition.Grades)
        first = self.spawn(0)
        self.assertEqual(first.level, 20)
        self.assertEqual(self.calls[-1][4], 30)
        self.assertIsNone(first.definition.DefaultExpLevel.BaseValueAttribute)
        self.assertEqual(first.definition.DefaultExpLevel.BaseValueConstant, 29)
        self.assertEqual(first.definition.Grades[0].GradeModifiers.ExpLevel, 20)
        self.assertEqual((first.definition.Grades[0].GameStageRequirement.MinGameStage,
                          first.definition.Grades[0].GameStageRequirement.MaxGameStage), (25, 40))
        self.assertEqual(self.definition.Grades[0].GradeModifiers.ExpLevel, before[0].GradeModifiers.ExpLevel)
        self.assertEqual(first.health_multiplier, 3)

    def test_floor_cache_keeps_distinct_native_defaults_at_different_area_stages(self):
        self.definition.Grades[0].GradeModifiers.ExpLevel = 3
        self.args.GameStage = 30
        first = self.spawn(0)
        self.args.GameStage = 40
        second = self.spawn(0)
        self.assertEqual((first.level, second.level), (20, 20))
        self.assertIsNot(first.definition, second.definition)
        self.assertEqual(first.definition.DefaultExpLevel.BaseValueConstant, 29)
        self.assertEqual(second.definition.DefaultExpLevel.BaseValueConstant, 39)

    def test_player_floor_never_mutates_previously_spawned_pawns(self):
        first = self.spawn(0)
        self.h.enable(30)
        second = self.spawn(0)
        self.assertEqual((first.level, second.level), (20, 30))
        self.assertEqual(first.definition.DefaultExpLevel.BaseValueConstant, 20)
        self.assertIs(self.factory.PawnBalanceDefinition, self.definition)

    def test_no_grade_default_gets_floor_without_changing_area_stage(self):
        self.definition.Grades = []
        self.definition.DefaultExpLevel = aid(3)
        stage, clone = self.h.runtime.spawns.plan(self.factory, 20, 30)
        self.assertEqual(stage, 30)
        self.assertEqual(clone.DefaultExpLevel.BaseValueConstant, 20)
        self.assertIsNone(clone.DefaultExpLevel.BaseValueAttribute)

    def test_high_native_area_is_floor_for_normal_and_rare_enemies(self):
        self.h.enable(8)
        self.args.GameStage = 30
        self.assertEqual([self.spawn(t).level for t in (0, 50, 70, 95, 99)], [29, 31, 32, 33, 33])

    def test_naturally_higher_enemy_never_gets_bonus_stacked(self):
        self.definition.DefaultExpLevel.BaseValueAttribute = Object("gd_Balance.EnemyLevel.EnemyLevel_GameStage_plus3")
        self.assertEqual([self.spawn(t).level for t in (0, 50, 70, 95, 99)], [23, 23, 23, 23, 23])

    def test_naturally_higher_grade_is_retained_without_stacking_bonus(self):
        self.definition.Grades[0].GradeModifiers.ExpLevel = 23
        self.assertEqual([self.spawn(t).level for t in (0, 50, 70, 95, 99)], [23, 23, 23, 23, 23])

    def test_tutorial_fixed_level_does_not_override_rare_upgrade(self):
        self.definition.Grades[0].GradeModifiers.ExpLevel = 3
        self.assertEqual([self.spawn(t).level for t in (0, 50, 70, 95, 99)], [20, 21, 22, 23, 23])

    def test_natural_high_default_does_not_raise_fixed_tutorial_grade_extra_levels(self):
        self.definition.DefaultExpLevel.BaseValueAttribute = Object("gd_Balance.EnemyLevel.EnemyLevel_GameStage_plus3")
        self.definition.Grades[0].GradeModifiers.ExpLevel = 3
        self.assertEqual([self.spawn(t).level for t in (0, 50, 70, 95, 99)], [20, 21, 22, 23, 23])

    def test_named_low_fixed_grade_floors_to_player_while_native_higher_grades_survive(self):
        self.definition.path = "gd_Balance_Enemies_Humans.Bandits.Named.Pawn_Balance_Bonehead"
        self.definition.DefaultExpLevel.BaseValueAttribute = Object("gd_Balance.EnemyLevel.EnemyLevel_GameStage_plus2")
        self.definition.Grades[0].GradeModifiers.ExpLevel = 12
        self.assertEqual(self.spawn(99).level, 20)
        self.definition.Grades[0].GradeModifiers.ExpLevel = 25
        self.assertEqual(self.spawn(99).level, 25)

    def test_private_high_grade_levels_remain_absolute_when_reused_later(self):
        self.definition.Grades[0].GradeModifiers.ExpLevel = 23
        first = self.spawn(50)
        self.h.enable(40)
        second = self.spawn(50)
        self.assertEqual((first.level, second.level), (23, 41))
        self.assertEqual(first.definition.Grades[0].GradeModifiers.ExpLevel, 23)
        self.assertEqual(second.definition.Grades[0].GradeModifiers.ExpLevel, 0)

    def test_shared_definition_and_old_pawn_unchanged_by_later_spawns(self):
        before = vars(self.definition.DefaultExpLevel).copy()
        first = self.spawn(50)
        self.h.enable(40)
        second = self.spawn(99)
        self.assertEqual((first.level, second.level), (21, 43))
        self.assertEqual(vars(self.definition.DefaultExpLevel), before)
        self.assertIs(self.factory.PawnBalanceDefinition, self.definition)
        self.assertEqual(first.definition.DefaultExpLevel.BaseValueAttribute, self.exact)
        self.assertEqual(first.health_multiplier, 3)
        self.assertEqual(first.definition.Grades[0].GradeModifiers.DamageMultiplier, 2)
        self.h.mod.on_disable()
        self.assertEqual(first.definition.DefaultExpLevel.BaseValueAttribute, self.exact)
        self.assertEqual(first.definition.ObjectFlags, 0)

    def test_named_base_game_and_every_dlc_are_excluded_from_roll(self):
        names = self.h.runtime.spawns.plan.__globals__["named_enemy"].__globals__["BALANCE_NAMES"]
        for difficulty in ("Easy", "Normal", "Hard"):
            self.h.mod.enemy_difficulty.value = difficulty
            for path in names:
                self.definition.path = path
                self.h.runtime.spawns.roll = lambda: self.fail("Named enemy used ordinary roll")
                stage, clone = self.h.runtime.spawns.plan(self.factory, 20, 30)
                self.assertEqual(stage, 30)
                self.assertIsNone(clone)

    def test_low_native_named_enemy_gets_player_floor_not_fixed_level(self):
        self.definition.path = "gd_Balance_Enemies_Humans.Bandits.Named.Pawn_Balance_Bonehead"
        self.definition.DefaultExpLevel = aid(12)
        self.assertEqual(self.spawn(99).level, 20)
        self.h.enable(8)
        self.args.GameStage = 8
        self.assertEqual(self.spawn(99).level, 12)

    def test_friendly_neutral_and_unknown_allegiance_do_not_roll(self):
        for allegiance in ("Native.Friendly.Bandit", "Native.Neutral", "Native.Player", None):
            self.definition.AIPawnArchetype.Allegiance = Object(allegiance) if allegiance else None
            self.h.runtime.spawns.roll = lambda: self.fail("Non-hostile enemy used ordinary roll")
            self.h.runtime.spawns.plan(self.factory, 20, 20)

    def test_custom_named_and_boss_paths_do_not_roll(self):
        for path in ("Custom_Enemies.Named.NewGuy", "Custom_Enemies.Boss.NewGuy"):
            self.definition.path = path
            self.h.runtime.spawns.roll = lambda: self.fail("Custom named enemy used ordinary roll")
            self.h.runtime.spawns.plan(self.factory, 20, 30)

    def test_restore_passes_memento_and_does_not_duplicate_native_call(self):
        self.spawn(99, restore=True)
        self.assertEqual(len(self.calls), 1)
        self.assertIs(self.calls[0][-1], self.args.AIPawnMemento)

    def test_throwing_native_call_restores_factory_and_never_retries(self):
        self.h.runtime.spawns.roll = lambda: 99
        def fail(*args):
            self.calls.append(args)
            self.assertIsNot(self.factory.PawnBalanceDefinition, self.definition)
            raise RuntimeError("modeled native error")
        result = self.h.mod.create_pawn(self.factory, self.args, None, fail)
        self.assertIsNone(result[1])
        self.assertEqual(len(self.calls), 1)
        self.assertIs(self.factory.PawnBalanceDefinition, self.definition)
        self.assertFalse(self.h.runtime.spawns.active)

    def test_clone_failure_keeps_native_factory_and_does_not_attempt_native_twice(self):
        self.h.runtime.spawns.roll = lambda: 99
        self.h.sdk.construct_object = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("clone failed"))
        self.assertIsNone(self.h.mod.create_pawn(self.factory, self.args, None, self.native))
        self.assertEqual(self.calls, [])  # SDK continues the single original call.
        self.assertIs(self.factory.PawnBalanceDefinition, self.definition)
        self.assertTrue(self.h.runtime.problems)

    def test_clones_reused_with_actor_local_stage_not_shared_mutable_level(self):
        first = self.spawn(50)
        self.h.enable(40)
        second = self.spawn(50)
        self.assertIs(first.definition, second.definition)
        self.assertEqual((first.level, second.level), (21, 41))
        self.assertEqual(first.definition.DefaultExpLevel.BaseValueConstant, 0)
        self.assertIs(first.definition.DefaultExpLevel.BaseValueAttribute, self.exact)

    def test_nested_factory_call_does_not_roll_or_intercept_again(self):
        self.h.runtime.spawns.active = True
        self.h.runtime.spawns.roll = lambda: self.fail("nested roll")
        self.assertIsNone(self.h.mod.create_pawn(self.factory, self.args, None, self.native))
        self.assertEqual(self.calls, [])

    def test_unknown_dynamic_formula_is_retained_without_guessing(self):
        self.definition.DefaultExpLevel.InitializationDefinition = Object("Custom.DynamicLevel")
        self.h.runtime.spawns.roll = lambda: 99
        stage, clone = self.h.runtime.spawns.plan(self.factory, 20, 30)
        self.assertEqual(stage, 30)
        self.assertIsNone(clone)
        self.assertTrue(self.h.runtime.problems)


if __name__ == "__main__":
    unittest.main()
