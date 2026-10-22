"""Read-only diagnostic probes: these do not claim to fix missed native paths."""

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace as NS
import tempfile
import unittest

from test_one_playthrough import Harness, Object, aid
from test_item_rewards import balance


class LootTraceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.h = Harness(self.tmp.name)
        self.h.enable(10)
        self.trace = self.h.runtime.loot.trace
        self.actor = Object("World.Chest")
        self.actor.Class = NS(Name="WillowInteractiveObject")
        self.actor.InteractiveObjectDefinition = Object("Native.InteractiveObj_TreasureChest")
        self.actor.bCanBeUsed = True

    def function(self, owner, name, inputs):
        return NS(Name=name, Outer=owner, Class=NS(Name="Function"),
                  _properties=lambda: [NS(Name=key, PropertyFlags=0x80) for key in inputs])

    def test_discovery_uses_loaded_metadata_excludes_existing_and_generic_actor_hooks(self):
        chest = Object("WillowGame.WillowInteractiveObject")
        chest.Name = "WillowInteractiveObject"
        engine = Object("Engine.Actor")
        engine.Name = "Actor"
        chest._fields = lambda: [self.function(chest, "UsedBy", ("User",)),
                                self.function(chest, "Tick", ("DeltaTime",)),
                                self.function(engine, "Spawn", ("SpawnClass",))]
        behavior = Object("WillowGame.Behavior_SpawnLoot")
        behavior.Name = "Behavior_SpawnLoot"
        behavior._fields = lambda: [self.function(behavior, "ApplyBehaviorToContext", ("Context",))]
        original = self.h.sdk.find_all
        self.h.sdk.find_all = lambda name, **kw: [chest, behavior] if name == "Class" else original(name, **kw)
        specs = self.h.mod.loot_trace_specs(self.h.sdk, set())
        self.assertEqual(specs, [("WillowGame.Behavior_SpawnLoot:ApplyBehaviorToContext", ("Context",)),
                                 ("WillowGame.WillowInteractiveObject:UsedBy", ("User",))])
        self.assertEqual(self.h.mod.loot_trace_specs(self.h.sdk, {specs[0][0]}), [specs[1]])

    def test_trace_never_blocks_recalls_or_changes_native_arguments(self):
        callback = self.h.mod.loot_trace_hook("Test:UsedBy", ("User",))
        args = NS(User=Object("World.Player"))
        before = vars(args).copy()
        called = []
        result = callback(self.actor, args, None, lambda: called.append(True))
        self.assertIsNone(result)
        self.assertEqual(called, [])
        self.assertEqual(vars(args), before)
        event = self.trace.snapshot()["events"][0]
        self.assertEqual(event["interactive_definition"], "Native.InteractiveObj_TreasureChest")
        self.assertEqual(event["arguments"], {"User": "World.Player"})

    def test_distinct_chest_definitions_are_not_lost_behind_first_usedby_event(self):
        for name in ("Native.NewU", "Native.InteractiveObj_TreasureChest", "Native.InteractiveObj_Crate_Metal"):
            self.actor.InteractiveObjectDefinition = Object(name)
            self.trace.event("Test:UsedBy", self.actor, NS(), ())
        self.assertEqual(len(self.trace.events), 3)
        self.trace.event("Test:UsedBy", self.actor, NS(), ())
        self.assertEqual(sum(e["count"] for e in self.trace.events.values()), 4)

    def test_samples_bounded_and_disabled_tracing_noop(self):
        for i in range(100):
            self.trace.event("Test:" + str(i), self.actor, NS(), ())
        self.assertEqual(len(self.trace.events), 64)
        self.h.mod.loot_floor.value = False
        self.trace.event("Disabled:Event", self.actor, NS(), ())
        self.assertEqual(len(self.trace.events), 64)

    def test_failed_trace_isolated_from_gameplay(self):
        callback = self.h.mod.loot_trace_hook("Test:UsedBy", ("Missing",))
        self.assertIsNone(callback(self.actor, NS(), None, None))
        self.assertIn("loot trace", str(self.h.runtime.problems))
        self.assertEqual(self.h.runtime.loot.scopes, [])

    def test_unscoped_equipment_initialization_is_visible_without_mutation(self):
        definition = Object("Native.Weapon")
        definition.bUsesPlayerLevelRequirement = True
        definition.PlayerUseLevelBonus = aid(2)
        data = NS(BalanceDefinition=balance("Native.Shotgun"), WeaponTypeDefinition=definition,
                  ManufacturerGradeIndex=0)
        original = vars(data).copy()
        callback = self.h.callbacks[("WillowGame.WillowWeapon:InitializeFromDefinitionData", "PRE")]
        self.assertIsNone(callback(self.actor, NS(NewDefinitionData=data), None, None))
        self.assertEqual(vars(data), original)
        report = self.trace.snapshot()
        self.assertEqual(report["initializer_calls"], 1)
        self.assertEqual(report["equipment_initializers"], 1)
        self.assertEqual(report["scoped_initializer_calls"], 0)
        self.assertIsNone(report["equipment_samples"][0]["loot_scope"])
        self.assertEqual(self.h.runtime.loot.raised, 0)

    def test_export_reads_chest_identity_without_invoking_actor_methods(self):
        original = self.h.sdk.find_all
        self.h.sdk.find_all = lambda name, **kw: [self.actor] if name == "WillowInteractiveObject" else original(name, **kw)
        self.actor.UsedBy = lambda: self.fail("must not invoke a chest")
        report = json.loads(self.h.mod.export_diagnostics().read_text())
        trace = report["loot_level_floor"]["trace"]
        self.assertEqual(trace["chests"][0]["object"], self.actor.path)
        self.assertTrue(trace["chests"][0]["usable"])
        self.assertEqual(trace["initializer_signatures"][0]["inputs"], ["NewDefinitionData"])

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
