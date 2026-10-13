"""Grenade slot regressions using the user's actual BL1E item export.

Native damage delivery/card rounding remain Windows verification points.
"""

from copy import deepcopy
import json
from pathlib import Path
import struct
import sys
from types import ModuleType, SimpleNamespace as NS
import unittest
from unittest.mock import patch

from test_enemy_levels import load as load_levels

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Source/sdk_mods/Playthrough 3"
FIXTURE = json.loads((ROOT / "tests/fixtures/bl1e_grenades.json").read_text())


class FloatStruct(NS):
    def __setattr__(self, key, value):
        if key in ("BaseValueScaleConstant", "ComputedModifierValue"):
            value = struct.unpack("f", struct.pack("f", value))[0]
        super().__setattr__(key, value)


class Object(NS):
    def _path_name(self): return self.path
    def _get_address(self): return id(self)
    def InitializeAttributeSlots(self, **kwargs): raise AssertionError("Never reinvoke initialization")
    def GetAttributeSlotModifierValue(self, *args): raise AssertionError("Never reinvoke damage getters")
    def SetExpLevel(self, *args): raise AssertionError("Never change item levels")


class SDK:
    def __init__(self):
        self.objects = {p: Object(path=p, ObjectFlags=0, Class=NS(Name=d["class"]))
                        for p, d in FIXTURE["definitions"].items()}
        self.loads, self.scans, self.items = [], [], []
        for path, record in FIXTURE["definitions"].items():
            for field, value in record["fields"].items():
                setattr(self.objects[path], field, self.convert(value))
        for record in FIXTURE["items"]:
            item = Object(path=record["path"], Class=NS(Name=record["class"]),
                          ExpLevel=record["ExpLevel"], bDeleteMe=False, bPendingDelete=False,
                          DefinitionData=self.convert(record["DefinitionData"]),
                          AttributeSlots=self.convert(record["AttributeSlots"]))
            self.items.append(item)

    def convert(self, value):
        if isinstance(value, list): return [self.convert(v) for v in value]
        if not isinstance(value, dict): return value
        if "ref" in value:
            path = value["ref"]
            if path not in self.objects:
                self.objects[path] = Object(path=path, ObjectFlags=0)
            return self.objects[path]
        if "struct" in value:
            return FloatStruct(**{k: self.convert(v) for k, v in value["fields"].items()})
        return {k: self.convert(v) for k, v in value.items()}

    def find_object(self, cls, path):
        if path not in self.objects: raise ValueError("Object not found")
        return self.objects[path]

    def load_package(self, name): self.loads.append(name)

    def find_all(self, cls, exact=True):
        if cls != "WillowItem" or exact:
            raise AssertionError("Only an explicit inventory subclass scan is allowed")
        self.scans.append(cls)
        return list(self.items)


