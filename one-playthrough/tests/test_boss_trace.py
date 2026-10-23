"""Read-only Bone Head diagnostic models; no native death/drop execution."""

from copy import deepcopy
import json
from types import SimpleNamespace as NS
import tempfile
import unittest

from test_one_playthrough import Harness, Object, aid
from test_item_rewards import balance, grade

DEATH = "WillowGame.WillowPawn:Died"
DROP = "WillowGame.WillowWeapon:DropFrom"


class BossTraceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.h = Harness(self.tmp.name)
        self.h.enable(12)
        self.trace = self.h.runtime.loot.native.boss_trace
        self.boss = Object("World.BoneHead")
        self.boss.Class = NS(Name="WillowAIPawn", _inherits=lambda cls: cls.Name == "WillowAIPawn")
        self.boss.BalanceDefinitionState = NS(BalanceDefinition=Object(
            "gd_Balance_Enemies_Humans.Bandits.Named.Pawn_Balance_BoneHead"))
        self.boss.Allegiance = Object("gd_AI_Allegiance.HumanEnemy.Bandit")
        self.boss.GetHealth = lambda: self.fail("diagnostics must not call an actor method")
        self.boss.GetExpLevel = lambda: self.fail("diagnostics must not call an actor method")
        self.manager = Object("World.BoneHead.InvManager")
        self.manager.Owner = self.boss
        self.boss.InvManager = self.manager
        self.weapon = Object("World.BoneShredder")
        self.weapon.Owner = self.boss
        self.weapon.ExpLevel = 5
        self.weapon.Inventory = None
        self.weapon.BalanceDefinitionState = None
        self.balance = balance("gd_customweapons.Weapons.CustomWeap_SMG_BoneShredder")
        self.balance.Manufacturers[0].Grades = [grade(5)]
        self.definition = Object("gd_weap_patrol_smg.A_Weapon.WeaponType_patrol_smg")
        self.definition.bUsesPlayerLevelRequirement = True
        self.definition.PlayerUseLevelBonus = aid(2)
        self.balance.InventoryDefinition = self.definition
        self.weapon.DefinitionData = NS(BalanceDefinition=self.balance,
            WeaponTypeDefinition=self.definition, ManufacturerGradeIndex=0,
            ManufacturerDefinition=self.balance.Manufacturers[0].Manufacturer,
            MagazinePartDefinition=Object("gd_weap_patrol_smg.UniqueParts.BoneShredder_mag5"))
        self.boss.Weapon = self.weapon
        self.manager.InventoryChain = self.weapon
        self.h.inventory.append(self.weapon)
        self.drop_args = NS(StartLocation=NS(X=10, Y=20, Z=30),
                            StartVelocity=NS(X=1, Y=2, Z=3), bForceNoRBPhysics=False)
        self.args = NS(InBalanceDef=self.balance,
            InManufacturer=self.weapon.DefinitionData.ManufacturerDefinition,
            InGradeIndex=0, InAdditionalQueryInterfaceSource=self.boss)

    def test_live_carried_initialization_is_logged_without_changing_floor_decision(self):
        data = vars(self.weapon.DefinitionData).copy()
        args = vars(self.args).copy()
        self.assertIsNone(self.h.runtime.loot.native.plan(self.weapon, self.args, self.h.pc))
        record = self.trace.decisions[-1]
        self.assertEqual(record["decision"], "live/neutral enemy")
        self.assertEqual(record["query_balance"], self.boss.BalanceDefinitionState.BalanceDefinition.path)
        self.assertEqual(record["item"]["internal_level"], 5)
        self.assertEqual(record["item"]["owner_chain"][0]["path"], self.boss.path)
        self.assertEqual(vars(self.weapon.DefinitionData), data)
        self.assertEqual(vars(self.args), args)
        self.assertEqual(self.weapon.ExpLevel, 5)
        self.assertEqual(self.h.runtime.loot.raised, 0)

    def test_death_and_drop_callbacks_capture_ownership_transition_without_replaying(self):
        data = vars(self.weapon.DefinitionData).copy()
        forbidden = lambda **kw: self.fail("trace must not call native gameplay")
        self.h.callbacks[(DEATH, "PRE")](self.boss, NS(), None, forbidden)
        self.assertIsNone(self.h.callbacks[(DROP, "PRE")](self.weapon, self.drop_args, None, forbidden))
        self.weapon.Owner = None  # Model the game's own drop, not diagnostic behavior.
        self.boss.Weapon = None
        self.assertIsNone(self.h.callbacks[(DROP, "POST_UNCONDITIONAL")](self.weapon, self.drop_args, None, forbidden))
        self.h.callbacks[(DEATH, "POST_UNCONDITIONAL")](self.boss, NS(), None, forbidden)
        self.assertEqual([r["phase"] for r in self.trace.deaths], ["before", "after"])
        self.assertEqual(self.trace.deaths[0]["bone_shredders"][0]["owner_chain"][0]["path"], self.boss.path)
        self.assertEqual(self.trace.deaths[1]["bone_shredders"][0]["owner_chain"], [])
        self.assertEqual([r["phase"] for r in self.trace.drops], ["before", "after"])
        self.assertEqual(self.trace.drops[0]["item"]["object"], self.trace.drops[1]["item"]["object"])
        self.assertEqual(vars(self.weapon.DefinitionData), data)
        self.assertEqual(self.weapon.ExpLevel, 5)
        self.assertEqual(self.h.runtime.loot.deaths, [])

    def test_inventory_manager_owner_chain_and_cycles_are_safe(self):
        self.weapon.Owner = self.manager
        self.weapon.Inventory = self.weapon
        self.trace.death(self.boss, "before")
        items = self.trace.deaths[0]["bone_shredders"]
        self.assertEqual(len(items), 1)
        self.assertEqual([r["path"] for r in items[0]["owner_chain"]], [self.manager.path, self.boss.path])
        self.manager.Owner = self.manager
        self.trace.drop(self.weapon, "before")
        self.assertEqual(len(self.trace.drops[0]["item"]["owner_chain"]), 1)

    def test_after_death_still_identifies_actor_if_balance_state_was_cleared(self):
        self.trace.death(self.boss, "before")
        self.boss.BalanceDefinitionState = None
        self.trace.death(self.boss, "after")
        self.assertEqual([r["phase"] for r in self.trace.deaths], ["before", "after"])

    def test_unrelated_enemies_do_not_trigger_inventory_scan_or_drop_records(self):
        self.boss.BalanceDefinitionState.BalanceDefinition = Object("Native.OrdinaryBandit")
        self.h.sdk.find_all = lambda *a, **kw: self.fail("must not scan normal enemy deaths")
        self.trace.death(self.boss, "before")
        self.weapon.DefinitionData.BalanceDefinition = balance("Native.RegularWeapon")
        self.trace.drop(self.weapon, "before")
        self.trace.native(self.weapon, NS(**{**vars(self.args), "InBalanceDef": balance("Native.RegularWeapon")}), "skip")
        self.assertEqual(self.trace.snapshot()["deaths"], {})
        self.assertEqual(self.trace.snapshot()["drops"], {})
        self.assertEqual(self.trace.snapshot()["native_decisions"], {})

    def test_trace_disabled_with_mod_or_loot_option(self):
        for enabled in (False, True):
            self.h.mod.loot_floor.value = enabled
            if enabled: self.h.mod.on_disable()
            self.trace.death(self.boss, "before")
            self.trace.drop(self.weapon, "before")
            self.trace.native(self.weapon, self.args, "skip")
        self.assertEqual(self.trace.decisions, [])
        self.assertEqual(self.trace.deaths, [])
        self.assertEqual(self.trace.drops, [])

    def test_snapshots_are_bounded_json_only_and_do_not_add_automatic_logs(self):
        messages = self.h.messages.copy()
        for _ in range(40):
            self.trace.native(self.weapon, self.args, "live/neutral enemy")
            self.trace.drop(self.weapon, "before")
            self.trace.death(self.boss, "before")
        snap = self.trace.snapshot()
        self.assertEqual(len(snap["native_decisions"]), 24)
        self.assertEqual(len(snap["drops"]), 16)
        self.assertEqual(len(snap["deaths"]), 8)
        json.dumps(snap)
        self.assertEqual(self.h.messages, messages)

    def test_read_failure_does_not_interrupt_death_scope_cleanup(self):
        def fail(*a, **kw): raise RuntimeError("unavailable trace inventory")
        self.h.sdk.find_all = fail
        self.h.callbacks[(DEATH, "PRE")](self.boss, NS(), None, None)
        self.assertTrue(self.h.runtime.loot.deaths)
        self.h.callbacks[(DEATH, "POST_UNCONDITIONAL")](self.boss, NS(), None, None)
        self.assertEqual(self.h.runtime.loot.deaths, [])
        self.assertIn("unavailable trace inventory", str(self.h.runtime.problems))

    def test_f10_contains_target_decisions_and_death_snapshot(self):
        self.h.runtime.loot.native.plan(self.weapon, self.args, self.h.pc)
        self.trace.death(self.boss, "before")
        report = json.loads(self.h.mod.export_diagnostics().read_text())
        trace = report["loot_level_floor"]["native_initializer"]["boss_trace"]
        self.assertEqual(trace["native_decisions"]["0"]["grade"], 0)
        self.assertEqual(trace["deaths"]["0"]["bone_shredders"]["0"]["internal_level"], 5)
        item = trace["deaths"]["0"]["bone_shredders"]["0"]
        self.assertEqual(item["owner_chain"]["0"]["path"], self.boss.path)
        self.assertEqual(item["definition_data"]["MagazinePartDefinition"],
                         "gd_weap_patrol_smg.UniqueParts.BoneShredder_mag5")
        self.assertNotIn("depth limit", json.dumps(trace))
        self.assertEqual(self.h.runtime.loot.raised, 0)


if __name__ == "__main__": unittest.main()
