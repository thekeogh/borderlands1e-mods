"""Mission/journal/payout lifecycle models; Windows verification still required."""

from types import SimpleNamespace as NS
import tempfile
import unittest
from unittest.mock import patch

from test_one_playthrough import Harness, Object
from test_item_rewards import balance


class MissionFollowingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.h = Harness(self.tmp.name)
        self.item = balance()
        self.h.mission.ItemRewards = [self.item]
        self.h.enable(30)
        self.h.accept()

    def grant(self, native):
        path = 'WillowGame.WillowPlayerController:GrantMissionRewards'
        args = NS(InMission=self.h.mission)
        self.h.callbacks[(path, 'PRE')](self.h.pc, args, None, None)
        try:
            return native()
        finally:
            self.h.callbacks[(path, 'POST_UNCONDITIONAL')](self.h.pc, args, None, None)

    def assert_level(self, expected):
        self.assertEqual((self.h.mission.GameStage, self.h.mission.ExpLevel), (expected, expected))

    def test_all_unpaid_statuses_follow_level_and_journal_preview(self):
        for status in (1, 2, 3):
            with self.subTest(status=status):
                self.h.pc.level = 30
                self.h.state(status)
                for level in (35, 40):
                    self.h.pc.level = level
                    self.h.mod.player_ready(self.h.pc, NS(), None, None)
                    self.assert_level(level)
                    for method, argument in (('GetMissionDescriptionForUI', NS(MissionDef=self.h.mission)),
                                             ('PopulateMissionDataFromStatus', NS(MStatus=NS(MissionDef=self.h.mission)))):
                        path = 'WillowGame.WillowPlayerController:' + method
                        self.h.callbacks[(path, 'PRE')](self.h.pc, argument, None, None)
                        self.assert_level(level)
                        self.h.callbacks[(path, 'POST_UNCONDITIONAL')](self.h.pc, argument, None, None)
                    self.assertEqual([r.Status for r in self.h.pc.MissionPlaythroughData[0].MissionList], [status])
                    self.assertEqual(self.h.pc.MissionPlaythroughData[0].MissionList[0].Objectives, [4, 7])

    def test_complete_early_or_late_then_turn_in_at_forty(self):
        for completion_level in (30, 40):
            with self.subTest(completion_level=completion_level):
                self.h.pc.level = completion_level
                self.h.state(2)
                self.h.runtime.sync(self.h.pc)
                self.h.pc.level = 40
                self.h.runtime.sync(self.h.pc)
                def native():
                    for method in ('GetExperienceReward', 'GetCreditReward', 'GetItemRewardForPlayer'):
                        self.assertEqual(self.h.reward(method), 40)
                self.grant(native)
                self.assert_level(40)

    def test_xp_level_up_and_paid_status_do_not_change_remaining_payout(self):
        self.h.state(3)
        self.h.pc.level = 40
        original_grades = [g.GradeModifiers.ExpLevel for g in self.item.Manufacturers[0].Grades]
        rewards = []
        def native():
            rewards.append(self.h.reward('GetExperienceReward'))
            self.h.pc.level = 41
            self.h.mod.player_ready(self.h.pc, NS(), None, None)
            self.assert_level(40)
            self.h.state(4)
            self.h.mod.player_ready(self.h.pc, NS(), None, None)
            rewards.append(self.h.reward('GetCreditReward'))
            def equipment():
                rewards.append(self.h.mission.GameStage)
                self.assertEqual([g.GradeModifiers.ExpLevel for g in self.item.Manufacturers[0].Grades], [40] * 3)
            self.h.reward('GetItemRewardForPlayer', equipment)
            self.assertEqual(self.h.row().DefaultGameStage.BaseValueConstant, 40)
        self.grant(native)
        self.assertEqual(rewards, [40, 40, 40])
        self.assert_level(40)
        self.assertEqual(self.h.row().DefaultGameStage.BaseValueConstant, 41)
        self.assertEqual([g.GradeModifiers.ExpLevel for g in self.item.Manufacturers[0].Grades], original_grades)
        self.assertEqual(self.h.runtime.missions.scopes, [])
        self.assertEqual(self.h.runtime.missions.scope_missions, {})
        self.h.pc.level = 50
        self.h.runtime.sync(self.h.pc)
        self.assert_level(40)
        reloaded = Harness(self.tmp.name)
        reloaded.state(4)
        reloaded.enable(50)
        self.assertEqual(reloaded.mission.ExpLevel, 40)

    def test_higher_native_mission_stays_higher_until_player_catches_up(self):
        def native_floor(_pc):
            self.h.mission.GameStage = self.h.mission.ExpLevel = 45
        self.h.mission.RefreshRewardGameStage = native_floor
        self.h.runtime.missions.floors.clear()
        for player in (30, 35, 40, 50):
            self.h.pc.level = player
            self.h.runtime.sync(self.h.pc)
            self.assert_level(max(45, player))
            self.assertEqual(self.h.reward(), max(45, player))

    def test_failed_payout_clears_freeze_and_active_mission_tracks_latest_level(self):
        self.h.pc.level = 40
        def failure():
            self.h.pc.level = 41
            self.h.runtime.sync(self.h.pc)
            self.assertEqual(self.h.reward('GetCreditReward'), 40)
            raise RuntimeError('modeled payout failure')
        with self.assertRaisesRegex(RuntimeError, 'modeled payout failure'):
            self.grant(failure)
        self.assert_level(41)
        self.assertEqual(self.h.runtime.missions.scope_missions, {})
        self.assertEqual(self.h.runtime.missions.scopes, [])
        self.assertEqual(self.h.row().DefaultGameStage.BaseValueConstant, 41)

    def test_frozen_mission_does_not_freeze_other_missions_in_same_region(self):
        other = Object('Native.IndependentMission')
        other.GameStageRegion = self.h.mission.GameStageRegion
        other.GameStage = other.ExpLevel = other.MinimumLevel = 0
        other.ItemRewards = []
        other.RefreshRewardGameStage = lambda pc: None
        self.h.missions.append(other)
        self.h.pc.MissionPlaythroughData[0].MissionList.append(NS(MissionDef=other, Status=1))
        def native():
            self.h.pc.level = 31
            self.h.runtime.sync(self.h.pc)
            self.assert_level(30)
            self.assertEqual(other.ExpLevel, 31)
            token = self.h.runtime.missions.enter_reward(other, self.h.pc)
            self.assertEqual(self.h.row().DefaultGameStage.BaseValueConstant, 31)
            self.h.runtime.missions.exit_reward(token)
            self.assertEqual(self.h.row().DefaultGameStage.BaseValueConstant, 30)
        self.grant(native)
        self.assert_level(31)

    def test_unchanged_refresh_does_not_rewrite_sidecar(self):
        with patch.object(self.h.runtime.store, 'save', wraps=self.h.runtime.store.save) as save:
            self.h.runtime.sync(self.h.pc)
            self.h.runtime.sync(self.h.pc)
            self.assertEqual(save.call_count, 0)
            self.h.pc.level = 31
            self.h.runtime.sync(self.h.pc)
            self.assertEqual(save.call_count, 1)
