"""Export through the registered UI callbacks, including real failure modes."""

import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from test_one_playthrough import Harness, Object, aid


class Schema:
    def __init__(self, name, names):
        self.Name, self.names = name, names

    def _properties(self):
        return [NS(Name=name) for name in self.names]


class WrappedArray:
    """Model the live SDK distinction: _type is the element property."""
    def __init__(self, values):
        self.values = values
        self._type = NS(Name="ElementProperty", Struct=NS())  # No _properties.

    def __len__(self): return len(self.values)
    def __getitem__(self, index): return self.values[index]


class WrappedStruct:
    def __init__(self, **fields):
        self._type = Schema("Native.Struct", list(fields))
        self.__dict__.update(fields)


class ReflectedObject(Object):
    def __init__(self, path, class_name, **fields):
        super().__init__(path)
        self.Class = Schema(class_name, list(fields))
        self.__dict__.update(fields)


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.h = Harness(self.tmp.name)
        self.h.enable(20)

    def files(self):
        return list((Path(self.tmp.name) / "OnePlaythrough/diagnostics").glob("*.json"))

    def test_regional_report_includes_original_and_current_floors(self):
        path = self.h.mod.export_diagnostics()
        report = json.loads(path.read_text())
        rows = report["regions"]["region_levels"]
        row = next(r for r in rows if r["region"] == self.h.mission.GameStageRegion.path.lower())
        self.assertEqual(row["native_default"]["BaseValueConstant"], 16)
        self.assertEqual(row["current_default"], 20)
        self.assertEqual(report["enemy_policy"]["ordinary_tickets"], {"native": 50, "+1": 20, "+2": 25, "+3": 5})

    def test_unreadable_region_does_not_prevent_basic_and_mission_report(self):
        self.h.runtime.regions.levels_snapshot = lambda: (_ for _ in ()).throw(RuntimeError("bad region"))
        path = self.h.mod.export_diagnostics()
        report = json.loads(path.read_text())
        self.assertTrue(report["export_complete"])
        self.assertTrue(report["partial"])
        self.assertEqual(report["regions"]["region_levels"], [])
        self.assertTrue(report["missions"])

    def test_registered_f10_callback_creates_versioned_export_and_reports_path(self):
        bind = self.h.registration["keybinds"][0]
        self.assertEqual(bind.key, "F10")
        self.assertEqual(bind.identifier, "Export One Playthrough diagnostics")
        bind.callback()
        paths = self.files()
        self.assertEqual(len(paths), 1)
        self.assertTrue(paths[0].name.startswith("one-playthrough-"))
        report = json.loads(paths[0].read_text())
        self.assertEqual(report["version"], "4.5.4")
        self.assertTrue(report["export_complete"])
        self.assertFalse(report["partial"])
        self.assertIn("Export requested", self.h.messages[-2])
        self.assertIn(str(paths[0]), self.h.messages[-1])

    def test_registered_menu_button_runs_same_export_without_keybind(self):
        option = next(o for o in self.h.registration["options"] if o.identifier == "Export diagnostics")
        path = option.on_press(option)
        self.assertEqual(path, self.files()[0])
        self.assertTrue(json.loads(path.read_text())["enabled"])

    def test_unreadable_mission_field_keeps_partial_report_and_good_missions(self):
        class Broken(Object):
            @property
            def GameStageRegion(self): raise AttributeError("Unavailable region")
        broken = Broken("Native.BrokenMission")
        broken.ExpLevel = broken.GameStage = 12
        broken.MinimumLevel = 0
        self.h.missions.append(broken)
        path = self.h.mod.export_diagnostics()
        report = json.loads(path.read_text())
        self.assertTrue(report["partial"])
        self.assertEqual(len(report["missions"]), 2)
        self.assertIn("Unavailable region", str(report["export_errors"]))
        self.assertEqual(report["world_base_level"], 20)

    def test_unreadable_enemy_grade_does_not_discard_export(self):
        enemy = Object("Native.Enemy")
        enemy.DefaultExpLevel = aid(0)
        enemy.Grades = [NS(GameStageRequirement=NS(MinGameStage=1, MaxGameStage=69),
                           GradeModifiers=NS())]  # ExpLevel unavailable.
        self.h.definitions.append(enemy)
        report = json.loads(self.h.mod.export_diagnostics().read_text())
        self.assertTrue(report["partial"])
        self.assertIn("ExpLevel", str(report["export_errors"]))
        self.assertTrue(report["enabled"])

    def test_missing_enemy_class_still_exports_runtime_and_mission_data(self):
        original = self.h.sdk.find_all
        def find_all(cls, **kwargs):
            if cls == "AIPawnBalanceDefinition": raise ValueError("Class unavailable")
            return original(cls, **kwargs)
        self.h.sdk.find_all = find_all
        report = json.loads(self.h.mod.export_diagnostics().read_text())
        self.assertTrue(report["partial"])
        self.assertEqual(len(report["missions"]), 1)
        self.assertEqual(report["world_base_level"], 20)

    def test_nonfinite_native_values_produce_valid_json(self):
        enemy = Object("Native.Enemy")
        enemy.DefaultExpLevel = aid(float("nan"))
        enemy.Grades = []
        self.h.definitions.append(enemy)
        report = json.loads(self.h.mod.export_diagnostics().read_text())
        self.assertEqual(report["enemy_definitions"][0]["default_level"]["BaseValueConstant"],
                         {"nonfinite": "nan"})

    def test_directory_write_failure_is_logged_instead_of_swallowed(self):
        directory = Path(self.tmp.name) / "OnePlaythrough/diagnostics"
        directory.parent.mkdir(parents=True, exist_ok=True)
        directory.write_text("a file blocks directory creation")
        self.assertIsNone(self.h.mod.export_diagnostics())
        self.assertIn("Export failed", self.h.messages[-1])
        self.assertIn("export diagnostics", self.h.runtime.problems[-1])
        self.assertEqual(directory.read_text(), "a file blocks directory creation")

    def test_basic_report_exists_before_optional_reflection(self):
        original = self.h.sdk.find_all
        observed = []
        def find_all(cls, **kwargs):
            files = self.files()
            self.assertEqual(len(files), 1)
            report = json.loads(files[0].read_text())
            observed.append(report["export_complete"])
            self.assertEqual(report["world_base_level"], 20)
            return original(cls, **kwargs)
        self.h.sdk.find_all = find_all
        path = self.h.mod.export_diagnostics()
        self.assertTrue(observed)
        self.assertFalse(any(observed))
        self.assertTrue(json.loads(path.read_text())["export_complete"])

    def test_failed_full_write_preserves_basic_report_and_logs_its_path(self):
        original = Path.open
        def opened(path, *args, **kwargs):
            if path.suffix == ".tmp": raise OSError("modeled full-write failure")
            return original(path, *args, **kwargs)
        with patch.object(Path, "open", opened):
            self.assertIsNone(self.h.mod.export_diagnostics())
        path = self.files()[0]
        self.assertFalse(json.loads(path.read_text())["export_complete"])
        self.assertIn(str(path), self.h.messages[-1])

    def test_export_is_available_when_mod_disabled_and_no_character_loaded(self):
        self.h.mod.on_disable()
        self.h.mod.get_pc = lambda: None
        path = self.h.mod.export_diagnostics()
        report = json.loads(path.read_text())
        self.assertFalse(report["enabled"])
        self.assertIsNone(report["world_base_level"])
        self.assertTrue(report["export_complete"])

    def test_native_wrapped_arrays_do_not_treat_element_property_as_struct_schema(self):
        self.h.pc.MissionPlaythroughData = WrappedArray([WrappedStruct(MissionList=WrappedArray([
            WrappedStruct(MissionDef=self.h.mission, Status=1)
        ]))])
        self.h.pc.NonStartedMissionData = WrappedArray([WrappedStruct(MissionDef=self.h.mission, GameStage=20)])
        report = json.loads(self.h.mod.export_diagnostics().read_text())
        self.assertFalse(report["partial"])
        status = report["mission_progress"][0]["MissionList"][0]
        self.assertEqual(status, {"MissionDef": self.h.mission.path, "Status": 1})
        self.assertEqual(report["unaccepted_mission_data"][0]["GameStage"], 20)

    def test_vendor_stock_and_native_item_requirement_are_exported_without_generation(self):
        shield_def = ReflectedObject("gd_shields.A_Item.Shield", "ShieldDefinition", PlayerUseLevelBonus=0)
        shield = ReflectedObject("World.Shield", "WillowShield", CashValue=94, ExpLevel=4,
                                 Owner=self.h.pc, DefinitionData=WrappedStruct(ItemDefinition=shield_def))
        calls = []
        shield.GetInventoryDefinition = lambda: shield_def
        shield.GetControllerPlayerExpLevelRequiredToUse = lambda pc: calls.append(pc) or 4
        def forbidden(*args): raise AssertionError("Export must not generate or refresh stock")
        vendor = ReflectedObject("World.ZedVendor", "WillowVendingMachine",
            ShopInventory=WrappedArray([WrappedStruct(Inventory=shield, Quantity=1)]),
            ShopGameStage=3, Markup=10.0)
        vendor.GenerateInventory = vendor.ResetInventory = forbidden
        self.h.inventory.append(shield)
        self.h.vendors.append(vendor)
        before = dict(shield.__dict__)
        report = json.loads(self.h.mod.export_diagnostics().read_text())
        economy = report["economy"]
        self.assertFalse(report["partial"])
        self.assertEqual(economy["vendors"][0]["fields"]["ShopInventory"],
                         [{"Inventory": shield.path, "Quantity": 1}])
        self.assertEqual(economy["inventory"][0]["native_required_level"], 4)
        self.assertIn(shield_def.path, economy["definitions"])
        self.assertNotIn(self.h.pc.path, economy["definitions"])
        self.assertEqual(calls, [self.h.pc])
        self.assertEqual(shield.__dict__, before)
        self.assertEqual(shield_def.ObjectFlags, 0)

    def test_empty_vendor_still_exports_shield_grade_filters_and_pool_references(self):
        stock = ReflectedObject("gd_itemgrades.Gear.ItemGrade_Gear_Shield_Intro", "InventoryBalanceDefinition",
            Grades=WrappedArray([WrappedStruct(GameStageRequirement=WrappedStruct(MinGameStage=4, MaxGameStage=10))]))
        pool = ReflectedObject("gd_itempools.Shields.Tutorial", "ItemPoolDefinition",
            BalancedItems=WrappedArray([WrappedStruct(InvBalanceDefinition=stock, Probability=1.0)]))
        vendor = ReflectedObject("World.ZedVendor", "WillowVendingMachine",
            ShopInventory=WrappedArray([]), ItemPool=pool)
        self.h.vendors.append(vendor)
        self.h.economy_definitions["InventoryBalanceDefinition"] = [stock]
        report = json.loads(self.h.mod.export_diagnostics().read_text())
        definitions = report["economy"]["definitions"]
        self.assertEqual(definitions[stock.path]["fields"]["Grades"][0]["GameStageRequirement"],
                         {"MinGameStage": 4, "MaxGameStage": 10})
        self.assertEqual(definitions[pool.path]["fields"]["BalancedItems"][0]["InvBalanceDefinition"], stock.path)
        self.assertEqual(stock.Grades[0].GameStageRequirement.MinGameStage, 4)

    def test_unreadable_vendor_field_keeps_remaining_stock_and_marks_partial(self):
        class Broken(ReflectedObject):
            @property
            def ShopInventory(self): raise AttributeError("Native stock field unavailable")
        vendor = Broken("World.ZedVendor", "WillowVendingMachine", ShopGameStage=3)
        vendor.Class.names.append("ShopInventory")
        self.h.vendors.append(vendor)
        report = json.loads(self.h.mod.export_diagnostics().read_text())
        self.assertTrue(report["partial"])
        self.assertIn("Native stock field unavailable", str(report["export_errors"]))
        self.assertEqual(report["economy"]["vendors"][0]["fields"]["ShopGameStage"], 3)

    def test_profile_struct_and_replication_currency_are_read_without_actor_traversal(self):
        self.h.pc.LastLoadedProfile = WrappedStruct(ExpLevel=20, ExpPoints=1350, SaveGameId=1)
        self.h.pc.PlayerReplicationInfo = ReflectedObject("World.PRI", "WillowPlayerReplicationInfo",
                                                         CurrencyOnHand=940, ExpPoints=1350)
        report = json.loads(self.h.mod.export_diagnostics().read_text())
        self.assertFalse(report["partial"])
        player = report["economy"]["player"]
        self.assertEqual(player["profile"]["ExpPoints"], 1350)
        self.assertEqual(player["replication"]["CurrencyOnHand"], 940)
        self.assertNotIn("World.PRI", report["economy"]["definitions"])

    def test_missing_vendor_class_keeps_mission_export_and_reports_failure(self):
        original = self.h.sdk.find_all
        def find_all(cls, **kwargs):
            if cls == "WillowVendingMachine": raise ValueError("Vendor class unavailable")
            return original(cls, **kwargs)
        self.h.sdk.find_all = find_all
        report = json.loads(self.h.mod.export_diagnostics().read_text())
        self.assertTrue(report["partial"])
        self.assertEqual(len(report["missions"]), 1)
        self.assertEqual(report["economy"]["vendors"], [])
        self.assertIn("Vendor class unavailable", str(report["export_errors"]))

    def test_data_definition_cycles_are_bounded_and_do_not_pin_objects(self):
        definitions = [ReflectedObject(f"Native.Shield{i}", "InventoryBalanceDefinition", Other=None)
                       for i in range(605)]
        for i, obj in enumerate(definitions):
            obj.Other = definitions[(i + 1) % len(definitions)]
        self.h.economy_definitions["InventoryBalanceDefinition"] = definitions
        report = json.loads(self.h.mod.export_diagnostics().read_text())
        self.assertEqual(len(report["economy"]["definitions"]), 600)
        self.assertIn("definition limit", report["economy"]["truncations"])
        self.assertTrue(all(obj.ObjectFlags == 0 for obj in definitions))


if __name__ == "__main__":
    unittest.main()
