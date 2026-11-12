"""Manual loot inspection stays available without background payload tracing."""

import json
from pathlib import Path
from types import SimpleNamespace as NS
import tempfile
import unittest

from test_one_playthrough import Harness, Object


class LootDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.h = Harness(self.tmp.name)
        self.h.enable(10)
        self.actor = Object("World.Chest")
        self.actor.Class = NS(Name="WillowInteractiveObject")
        self.actor.InteractiveObjectDefinition = Object("Native.InteractiveObj_TreasureChest")
        self.actor.bCanBeUsed = True

    def test_export_reads_chest_identity_without_invoking_actor_methods(self):
        original = self.h.sdk.find_all
        scans = []
        def find_all(name, **kw):
            if name == "WillowInteractiveObject":
                scans.append(name)
                return [self.actor]
            return original(name, **kw)
        self.h.sdk.find_all = find_all
        self.actor.UsedBy = lambda: self.fail("must not invoke a chest")
        self.h.runtime.sync(self.h.pc)
        self.assertEqual(scans, [])
        path = self.h.mod.export_diagnostics()
        report = json.loads(path.read_text())["loot_level_floor"]["diagnostics"]
        self.assertEqual(scans, ["WillowInteractiveObject"])
        self.assertEqual(report["chests"][0]["object"], self.actor.path)
        self.assertTrue(report["chests"][0]["usable"])
        self.assertEqual(report["initializer_signatures"][0]["inputs"], ["NewDefinitionData"])

    def test_manual_chest_listing_is_bounded(self):
        original = self.h.sdk.find_all
        self.h.sdk.find_all = lambda name, **kw: [self.actor]*100 if name == "WillowInteractiveObject" else original(name, **kw)
        self.assertEqual(len(self.h.runtime.loot.diagnostics.snapshot()["chests"]), 24)

    def test_manual_inspection_failure_keeps_other_diagnostics(self):
        def fail(*args, **kw):
            raise RuntimeError("unavailable objects")
        self.h.sdk.find_all = fail
        report = self.h.runtime.loot.diagnostics.snapshot()
        self.assertEqual(report["chests"], [])
        self.assertTrue(report["initializer_signatures"])
        self.assertIn("loot chest diagnostics", str(self.h.runtime.problems))

    def test_captured_failure_is_a_coverage_gap_not_evidence_of_a_successful_floor(self):
        fixture = json.loads((Path(__file__).parent / "fixtures/bl1e_loot_floor_missed.json").read_text())
        self.assertEqual(fixture["player_level"], 10)
        self.assertTrue(fixture["loot_level_floor"]["enabled"])
        self.assertEqual(fixture["loot_level_floor"]["equipment_seen"], 0)
        self.assertEqual(fixture["loot_level_floor"]["raised"], 0)
        self.assertEqual(fixture["ground_item"]["native_required_level"], 1)
        self.assertEqual(fixture["ground_item"]["fields"]["ExpLevel"], 3)
        self.assertEqual(fixture["problems"], [])


if __name__ == "__main__":
    unittest.main()
