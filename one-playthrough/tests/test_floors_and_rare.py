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