class GrenadeTests(unittest.TestCase):
    def setUp(self):
        self.levels, self.pc, modules = load_levels()
        modules["pt3_level_test"].enemy_levels = self.levels
        self.sdk = SDK()
        native = modules["unrealsdk"]
        native.find_object, native.find_all, native.load_package = self.sdk.find_object, self.sdk.find_all, self.sdk.load_package
        self.mod = ModuleType("pt3_level_test.grenades")
        self.mod.__package__ = "pt3_level_test"
        modules[self.mod.__name__] = self.mod
        modules["mods_base"].get_pc = lambda: self.pc
        with patch.dict(sys.modules, modules):
            exec(compile((SOURCE / "grenades.py").read_text(), "grenades.py", "exec"), self.mod.__dict__)
        self.definition = self.sdk.objects[self.mod.GRENADE_DEFINITION]
        self.formula = self.sdk.objects[self.mod.PROJECTILE_FORMULA]
        self.original = [(self.slot(i).BaseModifierValue.BaseValueScaleConstant, self.slot(i).ComputedModifierValue)
                         for i in self.sdk.items]

    def slot(self, item=None):
        return self.mod.GrenadeDamage.damage_slot(item or self.sdk.items[0])

    def assert_damage(self, value):
        self.assertEqual([self.slot(i).ComputedModifierValue for i in self.sdk.items[:4]], [value] * 4)

    def assert_native(self):
        for item, original in zip(self.sdk.items[:4], self.original):
            slot = self.slot(item)
            self.assertEqual((slot.BaseModifierValue.BaseValueScaleConstant, slot.ComputedModifierValue), original)

    def test_default_five_and_no_grenade_toggle(self):
        self.assertEqual(self.levels.max_level.value, 5)
        self.assertFalse(hasattr(self.mod, "boost"))
        self.mod.on_enable()
        self.assert_damage(800)

    def test_exact_card_damage_for_every_preset(self):
        self.assertEqual(self.definition.UIStats[0].AttributeSlotName, "GrenadeDamage")
        self.assertEqual(self.definition.UIStats[0].Attribute._path_name(), "d_attributes.Projectile.ProjectileDamage")
        for value, damage in ((3, 700), (4, 775), (5, 800)):
            self.levels.max_level.value = value
            self.mod.on_enable()
            self.assert_damage(damage)
            self.mod.on_disable()
            self.assert_native()

    def test_shared_definitions_levels_parts_and_other_items_unchanged(self):
        formula, definition = deepcopy(vars(self.formula)), deepcopy(vars(self.definition))
        before = [(i.DefinitionData, i.ExpLevel, i.DefinitionData.ManufacturerGradeIndex) for i in self.sdk.items]
        other = Object(path="Shield", DefinitionData=NS(ItemDefinition=Object(path="gd_Shields.Shield")),
                       AttributeSlots=[NS(SlotName="ShieldCapacity", ComputedModifierValue=4200)],
                       bDeleteMe=False, bPendingDelete=False)
        self.sdk.items.append(other)
        self.mod.on_enable()
        self.assertEqual(vars(self.formula), formula)
        self.assertEqual(vars(self.definition), definition)
        for item, (data, level, grade) in zip(self.sdk.items, before):
            self.assertIs(item.DefinitionData, data)
            self.assertEqual((item.ExpLevel, data.ManufacturerGradeIndex), (level, grade))
        self.assertEqual(other.AttributeSlots[0].ComputedModifierValue, 4200)
        self.assertEqual(self.sdk.loads, [])

    def test_repeated_damage_reads_do_not_compound(self):
        self.mod.on_enable()
        for _ in range(20):
            for item in self.sdk.items:
                self.mod.damage_read(item, NS(SlotName="GrenadeDamage"), None, None)
        self.assert_damage(800)
        self.mod.on_disable()
        self.assert_native()

    def test_callback_uses_new_setting_before_option_updates(self):
        self.mod.on_enable()
        for value, damage in ((3, 700), (4, 775), (5, 800)):
            self.mod.change_max_level(self.levels.max_level, value)
            self.assert_damage(damage)
            self.levels.max_level.value = value
        self.mod.on_disable()
        self.assert_native()

    def test_disable_restores_slots_without_gc_flag_changes(self):
        self.definition.ObjectFlags = 0x4000 | 16
        self.mod.on_enable()
        self.mod.on_disable()
        self.assert_native()
        self.assertEqual(self.definition.ObjectFlags, 0x4000 | 16)
        self.assertEqual(self.mod._policy._items, {})

    def test_dropped_item_not_in_enumeration_still_restores(self):
        self.mod.on_enable()
        item = self.sdk.items.pop()
        self.mod.on_disable()
        slot = self.slot(item)
        self.assertEqual((slot.BaseModifierValue.BaseValueScaleConstant, slot.ComputedModifierValue), self.original[-1])

    def test_lower_level_mod_has_fixed_damage_and_restores_own_native_value(self):
        self.sdk.items[0].ExpLevel = 10
        self.slot().ComputedModifierValue = 25.5
        self.mod.on_enable()
        self.assertEqual(self.slot().ComputedModifierValue, 800)
        self.mod.on_disable()
        self.assertEqual(self.slot().ComputedModifierValue, 25.5)
        self.assertEqual(self.sdk.items[0].ExpLevel, 10)

    def test_original_nondefault_scale_restores_exactly(self):
        for item in self.sdk.items:
            self.slot(item).BaseModifierValue.BaseValueScaleConstant = 1.25
            self.slot(item).ComputedModifierValue *= 1.25
        before = [(self.slot(i).BaseModifierValue.BaseValueScaleConstant, self.slot(i).ComputedModifierValue)
                  for i in self.sdk.items]
        self.mod.on_enable()
        self.assert_damage(800)
        self.mod.on_disable()
        for item, original in zip(self.sdk.items, before):
            self.assertEqual((self.slot(item).BaseModifierValue.BaseValueScaleConstant,
                              self.slot(item).ComputedModifierValue), original)

    def test_other_playthroughs_stay_native(self):
        for pt in (0, 1):
            self.pc.GetCurrentPlaythrough = lambda: pt
            self.mod.on_enable()
            self.mod.sync_runtime()
            self.assert_native()
            self.mod.on_disable()

    def test_explicit_pt1_choice_cannot_be_undone_by_outgoing_pt3_controller(self):
        self.mod.on_enable()
        self.mod.set_mode(False, refresh=False)
        for item in self.sdk.items:
            self.mod.damage_read(item, NS(SlotName="GrenadeDamage"), None, None)
        self.assert_native()

    def test_continue_without_difficulty_click_activates_on_loaded_pawn(self):
        self.assertIn("WillowGame.WillowPlayerController:OnExpLevelChange", self.levels.registrations)
        self.pc.Pawn = None
        self.pc.GetCurrentPlaythrough = lambda: 0
        self.mod.on_enable()
        self.mod.reset_loading()
        self.assert_native()
        self.pc.Pawn = Object(path="Player")
        self.pc.GetCurrentPlaythrough = lambda: 2
        self.mod.player_ready(self.pc, None, None, None)
        self.assert_damage(800)

    def test_late_pawn_activates_on_first_damage_read(self):
        self.pc.Pawn = None
        self.mod.on_enable()
        self.mod.player_ready(self.pc, None, None, None)
        self.pc.Pawn = Object(path="Player")
        self.mod.damage_read(self.sdk.items[0], NS(SlotName="GrenadeDamage"), None, None)
        self.assertEqual(self.slot().ComputedModifierValue, 800)

    def test_early_old_controller_preserves_explicit_pt3_choice(self):
        self.pc.Pawn = None
        self.mod.on_enable()
        self.mod.set_mode(True)
        self.pc.Pawn = Object(path="Player")
        self.pc.GetCurrentPlaythrough = lambda: 0
        self.mod.player_ready(self.pc, None, None, None)
        self.assert_damage(800)

    def test_selection_override_expires_when_controller_matches(self):
        self.mod.on_enable()
        self.mod.set_mode(False)
        self.pc.GetCurrentPlaythrough = lambda: 1
        self.mod.player_ready(self.pc, None, None, None)
        self.assert_native()
        self.assertIsNone(self.mod._pending_selection)
        self.pc.GetCurrentPlaythrough = lambda: 2
        self.mod.player_ready(self.pc, None, None, None)
        self.assert_damage(800)

    def test_automatic_pt3_restores_on_later_pt2_load(self):
        self.mod.on_enable()
        self.pc.GetCurrentPlaythrough = lambda: 1
        self.mod.player_ready(self.pc, None, None, None)
        self.assert_native()

    def test_new_native_item_gets_target_and_restores(self):
        item = deepcopy(self.sdk.items[0])
        item.path = "NewGrenade"
        self.mod.on_enable()
        self.sdk.items.append(item)
        self.mod.after_slots(item, None, None, None)
        self.assertEqual(self.slot(item).ComputedModifierValue, 800)
        self.mod.on_disable()
        self.assertEqual(self.slot(item).ComputedModifierValue, self.original[0][1])

    def test_native_reinitialization_recaptures_changed_baseline(self):
        self.mod.on_enable()
        for item, (scale, damage) in zip(self.sdk.items, self.original):
            self.slot(item).BaseModifierValue.BaseValueScaleConstant = scale
            self.slot(item).ComputedModifierValue = damage + 10
            self.mod.after_slots(item, None, None, None)
        self.assert_damage(800)
        self.mod.on_disable()
        for item, (_, damage) in zip(self.sdk.items, self.original):
            self.assertEqual(self.slot(item).ComputedModifierValue, damage + 10)

    def test_damage_read_inside_native_initialization_waits_for_completion(self):
        item = self.sdk.items[0]
        self.mod.on_enable()
        self.mod.before_slots(item, None, None, None)
        self.slot(item).BaseModifierValue.BaseValueScaleConstant = self.original[0][0]
        self.slot(item).ComputedModifierValue = self.original[0][1]
        self.mod.damage_read(item, NS(SlotName="GrenadeDamage"), None, None)
        self.assertEqual(self.slot(item).ComputedModifierValue, self.original[0][1])
        self.mod.after_slots(item, None, None, None)
        self.mod.finish_slots(item, None, None, None)
        self.assertEqual(self.slot(item).ComputedModifierValue, 800)
        self.assertEqual(self.mod._initializing, {})
        self.mod.on_disable()
        self.assertEqual(self.slot(item).ComputedModifierValue, self.original[0][1])

    def test_nested_or_blocked_initialization_unwinds_context(self):
        item = self.sdk.items[0]
        self.mod.on_enable()
        self.mod.before_slots(item, None, None, None)
        self.mod.before_slots(item, None, None, None)
        self.mod.finish_slots(item, None, None, None)
        self.assertEqual(self.mod._initializing[item._get_address()], 1)
        self.mod.finish_slots(item, None, None, None)
        self.assertEqual(self.mod._initializing, {})

    def test_cloned_boosted_slots_inherit_native_baseline_for_restore(self):
        self.mod.on_enable()
        original = self.sdk.items[0]
        cloned = deepcopy(original)
        cloned.path = "ClonedGrenade"
        self.sdk.items.append(cloned)
        self.mod.slots_cloned(original, NS(NewItem=cloned), None, None)
        self.assertEqual(self.slot(cloned).ComputedModifierValue, 800)
        self.mod.on_disable()
        self.assertEqual(self.slot(cloned).ComputedModifierValue, self.original[0][1])

    def test_copy_direction_is_inferred_from_known_matching_source(self):
        self.mod.on_enable()
        original = self.sdk.items[0]
        cloned = deepcopy(original)
        cloned.path = "ClonedGrenade"
        self.mod.slots_cloned(cloned, NS(NewItem=original), None, None)
        self.mod.on_disable()
        self.assertEqual(self.slot(cloned).ComputedModifierValue, self.original[0][1])

    def test_non_grenade_getter_does_not_mutate(self):
        item = deepcopy(self.sdk.items[0])
        self.mod.on_enable()
        self.mod.damage_read(item, NS(SlotName="ShieldCapacity"), None, None)
        self.assertEqual(self.slot(item).ComputedModifierValue, self.original[0][1])

    def test_unknown_damage_layout_is_native_and_error_is_silent(self):
        slot = self.slot()
        original = slot.ComputedModifierValue
        slot.BaseModifierValue.InitializationDefinition = Object(path="Custom.GrenadeFormula")
        self.mod.on_enable()
        self.assertEqual(slot.ComputedModifierValue, original)
        self.assertTrue(self.mod._policy.problems)
        self.assertEqual(self.levels.messages, [])

    def test_missing_item_definition_does_not_mutate(self):
        slot = self.slot()
        self.sdk.items[0].DefinitionData.ItemDefinition = None
        self.mod.on_enable()
        self.assertEqual(slot.ComputedModifierValue, self.original[0][1])

    def test_default_and_deleted_items_are_not_mutated(self):
        for item, attr, value in zip(self.sdk.items, ("path", "bDeleteMe", "bPendingDelete"),
                                     ("Default__WillowItem", True, True)):
            setattr(item, attr, value)
        self.mod.on_enable()
        for item, (_, damage) in zip(self.sdk.items[:3], self.original[:3]):
            self.assertEqual(item.AttributeSlots[0].ComputedModifierValue, damage)

    def test_snapshot_is_read_only_and_reports_fixed_damage(self):
        self.mod.on_enable()
        before = self.mod._policy.updated_slots
        result = self.mod._policy.snapshot()
        json.dumps(result, allow_nan=False)
        self.assertEqual(result["applied_damage"], 800)
        self.assertEqual(result["max_level"], 5)
        self.assertEqual(result["items"][0]["computed_damage"], 800)
        self.assertEqual(self.mod._policy.updated_slots, before)
        self.assertNotIn("toggle", result)

    def test_foreign_later_write_is_preserved_on_disable(self):
        self.mod.on_enable()
        self.slot().ComputedModifierValue = 500
        self.mod.on_disable()
        self.assertEqual(self.slot().ComputedModifierValue, 500)


if __name__ == "__main__":
    unittest.main()
