import copy
import json
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from support import FIXTURE, Object, Struct, load_mod


class EconomyTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.stack, self.sdk, self.mods, self.mod, self.pc, self.messages = load_mod(self.temp.name)
        self.addCleanup(self.stack.close)
        self.policy = self.mod.runtime
        self.item = self.sdk.item()

    def test_equipment_values_frozen_across_levels_without_changing_gear(self):
        before = (self.item.DefinitionData, self.item.DefinitionData.ManufacturerGradeIndex,
                  self.item.ShieldCapacity, self.item.RarityLevel)
        self.assertTrue(self.policy.enable())
        for level in (1, 10, 35, 69, 70):
            self.item.ExpLevel = level
            self.policy.refresh_item(self.item)
            self.assertEqual(self.item.CashValue, 44)
            self.assertEqual(self.item.ExpLevel, level)
        self.assertEqual(before, (self.item.DefinitionData, self.item.DefinitionData.ManufacturerGradeIndex,
                                 self.item.ShieldCapacity, self.item.RarityLevel))
        self.assertEqual(self.item.slot_calls, 0)

    def test_only_six_money_inputs_change(self):
        snapshot = {k: copy.deepcopy(v.ValueFormula) for k, v in self.sdk.objects.items() if hasattr(v, "ValueFormula")}
        self.policy.enable()
        inputs = {p: name for p, name, _ in self.mod.economy.FORMULA_INPUTS}
        for path, old in snapshot.items():
            new = self.sdk.objects[path].ValueFormula
            for field in ("bEnabled", "Multiplier", "Level", "Power", "Offset"):
                if field == inputs.get(path):
                    target = getattr(new, field)
                    self.assertEqual(vars(target), self.mod.economy.LEVEL_ONE)
                else:
                    # Compare primitives/reference paths rather than copied UObject identities.
                    def inert(v):
                        if hasattr(v, "_path_name"): return v._path_name()
                        if isinstance(v, SimpleNamespace): return {k: inert(x) for k, x in vars(v).items()}
                        return v
                    self.assertEqual(inert(getattr(new, field)), inert(getattr(old, field)))

    def test_all_cash_variants_refresh_effect_slots(self):
        cash = [self.sdk.item("gd_currency.A_Item." + name, modifier=1.1, class_name="WillowUsableItem")
                for name in ("Currency", "Currency_big", "Currency_PrizeFighter", "Bobblehead", "SkagPearl")]
        self.policy.enable()
        for item in cash:
            base = item.DefinitionData.ItemDefinition.AttributeSlotEffects[0].BaseModifierValue
            self.assertAlmostEqual(item.computed_cash_slot, 1.1 * 1.12 * base.BaseValueScaleConstant, places=4)
            self.assertEqual(item.slot_calls, 1)
            self.assertEqual(item.ExpLevel, 69)

    def test_fixed_ammo_and_upgrade_effects_remain_intact(self):
        ammo = self.sdk.item("gd_ammodrops.Shop.AmmoShop_Grenade_Protean", class_name="WillowUsableItem")
        sdu = self.sdk.item("gd_StorageDeckUpgrade.A_Item.INV_SDU_Ammo", modifier=71, class_name="WillowUsableItem")
        bank = self.sdk.item("dlc2_gd_Bank.A_Item.INV_BankUpgrade_10", modifier=855, class_name="WillowUsableItem")
        data = sdu.DefinitionData
        effects = data.ItemDefinition.ExternalAttributeEffects
        self.policy.enable()
        self.assertEqual(ammo.CashValue, 14)
        self.assertEqual(sdu.CashValue, int(71 * 1.16))
        self.assertEqual(bank.CashValue, int(855 * 1.16))
        self.assertIs(data, sdu.DefinitionData)
        self.assertIs(effects, data.ItemDefinition.ExternalAttributeEffects)
        self.assertEqual((ammo.slot_calls, sdu.slot_calls, bank.slot_calls), (0, 0, 0))

    def test_mission_reward_tracks_its_multiplier_but_not_stage(self):
        mission = SimpleNamespace(GameStage=69, ExpLevel=69, CreditRewardMultiplier=2.0, XP=12345)
        self.policy.enable()
        formula = self.sdk.objects["gd_Balance.Missions.MissionCreditRewardFormula"]
        for stage in (1, 30, 69):
            mission.GameStage = stage
            self.assertAlmostEqual(self.sdk.formula(formula, mission) * mission.CreditRewardMultiplier, 560, places=3)
            self.assertEqual((mission.GameStage, mission.ExpLevel, mission.XP), (stage, 69, 12345))

    def test_respec_and_death_cap_only(self):
        self.policy.enable()
        context = SimpleNamespace(ExpLevel=69, CurrencyOnHand=1234567)
        cap = self.sdk.objects["gd_Balance_Inventory.Commerce.DeathPenaltyCap"]
        respec = self.sdk.objects["gd_globals.Skills.CostToResetSkillPoints"]
        vendor_respec = self.sdk.objects["gd_Balance_Inventory.Commerce.CostToResetSkillPoints"]
        percentage = self.sdk.objects["gd_Balance_Inventory.Commerce.DeathPenaltyCost"]
        self.assertAlmostEqual(self.sdk.formula(cap, context), 131, places=3)
        self.assertAlmostEqual(self.sdk.formula(respec, context), 115.66, places=3)
        self.assertAlmostEqual(self.sdk.formula(vendor_respec, context), 720, places=3)
        self.assertAlmostEqual(percentage.ValueFormula.Multiplier.BaseValueConstant, 0.07)
        self.assertEqual(context.CurrencyOnHand, 1234567)

    def test_no_player_or_playthrough_gate(self):
        self.mods.pc = None
        self.mod.on_enable()
        self.assertTrue(self.policy.active)
        for index in (0, 1, 2, 7):
            self.pc.GetCurrentPlaythrough = lambda index=index: index
            self.mods.pc = self.pc
            self.mod.player_ready(self.pc, None, None, None)
            self.assertTrue(self.policy.active)
            self.assertEqual(self.item.CashValue, 44)

    def test_restore_cash_and_pins_without_reverting_wallet(self):
        native = self.item.ComputeCashValue()
        definition = self.sdk.objects[self.mod.economy.FORMULA_INPUTS[0][0]]
        definition.ObjectFlags = self.mod.economy.KEEP_ALIVE
        self.policy.enable()
        self.pc.PlayerReplicationInfo.CurrencyOnHand += 22
        self.policy.disable()
        self.assertEqual(self.item.CashValue, native)
        self.assertEqual(self.pc.PlayerReplicationInfo.CurrencyOnHand, 1234589)
        self.assertEqual(definition.ObjectFlags, self.mod.economy.KEEP_ALIVE)
        self.assertFalse(self.policy.patches)
        self.assertFalse(self.policy.pinned)
        for path, name, expected in self.mod.economy.FORMULA_INPUTS:
            self.assertEqual(getattr(self.sdk.objects[path].ValueFormula, name).BaseValueAttribute._path_name(), expected)

    def test_unknown_or_missing_formula_changes_nothing(self):
        for mode in ("missing", "unknown"):
            with self.subTest(mode=mode):
                path, name, _ = self.mod.economy.FORMULA_INPUTS[-1]
                obj = self.sdk.objects[path]
                if mode == "missing":
                    del self.sdk.objects[path]
                else:
                    getattr(obj.ValueFormula, name).BaseValueAttribute = Object("OtherMod.MoneyLevel")
                self.assertFalse(self.policy.enable())
                first_path, first_name, expected = self.mod.economy.FORMULA_INPUTS[0]
                self.assertEqual(getattr(self.sdk.objects[first_path].ValueFormula, first_name).BaseValueAttribute._path_name(), expected)
                self.assertFalse(self.policy.pinned)
                self.sdk.objects[path] = obj

    def test_write_failure_rolls_back_all_inputs(self):
        self.assertTrue(self.policy.prepare())
        broken = self.policy.patches[3]
        native_write = broken.write
        def write(values):
            if values == self.mod.economy.LEVEL_ONE:
                getattr(broken.definition.ValueFormula, broken.input_name).BaseValueAttribute = None
                raise RuntimeError("native write failed")
            native_write(values)
        broken.write = write
        self.assertFalse(self.policy.enable())
        self.assertTrue(all(p.current() == p.original for p in self.policy.patches))
        self.assertFalse(self.policy.active)

    def test_failed_restore_keeps_originals_pinned_for_retry(self):
        self.policy.enable()
        first = self.policy.patches[0]
        native = first.write
        def fail(_values): raise RuntimeError("restore failed")
        first.write = fail
        self.policy.disable()
        self.assertTrue(self.policy.patches)
        self.assertTrue(self.policy.pinned)
        self.assertFalse(self.policy.enabled)
        first.write = native
        self.policy.disable()
        self.assertFalse(self.policy.patches)
        self.assertFalse(self.policy.pinned)

    def test_failed_partial_write_and_rollback_can_be_recovered_on_disable(self):
        self.policy.prepare()
        first = self.policy.patches[0]
        native_write = first.write
        def damaged(_values):
            target = getattr(first.definition.ValueFormula, first.input_name)
            target.BaseValueConstant = 7.5
            raise RuntimeError("partial write then failed rollback")
        first.write = damaged
        self.assertFalse(self.policy.enable())
        self.assertTrue(first.recovery_required)
        self.assertTrue(self.policy.pinned)
        first.write = native_write
        self.policy.disable()
        self.assertEqual(first.current(), first.original)
        self.assertFalse(self.policy.pinned)

    def test_external_level_input_and_multiplier_changes_are_preserved(self):
        self.policy.enable()
        first = self.policy.patches[0]
        external = Object("OtherMod.NewPriceLevel")
        target = getattr(first.definition.ValueFormula, first.input_name)
        target.BaseValueAttribute = external
        first.definition.ValueFormula.Level.BaseValueConstant = 1.2
        self.assertFalse(self.policy.ensure("external conflict"))
        self.policy.disable()
        self.assertIs(target.BaseValueAttribute, external)
        self.assertEqual(first.definition.ValueFormula.Level.BaseValueConstant, 1.2)

    def test_deleted_default_and_pending_inventory_are_skipped(self):
        default = self.sdk.item()
        default.path = "WillowGame.Default__WillowItem"
        pending = self.sdk.item()
        pending.bPendingDelete = True
        self.item.bDeleteMe = True
        self.policy.enable()
        self.assertEqual([item.CashValue for item in (self.item, default, pending)], [999999] * 3)

    def test_snapshot_is_inert_and_repeated_refresh_does_not_compound(self):
        self.policy.enable()
        self.policy.enable()
        self.assertEqual(self.item.CashValue, 44)
        count = dict(self.policy.counts)
        json.dumps(self.policy.snapshot(), allow_nan=False)
        self.assertEqual(dict(self.policy.counts), count)
        self.assertEqual(self.sdk.loads, list(self.mod.economy.PACKAGES))


if __name__ == "__main__":
    unittest.main()
