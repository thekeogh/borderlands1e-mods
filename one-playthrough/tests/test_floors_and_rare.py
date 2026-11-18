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

    def test_offer_and_active_mission_preserve_vanilla_floor_then_track_player(self):
        h = self.h
        h.enable(5)
        self.assertEqual(h.mission.ExpLevel, 16)
        h.enable(20)
        self.assertEqual(h.mission.ExpLevel, 20)
        h.accept()
        h.enable(30)
        self.assertEqual(h.mission.ExpLevel, 30)

    def test_accepted_high_level_mission_tracks_player_after_catching_up(self):
        h = self.h
        h.enable(5)
        h.accept()
        self.assertEqual(h.runtime.missions.levels[h.mission.path.lower()], 16)
        h.enable(30)
        self.assertEqual(h.reward(), 30)

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
                self.assertEqual(h.reward(), 69)
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

    def test_legacy_acceptance_record_no_longer_overrides_active_vanilla_floor(self):
        h = self.h
        h.state()
        h.runtime.store.levels("slot:1:gd_playerclassid.soldier")[h.mission.path.lower()] = 7
        h.runtime.store.save()
        h.enable(10)
        self.assertEqual(h.mission.ExpLevel, 16)
        self.assertEqual(h.reward(), 16)
        self.assertEqual(h.row().DefaultGameStage.BaseValueConstant, 16)

    def test_exception_during_native_floor_query_restores_all_live_fields(self):
        h = self.h
        h.enable(30)
        before = (h.row().DefaultGameStage.BaseValueConstant, h.mission.GameStage, h.mission.ExpLevel, h.mission.MinimumLevel)
        h.runtime.missions.floors.clear()
        def fail(_pc):
            self.assertEqual(h.row().DefaultGameStage.BaseValueConstant, 16)
            self.assertEqual(h.mission.MinimumLevel,12)
            raise RuntimeError("modeled native refresh error")
        h.mission.RefreshRewardGameStage = fail
        with self.assertRaises(RuntimeError): h.runtime.missions.apply(h.mission, h.pc)
        self.assertEqual(before, (h.row().DefaultGameStage.BaseValueConstant, h.mission.GameStage, h.mission.ExpLevel, h.mission.MinimumLevel))
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
        h.mod.enemy_difficulty.value = "Easy"
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

    def test_normal_all_100_tickets_produce_exact_60_40_distribution(self):
        self.h.mod.enemy_difficulty.value = "Medium"
        levels = [self.spawn(ticket).level for ticket in range(100)]
        self.assertEqual({level: levels.count(level) for level in set(levels)}, {22: 60, 23: 40})

    def test_all_presets_produce_exact_weighted_levels(self):
        expected = {
            "Easy": {21: 40, 22: 60},
            "Medium": {22: 60, 23: 40},
            "Hard": {23: 80, 24: 20},
            "Very Hard": {23: 20, 24: 75, 25: 5},
        }
        for difficulty, counts in expected.items():
            with self.subTest(difficulty=difficulty):
                self.h.mod.enemy_difficulty.value = difficulty
                levels = [self.spawn(ticket).level for ticket in range(100)]
                self.assertEqual({level: levels.count(level) for level in set(levels)}, counts)
                report = self.h.runtime.spawns.snapshot()
                self.assertEqual(report["difficulty"], difficulty)
                self.assertEqual(sum(report["ordinary_tickets"].values()), 100)

    def test_very_hard_player_36_rolls_39_through_41_at_agreed_percentages(self):
        self.h.enable(36)
        self.h.mod.enemy_difficulty.value = 'Very Hard'
        levels = [self.spawn(ticket).level for ticket in range(100)]
        self.assertEqual({level:levels.count(level) for level in set(levels)},
                         {39:20,40:75,41:5})

    def test_every_preset_keeps_max_player_vanilla_area_as_spawn_base(self):
        policies = {"Easy": (0, 40, 60), "Medium": (0, 0, 60, 40),
                    "Hard": (0, 0, 0, 80, 20), "Very Hard": (0, 0, 0, 20, 75, 5)}
        for difficulty, weights in policies.items():
            self.h.mod.enemy_difficulty.value = difficulty
            for player, area in ((8, 30), (40, 12)):
                self.h.enable(player)
                self.args.GameStage = area
                ticket = 0
                for extra, count in enumerate(weights):
                    for _ in range(count):
                        spawned = self.spawn(ticket)
                        expected = max(player + 1, max(player, area) + (extra if extra else -1))
                        self.assertEqual(spawned.level, expected, (difficulty, player, area, ticket))
                        self.assertEqual(self.calls[-1][4], max(player, area) + extra)
                        ticket += 1

    def test_difficulty_change_affects_new_spawns_without_mutating_old_ones(self):
        self.h.mod.enemy_difficulty.value = "Easy"
        first = self.spawn(85)
        self.h.mod.enemy_difficulty.value = "Hard"
        second = self.spawn(95)
        self.h.mod.enemy_difficulty.value = "Very Hard"
        third = self.spawn(99)
        self.assertEqual((first.level, second.level, third.level), (22, 24, 25))
        self.assertEqual(first.definition.DefaultExpLevel.BaseValueConstant, 0)
        self.assertIs(first.definition.DefaultExpLevel.BaseValueAttribute, self.exact)
        self.assertIs(self.factory.PawnBalanceDefinition, self.definition)

    def test_all_presets_keep_naturally_higher_levels_without_stacking(self):
        self.definition.DefaultExpLevel.BaseValueAttribute = Object("gd_Balance.EnemyLevel.EnemyLevel_GameStage_plus5")
        for difficulty in ("Easy", "Medium", "Hard", "Very Hard"):
            self.h.mod.enemy_difficulty.value = difficulty
            self.assertTrue(all(self.spawn(t).level == 25 for t in range(100)))

    def test_very_hard_reports_plus_five_and_keeps_rare_spawn_above_player_cap(self):
        self.h.mod.enemy_difficulty.value = "Very Hard"
        self.assertEqual(self.h.runtime.spawns.snapshot()["ordinary_tickets"],
                         {"native": 0, "+1": 0, "+2": 0, "+3": 20, "+4": 75, "+5": 5})
        self.h.enable(69)
        self.args.GameStage = 69
        for ticket, level in ((0, 72), (19, 72), (20, 73), (94, 73), (95, 74), (99, 74)):
            self.assertEqual(self.spawn(ticket).level, level)

    def test_invalid_difficulty_falls_back_to_normal(self):
        self.h.mod.enemy_difficulty.value = "Invalid saved value"
        self.assertEqual(self.h.runtime.spawns.snapshot()["difficulty"], "Medium")
        self.assertEqual(self.spawn(90).level, 23)

    def test_native_equal_player_defaults_and_fixed_grades_now_spawn_at_plus_one(self):
        self.definition.DefaultExpLevel = aid(20)
        self.definition.Grades[0].GradeModifiers.ExpLevel = 20
        self.assertEqual(self.spawn(0).level, 21)
        self.assertEqual(self.calls[-1][4], 21)
        self.assertEqual(self.definition.Grades[0].GradeModifiers.ExpLevel, 20)

    def test_native_plus_one_floor_applies_at_level_one_and_above_player_cap(self):
        for difficulty in ("Easy", "Medium", "Hard", "Very Hard"):
            self.h.mod.enemy_difficulty.value = difficulty
            for player in (1, 12, 69):
                with self.subTest(difficulty=difficulty, player=player):
                    self.h.enable(player)
                    self.args.GameStage = player
                    self.definition.DefaultExpLevel = aid(player)
                    self.definition.Grades[0].GradeModifiers.ExpLevel = 0
                    extra = {"Easy":1,"Medium":2,"Hard":3,"Very Hard":3}[difficulty]
                    self.assertEqual(self.spawn(0).level, player + (extra or 1))
                    self.assertEqual(self.calls[-1][4], player + extra)

    def test_easy_named_enemy_is_fixed_at_player_plus_two(self):
        self.definition.path = "gd_Balance_Enemies_Humans.Bandits.Named.Pawn_Balance_Bonehead"
        self.definition.DefaultExpLevel = aid(20)
        self.definition.Grades[0].GradeModifiers.ExpLevel = 20
        self.h.runtime.spawns.roll = lambda: self.fail("named enemy must not roll")
        stage, clone = self.h.runtime.spawns.plan(self.factory,20,20)
        self.assertEqual(stage,20)
        self.assertEqual(clone.DefaultExpLevel.BaseValueConstant,22)
        self.assertTrue(all(g.GradeModifiers.ExpLevel == 22 for g in clone.Grades))

    def test_easy_bonus_preserves_native_grade_selection_bands(self):
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
        self.assertEqual(first.level, 31)
        self.assertEqual(self.calls[-1][4], 31)
        self.assertIs(first.definition.DefaultExpLevel.BaseValueAttribute,self.exact)
        self.assertEqual(first.definition.DefaultExpLevel.BaseValueConstant, 0)
        self.assertEqual(first.definition.Grades[0].GradeModifiers.ExpLevel, 0)
        self.assertEqual((first.definition.Grades[0].GameStageRequirement.MinGameStage,
                          first.definition.Grades[0].GameStageRequirement.MaxGameStage), (25, 40))
        self.assertEqual(self.definition.Grades[0].GradeModifiers.ExpLevel, before[0].GradeModifiers.ExpLevel)
        self.assertEqual(first.health_multiplier, 3)

    def test_easy_cache_uses_actor_local_area_stage(self):
        self.definition.Grades[0].GradeModifiers.ExpLevel = 3
        self.args.GameStage = 30
        first = self.spawn(0)
        self.args.GameStage = 40
        second = self.spawn(0)
        self.assertEqual((first.level, second.level), (31, 41))
        self.assertIs(first.definition, second.definition)
        self.assertEqual(first.definition.DefaultExpLevel.BaseValueConstant, 0)
        self.assertEqual(second.definition.DefaultExpLevel.BaseValueConstant, 0)

    def test_player_floor_never_mutates_previously_spawned_pawns(self):
        first = self.spawn(0)
        self.h.enable(30)
        second = self.spawn(0)
        self.assertEqual((first.level, second.level), (21, 31))
        self.assertEqual(first.definition.DefaultExpLevel.BaseValueConstant, 0)
        self.assertIs(self.factory.PawnBalanceDefinition, self.definition)

    def test_easy_no_grade_default_gets_bonus_at_high_area_stage(self):
        self.definition.Grades = []
        self.definition.DefaultExpLevel = aid(3)
        stage, clone = self.h.runtime.spawns.plan(self.factory, 20, 30)
        self.assertEqual(stage, 31)
        self.assertEqual(clone.DefaultExpLevel.BaseValueConstant, 31)
        self.assertIsNone(clone.DefaultExpLevel.BaseValueAttribute)

    def test_high_native_area_is_floor_for_normal_and_rare_enemies(self):
        self.h.enable(8)
        self.args.GameStage = 30
        self.assertEqual([self.spawn(t).level for t in (0, 70, 90, 99)], [31, 32, 32, 32])

    def test_naturally_higher_enemy_never_gets_bonus_stacked(self):
        self.definition.DefaultExpLevel.BaseValueAttribute = Object("gd_Balance.EnemyLevel.EnemyLevel_GameStage_plus3")
        self.assertEqual([self.spawn(t).level for t in (0, 70, 90, 99)], [23, 23, 23, 23])

    def test_naturally_higher_grade_is_retained_without_stacking_bonus(self):
        self.definition.Grades[0].GradeModifiers.ExpLevel = 23
        self.assertEqual([self.spawn(t).level for t in (0, 70, 90, 99)], [23, 23, 23, 23])

    def test_tutorial_fixed_level_does_not_override_rare_upgrade(self):
        self.definition.Grades[0].GradeModifiers.ExpLevel = 3
        self.assertEqual([self.spawn(t).level for t in (0, 70, 90, 99)], [21, 22, 22, 22])

    def test_natural_high_default_does_not_raise_fixed_tutorial_grade_extra_levels(self):
        self.definition.DefaultExpLevel.BaseValueAttribute = Object("gd_Balance.EnemyLevel.EnemyLevel_GameStage_plus3")
        self.definition.Grades[0].GradeModifiers.ExpLevel = 3
        self.assertEqual([self.spawn(t).level for t in (0, 70, 90, 99)], [21, 22, 22, 22])

    def test_easy_named_fixed_level_replaces_low_and_high_grade(self):
        self.definition.path = "gd_Balance_Enemies_Humans.Bandits.Named.Pawn_Balance_Bonehead"
        self.definition.DefaultExpLevel.BaseValueAttribute = Object("gd_Balance.EnemyLevel.EnemyLevel_GameStage_plus2")
        self.definition.Grades[0].GradeModifiers.ExpLevel = 12
        self.assertEqual(self.spawn(99).level, 22)
        self.definition.Grades[0].GradeModifiers.ExpLevel = 25
        self.assertEqual(self.spawn(99).level, 22)

    def test_private_high_grade_levels_remain_absolute_when_reused_later(self):
        self.definition.Grades[0].GradeModifiers.ExpLevel = 23
        first = self.spawn(0)
        self.h.enable(40)
        second = self.spawn(0)
        self.assertEqual((first.level, second.level), (23, 41))
        self.assertEqual(first.definition.Grades[0].GradeModifiers.ExpLevel, 23)
        self.assertEqual(second.definition.Grades[0].GradeModifiers.ExpLevel, 0)

    def test_shared_definition_and_old_pawn_unchanged_by_later_spawns(self):
        before = vars(self.definition.DefaultExpLevel).copy()
        first = self.spawn(0)
        self.h.enable(40)
        second = self.spawn(99)
        self.assertEqual((first.level, second.level), (21, 42))
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
        for difficulty in ("Easy", "Medium", "Hard", "Very Hard"):
            self.h.mod.enemy_difficulty.value = difficulty
            for path in names:
                self.definition.path = path
                self.h.runtime.spawns.roll = lambda: self.fail("Named enemy used ordinary roll")
                stage, clone = self.h.runtime.spawns.plan(self.factory, 20, 30)
                self.assertEqual(stage, 30)
                if difficulty in ("Easy", "Medium", "Hard", "Very Hard"):
                    target = {"Easy":22,"Medium":22,"Hard":23,"Very Hard":24}[difficulty]
                    self.assertEqual(clone.DefaultExpLevel.BaseValueConstant,target)
                    self.assertTrue(all(g.GradeModifiers.ExpLevel==target for g in clone.Grades))
                else:
                    self.assertIsNone(clone)

    def test_all_play_modes_named_levels_are_fixed_even_with_higher_native_inputs(self):
        self.definition.path = 'gd_Balance_Enemies_Humans.Bandits.Named.Pawn_Balance_Bonehead'
        self.h.runtime.spawns.roll = lambda:self.fail('Named enemy used RNG')
        for difficulty,offset in (('Easy',2),('Medium',2),('Hard',3),('Very Hard',4)):
            self.h.mod.enemy_difficulty.value = difficulty
            for player in (1,20,69):
                self.h.enable(player)
                for native in (1,99):
                    self.definition.DefaultExpLevel = aid(native)
                    self.definition.Grades[0].GradeModifiers.ExpLevel = native
                    original = deepcopy(self.definition.Grades[0])
                    stage,clone = self.h.runtime.spawns.plan(self.factory,player,80)
                    self.assertEqual(stage,80)
                    self.assertEqual(clone.DefaultExpLevel.BaseValueConstant,player+offset)
                    self.assertEqual(clone.Grades[0].GradeModifiers.ExpLevel,player+offset)
                    self.assertEqual(vars(clone.Grades[0].GameStageRequirement),vars(original.GameStageRequirement))
                    self.assertEqual(clone.Grades[0].GradeModifiers.HealthMultiplier,original.GradeModifiers.HealthMultiplier)
                    self.assertEqual(self.definition.Grades[0].GradeModifiers.ExpLevel,native)
            self.assertEqual(self.h.runtime.spawns.snapshot()['named_level'],f'exactly player level + {offset}')

    def test_fixed_named_vehicle_modes_keep_factory_and_existing_spawn_data(self):
        self.definition.AIPawnArchetype.path = 'gd_cheetahspaw.vehiclearchetype.mad_mel'
        factory = NS(VehicleBalanceDefinition=self.definition,VehicleArchetype=self.definition.AIPawnArchetype)
        self.definition.DefaultExpLevel = aid(99)
        self.h.runtime.spawns.roll = lambda:self.fail('Named vehicle used RNG')
        old = None
        for difficulty,target in (('Hard',23),('Very Hard',24)):
            self.h.mod.enemy_difficulty.value = difficulty
            stage,clone = self.h.runtime.spawns.plan(factory,20,80,vehicle=True)
            self.assertEqual(stage,80)
            self.assertEqual(clone.DefaultExpLevel.BaseValueConstant,target)
            self.assertTrue(all(g.GradeModifiers.ExpLevel==target for g in clone.Grades))
            self.assertIs(factory.VehicleBalanceDefinition,self.definition)
            if old is not None:self.assertEqual(old.DefaultExpLevel.BaseValueConstant,23)
            old = clone
        self.h.mod.enemy_difficulty.value = 'Easy'
        stage,clone = self.h.runtime.spawns.plan(factory,20,80,vehicle=True)
        self.assertEqual(clone.DefaultExpLevel.BaseValueConstant,22)
        self.assertEqual(old.DefaultExpLevel.BaseValueConstant,24)

    def test_easy_named_fixed_plus_two_tracks_player(self):
        self.definition.path = "gd_Balance_Enemies_Humans.Bandits.Named.Pawn_Balance_Bonehead"
        self.definition.DefaultExpLevel = aid(12)
        self.assertEqual(self.spawn(99).level, 22)
        self.h.enable(8)
        self.args.GameStage = 8
        self.assertEqual(self.spawn(99).level, 10)

    def test_easy_bone_head_overrides_native_levels_with_fixed_plus_two(self):
        self.definition.path = 'gd_Balance_Enemies_Humans.Bandits.Named.Pawn_Balance_Bonehead'
        self.h.enable(5)
        self.args.GameStage = 5
        for native,expected in ((10,7),(12,7),(6,7)):
            self.definition.DefaultExpLevel = aid(native)
            self.definition.Grades[0].GradeModifiers.ExpLevel = native
            self.assertEqual(self.spawn().level,expected)
        self.h.enable(12)
        self.args.GameStage = 12
        self.assertEqual(self.spawn().level,14)

    def test_easy_named_dynamic_input_is_replaced_only_on_private_clone(self):
        self.definition.path = 'Custom_Enemies.Boss.NewGuy'
        dynamic = Object('Custom.DynamicLevel')
        self.definition.DefaultExpLevel.InitializationDefinition = dynamic
        self.h.runtime.spawns.roll = lambda:self.fail('Named enemy used RNG')
        stage,clone = self.h.runtime.spawns.plan(self.factory,20,20)
        self.assertEqual(stage,20)
        self.assertEqual(clone.DefaultExpLevel.BaseValueConstant,22)
        self.assertIsNone(clone.DefaultExpLevel.InitializationDefinition)
        self.assertIs(self.definition.DefaultExpLevel.InitializationDefinition,dynamic)
        self.assertEqual(self.h.runtime.problems,[])

    def test_easy_named_fixed_level_preserves_combat_modifiers(self):
        self.definition.path = 'gd_Balance_Enemies_Humans.Bandits.Named.Pawn_Balance_Bonehead'
        second = deepcopy(self.definition.Grades[0])
        second.GradeModifiers.ExpLevel = 25
        self.definition.Grades[0].GradeModifiers.ExpLevel = 12
        self.definition.Grades.append(second)
        self.h.runtime.spawns.roll = lambda:self.fail('Named enemy used RNG')
        stage,clone = self.h.runtime.spawns.plan(self.factory,20,20)
        self.assertEqual(stage,20)
        self.assertEqual([g.GradeModifiers.ExpLevel for g in clone.Grades],[22,22])
        self.assertEqual(clone.Grades[0].GradeModifiers.HealthMultiplier,3)
        self.assertEqual(clone.Grades[0].GradeModifiers.DamageMultiplier,2)
        self.assertEqual([g.GradeModifiers.ExpLevel for g in self.definition.Grades],[12,25])
        self.definition.DefaultExpLevel.BaseValueAttribute = Object('gd_Balance.EnemyLevel.EnemyLevel_GameStage_plus9')
        self.definition.Grades[0].GradeModifiers.ExpLevel = 0
        stage,clone = self.h.runtime.spawns.plan(self.factory,20,20)
        self.assertEqual(stage,20)
        self.assertEqual(clone.DefaultExpLevel.BaseValueConstant,22)

    def test_easy_named_without_grades_uses_fixed_default(self):
        self.definition.path = 'Custom_Enemies.Boss.NewGuy'
        self.definition.Grades = []
        self.definition.DefaultExpLevel = aid(99)
        stage,clone = self.h.runtime.spawns.plan(self.factory,36,20)
        self.assertEqual(stage,36)
        self.assertEqual(clone.DefaultExpLevel.BaseValueConstant,38)
        self.definition.DefaultExpLevel = aid(1)
        stage,clone = self.h.runtime.spawns.plan(self.factory,36,20)
        self.assertEqual(clone.DefaultExpLevel.BaseValueConstant,38)
        self.assertEqual(clone.Grades,[])

    def test_named_private_clone_keeps_old_spawn_and_source_unchanged(self):
        self.definition.path = 'gd_Balance_Enemies_Humans.Bandits.Named.Pawn_Balance_Bonehead'
        before = vars(self.definition.DefaultExpLevel).copy()
        first = self.spawn()
        self.h.enable(40)
        second = self.spawn()
        self.assertEqual((first.level,second.level),(22,42))
        self.assertEqual(first.definition.Grades[0].GradeModifiers.ExpLevel,22)
        self.assertIs(self.factory.PawnBalanceDefinition,self.definition)
        self.assertEqual(vars(self.definition.DefaultExpLevel),before)
        self.h.mod.on_disable()
        self.assertEqual(first.definition.Grades[0].GradeModifiers.ExpLevel,22)

    def test_easy_named_vehicle_boss_fixed_plus_two_restores_factory(self):
        self.definition.path = 'Native.VehicleBalance'
        archetype = self.definition.AIPawnArchetype
        archetype.path = 'gd_cheetahspaw.vehiclearchetype.mad_mel'
        factory = NS(VehicleBalanceDefinition=self.definition,VehicleArchetype=archetype)
        self.h.runtime.spawns.roll = lambda:self.fail('Named vehicle used RNG')
        calls=[]
        def native(*args):
            calls.append(args)
            clone = factory.VehicleBalanceDefinition
            self.assertEqual(args[4],20)
            self.assertEqual(clone.DefaultExpLevel.BaseValueConstant,22)
            self.assertTrue(all(g.GradeModifiers.ExpLevel==22 for g in clone.Grades))
            return 'spawned boss'
        result = self.h.mod.create_vehicle(factory,self.args,None,native)
        self.assertEqual(result,(self.h.mod.Block,'spawned boss'))
        self.assertEqual(len(calls),1)
        self.assertIs(factory.VehicleBalanceDefinition,self.definition)

    def test_ordinary_vehicle_still_keeps_native_stage_and_no_rng(self):
        factory = NS(VehicleBalanceDefinition=self.definition,VehicleArchetype=self.definition.AIPawnArchetype)
        self.h.runtime.spawns.roll = lambda:self.fail('Ordinary vehicle used RNG')
        stage,clone = self.h.runtime.spawns.plan(factory,20,30,vehicle=True)
        self.assertEqual(stage,30)
        self.assertIsNone(clone)

    def test_unsupported_named_layout_records_reason_without_native_mutation(self):
        definition = Object('Custom_Enemies.Boss.Unsupported')
        definition.Grades = []
        archetype = self.definition.AIPawnArchetype
        definition.AIPawnArchetype = archetype
        factory = NS(PawnBalanceDefinition=definition)
        stage,clone = self.h.runtime.spawns.plan(factory,20,30)
        self.assertEqual(stage,30)
        self.assertIsNone(clone)
        self.assertIn('Unsupported named balance layout',str(self.h.runtime.problems))
        self.assertIs(factory.PawnBalanceDefinition,definition)

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
        first = self.spawn(0)
        self.h.enable(40)
        second = self.spawn(0)
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
