"""Test cash policy against exported BL1E definitions through a mocked SDK.

The native ComputeCashValue/InitializeAttributeSlots calls remain in-game
validation points. The mock evaluates the exported formula, without UE floats.
"""

import importlib.util
import json
import math
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "tests/fixtures/bl1e_economy.json").read_text())

sdk_module = sys.modules.setdefault("unrealsdk", ModuleType("unrealsdk"))
sdk_module.logging = SimpleNamespace(info=lambda _msg: None, error=lambda _msg: None)
mods_module = sys.modules.setdefault("mods_base", ModuleType("mods_base"))
mods_module.get_pc = lambda: None
mods_module.hook = lambda *_args, **_kwargs: lambda callback: callback
hooks_module = sys.modules.setdefault("unrealsdk.hooks", ModuleType("unrealsdk.hooks"))
hooks_module.Type = SimpleNamespace(POST="POST")
spec = importlib.util.spec_from_file_location("pt3_economy", ROOT / "Source/sdk_mods/Playthrough 3/economy.py")
economy = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = economy
spec.loader.exec_module(economy)


class Object(SimpleNamespace):
    def _path_name(self):
        return self.path

    def _get_address(self):
        return id(self)


class SDK:
    def __init__(self):
        self.objects = {
            path: Object(path=path, Class=SimpleNamespace(Name=record["class"]), ObjectFlags=0)
            for path, record in FIXTURE["definitions"].items()
        }
        self.inventories = []
        self.loads = []
        self.refreshes = 0
        for path, record in FIXTURE["definitions"].items():
            for key, value in record["fields"].items():
                setattr(self.objects[path], key, self.convert(value))

    def convert(self, value):
        if isinstance(value, dict):
            if "ref" in value:
                path = value["ref"]
                if path not in self.objects:
                    self.objects[path] = Object(path=path, Class=SimpleNamespace(Name=value["class"]), ObjectFlags=0)
                return self.objects[path]
            if "struct" in value:
                return SimpleNamespace(**{key: self.convert(val) for key, val in value["fields"].items()})
            return {key: self.convert(val) for key, val in value.items()}
        if isinstance(value, list):
            return [self.convert(val) for val in value]
        return value

    def find_object(self, _cls, path):
        return self.objects[path]

    def load_package(self, name):
        self.loads.append(name)

    def find_all(self, _cls, exact=True):
        self.refreshes += 1
        if exact:
            raise AssertionError("Inventory subclasses must be included")
        return iter(self.inventories)

    def input_value(self, data, context):
        if data.InitializationDefinition is not None:
            value = self.formula(data.InitializationDefinition, context)
        elif data.BaseValueAttribute is not None:
            attr = data.BaseValueAttribute._path_name()
            if attr.endswith("InventoryPartCashValueModifierTotal"):
                value = context.CashValueModifierTotal
            elif attr.endswith("GameStage"):
                value = context.GameStage
            else:
                value = context.ExpLevel
        else:
            value = data.BaseValueConstant
        return value * data.BaseValueScaleConstant

    def formula(self, definition, context):
        formula = definition.ValueFormula
        return (
            self.input_value(formula.Multiplier, context)
            * self.input_value(formula.Level, context) ** self.input_value(formula.Power, context)
            + self.input_value(formula.Offset, context)
        )

    def item(self, case, modifier=0.0):
        sdk = self

        class Item(Object):
            def ComputeCashValue(self):
                definition = self.DefinitionData.ItemDefinition
                return int(sdk.input_value(definition.CashValue, self))

            def InitializeAttributeSlots(self, *, bIncludeNameParts):
                self.slot_calls += 1
                self.includes_name_parts = bIncludeNameParts
                slot = self.DefinitionData.ItemDefinition.AttributeSlotEffects[0]
                self.computed_cash_slot = sdk.input_value(slot.BaseModifierValue, self)

        item = Item(
            path=case["path"], Class=SimpleNamespace(Name=case["class"]),
            DefinitionData=self.convert(case["DefinitionData"]), ExpLevel=case["ExpLevel"],
            CashValue=case["CashValue"], CashValueModifierTotal=modifier,
            bDeleteMe=False, bPendingDelete=False, slot_calls=0,
        )
        self.inventories.append(item)
        return item


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.sdk = SDK()
        self.messages = []
        reporter = SimpleNamespace(info=self.messages.append, error=self.messages.append)
        self.policy = economy.Economy(self.sdk, reporter)
        self.shield = self.sdk.item(FIXTURE["inventory_cases"][0], modifier=38.4)

    def assert_original_inputs(self):
        for path, input_name, attribute in economy.FORMULA_INPUTS:
            target = getattr(self.sdk.objects[path].ValueFormula, input_name)
            self.assertEqual(target.BaseValueAttribute._path_name(), attribute)

    def test_level_70_shield_price_changes_without_downgrading(self):
        self.assertEqual(self.shield.ComputeCashValue(), 1248503)
        definition = self.shield.DefinitionData
        grade = definition.ManufacturerGradeIndex
        self.shield.ShieldCapacity = 4200
        self.shield.RarityLevel = 1
        self.assertTrue(self.policy.set_mode(True))
        self.assertEqual(self.shield.CashValue, 44)
        self.assertEqual(self.shield.CashValue * 7, 308)
        self.assertEqual(self.shield.ExpLevel, 70)
        self.assertIs(self.shield.DefinitionData, definition)
        self.assertEqual(definition.ManufacturerGradeIndex, grade)
        self.assertEqual(self.shield.ShieldCapacity, 4200)
        self.assertEqual(self.shield.RarityLevel, 1)

    def test_only_six_money_inputs_change(self):
        self.policy.set_mode(True, refresh=False)
        for path, input_name, _ in economy.FORMULA_INPUTS:
            target = getattr(self.sdk.objects[path].ValueFormula, input_name)
            self.assertEqual(target.BaseValueConstant, 1.0)
            self.assertIsNone(target.BaseValueAttribute)
            self.assertIsNone(target.InitializationDefinition)
            self.assertEqual(target.BaseValueScaleConstant, 1.0)
        weapon_formula = self.sdk.objects[economy.FORMULA_INPUTS[0][0]].ValueFormula
        self.assertEqual(weapon_formula.Level.BaseValueConstant, 1.159999966621399)
        self.assertEqual(weapon_formula.Multiplier.BaseValueAttribute._path_name(),
                         "d_attributes.Inventory.InventoryPartCashValueModifierTotal")

    def test_repeated_refresh_does_not_scale_twice(self):
        self.policy.set_mode(True)
        self.policy.set_mode(True)
        self.assertEqual(self.shield.CashValue, 44)
        self.assertEqual(len(self.policy.patches), 6)
        self.assertEqual(len(self.sdk.loads), 4)
        self.policy.set_mode(False)
        self.assertEqual(self.shield.CashValue, 1248503)
        self.assert_original_inputs()

    def test_currency_effect_formula_is_level_one(self):
        context = SimpleNamespace(ExpLevel=69, CashValueModifierTotal=1.1)
        formula = self.sdk.objects[economy.CURRENCY_FORMULA]
        vanilla = self.sdk.formula(formula, context)
        self.assertGreater(vanilla, 2000)
        self.policy.set_mode(True)
        self.assertAlmostEqual(self.sdk.formula(formula, context), 1.232000005245209)
        self.assertEqual(context.ExpLevel, 69)

    def test_loaded_currency_slots_are_refreshed(self):
        definition = SimpleNamespace(ItemDefinition=self.sdk.objects["gd_currency.A_Item.Currency"])
        calls = []
        coin = Object(
            path="Map.Coin", Class=SimpleNamespace(Name="WillowUsableItem"),
            DefinitionData=definition, bDeleteMe=False, bPendingDelete=False,
            ExpLevel=69, CashValue=2000,
            InitializeAttributeSlots=lambda **args: calls.append(args),
            ComputeCashValue=lambda: 2,
        )
        self.sdk.inventories.append(coin)
        self.policy.set_mode(True)
        self.assertEqual(calls, [{"bIncludeNameParts": True}])
        self.assertEqual(coin.CashValue, 2)
        self.assertEqual(coin.ExpLevel, 69)

    def test_consumable_fixed_prices_stay_native(self):
        health = self.sdk.item(FIXTURE["inventory_cases"][1])
        ammo = self.sdk.item(FIXTURE["inventory_cases"][2])
        self.policy.set_mode(True)
        self.assertEqual(health.CashValue, 75)
        self.assertEqual(ammo.CashValue, 14)

    def test_mission_cash_changes_without_changing_mission_level(self):
        mission = SimpleNamespace(GameStage=70, ExpLevel=70, CreditMultiplier=2.0, ExperienceReward=12345)
        formula = self.sdk.objects["gd_Balance.Missions.MissionCreditRewardFormula"]
        self.policy.set_mode(True)
        self.assertAlmostEqual(self.sdk.formula(formula, mission) * mission.CreditMultiplier, 560, places=3)
        self.assertEqual((mission.GameStage, mission.ExpLevel, mission.ExperienceReward), (70, 70, 12345))

    def test_death_cap_and_respec_use_level_one(self):
        context = SimpleNamespace(ExpLevel=69, CurrencyOnHand=3262489)
        self.policy.set_mode(True)
        death_cap = self.sdk.formula(self.sdk.objects["gd_Balance_Inventory.Commerce.DeathPenaltyCap"], context)
        respec = self.sdk.formula(self.sdk.objects["gd_globals.Skills.CostToResetSkillPoints"], context)
        self.assertAlmostEqual(death_cap, 131, places=3)
        self.assertAlmostEqual(respec, 115.66, places=3)
        self.assertEqual(context.CurrencyOnHand, 3262489)

    def test_other_playthroughs_restore_originals(self):
        self.policy.set_mode(True)
        self.policy.set_mode(False)
        self.assert_original_inputs()
        self.assertEqual(self.shield.CashValue, FIXTURE["inventory_cases"][0]["CashValue"])
        self.assertFalse(self.policy.active)

    def test_unknown_formula_aborts_before_changing_any_inputs(self):
        path, input_name, _ = economy.FORMULA_INPUTS[-1]
        target = getattr(self.sdk.objects[path].ValueFormula, input_name)
        target.BaseValueAttribute = Object(path="OtherMod.Unknown")
        first = self.sdk.objects[economy.FORMULA_INPUTS[0][0]].ValueFormula.Power.BaseValueAttribute
        self.assertFalse(self.policy.set_mode(True))
        self.assertIs(self.sdk.objects[economy.FORMULA_INPUTS[0][0]].ValueFormula.Power.BaseValueAttribute, first)
        self.assertEqual(self.policy.patches, [])
        self.assertFalse(self.policy.active)
        self.assertTrue(self.messages)

    def test_missing_definition_aborts_before_changing_any_inputs(self):
        del self.sdk.objects[economy.FORMULA_INPUTS[-1][0]]
        self.assertFalse(self.policy.set_mode(True))
        self.assertFalse(self.policy.active)
        self.assertEqual(self.policy.patches, [])

    def test_deleted_items_are_not_touched(self):
        self.shield.bDeleteMe = True
        self.policy.set_mode(True)
        self.assertEqual(self.shield.CashValue, 1248503)

    def test_disable_restores_values_and_original_pin_flags(self):
        original_pinned = self.sdk.objects[economy.FORMULA_INPUTS[0][0]]
        original_pinned.ObjectFlags |= economy.KEEP_ALIVE
        self.policy.set_mode(True)
        self.policy.release()
        self.assert_original_inputs()
        self.assertEqual(self.shield.CashValue, 1248503)
        self.assertEqual(original_pinned.ObjectFlags & economy.KEEP_ALIVE, economy.KEEP_ALIVE)
        for path, _, _ in economy.FORMULA_INPUTS[1:]:
            self.assertEqual(self.sdk.objects[path].ObjectFlags & economy.KEEP_ALIVE, 0)

    def test_native_calls_match_exported_signatures(self):
        funcs = FIXTURE["native_functions"]
        compute = funcs["Engine.WillowInventory:ComputeCashValue"]["fields"]
        params = [field["name"] for field in compute if field["PropertyFlags"] & 128 and field["name"] != "ReturnValue"]
        self.assertEqual(params, [])
        slots = funcs["WillowGame.WillowItem:InitializeAttributeSlots"]["fields"]
        self.assertEqual([field["name"] for field in slots if field["PropertyFlags"] & 128], ["bIncludeNameParts"])

    def test_inputs_reapply_if_a_later_callback_overwrites_them(self):
        self.policy.set_mode(True)
        self.policy.patches[0].write(False)
        self.assertEqual(self.shield.ComputeCashValue(), 1248503)
        self.policy.set_mode(True)
        self.assertEqual(self.shield.CashValue, 44)

    def test_status_is_json_safe_and_does_not_change_prices(self):
        self.policy.set_mode(True)
        status = self.policy.snapshot()
        json.dumps(status, allow_nan=False)
        self.assertTrue(status["active"])
        self.assertEqual(status["prepared_count"], 6)
        self.assertEqual(status["formula_inputs"][0]["BaseValueConstant"], 1.0)
        self.assertIsNone(status["formula_inputs"][0]["BaseValueAttribute"])
        self.assertEqual(self.shield.CashValue, 44)


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        PolicyTests.setUp(self)
        self.pc = Object(Pawn=Object(), GetCurrentPlaythrough=lambda: self.index)
        self.index = 0
        self.globals_patch = patch.object(economy, "_economy", self.policy)
        self.pc_patch = patch.object(economy, "get_pc", lambda: self.pc)
        self.globals_patch.start()
        self.pc_patch.start()
        self.addCleanup(self.globals_patch.stop)
        self.addCleanup(self.pc_patch.stop)

    def test_pt3_selection_survives_early_profile_callback_reporting_pt1(self):
        self.policy.set_mode(True, refresh=False)
        self.pc.Pawn = None
        economy.profile_loaded(self.pc, None, None, None)
        economy.cash_calculation(self.shield, None, None, None)
        self.assertTrue(self.policy.active)
        self.assertEqual(self.shield.ComputeCashValue(), 44)
        self.pc.Pawn = Object()
        economy.cash_calculation(self.shield, None, None, None)
        self.assertTrue(self.policy.active)
        self.index = 2
        economy.profile_loaded(self.pc, None, None, None)
        self.assertEqual(self.shield.CashValue, 44)
        # Choosing PT2 is an explicit restore, independent of profile timing.
        self.index = 1
        self.policy.set_mode(False)
        economy.profile_loaded(self.pc, None, None, None)
        self.assertFalse(self.policy.active)
        self.assertEqual(self.shield.CashValue, 1248503)

    def test_vendor_repairs_cache_when_profile_callback_did_not_activate(self):
        self.index = 2
        economy.vendor_price(None, Object(InventoryForSale=self.shield), None, None)
        self.assertTrue(self.policy.active)
        self.assertEqual(self.shield.CashValue, 44)
        self.assertEqual(self.sdk.refreshes, 0)
        self.assertEqual(self.shield.ExpLevel, 70)

    def test_display_and_transactions_refresh_the_same_cash_value(self):
        self.index = 2
        self.policy.set_mode(True, refresh=False)
        for field in ("Thing", "Item"):
            self.shield.CashValue = 1248503
            economy.vendor_item(None, Object(**{field: self.shield}), None, None)
            self.assertEqual(self.shield.CashValue, 44)

    def test_cash_calculation_repairs_formula_without_world_scan(self):
        self.index = 2
        economy.cash_calculation(self.shield, None, None, None)
        self.assertEqual(self.shield.ComputeCashValue(), 44)
        self.assertEqual(self.sdk.refreshes, 0)

    def test_pt1_vendor_keeps_normal_cash_values(self):
        economy.vendor_item(None, Object(Thing=self.shield), None, None)
        self.assertFalse(self.policy.active)
        self.assertEqual(self.shield.CashValue, 1248503)

    def test_refresh_does_not_reenter_runtime_synchronization(self):
        self.index = 2
        original_compute = self.shield.ComputeCashValue

        def hooked_compute():
            economy.cash_calculation(self.shield, None, None, None)
            return original_compute()

        self.shield.ComputeCashValue = hooked_compute
        self.policy.set_mode(True)
        self.assertEqual(self.shield.CashValue, 44)
        self.assertEqual(len(self.policy.events), 1)

    def test_native_vendor_and_cash_hook_signatures_match_live_export(self):
        funcs = FIXTURE["native_functions"]
        expected = {
            "WillowGame.WillowVendingMachine:GetSellingPriceForInventory": ["InventoryForSale", "Quantity"],
            "WillowGame.VendingMachineGFxMovie:SetPrice": ["WP", "Thing", "CardIndex"],
            "WillowGame.WillowVendingMachine:PlayerBuyItem": ["Item", "WPC", "Quantity"],
            "WillowGame.WillowVendingMachine:PlayerSellItem": ["Item", "WPC", "Quantity"],
            "WillowGame.WillowVendingMachine:PlayerBuyBackItem": ["Item", "WPC"],
            "WillowGame.WillowVendingMachine:GetResetCost": [],
            "WillowGame.MissionDefinition:GetCreditReward": ["InWPC"],
        }
        for name, params in expected.items():
            fields = funcs[name]["fields"]
            actual = [field["name"] for field in fields if field["PropertyFlags"] & 128 and field["name"] != "ReturnValue"]
            self.assertEqual(actual, params, name)


if __name__ == "__main__":
    unittest.main()
