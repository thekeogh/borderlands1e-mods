"""Native grade-data models, not Windows engine execution."""

from copy import deepcopy
from types import SimpleNamespace as NS
import tempfile
import unittest

from test_one_playthrough import Harness, Object


def grade(level, low=1, high=100):
    return NS(GameStageRequirement=NS(MinGameStage=low, MaxGameStage=high),
              GradeModifiers=NS(ExpLevel=level, CustomInventoryDefinition=Object("Native.Shield"),
                                ShieldStrength=1.4),
              MinSpawnProbabilityModifier=0.25, MaxSpawnProbabilityModifier=0.75)


def balance(path="gd_customitems.Items.Reward_Shield"):
    item = Object(path)
    item.Manufacturers = [NS(Manufacturer=Object("Native.Manufacturer"),
                            Grades=[grade(7), grade(-3), grade(0)])]
    return item


class ItemRewardsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.h = Harness(self.tmp.name)
        self.balance = balance()
        self.h.mission.ItemRewards = [None, self.balance]
        def native_level(pc):
            self.h.mission.GameStage = self.h.mission.ExpLevel = 10
        self.h.mission.RefreshRewardGameStage = native_level

    def levels(self, item=None):
        return [g.GradeModifiers.ExpLevel for m in (item or self.balance).Manufacturers for g in m.Grades]

    def accept(self, player=5):
        self.h.enable(player)
        self.h.accept()
        self.assertEqual(self.h.mission.ExpLevel, 10)

    def test_low_and_high_character_both_receive_accepted_mission_level(self):
        self.accept()
        for player in (5, 20, 69):
            self.h.pc.level = player
            self.h.runtime.sync(self.h.pc)
            generated = []
            def native_generate():
                # Positive inventory grade ExpLevel is an explicit level;
                # fixed low values and negative offsets must not survive.
                for manufacturer in self.balance.Manufacturers:
                    for g in manufacturer.Grades:
                        generated.append(NS(level=g.GradeModifiers.ExpLevel,
                                            saved_balance=self.balance._path_name()))
            self.h.reward(native=native_generate)
            self.assertEqual([item.level for item in generated], [10, 10, 10])
            self.assertTrue(all(item.saved_balance == self.balance._path_name() for item in generated))
            self.assertEqual(self.levels(), [7, -3, 0])
            self.assertEqual(self.h.mission.ExpLevel, 10)
            self.assertEqual(self.h.runtime.missions.scopes, [])

    def test_no_parts_probabilities_or_reward_identity_change(self):
        self.accept()
        before = deepcopy(vars(self.balance.Manufacturers[0].Grades[0].GradeModifiers))
        rewards = self.h.mission.ItemRewards[:]
        def native_generate():
            g = self.balance.Manufacturers[0].Grades[0]
            self.assertEqual(g.GradeModifiers.ExpLevel, 10)
            self.assertEqual(g.GradeModifiers.ShieldStrength, before["ShieldStrength"])
            self.assertEqual((g.MinSpawnProbabilityModifier, g.MaxSpawnProbabilityModifier), (0.25, 0.75))
            self.assertEqual(self.h.mission.ItemRewards, rewards)
        self.h.reward(native=native_generate)
        self.assertEqual(self.balance.ObjectFlags, 0)
        self.assertIs(self.h.mission.ItemRewards[1], self.balance)
        self.assertEqual(self.levels(), [7, -3, 0])

    def test_all_reward_generation_and_preview_scopes_apply_same_level(self):
        self.accept()
        for name in ("GetItemRewardForPlayer", "GenerateRewardString"):
            self.h.reward(name, lambda: self.assertEqual(self.levels(), [10] * 3))
        path = "WillowGame.WillowPlayerController:GrantMissionRewards"
        args = NS(InMission=self.h.mission)
        self.h.callbacks[(path, "PRE")](self.h.pc, args, None, None)
        self.assertEqual(self.levels(), [10] * 3)
        self.h.callbacks[(path, "POST_UNCONDITIONAL")](self.h.pc, args, None, None)
        self.assertEqual(self.levels(), [7, -3, 0])

    def test_preview_follows_offer_but_acceptance_locks_it(self):
        self.h.enable(5)
        self.h.reward(native=lambda: self.assertEqual(self.levels(), [10] * 3))
        self.h.pc.level = 20
        self.h.runtime.sync(self.h.pc)
        self.h.reward(native=lambda: self.assertEqual(self.levels(), [20] * 3))
        self.h.accept()
        self.h.pc.level = 30
        self.h.runtime.sync(self.h.pc)
        self.h.reward(native=lambda: self.assertEqual(self.levels(), [20] * 3))
        self.assertEqual(self.levels(), [7, -3, 0])

    def test_nested_missions_sharing_reward_restore_outer_then_original(self):
        self.accept()
        other = Object("Native.OtherMission")
        other.GameStageRegion = self.h.mission.GameStageRegion
        other.GameStage, other.ExpLevel, other.MinimumLevel = 20, 20, 0
        other.ItemRewards = [self.balance]
        self.h.pc.MissionPlaythroughData[0].MissionList.append(NS(MissionDef=other, Status=1))
        self.h.runtime.missions.remember(other._path_name().lower(), 20)
        outer = self.h.runtime.missions.enter_reward(self.h.mission, self.h.pc)
        self.assertEqual(self.levels(), [10] * 3)
        inner = self.h.runtime.missions.enter_reward(other, self.h.pc)
        self.assertEqual(self.levels(), [20] * 3)
        self.h.runtime.missions.exit_reward(inner)
        self.assertEqual(self.levels(), [10] * 3)
        self.h.runtime.missions.exit_reward(outer)
        self.assertEqual(self.levels(), [7, -3, 0])

    def test_exception_and_disabling_restore_active_reward_edits(self):
        self.accept()
        def failure():
            self.assertEqual(self.levels(), [10] * 3)
            raise RuntimeError("native reward failed")
        with self.assertRaises(RuntimeError): self.h.reward(native=failure)
        self.assertEqual(self.levels(), [7, -3, 0])
        token = self.h.runtime.missions.enter_reward(self.h.mission, self.h.pc)
        self.h.mod.on_disable()
        self.h.runtime.missions.exit_reward(token)
        self.assertEqual(self.levels(), [7, -3, 0])
        self.assertEqual(self.h.runtime.missions.scopes, [])
        self.assertEqual(self.balance.ObjectFlags, 0)

    def test_regionless_rewards_and_class_specific_rewards_are_covered(self):
        self.accept()
        self.h.mission.GameStageRegion = None
        other = balance("gd_customitems.Items.Reward_OtherClass")
        self.h.mission.ItemRewards = [self.balance, None, other]
        token = self.h.runtime.missions.enter_reward(self.h.mission, self.h.pc)
        self.assertEqual(self.levels(), [10] * 3)
        self.assertEqual(self.levels(other), [10] * 3)
        self.h.runtime.missions.exit_reward(token)
        self.assertEqual(self.levels(), [7, -3, 0])
        self.assertEqual(self.levels(other), [7, -3, 0])

    def test_sdu_levels_and_unrelated_loot_definitions_are_preserved(self):
        self.accept()
        sdu = balance("gd_itemgrades.StorageDeckUpgrades.ItemGrade_SDU_InventorySlots")
        untouched = balance("Native.Unrelated.ShieldStock")
        self.h.mission.ItemRewards.append(sdu)
        self.h.reward(native=lambda: (self.assertEqual(self.levels(sdu), [7, -3, 0]),
                                     self.assertEqual(self.levels(untouched), [7, -3, 0])))

    def test_partial_preparation_failure_rolls_back_previous_balances(self):
        self.accept()
        bad = balance("Native.BadReward")
        del bad.Manufacturers[0].Grades[0].GradeModifiers.ExpLevel
        self.h.mission.ItemRewards.append(bad)
        with self.assertRaises(AttributeError):
            self.h.runtime.missions.enter_reward(self.h.mission, self.h.pc)
        self.assertEqual(self.levels(), [7, -3, 0])
        self.assertEqual(self.balance.ObjectFlags, 0)
        self.assertEqual(self.h.runtime.missions.scopes, [])

    def test_high_level_dlc_reward_extends_last_band_only(self):
        self.accept()
        self.balance.path = "dlc3_gd_customitems.Rewards.Shield"
        self.balance.Manufacturers[0].Grades = [grade(3, 1, 5), grade(7, 6, 8)]
        token = self.h.runtime.missions.enter_reward(self.h.mission, self.h.pc)
        gs = self.balance.Manufacturers[0].Grades
        self.assertEqual([(g.GameStageRequirement.MinGameStage, g.GameStageRequirement.MaxGameStage) for g in gs],
                         [(1, 5), (6, 10)])
        self.assertEqual(self.levels(), [10, 10])
        self.h.runtime.missions.exit_reward(token)
        self.assertEqual([(g.GameStageRequirement.MinGameStage, g.GameStageRequirement.MaxGameStage) for g in gs],
                         [(1, 5), (6, 8)])

    def test_extend_only_outer_grade_bands_and_restore_them(self):
        self.accept()
        self.balance.Manufacturers[0].Grades = [grade(1, 15, 20), grade(2, 21, 30)]
        token = self.h.runtime.missions.enter_reward(self.h.mission, self.h.pc)
        gs = self.balance.Manufacturers[0].Grades
        self.assertEqual([(g.GameStageRequirement.MinGameStage, g.GameStageRequirement.MaxGameStage) for g in gs],
                         [(10, 20), (21, 30)])
        self.h.runtime.missions.exit_reward(token)
        self.assertEqual([(g.GameStageRequirement.MinGameStage, g.GameStageRequirement.MaxGameStage) for g in gs],
                         [(15, 20), (21, 30)])


if __name__ == "__main__": unittest.main()
