"""Native grade-data models, not Windows engine execution."""

from copy import deepcopy
from types import SimpleNamespace as NS
import tempfile
import unittest

from test_one_playthrough import Harness, Object


def grade(level, low=1, high=100):
    return NS(GameStageRequirement=NS(MinGameStage=low, MaxGameStage=high),
              GradeModifiers=NS(ExpLevel=level, CustomInventoryDefinition=Object("Native.Shield"),
                                ShieldStrength=1.4),
              MinSpawnProbabilityModifier=0.25, MaxSpawnProbabilityModifier=0.75)


def balance(path="gd_customitems.Items.Reward_Shield"):
    item = Object(path)
    item.Manufacturers = [NS(Manufacturer=Object("Native.Manufacturer"),
                            Grades=[grade(7), grade(-3), grade(0)])]
    return item


class ItemRewardsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.h = Harness(self.tmp.name)
        self.balance = balance()
        self.h.mission.ItemRewards = [None, self.balance]
        def native_level(pc):
            self.h.mission.GameStage = self.h.mission.ExpLevel = 10
        self.h.mission.RefreshRewardGameStage = native_level

    def levels(self, item=None):
        return [g.GradeModifiers.ExpLevel for m in (item or self.balance).Manufacturers for g in m.Grades]

    def accept(self, player=5):
        self.h.enable(player)
        self.h.accept()
        self.assertEqual(self.h.mission.ExpLevel, 10)

    def test_low_and_high_character_both_receive_accepted_mission_level(self):
        self.accept()
        for player in (5, 20, 69):
            self.h.pc.level = player
            self.h.runtime.sync(self.h.pc)
            generated = []
            def native_generate():
                # Positive inventory grade ExpLevel is an explicit level;
                # fixed low values and negative offsets must not survive.
                for manufacturer in self.balance.Manufacturers:
                    for g in manufacturer.Grades:
                        generated.append(NS(level=g.GradeModifiers.ExpLevel,
                                            saved_balance=self.balance._path_name()))
            self.h.reward(native=native_generate)
            self.assertEqual([item.level for item in generated], [10, 10, 10])
            self.assertTrue(all(item.saved_balance == self.balance._path_name() for item in generated))
            self.assertEqual(self.levels(), [7, -3, 0])
            self.assertEqual(self.h.mission.ExpLevel, 10)
            self.assertEqual(self.h.runtime.missions.scopes, [])

    def test_no_parts_probabilities_or_reward_identity_change(self):
        self.accept()
        before = deepcopy(vars(self.balance.Manufacturers[0].Grades[0].GradeModifiers))
        rewards = self.h.mission.ItemRewards[:]
        def native_generate():
            g = self.balance.Manufacturers[0].Grades[0]
            self.assertEqual(g.GradeModifiers.ExpLevel, 10)
            self.assertEqual(g.GradeModifiers.ShieldStrength, before["ShieldStrength"])
            self.assertEqual((g.MinSpawnProbabilityModifier, g.MaxSpawnProbabilityModifier), (0.25, 0.75))
            self.assertEqual(self.h.mission.ItemRewards, rewards)
        self.h.reward(native=native_generate)
        self.assertEqual(self.balance.ObjectFlags, 0)
        self.assertIs(self.h.mission.ItemRewards[1], self.balance)
        self.assertEqual(self.levels(), [7, -3, 0])

    def test_all_reward_generation_and_preview_scopes_apply_same_level(self):
        self.accept()
        for name in ("GetItemRewardForPlayer", "GenerateRewardString"):
            self.h.reward(name, lambda: self.assertEqual(self.levels(), [10] * 3))
        path = "WillowGame.WillowPlayerController:GrantMissionRewards"
        args = NS(InMission=self.h.mission)
        self.h.callbacks[(path, "PRE")](self.h.pc, args, None, None)
        self.assertEqual(self.levels(), [10] * 3)
        self.h.callbacks[(path, "POST_UNCONDITIONAL")](self.h.pc, args, None, None)
        self.assertEqual(self.levels(), [7, -3, 0])

    def test_preview_follows_offer_but_acceptance_locks_it(self):
        self.h.enable(5)
        self.h.reward(native=lambda: self.assertEqual(self.levels(), [10] * 3))
        self.h.pc.level = 20
        self.h.runtime.sync(self.h.pc)
        self.h.reward(native=lambda: self.assertEqual(self.levels(), [20] * 3))
        self.h.accept()
        self.h.pc.level = 30
        self.h.runtime.sync(self.h.pc)
        self.h.reward(native=lambda: self.assertEqual(self.levels(), [20] * 3))
        self.assertEqual(self.levels(), [7, -3, 0])

    def test_nested_missions_sharing_reward_restore_outer_then_original(self):
        self.accept()
        other = Object("Native.OtherMission")
        other.GameStageRegion = self.h.mission.GameStageRegion
        other.GameStage, other.ExpLevel, other.MinimumLevel = 20, 20, 0
        other.ItemRewards = [self.balance]
        self.h.pc.MissionPlaythroughData[0].MissionList.append(NS(MissionDef=other, Status=1))
        self.h.runtime.missions.remember(other._path_name().lower(), 20)
        outer = self.h.runtime.missions.enter_reward(self.h.mission, self.h.pc)
        self.assertEqual(self.levels(), [10] * 3)
        inner = self.h.runtime.missions.enter_reward(other, self.h.pc)
        self.assertEqual(self.levels(), [20] * 3)
        self.h.runtime.missions.exit_reward(inner)
        self.assertEqual(self.levels(), [10] * 3)
        self.h.runtime.missions.exit_reward(outer)
        self.assertEqual(self.levels(), [7, -3, 0])

    def test_exception_and_disabling_restore_active_reward_edits(self):
        self.accept()
        def failure():
            self.assertEqual(self.levels(), [10] * 3)
            raise RuntimeError("native reward failed")
        with self.assertRaises(RuntimeError): self.h.reward(native=failure)
        self.assertEqual(self.levels(), [7, -3, 0])
        token = self.h.runtime.missions.enter_reward(self.h.mission, self.h.pc)
        self.h.mod.on_disable()
        self.h.runtime.missions.exit_reward(token)
        self.assertEqual(self.levels(), [7, -3, 0])
        self.assertEqual(self.h.runtime.missions.scopes, [])
        self.assertEqual(self.balance.ObjectFlags, 0)

    def test_regionless_rewards_and_class_specific_rewards_are_covered(self):
        self.accept()
        self.h.mission.GameStageRegion = None
        other = balance("gd_customitems.Items.Reward_OtherClass")
        self.h.mission.ItemRewards = [self.balance, None, other]
        token = self.h.runtime.missions.enter_reward(self.h.mission, self.h.pc)
        self.assertEqual(self.levels(), [10] * 3)
        self.assertEqual(self.levels(other), [10] * 3)
        self.h.runtime.missions.exit_reward(token)
        self.assertEqual(self.levels(), [7, -3, 0])
        self.assertEqual(self.levels(other), [7, -3, 0])

    def test_sdu_levels_and_unrelated_loot_definitions_are_preserved(self):
        self.accept()
        sdu = balance("gd_itemgrades.StorageDeckUpgrades.ItemGrade_SDU_InventorySlots")
        untouched = balance("Native.Unrelated.ShieldStock")
        self.h.mission.ItemRewards.append(sdu)
        self.h.reward(native=lambda: (self.assertEqual(self.levels(sdu), [7, -3, 0]),
                                     self.assertEqual(self.levels(untouched), [7, -3, 0])))

    def test_partial_preparation_failure_rolls_back_previous_balances(self):
        self.accept()
        bad = balance("Native.BadReward")
        del bad.Manufacturers[0].Grades[0].GradeModifiers.ExpLevel
        self.h.mission.ItemRewards.append(bad)
        with self.assertRaises(AttributeError):
            self.h.runtime.missions.enter_reward(self.h.mission, self.h.pc)
        self.assertEqual(self.levels(), [7, -3, 0])
        self.assertEqual(self.balance.ObjectFlags, 0)
        self.assertEqual(self.h.runtime.missions.scopes, [])

    def test_high_level_dlc_reward_extends_last_band_only(self):
        self.accept()
        self.balance.path = "dlc3_gd_customitems.Rewards.Shield"
        self.balance.Manufacturers[0].Grades = [grade(3, 1, 5), grade(7, 6, 8)]
        token = self.h.runtime.missions.enter_reward(self.h.mission, self.h.pc)
        gs = self.balance.Manufacturers[0].Grades
        self.assertEqual([(g.GameStageRequirement.MinGameStage, g.GameStageRequirement.MaxGameStage) for g in gs],
                         [(1, 5), (6, 10)])
        self.assertEqual(self.levels(), [10, 10])
        self.h.runtime.missions.exit_reward(token)
        self.assertEqual([(g.GameStageRequirement.MinGameStage, g.GameStageRequirement.MaxGameStage) for g in gs],
                         [(1, 5), (6, 8)])

    def test_extend_only_outer_grade_bands_and_restore_them(self):
        self.accept()
        self.balance.Manufacturers[0].Grades = [grade(1, 15, 20), grade(2, 21, 30)]
        token = self.h.runtime.missions.enter_reward(self.h.mission, self.h.pc)
        gs = self.balance.Manufacturers[0].Grades
        self.assertEqual([(g.GameStageRequirement.MinGameStage, g.GameStageRequirement.MaxGameStage) for g in gs],
                         [(10, 20), (21, 30)])
        self.h.runtime.missions.exit_reward(token)
        self.assertEqual([(g.GameStageRequirement.MinGameStage, g.GameStageRequirement.MaxGameStage) for g in gs],
                         [(15, 20), (21, 30)])




