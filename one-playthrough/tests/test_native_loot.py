"""Captured BL1E native-boundary regression models, not native Windows execution."""

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace as NS
import tempfile
import unittest

from test_one_playthrough import Harness, Object, aid
from test_item_rewards import balance, grade

PATH = "Engine.WillowInventory:InitializeInventory"
DEF = "WillowGame.WillowWeapon:InitializeFromDefinitionData"
INPUTS = ("InBalanceDef", "InManufacturer", "InGradeIndex", "InAdditionalQueryInterfaceSource")


class NativeLootTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.h = Harness(self.tmp.name)
        self.h.enable(12)
        self.h.pc.Pawn._path_name = lambda: "World.PlayerPawn"
        for name in ("WillowVendingMachine", "WillowPlayerPawn"):
            cls = Object("WillowGame." + name)
            cls.Name = name
            self.h.classes[name] = cls
        self.fixture = json.loads((Path(__file__).parent / "fixtures/bl1e_native_loot.json").read_text())
        self.calls = []

    def actor(self, kind, path, parents=()):
        obj = Object(path)
        obj.Class = NS(Name=kind, _inherits=lambda cls: cls.Name in (kind, *parents))
        obj.Owner = None
        return obj

    def item(self, record=None):
        record = record or self.fixture["vendor_item"]
        data = record["fields"]["DefinitionData"]
        obj = self.actor(record["class"], "World.FreshEquipment")
        self.definition = Object(data.get("WeaponTypeDefinition") or data["ItemDefinition"])
        self.definition.bUsesPlayerLevelRequirement = True
        self.definition.PlayerUseLevelBonus = aid(2)
        self.balance = balance(data["BalanceDefinition"])
        manufacturer = Object(data["ManufacturerDefinition"])
        self.balance.InventoryDefinition = self.definition
        count = (data["ManufacturerGradeIndex"] & 0xFFFF) + 1
        self.balance.Manufacturers = [NS(Manufacturer=manufacturer,
            Grades=[grade(record["fields"]["ExpLevel"]) for _ in range(count)])]
        fields = {name: Object(value) if isinstance(value, str) else value for name, value in data.items()}
        fields["BalanceDefinition"] = self.balance
        fields["ManufacturerDefinition"] = manufacturer
        fields["WeaponTypeDefinition" if "WeaponTypeDefinition" in data else "ItemDefinition"] = self.definition
        obj.DefinitionData = NS(**fields)
        return obj

    def args(self, obj, query=None):
        data = obj.DefinitionData
        return NS(InBalanceDef=self.balance, InManufacturer=data.ManufacturerDefinition,
                  InGradeIndex=data.ManufacturerGradeIndex, InAdditionalQueryInterfaceSource=query)

    def native(self, obj, **values):
        self.calls.append(values.copy())
        packed = values["InGradeIndex"]
        raw = packed >> 16 or self.balance.Manufacturers[0].Grades[packed & 0xFFFF].GradeModifiers.ExpLevel
        obj.ExpLevel = raw
        obj.required = raw - self.definition.PlayerUseLevelBonus.BaseValueConstant
        obj.damage = raw * 17  # Model real stats being built from the new internal level.

    def initialize(self, obj, args=None):
        args = args or self.args(obj)
        callback = self.h.callbacks[(PATH, "PRE")]
        result = callback(obj, args, None, lambda **values: self.native(obj, **values))
        if result is None:
            self.native(obj, **vars(args))
        else:
            self.assertIs(result, self.h.mod.Block)
        return obj

    def reconstruct(self, obj, data):
        args = NS(NewDefinitionData=data)
        def native(**values):
            obj.DefinitionData = deepcopy(values["NewDefinitionData"])
            self.initialize(obj)
        try:
            result = self.h.callbacks[(DEF, "PRE")](obj, args, None, native)
            if result is None:
                native(NewDefinitionData=data)
            else:
                self.assertIs(result, self.h.mod.Block)
        finally:
            self.h.callbacks[(DEF, "POST_UNCONDITIONAL")](obj, args, None, native)

    def test_captured_vendor_sniper_five_becomes_ten_without_a_reroll(self):
        obj = self.item()
        self.assertEqual(self.fixture["vendor_item"]["native_required_level"], 5)
        obj.Owner = self.actor("WillowVendingMachine", "World.Vendor", ("WillowInteractiveObject",))
        before = vars(obj.DefinitionData).copy()
        tables = deepcopy(self.balance.Manufacturers)
        self.initialize(obj)
        self.assertEqual((obj.ExpLevel, obj.required, obj.damage), (12, 10, 204))
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0]["InGradeIndex"], 12 << 16)
        self.assertEqual(obj.DefinitionData.ManufacturerGradeIndex, 12 << 16)
        self.assertEqual(self.balance.Manufacturers, tables)
        for key, value in before.items():
            if key != "ManufacturerGradeIndex":
                self.assertIs(getattr(obj.DefinitionData, key), value)
        self.assertEqual(self.h.runtime.loot.native.recent[-1]["kind"], "vendor")

    def test_captured_enemy_grenade_seven_becomes_ten(self):
        obj = self.item(self.fixture["enemy_drop"])
        self.assertEqual(self.fixture["enemy_drop"]["native_required_level"], 7)
        self.initialize(obj)
        self.assertEqual(obj.required, 10)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(obj.DefinitionData.ManufacturerGradeIndex, 12 << 16)

    def test_captured_chest_rifle_and_shotgun_already_high_enough_stay_native(self):
        for record in self.fixture["chest_items"]:
            obj = self.item(record)
            original = obj.DefinitionData
            self.initialize(obj)
            self.assertEqual(obj.required, record["native_required_level"])
            self.assertIs(obj.DefinitionData, original)
        self.assertEqual(self.h.runtime.loot.raised, 0)
        self.assertEqual(len(self.calls), 2)

    def test_chests_skag_piles_and_other_containers_share_same_floor_without_name_allowlist(self):
        for name in ("RedChest", "SkagPile", "Locker", "WhiteChest", "DLCChest"):
            obj = self.item()
            obj.Owner = self.actor("WillowInteractiveObject", "World." + name)
            self.initialize(obj)
            self.assertEqual(obj.required, 10)
            self.assertEqual(self.h.runtime.loot.native.recent[-1]["kind"], "container")

    def test_stat_initialization_and_definition_data_use_identical_packed_level(self):
        obj = self.item()
        args = self.args(obj)
        before = vars(args).copy()
        self.initialize(obj, args)
        self.assertEqual(vars(args), before)  # SDK args are snapshots, unchanged.
        self.assertEqual(self.calls[0]["InGradeIndex"], obj.DefinitionData.ManufacturerGradeIndex)
        for key in INPUTS:
            if key != "InGradeIndex":
                self.assertIs(self.calls[0][key], getattr(args, key))

    def test_new_vendor_stock_with_player_attribute_query_is_still_new_stock(self):
        obj = self.item()
        obj.Owner = self.actor("WillowVendingMachine", "World.Vendor", ("WillowInteractiveObject",))
        self.initialize(obj, self.args(obj, self.h.pc.Pawn))
        self.assertEqual(obj.required, 10)
        self.assertIs(self.calls[0]["InAdditionalQueryInterfaceSource"], self.h.pc.Pawn)

    def test_pickup_save_reload_and_player_drop_copies_are_excluded_even_when_owner_none(self):
        obj = self.item()
        self.initialize(obj)
        saved = deepcopy(obj.DefinitionData)
        self.h.pc.level = 30
        self.h.runtime.sync(self.h.pc)
        for _ in range(3):
            copy = self.actor("WillowWeapon", "World.Copy")
            self.reconstruct(copy, saved)
            self.assertEqual(copy.required, 10)
        self.assertEqual(self.h.runtime.loot.native.definition_scopes, [])
        self.assertEqual(self.h.runtime.loot.raised, 1)

    def test_old_low_level_saved_equipment_does_not_get_retroactively_upgraded(self):
        obj = self.item()
        original_grade = obj.DefinitionData.ManufacturerGradeIndex
        self.reconstruct(obj, obj.DefinitionData)
        self.assertEqual(obj.required, 5)
        self.assertEqual(obj.DefinitionData.ManufacturerGradeIndex, original_grade)
        self.assertEqual(self.h.runtime.loot.raised, 0)
        self.assertEqual(self.h.runtime.loot.native.skipped["definition-data reconstruction"], 1)

    def test_owned_player_items_and_inventory_manager_chain_are_untouched(self):
        for owner in (self.h.pc, self.h.pc.Pawn):
            obj = self.item()
            obj.Owner = owner
            self.initialize(obj)
            self.assertEqual(obj.required, 5)
        manager = self.actor("InventoryManager", "World.Manager")
        manager.Owner = self.h.pc.Pawn
        obj = self.item()
        obj.Owner = manager
        self.initialize(obj)
        self.assertEqual(obj.required, 5)

    def test_live_enemy_carried_gear_and_neutral_npc_are_not_upgraded(self):
        for allegiance in ("gd_AI_Allegiance.CreatureEnemy.Skag", "gd_AI_Allegiance.Friendly.NPC"):
            enemy = self.actor("WillowAIPawn", "World.Enemy")
            enemy.Allegiance = Object(allegiance)
            enemy.GetHealth = lambda: 100
            for owned in (False, True):
                obj = self.item()
                obj.Owner = enemy if owned else None
                self.initialize(obj, self.args(obj, None if owned else enemy))
                self.assertEqual(obj.required, 5)
        self.assertEqual(self.h.runtime.loot.raised, 0)

    def test_fresh_death_loot_with_dead_enemy_query_is_floored(self):
        obj = self.item()
        enemy = self.actor("WillowAIPawn", "World.DeadEnemy")
        enemy.Allegiance = Object("gd_AI_Allegiance.CreatureEnemy.Skag")
        enemy.GetHealth = lambda: 0
        token = self.h.runtime.loot.dying(enemy)
        try:
            self.initialize(obj, self.args(obj, enemy))
        finally:
            self.h.runtime.loot.end_death(token)
        self.assertEqual(obj.required, 10)
        self.assertEqual(self.h.runtime.loot.native.recent[-1]["kind"], "enemy")

    def test_mission_level_wins_even_when_below_world_loot_floor(self):
        obj = self.item()
        self.balance.Manufacturers[0].Grades[0].GradeModifiers.ExpLevel = 8
        self.h.runtime.missions.scopes.append((object(), None, 6, NS()))
        try:
            self.initialize(obj)
        finally:
            self.h.runtime.missions.scopes.clear()
        self.assertEqual(obj.required, 6)
        self.assertEqual(self.h.runtime.loot.raised, 0)

    def test_disabled_toggle_or_mod_preserves_native_level(self):
        for enabled in (False, True):
            self.h.mod.loot_floor.value = enabled
            if enabled:
                self.h.mod.on_disable()
            obj = self.item()
            self.initialize(obj)
            self.assertEqual(obj.required, 5)

    def test_level_one_floor_at_player_levels_one_to_four(self):
        for player in range(1, 5):
            self.h.pc.level = player
            obj = self.item()
            self.balance.Manufacturers[0].Grades[0].GradeModifiers.ExpLevel = 2
            self.initialize(obj)
            self.assertEqual(obj.required, max(1, player - 2))

    def test_weapon_and_other_gear_share_same_safe_floor_at_low_levels(self):
        for player in range(1, 7):
            self.h.pc.level = player
            for record in (self.fixture["vendor_item"], self.fixture["enemy_drop"]):
                with self.subTest(player=player, kind=record["class"]):
                    obj = self.item(record)
                    self.balance.Manufacturers[0].Grades[0].GradeModifiers.ExpLevel = 2
                    self.initialize(obj)
                    self.assertEqual(obj.required, max(1, player - 2))

    def test_consumables_mission_items_sdus_and_unknown_formats_remain_native(self):
        for kind in ("non-levelled", "mission", "SDU", "interpolated", "dynamic"):
            obj = self.item()
            if kind == "non-levelled": self.definition.bUsesPlayerLevelRequirement = False
            if kind == "mission": self.definition.bMissionItem = True
            if kind == "SDU": self.balance.BaseDefinition = Object("Native.StorageDeckUpgrade")
            if kind == "interpolated": self.balance.bInterpolateExpLevel = True
            if kind == "dynamic": self.balance.Manufacturers[0].Grades[0].GradeModifiers.ExpLevel = -2
            original = obj.DefinitionData
            self.initialize(obj)
            self.assertIs(obj.DefinitionData, original)
        self.assertEqual(self.h.runtime.loot.raised, 0)

    def test_native_failure_blocks_retry_and_records_error(self):
        obj = self.item()
        calls = []
        def fail(**values):
            calls.append(values)
            raise RuntimeError("native failed")
        result = self.h.callbacks[(PATH, "PRE")](obj, self.args(obj), None, fail)
        self.assertIs(result, self.h.mod.Block)
        self.assertEqual(len(calls), 1)
        self.assertIn("native failed", str(self.h.runtime.problems))

    def test_partial_assignment_failure_restores_detached_original_data(self):
        initial = self.item()
        class ViewActor(Object):
            fail = True
            @property
            def DefinitionData(self): return self.view
            @DefinitionData.setter
            def DefinitionData(self, value):
                self.view.__dict__.clear()
                self.view.__dict__.update(deepcopy(vars(value)))
                if self.fail:
                    self.fail = False
                    raise RuntimeError("partially assigned")
        obj = ViewActor("World.FreshViewActor")
        obj.view = deepcopy(initial.DefinitionData)
        obj.Owner = None
        result = self.h.callbacks[(PATH, "PRE")](obj, self.args(obj), None,
                                                lambda **kw: self.fail("must not invoke native"))
        self.assertIsNone(result)
        self.assertEqual(obj.DefinitionData.ManufacturerGradeIndex, 0)
        self.assertIn("partially assigned", str(self.h.runtime.problems))

    def test_native_spec_matches_captured_windows_signature_and_broad_trace_hooks_are_removed(self):
        signature = self.h.runtime.loot.native.signature
        self.assertEqual(signature["path"], self.fixture["native_signature"]["path"])
        self.assertEqual(list(signature["inputs"]), self.fixture["native_signature"]["inputs"])
        self.assertEqual(self.h.runtime.loot.trace.hooks, [])
        self.assertNotIn(("Engine.WillowInventory:GetInventoryDefinition", "PRE"), self.h.callbacks)

    def test_query_npc_health_is_never_called_during_native_item_construction(self):
        obj = self.item()
        enemy = self.actor("WillowAIPawn", "gd_Enemies.Archetypes.NotInitialized")
        enemy.Allegiance = Object("gd_AI_Allegiance.CreatureEnemy.Skag")
        enemy.GetHealth = lambda: self.fail("must not call a method on an uninitialized enemy")
        self.initialize(obj, self.args(obj, enemy))
        self.assertEqual(obj.required, 5)
        self.assertEqual(self.h.runtime.problems, [])

    def test_native_inputs_and_return_value_forwarded_without_void_override(self):
        obj = self.item()
        callback = self.h.mod.native_loot_hook("Test:NativeInit", (*INPUTS, "Extra"), True)
        args = self.args(obj)
        args.Extra = True
        calls = []
        def native(**values):
            calls.append(values)
            return False
        result = callback(obj, args, None, native)
        self.assertEqual(result, (self.h.mod.Block, False))
        self.assertEqual(len(calls), 1)
        self.assertIs(calls[0]["Extra"], True)
        self.assertEqual(calls[0]["InGradeIndex"], 12 << 16)

    def test_item_definition_not_yet_copied_uses_native_balance_without_replacing_parts(self):
        obj = self.item()
        obj.DefinitionData.WeaponTypeDefinition = None
        body = obj.DefinitionData.BodyPartDefinition
        self.initialize(obj)
        self.assertEqual(obj.required, 10)
        self.assertIsNone(obj.DefinitionData.WeaponTypeDefinition)
        self.assertIs(obj.DefinitionData.BodyPartDefinition, body)

    def test_each_definition_fallback_bonus_is_respected(self):
        obj = self.item()
        self.definition.PlayerUseLevelBonus = aid(1)
        self.initialize(obj)
        self.assertEqual((obj.ExpLevel, obj.required), (11, 10))

    def test_definition_guard_unwinds_on_native_exception(self):
        obj = self.item()
        before = self.h.callbacks[(DEF, "PRE")]
        after = self.h.callbacks[(DEF, "POST_UNCONDITIONAL")]
        args = NS(NewDefinitionData=obj.DefinitionData)
        before(obj, args, None, None)
        try:
            self.assertTrue(self.h.runtime.loot.native.definition_scopes)
            raise RuntimeError("native reconstruction failed")
        except RuntimeError:
            pass
        finally:
            after(obj, args, None, None)
        self.assertEqual(self.h.runtime.loot.native.definition_scopes, [])
        self.initialize(obj)
        self.assertEqual(obj.required, 10)


if __name__ == "__main__": unittest.main()
