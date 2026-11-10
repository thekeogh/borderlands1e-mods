import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from support import FIXTURE, Object, Struct, load_mod


class HookAndExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.stack, self.sdk, self.mods, self.mod, self.pc, self.messages = load_mod(self.temp.name)
        self.addCleanup(self.stack.close)
        self.item = self.sdk.item()
        self.mod.on_enable()

    def test_only_export_button_no_keybind_or_gameplay_options(self):
        registration = self.mods.registration
        self.assertEqual(registration["keybinds"], [])
        self.assertEqual([o.name for o in registration["options"]], ["Export diagnostics"])
        self.assertIs(registration["options"][0].on_press, self.mod.export_diagnostics)

    def test_vendor_query_refreshes_cache_and_leaves_native_quantity_and_return(self):
        self.item.CashValue = 999999
        args = Struct(InventoryForSale=self.item, Quantity=3)
        before = vars(args).copy()
        path = "WillowGame.WillowVendingMachine:GetSellingPriceForInventory"
        result = self.sdk.dispatch(path, Object("Map.Vendor"), args, lambda: self.item.CashValue * 7 * args.Quantity)
        self.assertEqual(result, 924)
        self.assertEqual(vars(args), before)
        self.assertEqual(self.mod.audit.recent[-1]["return_value"], 924)
        self.assertEqual(self.item.ExpLevel, 69)
        self.assertEqual(self.item.slot_calls, 0)

    def test_vendor_display_refreshes_without_a_transaction(self):
        self.item.CashValue = 999999
        args = Struct(WP=self.pc.Pawn, Thing=self.item, CardIndex=0)
        self.sdk.dispatch("WillowGame.VendingMachineGFxMovie:SetPrice", Object("Map.UI"), args)
        self.assertEqual(self.item.CashValue, 44)
        self.assertEqual(self.pc.PlayerReplicationInfo.CurrencyOnHand, 1234567)

    def test_buy_sell_buyback_native_wallet_deltas_observed_once(self):
        pri = self.pc.PlayerReplicationInfo
        for function, delta in (("PlayerBuyItem", -308), ("PlayerSellItem", 44), ("PlayerBuyBackItem", -44)):
            with self.subTest(function=function):
                self.item.CashValue = 999999
                before = pri.CurrencyOnHand
                args = Struct(Item=self.item, WPC=self.pc, Quantity=1)
                def native():
                    self.assertEqual(self.item.CashValue, 44)
                    self.assertEqual(pri.CurrencyOnHand, before)
                    pri.CurrencyOnHand += delta
                    return True
                result = self.sdk.dispatch("WillowGame.WillowVendingMachine:" + function,
                                           Object("Map.Vendor"), args, native)
                self.assertIs(result, True)
                self.assertEqual(pri.CurrencyOnHand, before + delta)
                self.assertEqual(self.mod.audit.recent[-1]["wallet_delta"], delta)
                self.assertFalse(self.mod.audit.pending)

    def test_currency_observer_records_the_target_wallet_without_rescaling(self):
        foreign = Object("Map.OtherPRI", CurrencyOnHand=1000)
        args = Struct(AddValue=37)
        def native(): foreign.CurrencyOnHand += args.AddValue
        self.sdk.dispatch("WillowGame.WillowPlayerReplicationInfo:AddCurrencyOnHand", foreign, args, native)
        record = self.mod.audit.recent[-1]
        self.assertEqual((record["AddValue"], record["wallet_before"], record["wallet_after"], record["wallet_delta"]), (37, 1000, 1037, 37))
        self.assertEqual(args.AddValue, 37)
        self.assertEqual(self.pc.PlayerReplicationInfo.CurrencyOnHand, 1234567)

    def test_formula_overwrite_repaired_without_world_scan_or_recursion(self):
        patch = self.mod.runtime.patches[0]
        patch.write(patch.original)
        passes = self.mod.runtime.counts["inventory_passes"]
        self.assertEqual(self.item.ComputeCashValue(), 44)
        self.assertEqual(self.mod.runtime.counts["inventory_passes"], passes)
        self.mod.runtime.refresh_item(self.item)
        self.assertEqual(self.item.CashValue, 44)
        self.assertFalse(self.mod.runtime.busy)

    def test_world_and_profile_load_repair_cash_caches(self):
        self.item.CashValue = 999999
        self.mod.world_ready(self.pc.WorldInfo, None, None, None)
        self.assertEqual(self.item.CashValue, 44)
        self.item.CashValue = 999999
        self.mod.player_ready(self.pc, None, None, None)
        self.assertEqual(self.item.CashValue, 44)
        self.item.CashValue = 999999
        self.mod.player_ready(Object("OtherPC"), None, None, None)
        self.assertEqual(self.item.CashValue, 999999)

    def test_level_changing_reward_wrapper_can_bypass_our_query_hook(self):
        # One Playthrough scopes native mission levels and may recall a bound
        # function with hooks suppressed. Shared money inputs still apply.
        mission = Struct(GameStage=70, ExpLevel=70, CreditRewardMultiplier=2)
        native = self.sdk.objects["gd_Balance.Missions.MissionCreditRewardFormula"]
        old = mission.GameStage
        try:
            mission.GameStage = 69
            cash = int(self.sdk.formula(native, mission) * mission.CreditRewardMultiplier)
        finally:
            mission.GameStage = old
        self.assertEqual(cash, 560)
        self.assertEqual((mission.GameStage, mission.ExpLevel), (70, 70))

    def test_unconditional_post_unwinds_a_blocked_call_without_wallet_change(self):
        path = "WillowGame.WillowVendingMachine:PlayerBuyItem"
        before, after = [c for c in self.mod.HOOKS if any(p == path for p, _ in c.specs)]
        args = Struct(Item=self.item, WPC=self.pc, Quantity=1)
        self.assertIsNone(before(Object("Vendor"), args, None, None))
        # Simulate another mod blocking the native function.
        self.assertIsNone(after(Object("Vendor"), args, False, None))
        self.assertFalse(self.mod.audit.pending)
        self.assertEqual(self.mod.audit.recent[-1]["wallet_delta"], 0)
        self.assertFalse(self.mod.audit.recent[-1]["return_value"])

    def test_nested_calls_and_bounded_observation_history(self):
        audit = self.mod.audit
        for _ in range(120):
            audit.begin("query", Object(), Struct(), self.pc)
            audit.finish("query", 3, self.pc)
        self.assertEqual(len(audit.recent), 100)
        audit.begin("nested", Object(), Struct(), self.pc)
        audit.begin("nested", Object(), Struct(), self.pc)
        audit.finish("nested", 2, self.pc)
        audit.finish("nested", 1, self.pc)
        self.assertGreater(audit.recent[-2]["sequence"], audit.recent[-1]["sequence"])
        self.assertFalse(audit.pending)

    def test_native_transaction_contracts_match_capture(self):
        expected = {
            "GetSellingPriceForInventory": ["InventoryForSale", "Quantity"],
            "PlayerBuyItem": ["Item", "WPC", "Quantity"],
            "PlayerSellItem": ["Item", "WPC", "Quantity"],
            "PlayerBuyBackItem": ["Item", "WPC"],
            "GetResetCost": [],
        }
        for name, parameters in expected.items():
            fields = FIXTURE["native_functions"]["WillowGame.WillowVendingMachine:" + name]["fields"]
            actual = [f["name"] for f in fields if f["PropertyFlags"] & 128 and f["name"] != "ReturnValue"]
            self.assertEqual(actual, parameters)

    def test_menu_export_preserves_every_money_state_and_calls_no_native_prices(self):
        before_counts = dict(self.mod.runtime.counts)
        before_loads = list(self.sdk.loads)
        before_wallet = self.pc.PlayerReplicationInfo.CurrencyOnHand
        before_cash = self.item.CashValue
        with patch.object(self.item, "ComputeCashValue", side_effect=AssertionError("diagnostics called native price")):
            path = self.mods.registration["options"][0].on_press(None)
        self.assertIsNotNone(path)
        result = json.loads(path.read_text())
        self.assertEqual(result["mod"], {"name": "Economy Buster", "version": "0.1.0", "author": "keogh"})
        self.assertEqual(result["context"]["wallet"], before_wallet)
        self.assertTrue(all(f["level_one"] for f in result["economy"]["formula_inputs"]))
        self.assertEqual(result["loaded_mods"][0]["name"], "One Playthrough")
        self.assertTrue(result["hooks"])
        self.assertEqual(before_counts, dict(self.mod.runtime.counts))
        self.assertEqual(before_loads, self.sdk.loads)
        self.assertEqual(before_wallet, self.pc.PlayerReplicationInfo.CurrencyOnHand)
        self.assertEqual(before_cash, self.item.CashValue)
        self.assertEqual(self.item.slot_calls, 0)
        self.assertEqual(path.parent, Path(self.temp.name) / "EconomyBuster/diagnostics")

    def test_export_available_in_main_menu_and_after_activation_failure(self):
        self.mod.on_disable()
        self.mods.pc = None
        path, _, _ = self.mod.economy.FORMULA_INPUTS[-1]
        del self.sdk.objects[path]
        self.mod.on_enable()
        self.assertFalse(self.mod.runtime.active)
        output = self.mod.export_diagnostics()
        report = json.loads(output.read_text())
        self.assertFalse(report["context"]["character_loaded"])
        self.assertTrue(report["economy"]["problems"])
        self.assertTrue(any("error" in f for f in report["economy"]["formula_inputs"]))

    def test_export_failure_is_visible(self):
        with patch.object(self.mod, "write_snapshot", side_effect=PermissionError("denied")):
            self.assertIsNone(self.mod.export_diagnostics())
        self.assertTrue(any(kind == "error" and "denied" in msg for kind, msg in self.messages))

    def test_disable_does_not_reactivate_from_price_callbacks(self):
        self.mod.on_disable()
        self.item.ComputeCashValue()
        self.assertFalse(self.mod.runtime.active)
        self.assertFalse(self.mod.runtime.enabled)
        self.assertGreater(self.item.CashValue, 100000)

    def test_reader_handles_cycles_limits_and_nonfinite_values(self):
        module = self.mod.diagnostics
        first = Object("Price.A", "AttributeInitializationDefinition")
        second = Object("Price.B", "AttributeInitializationDefinition", ObjectArchetype=first)
        first.ObjectArchetype = second
        reader = module.Reader()
        reader.queue(first)
        reader.drain()
        self.assertEqual(set(reader.definitions), {"Price.A", "Price.B"})
        with patch.object(module, "MAX_ARRAY", 1):
            self.assertEqual(reader.value([1, 2]), [1, {"omitted": 1}])
        with patch.object(module, "MAX_DEFINITIONS", 2):
            reader.queue(Object("Price.C", "AttributeDefinition"))
        self.assertIn("definition limit", reader.truncations)
        self.assertEqual(reader.value(float("nan")), {"nonfinite": "nan"})
        json.dumps(reader.value(self.mod.runtime.snapshot()), allow_nan=False)

    def test_reader_never_follows_actor_ownership(self):
        reader = self.mod.diagnostics.Reader()
        actor = Object("Map.Player", "WillowPlayerPawn", CurrencyOnHand=9999)
        result = reader.value(actor)
        reader.drain()
        self.assertEqual(result["ref"], "Map.Player")
        self.assertEqual(reader.definitions, {})

    def test_runtime_limits_reported_and_partial_fields_survive(self):
        self.sdk.item()
        with patch.object(self.mod.diagnostics, "MAX_INVENTORY", 1):
            path = self.mod.export_diagnostics()
        report = json.loads(path.read_text())
        self.assertEqual(len(report["runtime_inventory"]), 1)
        self.assertIn("runtime_inventory limit", report["truncations"])
        reader = self.mod.diagnostics.Reader()
        fields = reader.fields(self.item, ["CashValue", "NonexistentField"])
        self.assertEqual(fields["CashValue"], 44)
        self.assertTrue(reader.errors)

    def test_exclusive_json_files_and_no_invalid_partial_report(self):
        module = self.mod.diagnostics
        folder = Path(self.temp.name) / "exports"
        first = module.write_snapshot({"cash": 1}, folder)
        second = module.write_snapshot({"cash": 2}, folder)
        self.assertNotEqual(first, second)
        before = set(folder.iterdir())
        with self.assertRaises(ValueError):
            module.write_snapshot({"broken": float("nan")}, folder)
        self.assertEqual(before, set(folder.iterdir()))


if __name__ == "__main__":
    unittest.main()
