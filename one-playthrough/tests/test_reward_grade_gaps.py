"""Captured missing-reward regressions; grade selection is a native-data model."""

import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest

from test_one_playthrough import Harness, Object, aid
from test_item_rewards import balance, grade

FIXTURE = json.loads((Path(__file__).parent / 'fixtures/bl1e_reward_grade_gaps.json').read_text())


def bands(item):
    return [(g.GameStageRequirement.MinGameStage, g.GameStageRequirement.MaxGameStage)
            for g in item.Manufacturers[0].Grades]


def eligible(item, stage):
    return [i for i, (low, high) in enumerate(bands(item)) if low <= stage <= high]


def captured_balance(case):
    data = case['reward']
    item = balance(data['balance'])
    definition = Object(data['inventory_definition'])
    definition.bUsesPlayerLevelRequirement = True
    # The F10 reports resolve target internal level two above mission level.
    # Model that observed offset; do not claim resolver metadata was captured here.
    definition.PlayerUseLevelBonus = aid(data['target_internal_level'] - data['mission_level'])
    item.InventoryDefinition = definition
    item.Manufacturers[0].Grades = []
    for row in data['manufacturer_grades']:
        g = grade(row['native_internal_level'], row['min_stage'], row['max_stage'])
        g.GradeModifiers.CustomInventoryDefinition = None
        item.Manufacturers[0].Grades.append(g)
    return item


class RewardGradeGapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.h = Harness(self.tmp.name)

    def accept_case(self, case, item):
        self.h.mission.path = case['mission']
        self.h.mission.ItemRewards = [item]
        self.h.enable(case['stage'])
        self.h.accept()

    def test_captured_spy_and_sentinel_gaps_select_one_existing_grade_and_restore(self):
        for case in FIXTURE['cases']:
            with self.subTest(mission=case['mission']):
                item = captured_balance(case)
                before = bands(item)
                levels = [g.GradeModifiers.ExpLevel for g in item.Manufacturers[0].Grades]
                self.assertEqual(eligible(item, case['stage']), [])
                self.accept_case(case, item)
                # A later turn-in must still use the accepted level.
                self.h.pc.level = 40
                self.h.runtime.sync(self.h.pc)
                for method in ('GenerateRewardString', 'GetItemRewardForPlayer'):
                    def native_select():
                        self.assertEqual(self.h.mission.GameStage, case['stage'])
                        self.assertEqual(eligible(item, case['stage']), [2])
                        expected = list(before)
                        expected[2] = (before[2][0], case['stage'])
                        self.assertEqual(bands(item), expected)
                        self.assertIs(self.h.mission.ItemRewards[0], item)
                        for g in item.Manufacturers[0].Grades:
                            self.assertEqual(g.GradeModifiers.ExpLevel, case['reward']['target_internal_level'])
                            self.assertEqual((g.MinSpawnProbabilityModifier, g.MaxSpawnProbabilityModifier), (0.25, 0.75))
                    self.h.reward(method, native_select)
                    self.assertEqual(bands(item), before)
                    self.assertEqual([g.GradeModifiers.ExpLevel for g in item.Manufacturers[0].Grades], levels)
                    self.assertEqual(self.h.runtime.missions.scopes, [])
                    self.assertEqual(item.ObjectFlags, 0)

    def test_all_supported_levels_cover_gaps_without_altering_already_eligible_bands(self):
        for case in FIXTURE['cases']:
            item = captured_balance(case)
            self.accept_case(case, item)
            before = bands(item)
            for level in range(1, 70):
                with self.subTest(mission=case['mission'], level=level):
                    self.h.runtime.missions.remember(case['mission'].lower(), level, replace=True)
                    token = self.h.runtime.missions.enter_reward(self.h.mission, self.h.pc)
                    try:
                        native_matches = [i for i, (low, high) in enumerate(before) if low <= level <= high]
                        if native_matches:
                            self.assertEqual(bands(item), before)
                            self.assertEqual(eligible(item, level), native_matches)
                        else:
                            previous = [i for i, (_, high) in enumerate(before) if high < level]
                            chosen = max(previous, key=lambda i: before[i][1]) if previous else 0
                            self.assertEqual(eligible(item, level), [chosen])
                            expected = list(before)
                            low, high = before[chosen]
                            expected[chosen] = (min(low, level), max(high, level))
                            self.assertEqual(bands(item), expected)
                    finally:
                        self.h.runtime.missions.exit_reward(token)
                    self.assertEqual(bands(item), before)

    def test_inherited_reward_changes_only_the_child_and_restores_after_failure(self):
        case = FIXTURE['cases'][0]
        parent = captured_balance(case)
        before = bands(parent)
        child = balance('Native.Reward.InheritedGap')
        child.Manufacturers = []
        child.BaseDefinition = parent
        self.accept_case(case, child)
        def native_failure():
            self.assertEqual(eligible(child, case['stage']), [2])
            self.assertEqual(bands(parent), before)
            self.assertIsNot(child.Manufacturers, parent.Manufacturers)
            raise RuntimeError('modeled generation failure')
        with self.assertRaisesRegex(RuntimeError, 'modeled generation failure'):
            self.h.reward(native=native_failure)
        self.assertEqual(child.Manufacturers, [])
        self.assertEqual(bands(parent), before)
        self.assertEqual(child.ObjectFlags, 0)
        self.assertEqual(self.h.runtime.missions.scopes, [])

    def test_nested_gap_levels_restore_outer_then_original_ranges(self):
        case = FIXTURE['cases'][0]
        item = captured_balance(case)
        self.accept_case(case, item)
        before = bands(item)
        outer = self.h.runtime.missions.enter_reward(self.h.mission, self.h.pc)
        outer_bands = bands(item)
        other = Object('Native.OtherGapMission')
        other.GameStageRegion = self.h.mission.GameStageRegion
        other.GameStage, other.ExpLevel, other.MinimumLevel = 32, 32, 0
        other.ItemRewards = [item]
        self.h.pc.MissionPlaythroughData[0].MissionList.append(NS(MissionDef=other, Status=1))
        self.h.runtime.missions.remember(other.path.lower(), 32)
        inner = self.h.runtime.missions.enter_reward(other, self.h.pc)
        self.assertEqual(eligible(item, 32), [2])
        self.h.runtime.missions.exit_reward(inner)
        self.assertEqual(bands(item), outer_bands)
        self.assertEqual(eligible(item, case['stage']), [2])
        self.h.runtime.missions.exit_reward(outer)
        self.assertEqual(bands(item), before)


if __name__ == '__main__':
    unittest.main()
