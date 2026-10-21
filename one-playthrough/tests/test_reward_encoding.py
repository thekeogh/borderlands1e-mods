"""Captured preview/copy regression; native initialization/save are modeled."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest

from test_one_playthrough import Harness, Object, aid
from test_item_rewards import balance, grade


class RewardEncodingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.h = Harness(self.tmp.name)
        self.encoding = NS(pack_level=self.h.mod.prepare_definition_data.__globals__["pack_level"],
                           initializer_specs=self.h.mod.initializer_specs)
        self.fixture = json.loads((Path(__file__).parent / "fixtures/bl1e_combat_rifle_copy.json").read_text())
        self.reward = balance(self.fixture["definition_data"]["BalanceDefinition"])
        self.definition = Object(self.fixture["definition_data"]["WeaponTypeDefinition"])
        self.definition.bUsesPlayerLevelRequirement = True
        self.definition.PlayerUseLevelBonus = aid(2)
        self.reward.bInterpolateExpLevel = False
        self.reward.InventoryDefinition = self.definition
        # The captured Dahl manufacturer grade 1 is internally level 18.
        self.reward.Manufacturers[0].Grades = [grade(9), grade(18)]
        for g in self.reward.Manufacturers[0].Grades:
            g.GradeModifiers.CustomInventoryDefinition = None
        self.h.mission.ItemRewards = [self.reward]
        self.h.enable(20)
        self.h.accept()
        self.original = NS(BalanceDefinition=self.reward, WeaponTypeDefinition=self.definition,
                           ManufacturerDefinition=Object("gd_manufacturers.Manufacturers.Dahl"),
                           ManufacturerGradeIndex=1, BodyPartDefinition=Object("Native.Rifle.Body"))
        self.callback = self.h.callbacks[("WillowGame.WillowWeapon:InitializeFromDefinitionData", "PRE")]

    def initialize(self, data):
        # SDK hook args are snapshots: mutation alone cannot change native input.
        calls = []
        def native(**values):
            calls.append(values["NewDefinitionData"])
        result = self.callback(Object("World.NewWeapon"), NS(NewDefinitionData=data), None, native)
        if result is None:
            native(NewDefinitionData=data)
        else:
            self.assertIs(result, self.h.mod.Block)
        self.assertEqual(len(calls), 1)
        data = calls[0]
        packed = data.ManufacturerGradeIndex
        # Existing BL1 definition-data convention; see captured packed level test.
        raw = packed >> 16 or self.reward.Manufacturers[0].Grades[packed & 0xFFFF].GradeModifiers.ExpLevel
        return NS(level=raw, required=raw - 2, DefinitionData=data)

    def test_old_temporary_grade_fix_reproduces_captured_preview_to_owned_drop(self):
        self.assertTrue(self.fixture["same_definition_data"])
        self.assertEqual(self.fixture["definition_data"]["ManufacturerGradeIndex"], 1)
        self.assertEqual((self.fixture["preview_internal"], self.fixture["owned_internal"],
                          self.fixture["owned_required"]), (22, 18, 16))
        # Without explicit data, the original parent grade resolves to 18 again.
        result = self.initialize(self.original)
        self.assertEqual((result.level, result.required), (18, 16))

    def test_pre_initializer_encoding_survives_grant_copy_after_scope_restoration(self):
        preview = []
        self.h.reward(native=lambda: preview.append(self.initialize(self.original)))
        first = preview[0]
        self.assertEqual((first.level, first.required), (22, 20))
        self.assertEqual(first.DefinitionData.ManufacturerGradeIndex, (22 << 16) | 1)
        self.assertEqual(self.reward.Manufacturers[0].Grades[1].GradeModifiers.ExpLevel, 18)
        # The grant copy is initialized AFTER all scoped grade edits are gone.
        owned = self.initialize(deepcopy(first.DefinitionData))
        self.assertEqual((owned.level, owned.required), (22, 20))
        self.assertEqual(self.original.ManufacturerGradeIndex, 1)
        self.assertIs(owned.DefinitionData.BalanceDefinition, self.reward)
        self.assertIs(owned.DefinitionData.BodyPartDefinition, self.original.BodyPartDefinition)
        self.assertEqual(self.h.runtime.missions.item_encoding["encoded"], 1)

    def test_native_data_roundtrip_works_without_active_mod_or_reward_scope(self):
        generated = []
        self.h.reward(native=lambda: generated.append(self.initialize(self.original)))
        saved = json.dumps({"balance": self.reward.path,
                            "grade": generated[0].DefinitionData.ManufacturerGradeIndex})
        self.h.mod.on_disable()
        values = json.loads(saved)
        loaded = deepcopy(self.original)
        loaded.ManufacturerGradeIndex = values["grade"]
        item = self.initialize(loaded)
        self.assertEqual((item.level, item.required), (22, 20))
        self.assertEqual(values["balance"], self.reward.path)

    def test_captured_bl1e_explicit_level_format_preserves_grade_bits(self):
        self.assertEqual(self.encoding.pack_level(5, 70), 4587525)
        self.assertEqual(self.encoding.pack_level(1, 22), 1441793)
        self.assertEqual(self.encoding.pack_level((7 << 16) | 5, 71), (71 << 16) | 5)
        with self.assertRaises(ValueError): self.encoding.pack_level(1, 0)

    def test_accepted_level_not_current_character_level_controls_encoding(self):
        self.h.pc.level = 40
        self.h.runtime.sync(self.h.pc)
        generated = []
        self.h.reward(native=lambda: generated.append(self.initialize(self.original)))
        self.assertEqual(generated[0].required, 20)

    def test_world_loot_and_existing_inventory_are_not_rewritten(self):
        args = NS(NewDefinitionData=self.original)
        self.callback(None, args, None, None)
        self.assertIs(args.NewDefinitionData, self.original)
        other = balance("Native.Unrelated.Loot")
        data = deepcopy(self.original)
        data.BalanceDefinition = other
        self.h.reward(native=lambda: self.callback(None, NS(NewDefinitionData=data), None, None))
        self.assertEqual(data.ManufacturerGradeIndex, 1)
        self.assertEqual(self.h.runtime.missions.item_encoding["encoded"], 0)

    def test_already_encoded_and_interpolated_formats_are_not_encoded_twice(self):
        data = deepcopy(self.original)
        data.ManufacturerGradeIndex = (22 << 16) | 1
        args = NS(NewDefinitionData=data)
        self.h.reward(native=lambda: self.callback(None, args, None, None))
        self.assertIs(args.NewDefinitionData, data)
        self.reward.bInterpolateExpLevel = True
        args = NS(NewDefinitionData=self.original)
        self.h.reward(native=lambda: self.callback(None, args, None, None))
        self.assertIs(args.NewDefinitionData, self.original)

    def test_item_initializer_uses_its_actual_definition_and_fallback_bonus(self):
        # Repeater-like custom item demonstrates this is not a hardcoded +2.
        definition = Object("Native.ItemDefinition")
        definition.bUsesPlayerLevelRequirement = True
        definition.PlayerUseLevelBonus = aid(1)
        data = NS(BalanceDefinition=self.reward, ItemDefinition=definition,
                  ManufacturerGradeIndex=1)
        args = NS(NewDefinitionData=data)
        callback = self.h.callbacks[("WillowGame.WillowItem:InitializeFromDefinitionData", "PRE")]
        calls = []
        self.h.reward(native=lambda: callback(None, args, None, lambda **kw: calls.append(kw)))
        self.assertEqual(calls[0]["NewDefinitionData"].ManufacturerGradeIndex, (21 << 16) | 1)
        self.assertEqual(args.NewDefinitionData.ManufacturerGradeIndex, 1)

    def test_discovery_uses_real_parameter_metadata_and_exports_selected_hooks(self):
        specs = self.encoding.initializer_specs(self.h.sdk)
        self.assertEqual(specs, [("WillowGame.WillowItem:InitializeFromDefinitionData",
                                 ("NewDefinitionData",), ("NewDefinitionData",), False),
                                ("WillowGame.WillowWeapon:InitializeFromDefinitionData",
                                 ("NewDefinitionData",), ("NewDefinitionData",), False)])
        report = json.loads(self.h.mod.export_diagnostics().read_text())
        self.assertEqual(report["reward_item_encoding"]["initializer_hooks"], [spec[0] for spec in specs])


    def test_native_recall_preserves_other_arguments_and_return_value(self):
        callback = self.h.mod.reward_initializer_hook("Test:Initialize", ("Data",),
                                                     ("Data", "Owner", "Flag"), True)
        owner = Object("Native.Owner")
        calls, results = [], []
        def native(**values):
            calls.append(values)
            return False
        args = NS(Data=self.original, Owner=owner, Flag=True)
        self.h.reward(native=lambda: results.append(callback(None, args, None, native)))
        self.assertEqual(results, [(self.h.mod.Block, False)])
        self.assertEqual(len(calls), 1)
        self.assertIs(calls[0]["Owner"], owner)
        self.assertIs(calls[0]["Flag"], True)
        self.assertEqual(calls[0]["Data"].ManufacturerGradeIndex, (22 << 16) | 1)
        self.assertEqual(args.Data.ManufacturerGradeIndex, 1)

    def test_failed_native_recall_blocks_retry(self):
        calls, results = [], []
        def native(**values):
            calls.append(values)
            raise RuntimeError("native initializer failed after invocation")
        self.h.reward(native=lambda: results.append(self.callback(None,
            NS(NewDefinitionData=self.original), None, native)))
        self.assertEqual(results, [self.h.mod.Block])
        self.assertEqual(len(calls), 1)
        self.assertIn("native initializer failed", str(self.h.runtime.problems))

    def test_discovery_forwards_all_inputs_detects_return_and_skips_out_parameters(self):
        cls = self.h.classes["WillowWeapon"]
        function = cls._fields()[0]
        original = list(function._properties())
        flag = NS(Name="Flag", Class=NS(Name="BoolProperty"), PropertyFlags=0x80)
        ret = NS(Name="ReturnValue", Class=NS(Name="BoolProperty"), PropertyFlags=0x480)
        function._properties = lambda: original + [flag, ret]
        spec = next(s for s in self.encoding.initializer_specs(self.h.sdk) if "WillowWeapon:" in s[0])
        self.assertEqual(spec[1:], (("NewDefinitionData",), ("NewDefinitionData", "Flag"), True))
        flag.PropertyFlags |= 0x100
        self.assertFalse(any("WillowWeapon:" in s[0] for s in self.encoding.initializer_specs(self.h.sdk)))

    def test_encoding_errors_leave_input_unchanged_and_diagnostics_record_failure(self):
        args = NS(NewDefinitionData=self.original)
        self.definition.PlayerUseLevelBonus.InitializationDefinition = Object("Native.Unsupported")
        # Bypass preparation so the initializer's own error handling is tested.
        scope = NS(reward_levels={self.reward.path.lower(): 20})
        self.h.runtime.missions.scopes.append((object(), None, 20, scope))
        self.callback(None, args, None, None)
        self.h.runtime.missions.scopes.clear()
        self.assertIs(args.NewDefinitionData, self.original)
        self.assertTrue(self.h.runtime.problems)


if __name__ == "__main__": unittest.main()
