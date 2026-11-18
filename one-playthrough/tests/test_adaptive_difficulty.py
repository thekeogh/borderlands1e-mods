"""Adaptive probability math and native-wrapper contracts, using local models."""

from collections import Counter
from types import SimpleNamespace as NS
import tempfile
import unittest

from test_one_playthrough import Harness, Object, aid
from test_settings import SDKSettingsMod
import test_floors_and_rare as models


class AdaptiveDifficultyTests(unittest.TestCase):
    def setUp(self):
        self.rig = models.Rare('test_all_presets_produce_exact_weighted_levels')
        self.rig.setUp()
        self.addCleanup(self.rig.doCleanups)
        self.h = self.rig.h
        self.svc = self.h.runtime.spawns
        self.h.mod.enemy_difficulty.value = 'Adaptive'
        self.functions = self.svc.plan.__globals__
        self.weights = self.functions['adaptive_weights']
        self.choose = self.functions['adaptive_bonus']

    def spawn(self, ticket):
        self.svc.adaptive_roll = lambda: ticket
        return self.rig.spawn()

    def test_all_agreed_anchors_and_endpoint_clamps(self):
        expected = {
            5: (0, 200, 800, 0, 0, 0),
            15: (0, 0, 800, 200, 0, 0),
            25: (0, 0, 400, 600, 0, 0),
            35: (0, 0, 200, 700, 100, 0),
            45: (0, 0, 0, 700, 300, 0),
            55: (0, 0, 0, 450, 520, 30),
            65: (0, 0, 0, 200, 750, 50),
        }
        for player, weights in expected.items():
            self.assertEqual(self.weights(player), weights)
        for player in (1, 2, 4):
            self.assertEqual(self.weights(player), expected[5])
        for player in (66, 69, 80):
            self.assertEqual(self.weights(player), expected[65])

    def test_interpolation_keeps_sub_percent_chances_and_overlap(self):
        self.assertEqual(self.weights(10), (0, 100, 800, 100, 0, 0))
        self.assertEqual(self.weights(30), (0, 0, 300, 650, 50, 0))
        self.assertEqual(self.weights(46), (0, 0, 0, 675, 322, 3))
        self.assertEqual(self.weights(50), (0, 0, 0, 575, 410, 15))

    def test_every_ticket_at_every_level_matches_the_exact_distribution(self):
        for player in range(1, 70):
            with self.subTest(player=player):
                weights = self.weights(player)
                self.assertEqual(sum(weights), 1000)
                self.assertTrue(all(isinstance(w, int) and w >= 0 for w in weights))
                self.assertEqual(weights[0], 0)
                counts = Counter(self.choose(ticket, player) for ticket in range(1000))
                self.assertEqual(counts, {extra: w for extra, w in enumerate(weights) if w})
        for ticket in (-1, 1000):
            with self.assertRaises(ValueError):
                self.choose(ticket, 46)

    def test_progression_never_gets_easier_and_has_no_bracket_jumps(self):
        previous = self.weights(1)
        for player in range(2, 70):
            current = self.weights(player)
            for extra in range(1, 6):
                self.assertGreaterEqual(sum(current[extra:]), sum(previous[extra:]))
            increase = sum(i * (b - a) for i, (a, b) in enumerate(zip(previous, current)))
            self.assertLessEqual(increase, 40)  # At most +0.04 mean bonus per level.
            previous = current

    def test_native_spawns_use_all_1000_tickets_and_initialize_once(self):
        self.h.enable(46)
        self.rig.args.GameStage = 46
        self.svc.roll = lambda: self.fail('Adaptive must not use preset RNG')
        counts = Counter(self.spawn(ticket).level for ticket in range(1000))
        self.assertEqual(counts, {49: 675, 50: 322, 51: 3})
        self.assertEqual(len(self.rig.calls), 1000)
        self.assertIs(self.rig.factory.PawnBalanceDefinition, self.rig.definition)
        self.assertEqual(self.rig.definition.Grades[0].GradeModifiers.ExpLevel, 0)

    def test_player_level_selects_weights_but_native_area_still_sets_base(self):
        self.h.enable(10)
        self.rig.args.GameStage = 60
        self.assertEqual(self.spawn(999).level, 63)  # Player 10 has +3, never +5.
        self.assertEqual(self.rig.calls[-1][4], 63)
        self.rig.definition.DefaultExpLevel.BaseValueAttribute = Object(
            'gd_Balance.EnemyLevel.EnemyLevel_GameStage_plus9')
        self.assertEqual(self.spawn(0).level, 69)
        self.assertEqual(self.spawn(999).level, 69)

    def test_named_delayed_thresholds_override_native_levels_without_rng(self):
        self.rig.definition.path = 'gd_Balance_Enemies_Humans.Bandits.Named.Pawn_Balance_Bonehead'
        self.svc.roll = self.svc.adaptive_roll = lambda: self.fail('Named enemies must not roll')
        for player, target in ((1, 3), (20, 22), (21, 23), (22, 24), (23, 26),
                               (50, 53), (51, 54), (52, 55), (53, 57), (69, 73)):
            for native in (1, 99):
                self.rig.definition.DefaultExpLevel = aid(native)
                self.rig.definition.Grades[0].GradeModifiers.ExpLevel = native
                stage, clone = self.svc.plan(self.rig.factory, player, 80)
                self.assertEqual(stage, 80)
                self.assertEqual(clone.DefaultExpLevel.BaseValueConstant, target)
                self.assertEqual(clone.Grades[0].GradeModifiers.ExpLevel, target)
                self.assertEqual(clone.Grades[0].GradeModifiers.HealthMultiplier, 3)
                self.assertEqual(self.rig.definition.Grades[0].GradeModifiers.ExpLevel, native)

    def test_named_vehicles_use_delayed_offsets_and_ordinary_vehicles_stay_native(self):
        archetype = self.rig.definition.AIPawnArchetype
        factory = NS(VehicleBalanceDefinition=self.rig.definition, VehicleArchetype=archetype)
        self.svc.adaptive_roll = lambda: self.fail('Vehicles must not roll')
        stage, clone = self.svc.plan(factory, 53, 80, vehicle=True)
        self.assertEqual(stage, 80)
        self.assertIsNone(clone)
        archetype.path = 'gd_cheetahspaw.vehiclearchetype.mad_mel'
        for player, target in ((22, 24), (23, 26), (52, 55), (53, 57)):
            stage, clone = self.svc.plan(factory, player, 80, vehicle=True)
            self.assertEqual(stage, 80)
            self.assertEqual(clone.DefaultExpLevel.BaseValueConstant, target)
            self.assertIs(factory.VehicleBalanceDefinition, self.rig.definition)

    def test_friendly_neutral_and_player_actors_never_roll(self):
        self.svc.adaptive_roll = lambda: self.fail('Non-hostile actor rolled')
        for path in ('Native.Friendly.NPC', 'Native.Neutral', 'Native.Player', None):
            self.rig.definition.AIPawnArchetype.Allegiance = Object(path) if path else None
            stage, clone = self.svc.plan(self.rig.factory, 53, 80)
            self.assertEqual(stage, 80)
            self.assertIsNone(clone)

    def test_level_and_mode_changes_leave_existing_pawns_unchanged(self):
        self.h.enable(5)
        self.rig.args.GameStage = 5
        first = self.spawn(0)
        self.h.enable(65)
        second = self.spawn(999)
        self.h.mod.enemy_difficulty.value = 'Medium'
        third = self.rig.spawn(0)
        self.assertEqual((first.level, second.level, third.level), (6, 70, 67))
        self.h.mod.enemy_difficulty.value = 'Debug'
        self.assertEqual(self.rig.spawn().level, 35)
        self.assertEqual((first.level, second.level, third.level), (6, 70, 67))

    def test_diagnostics_report_actual_player_weights_without_rng_or_sampling(self):
        self.h.enable(46)
        self.svc.adaptive_roll = lambda: self.fail('Diagnostics must not roll')
        report = self.svc.snapshot()
        self.assertEqual(report['ordinary_tickets'],
                         {'native': 0, '+1': 0, '+2': 0, '+3': 67.5, '+4': 32.2, '+5': 0.3})
        self.assertEqual(report['named_level'], 'exactly player level + 3')
        self.assertEqual(report['adaptive']['player_level'], 46)
        self.assertEqual(len(self.rig.calls), 0)
        self.h.mod.on_disable()
        report = self.svc.snapshot()
        self.assertEqual(report['ordinary_tickets'], {})
        self.assertIsNone(report['adaptive']['player_level'])

    def test_adaptive_setting_survives_restart_without_changing_default_or_order(self):
        with tempfile.TemporaryDirectory() as folder:
            first = Harness(folder, registration_factory=SDKSettingsMod, in_menu=True)
            self.assertEqual(first.mod.enemy_difficulty.value, 'Medium')
            self.assertEqual(first.mod.enemy_difficulty.choices,
                             ['Easy', 'Medium', 'Hard', 'Very Hard', 'Debug', 'Adaptive'])
            first.mod.enemy_difficulty.value = 'Adaptive'
            first.registered_mod.save_settings()
            second = Harness(folder, registration_factory=SDKSettingsMod, in_menu=True)
            self.assertEqual(second.runtime.spawns.selected_difficulty(), 'Adaptive')


if __name__ == '__main__':
    unittest.main()
