"""Data-export safety tests; native BL1E execution needs an in-game run."""

import importlib.util
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import ModuleType, SimpleNamespace
import unittest


class FakeObject:
    def __init__(self, path, fields, class_name="AttributeDefinition"):
        self._path = path
        self.Class = FakeSchema(class_name, fields)
        self.fields = fields

    def _path_name(self):
        return self._path

    def __getattr__(self, name):
        value = self.fields[name]
        if isinstance(value, Exception):
            raise value
        return value


class FakeSchema:
    def __init__(self, name, fields):
        self.Name = name
        self.fields = fields

    def _path_name(self):
        return self.Name

    def _properties(self):
        return iter(SimpleNamespace(Name=name) for name in self.fields)


class FakeStruct:
    def __init__(self, fields):
        self._type = FakeSchema("Formula", fields)
        self.fields = fields

    def __getattr__(self, name):
        return self.fields[name]


sdk_module = ModuleType("unrealsdk")
unreal_module = ModuleType("unrealsdk.unreal")
unreal_module.UObject = FakeObject
unreal_module.WrappedStruct = FakeStruct
sys.modules.setdefault("unrealsdk", sdk_module)
sys.modules.setdefault("unrealsdk.unreal", unreal_module)
module_path = Path(__file__).resolve().parents[1] / "diagnostics/PT3EconomyDiagnostics/exporter.py"
spec = importlib.util.spec_from_file_location("economy_exporter", module_path)
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


class ExporterTests(unittest.TestCase):
    def test_cyclic_definition_graph_is_finite(self):
        first = FakeObject("Price.First", {})
        second = FakeObject("Price.Second", {"Input": first})
        first.fields["Input"] = second
        dump = exporter.Exporter()
        dump.queue(first)
        dump.drain()
        self.assertEqual(set(dump.objects), {"Price.First", "Price.Second"})
        self.assertEqual(dump.objects["Price.Second"]["fields"]["Input"]["ref"], "Price.First")

    def test_export_preserves_cash_grade_and_formula_objects(self):
        formula = FakeStruct({"BaseValueConstant": 123, "BaseValueScaleConstant": 2.5})
        obj = FakeObject("Price.Shield", {"CashValue": 9999999, "Grade": 69, "Formula": formula})
        dump = exporter.Exporter()
        dump.queue(obj)
        dump.drain()
        self.assertIs(obj.fields["Formula"], formula)
        self.assertEqual(obj.fields["CashValue"], 9999999)
        self.assertEqual(obj.fields["Grade"], 69)
        self.assertEqual(formula.fields, {"BaseValueConstant": 123, "BaseValueScaleConstant": 2.5})

    def test_actor_references_are_not_traversed(self):
        actor = FakeObject("Map.Player", {"PrivateSaveData": "excluded"}, "WillowPawn")
        obj = FakeObject("Price.Shield", {"Owner": actor})
        dump = exporter.Exporter()
        dump.queue(obj)
        dump.drain()
        self.assertEqual(set(dump.objects), {"Price.Shield"})
        self.assertNotIn("PrivateSaveData", json.dumps(dump.objects))

    def test_property_failure_does_not_discard_other_data(self):
        obj = FakeObject("Price.Shield", {"Broken": RuntimeError("unavailable"), "CashValue": 200})
        dump = exporter.Exporter()
        dump.queue(obj)
        dump.drain()
        self.assertEqual(dump.objects["Price.Shield"]["fields"]["CashValue"], 200)
        self.assertEqual(len(dump.errors), 1)

    def test_definition_limit_is_reported(self):
        dump = exporter.Exporter()
        original = exporter.MAX_OBJECTS
        exporter.MAX_OBJECTS = 1
        try:
            dump.queue(FakeObject("Price.First", {}))
            dump.queue(FakeObject("Price.Second", {}))
        finally:
            exporter.MAX_OBJECTS = original
        dump.drain()
        self.assertEqual(set(dump.objects), {"Price.First"})
        self.assertEqual(dump.truncations, ["object limit"])

    def test_nested_value_limit_is_reported(self):
        nested = []
        nested.append(nested)
        dump = exporter.Exporter()
        result = dump.value(nested)
        self.assertIn("truncated", json.dumps(result))
        self.assertIn("nested value depth", dump.truncations)

    def test_nonfinite_game_values_remain_valid_json(self):
        dump = exporter.Exporter()
        result = dump.value([float("inf"), float("nan")])
        self.assertEqual(result[0], {"nonfinite": "inf"})
        json.dumps(result, allow_nan=False)

    def test_writes_distinct_valid_json_exports(self):
        with TemporaryDirectory() as temp:
            folder = Path(temp) / "exports"
            first = exporter.write_snapshot({"price": 100, "name": "Tédiore"}, folder)
            second = exporter.write_snapshot({"price": 200}, folder)
            self.assertNotEqual(first, second)
            self.assertEqual(json.loads(first.read_text())["price"], 100)
            self.assertEqual(json.loads(second.read_text())["price"], 200)

    def test_collect_survives_unavailable_classes(self):
        class FakeSDK:
            def load_package(self, _name):
                pass

            def find_class(self, _name):
                raise ValueError("missing class")

            def find_all(self, _name, exact=True):
                return []

        pc = SimpleNamespace(
            GetCurrentPlaythrough=lambda: 2,
            Pawn=SimpleNamespace(GetExpLevel=lambda: 69),
            PlayerReplicationInfo=SimpleNamespace(CurrencyOnHand=920631),
            WorldInfo=SimpleNamespace(GetMapName=lambda: "Arid_P"),
        )
        snapshot = exporter.collect(FakeSDK(), pc)
        self.assertEqual(snapshot["context"]["character_level"], 69)
        self.assertEqual(snapshot["context"]["wallet"], 920631)
        self.assertEqual(pc.PlayerReplicationInfo.CurrencyOnHand, 920631)
        self.assertTrue(snapshot["errors"])
        json.dumps(snapshot)


if __name__ == "__main__":
    unittest.main()