class InheritedRewardTests(unittest.TestCase):
    def setUp(self):
        import json
        from pathlib import Path
        self.data = json.loads((Path(__file__).parent / "fixtures/bl1e_scavenger_sniper.json").read_text())
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.h = Harness(self.tmp.name)
        defs = self.data["definitions"]
        self.child = balance("gd_customweapons.Reward_Weapons.CustomWeap_reward_SniperRifle")
        self.parent = balance("gd_itemgrades.Weapons.ItemGrade_Weapon_SniperRifle")
        self.child.Manufacturers = []
        self.child.BaseDefinition = self.parent
        self.child.PartListCollection = defs[self.child.path]["PartListCollection"]
        self.inventory = Object("gd_weap_sniper_rifle.A_Weapon.WeaponType_sniper_rifle")
        self.inventory.bUsesPlayerLevelRequirement = True
        bonus = defs[self.inventory.path]["PlayerUseLevelBonus"]
        self.inventory.PlayerUseLevelBonus = NS(**bonus)
        self.inventory.PlayerUseLevelBonus.BaseValueAttribute = Object(bonus["BaseValueAttribute"])
        attr = self.inventory.PlayerUseLevelBonus.BaseValueAttribute
        # Modeled native constant resolver metadata; captured requirement offset is 2.
        attr.AttributeContextClass = None
        attr.bIsSimpleAttribute = True
        attr.ContextResolverChain = [NS(Class=NS(Name="NoContextNeededAttributeContextResolver"))]
        attr.ValueResolverChain = [NS(Class=NS(Name="SimpleMathValueResolver"))]
        attr.native_value = 2
        self.parent.InventoryDefinition = self.inventory
        # Explicit model of the depth-limited rows; these are NOT captured data.
        self.parent.Manufacturers[0].Grades = [grade(7)]
        self.parent.Manufacturers[0].Grades[0].GradeModifiers.CustomInventoryDefinition = None
        self.h.mission.path = self.data["mission"]["path"]
        self.h.mission.ItemRewards = [self.child]
        def native_level(pc):
            self.h.mission.GameStage = self.h.mission.ExpLevel = 17
        self.h.mission.RefreshRewardGameStage = native_level
        self.h.enable(17)
        self.h.accept()
        self.h.pc.level = 20
        self.h.runtime.sync(self.h.pc)

    def test_real_sniper_shape_requires_inheritance_and_native_two_level_offset(self):
        self.assertEqual(self.data["observed_reward"]["internal_level"], 7)
        self.assertEqual(self.data["observed_reward"]["required_level"], 5)
        self.assertEqual(self.h.mission.ExpLevel, 17)
        created = []
        def native_generate():
            raw = self.child.Manufacturers[0].Grades[0].GradeModifiers.ExpLevel
            # This ordinary use-bonus conversion is observed in the export.
            created.append(NS(internal=raw, required=raw - 2, saved_balance=self.child.path))
            self.assertEqual(self.parent.Manufacturers[0].Grades[0].GradeModifiers.ExpLevel, 7)
        self.h.reward(native=native_generate)
        self.assertEqual((created[0].internal, created[0].required), (19, 17))
        self.assertEqual(created[0].saved_balance, self.child.path)
        self.assertEqual(self.child.Manufacturers, [])
        self.assertEqual(self.parent.Manufacturers[0].Grades[0].GradeModifiers.ExpLevel, 7)
        self.assertEqual(self.child.ObjectFlags, 0)

    def test_parent_world_loot_and_reward_parts_stay_unchanged(self):
        parent_table = self.parent.Manufacturers
        part_collection = self.child.PartListCollection
        def native_generate():
            self.assertIs(self.parent.Manufacturers, parent_table)
            self.assertIsNot(self.child.Manufacturers, parent_table)
            self.assertIsNot(self.child.Manufacturers[0].Grades[0], parent_table[0].Grades[0])
            self.assertEqual(self.child.PartListCollection, part_collection)
        self.h.reward(native=native_generate)
        self.assertIs(self.parent.Manufacturers, parent_table)
        self.assertEqual(self.child.Manufacturers, [])

    def test_nested_same_inherited_child_restores_then_removes_shadow_table(self):
        scopes = self.h.runtime.missions
        outer = scopes.enter_reward(self.h.mission, self.h.pc)
        shadow = self.child.Manufacturers
        inner = scopes.enter_reward(self.h.mission, self.h.pc)
        scopes.exit_reward(inner)
        self.assertIs(self.child.Manufacturers, shadow)
        self.assertEqual(shadow[0].Grades[0].GradeModifiers.ExpLevel, 19)
        scopes.exit_reward(outer)
        self.assertEqual(self.child.Manufacturers, [])

    def test_exception_restores_empty_child_and_keeps_parent(self):
        def failure():
            self.assertTrue(self.child.Manufacturers)
            raise RuntimeError("reward failed")
        with self.assertRaises(RuntimeError): self.h.reward(native=failure)
        self.assertEqual(self.child.Manufacturers, [])
        self.assertEqual(self.parent.Manufacturers[0].Grades[0].GradeModifiers.ExpLevel, 7)

    def test_custom_inventory_override_uses_its_own_bonus_not_universal_two(self):
        definition = Object("gd_weap_repeater_pistol.A_Weapon.WeaponType_repeater_pistol")
        definition.bUsesPlayerLevelRequirement = True
        definition.PlayerUseLevelBonus = NS(BaseValueConstant=1.0, BaseValueScaleConstant=1.0,
                                           BaseValueAttribute=None, InitializationDefinition=None)
        self.parent.Manufacturers[0].Grades[0].GradeModifiers.CustomInventoryDefinition = definition
        def native_generate():
            self.assertEqual(self.child.Manufacturers[0].Grades[0].GradeModifiers.ExpLevel, 18)
        self.h.reward(native=native_generate)
        self.assertEqual(self.child.Manufacturers, [])

    def test_cyclic_inheritance_and_unknown_bonus_fail_without_leftover_edits(self):
        self.parent.BaseDefinition = self.child
        with self.assertRaises(ValueError):
            self.h.runtime.missions.enter_reward(self.h.mission, self.h.pc)
        self.assertEqual(self.child.Manufacturers, [])
        self.parent.BaseDefinition = None
        self.inventory.PlayerUseLevelBonus.InitializationDefinition = Object("Custom.UnknownFormula")
        with self.assertRaises(ValueError):
            self.h.runtime.missions.enter_reward(self.h.mission, self.h.pc)
        self.assertEqual(self.child.Manufacturers, [])
        self.assertEqual(self.child.ObjectFlags, 0)

    def test_backpack_level_69_can_use_internal_level_above_69(self):
        self.h.runtime.missions.remember(self.h.mission.path.lower(), 69, replace=True)
        self.h.reward(native=lambda: self.assertEqual(
            self.child.Manufacturers[0].Grades[0].GradeModifiers.ExpLevel, 71))
        self.assertEqual(self.child.Manufacturers, [])

    def test_manual_diagnostics_include_inheritance_without_depth_limited_grades(self):
        import json
        report = json.loads(self.h.mod.export_diagnostics().read_text())
        mission = next(m for m in report["missions"] if m["path"] == self.h.mission.path)
        reward = mission["item_rewards"][0]
        self.assertEqual(reward["chain"], [self.child.path, self.parent.path])
        self.assertEqual(reward["mission_level"], 17)
        self.assertEqual(reward["target_internal_level"], 19)
        self.assertEqual(reward["manufacturer_grades"][0]["native_internal_level"], 7)
        self.assertEqual(self.child.Manufacturers, [])


if __name__ == "__main__": unittest.main()
