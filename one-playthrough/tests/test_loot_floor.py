"""Modeled native pool/initializer integration, not Windows engine execution."""

from contextlib import contextmanager
from copy import deepcopy
import json
from types import SimpleNamespace as NS
import tempfile
import unittest

from test_one_playthrough import Harness, Object, aid
from test_item_rewards import balance, grade
from test_settings import SDKSettingsMod

POOL = "WillowGame.ItemPool:SpawnBalancedInventoryFromPool"
INIT = "WillowGame.WillowWeapon:InitializeFromDefinitionData"
DEATH = "WillowGame.WillowPawn:Died"


class LootFloorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.h = Harness(self.tmp.name)
        self.h.enable(20)
        self.balance = balance("Native.Loot.Rifle")
        self.balance.Manufacturers[0].Grades = [grade(7)]
        self.definition = Object("Native.RifleDefinition")
        self.definition.bUsesPlayerLevelRequirement = True
        self.definition.PlayerUseLevelBonus = aid(2)
        self.balance.InventoryDefinition = self.definition
        self.data = NS(BalanceDefinition=self.balance, WeaponTypeDefinition=self.definition,
                       ManufacturerDefinition=self.balance.Manufacturers[0].Manufacturer,
                       ManufacturerGradeIndex=0, BodyPartDefinition=Object("Native.Rifle.Body"))
        self.chest = self.actor("WillowInteractiveObject", "World.Chest")
        self.chest.InteractiveObjectDefinition = Object("gd_InteractiveObjects.Chests.InteractiveObj_TreasureChest")
        self.enemy = self.actor("WillowAIPawn", "World.Enemy")
        self.enemy.Allegiance = Object("gd_AI_Allegiance.CreatureEnemy.Skag")
        self.enemy.GetHealth = lambda: 0
        self.calls = []

    def actor(self, kind, path):
        actor = Object(path)
        actor.Class = NS(Name=kind, _inherits=lambda cls: cls.Name == kind)
        return actor

    @contextmanager
    def pool(self, source):
        args = NS(ContextSource=source, Definition=Object("Native.UnchangedPool"),
                  GameStage=20, AwesomeLevel=42, SpawnedInventory=[])
        before = deepcopy(vars(args))
        self.assertIsNone(self.h.callbacks[(POOL, "PRE")](None, args, None, None))
        try:
            yield
        finally:
            self.h.callbacks[(POOL, "POST_UNCONDITIONAL")](None, args, None, None)
            self.assertEqual(vars(args), before)  # No reroll/stage/quality/quantity changes.

    def initialize(self, data=None):
        data = data or self.data
        result = []
        def native(**values):
            actual = values["NewDefinitionData"]
            self.calls.append(actual)
            raw = actual.ManufacturerGradeIndex >> 16
            if not raw:
                source = actual.BalanceDefinition
                while not source.Manufacturers:
                    source = source.BaseDefinition
                row = next(row for row in source.Manufacturers if row.Manufacturer == actual.ManufacturerDefinition)
                raw = row.Grades[actual.ManufacturerGradeIndex & 0xFFFF].GradeModifiers.ExpLevel
            bonus = self.definition.PlayerUseLevelBonus.BaseValueConstant
            result.append(NS(raw=raw, required=raw - bonus, data=actual, damage=raw * 10))
        blocked = self.h.callbacks[(INIT, "PRE")](None, NS(NewDefinitionData=data), None, native)
        if blocked is None:
            native(NewDefinitionData=data)
        else:
            self.assertIs(blocked, self.h.mod.Block)
        return result[0]

    def test_enemy_and_chest_floor_changes_actual_native_stats_not_just_card(self):
        for source in (self.enemy, self.chest):
            with self.subTest(source=source.path), self.pool(source):
                item = self.initialize()
                self.assertEqual((item.raw, item.required, item.damage), (19, 17, 190))
                self.assertEqual(item.data.ManufacturerGradeIndex, 19 << 16)
        self.assertEqual(len(self.calls), 2)  # Native initialization exactly once per item.
        self.assertEqual(self.h.runtime.loot.raised, 2)
        self.assertEqual(self.data.ManufacturerGradeIndex, 0)

    def test_existing_acceptable_and_higher_levels_are_never_lowered_or_reencoded(self):
        for raw in (19, 20, 22, 30, 71):
            self.balance.Manufacturers[0].Grades[0].GradeModifiers.ExpLevel = raw
            with self.pool(self.chest):
                item = self.initialize()
            self.assertEqual(item.raw, raw)
            self.assertIs(item.data, self.data)
        self.assertEqual(self.h.runtime.loot.raised, 0)

    def test_grade_bits_parts_manufacturer_balance_and_rarity_tables_preserved(self):
        self.balance.Manufacturers[0].Grades.append(grade(10))
        self.data.ManufacturerGradeIndex = 1
        before = deepcopy(vars(self.balance.Manufacturers[0].Grades[1]))
        with self.pool(self.chest):
            item = self.initialize()
        self.assertEqual(item.data.ManufacturerGradeIndex, (19 << 16) | 1)
        for field in vars(self.data):
            if field != "ManufacturerGradeIndex":
                self.assertIs(getattr(item.data, field), getattr(self.data, field))
        self.assertEqual(vars(self.balance.Manufacturers[0].Grades[1]), before)

    def test_inherited_and_correct_manufacturer_grade_are_resolved_without_parent_edits(self):
        parent = self.balance
        child = balance("Native.Loot.CustomRifle")
        child.Manufacturers = []
        child.BaseDefinition = parent
        parent.Manufacturers.insert(0, NS(Manufacturer=Object("Other.Manufacturer"), Grades=[grade(60)]))
        self.data.BalanceDefinition = child
        with self.pool(self.chest):
            self.assertEqual(self.initialize().required, 17)
        self.assertEqual(child.Manufacturers, [])
        self.assertEqual(parent.Manufacturers[1].Grades[0].GradeModifiers.ExpLevel, 7)

    def test_packed_item_level_takes_precedence_and_persists_outside_scope_and_on_disable(self):
        self.data.ManufacturerGradeIndex = (9 << 16) | 0
        with self.pool(self.chest):
            item = self.initialize()
        saved = json.loads(json.dumps({"grade": item.data.ManufacturerGradeIndex}))
        loaded = deepcopy(self.data)
        loaded.ManufacturerGradeIndex = saved["grade"]
        self.h.mod.on_disable()
        self.assertEqual(self.initialize(loaded).required, 17)
        self.assertEqual(self.h.runtime.loot.raised, 1)

    def test_world_existing_inventory_player_drops_vendors_and_unknown_sources_untouched(self):
        self.assertEqual(self.initialize().required, 5)
        vendor = self.actor("WillowVendingMachine", "World.Vendor")
        player = self.actor("WillowPlayerPawn", "World.Player")
        for source in (vendor, player, None):
            with self.pool(source):
                self.assertEqual(self.initialize().required, 5)
        self.assertEqual(self.h.runtime.loot.raised, 0)

    def test_live_enemy_and_friendly_npc_equipment_untouched(self):
        self.enemy.GetHealth = lambda: 100
        with self.pool(self.enemy):
            self.assertEqual(self.initialize().required, 5)
        self.enemy.Allegiance = Object("gd_AI_Allegiance.Friendly.NPC")
        self.enemy.GetHealth = lambda: 0
        with self.pool(self.enemy):
            self.assertEqual(self.initialize().required, 5)

    def test_death_scope_handles_generation_before_health_is_updated(self):
        self.enemy.GetHealth = lambda: 100
        self.h.callbacks[(DEATH, "PRE")](self.enemy, None, None, None)
        with self.pool(self.enemy):
            self.assertEqual(self.initialize().required, 17)
        self.h.callbacks[(DEATH, "POST_UNCONDITIONAL")](self.enemy, None, None, None)
        self.assertEqual(self.h.runtime.loot.deaths, [])
        with self.pool(self.enemy):
            self.assertEqual(self.initialize().required, 5)

    def test_known_white_red_and_knoxx_chests_supported_other_interactives_untouched(self):
        for name in ("InteractiveObj_TreasureChest", "InteractiveObj_Crate_Metal", "InteractiveObj_crimson_Chest"):
            self.chest.InteractiveObjectDefinition = Object("DLC.Custom." + name)
            with self.pool(self.chest):
                self.assertEqual(self.initialize().required, 17)
        self.chest.InteractiveObjectDefinition = Object("Native.NewUStation")
        with self.pool(self.chest):
            self.assertEqual(self.initialize().required, 5)

    def test_unknown_nested_generation_shadows_then_restores_outer_scope(self):
        with self.pool(self.chest):
            with self.pool(None):
                self.assertEqual(self.initialize().required, 5)
            self.assertEqual(self.initialize().required, 17)
        self.assertEqual(self.h.runtime.loot.scopes, [])
        self.assertEqual(self.initialize().required, 5)

    def test_toggle_and_mod_disabled_leave_loot_native(self):
        self.h.mod.loot_floor.value = False
        with self.pool(self.chest):
            self.assertEqual(self.initialize().required, 5)
        self.h.mod.loot_floor.value = True
        self.h.mod.on_disable()
        with self.pool(self.chest):
            self.assertEqual(self.initialize().required, 5)

    def test_levels_one_through_four_keep_a_minimum_requirement_of_one(self):
        self.balance.Manufacturers[0].Grades[0].GradeModifiers.ExpLevel = 2
        for player in range(1, 5):
            self.h.pc.level = player
            with self.pool(self.chest):
                self.assertEqual(self.initialize().required, 1)

    def test_accepted_mission_below_loot_floor_stays_at_accepted_level_even_nested(self):
        def native_level(_pc):
            self.h.mission.GameStage = self.h.mission.ExpLevel = 12
        self.h.mission.RefreshRewardGameStage = native_level
        self.h.runtime.missions.floors.clear()
        self.h.enable(12)
        self.h.mission.ItemRewards = [self.balance]
        self.h.accept()
        self.h.pc.level = 20
        self.h.runtime.sync(self.h.pc)
        items = []
        with self.pool(self.chest):
            self.h.reward(native=lambda: items.append(self.initialize()))
        self.assertEqual(items[0].required, 12)
        self.assertEqual(self.h.runtime.loot.raised, 0)

    def test_equipment_types_use_their_own_fallback_and_skip_non_equipment(self):
        self.definition.PlayerUseLevelBonus = aid(1)
        self.data.ItemDefinition = self.data.WeaponTypeDefinition
        self.data.WeaponTypeDefinition = None
        with self.pool(self.chest):
            self.assertEqual(self.initialize().required, 17)
        for field in ("bMissionItem", "bPlayerUseItemOnPickup"):
            setattr(self.definition, field, True)
            with self.pool(self.chest):
                self.assertEqual(self.initialize().raw, 7)
            setattr(self.definition, field, False)
        self.definition.bUsesPlayerLevelRequirement = False
        with self.pool(self.chest):
            self.assertEqual(self.initialize().raw, 7)
        self.definition.bUsesPlayerLevelRequirement = True
        self.balance.BaseDefinition = Object("Native.StorageDeckUpgrade")
        with self.pool(self.chest):
            self.assertEqual(self.initialize().raw, 7)

    def test_unsupported_formats_are_left_native_and_diagnosed(self):
        self.balance.bInterpolateExpLevel = True
        with self.pool(self.chest):
            self.assertEqual(self.initialize().raw, 7)
        self.assertEqual(self.h.runtime.loot.skipped, {"interpolated format": 1})
        self.balance.bInterpolateExpLevel = False
        self.balance.Manufacturers[0].Grades[0].GradeModifiers.ExpLevel = -2
        with self.pool(self.chest):
            self.assertEqual(self.initialize().raw, -2)
        self.assertEqual(self.h.runtime.loot.skipped["dynamic native item level"], 1)

    def test_generation_failure_unwinds_scope_without_changing_later_inventory(self):
        with self.assertRaisesRegex(RuntimeError, "native pool failed"):
            with self.pool(self.chest):
                raise RuntimeError("native pool failed")
        self.assertEqual(self.h.runtime.loot.scopes, [])
        self.assertEqual(self.initialize().required, 5)

    def test_native_initializer_failure_never_retries(self):
        calls, result = [], []
        def native(**kwargs):
            calls.append(kwargs)
            raise RuntimeError("initializer failed")
        with self.pool(self.chest):
            result.append(self.h.callbacks[(INIT, "PRE")](None, NS(NewDefinitionData=self.data), None, native))
        self.assertEqual(result, [self.h.mod.Block])
        self.assertEqual(len(calls), 1)
        self.assertIn("initializer failed", str(self.h.runtime.problems))

    def test_discovery_exports_actual_context_parameters_and_diagnostics(self):
        report = json.loads(self.h.mod.export_diagnostics().read_text())
        loot = report["loot_level_floor"]
        self.assertEqual(loot["pool_hooks"][0]["context"], "ContextSource")
        self.assertEqual(loot["pool_hooks"][0]["path"], POOL)
        self.assertEqual(loot["active_scopes"], 0)
        self.assertEqual(report["problems"], [])
        fn = self.h.classes["ItemPool"]._fields()[0]
        fn._properties = lambda: [NS(Name="Unknown", Class=NS(Name="ObjectProperty"), PropertyFlags=0x80)]
        self.assertIsNone(self.h.mod.pool_specs(self.h.sdk)[0][1])

    def test_failed_nested_context_read_shadows_outer_scope_and_unwinds(self):
        self.enemy.GetHealth = lambda: (_ for _ in ()).throw(RuntimeError("unavailable health"))
        with self.pool(self.chest):
            with self.pool(self.enemy):
                self.assertEqual(self.initialize().required, 5)
            self.assertEqual(self.initialize().required, 17)
        self.assertEqual(self.h.runtime.loot.scopes, [])
        self.assertIn("unavailable health", str(self.h.runtime.problems))

    def test_unknown_grade_is_not_guessed_and_input_remains_original(self):
        self.data.ManufacturerGradeIndex = 100
        calls = []
        with self.pool(self.chest):
            blocked = self.h.callbacks[(INIT, "PRE")](None, NS(NewDefinitionData=self.data),
                                                     None, lambda **kw: calls.append(kw))
        self.assertIsNone(blocked)
        self.assertEqual(calls, [])  # Original native call remains responsible.
        self.assertEqual(self.data.ManufacturerGradeIndex, 100)
        self.assertEqual(self.h.runtime.loot.skipped, {"unknown manufacturer grade": 1})

    def test_disable_cleans_inflight_pool_and_death_scopes(self):
        self.h.callbacks[(DEATH, "PRE")](self.enemy, None, None, None)
        with self.pool(self.chest):
            self.h.mod.on_disable()
            self.assertEqual(self.h.runtime.loot.scopes, [])
            self.assertEqual(self.h.runtime.loot.deaths, [])
            self.assertEqual(self.initialize().required, 5)
        self.h.callbacks[(DEATH, "POST_UNCONDITIONAL")](self.enemy, None, None, None)
        self.assertEqual(self.h.runtime.loot.scopes, [])
        self.assertEqual(self.h.runtime.loot.deaths, [])

    def test_option_persists_across_restarts(self):
        first = Harness(self.tmp.name, registration_factory=SDKSettingsMod, in_menu=True)
        self.assertTrue(first.mod.loot_floor.value)
        first.mod.loot_floor.value = False
        first.registered_mod.enable()
        second = Harness(self.tmp.name, registration_factory=SDKSettingsMod, in_menu=True)
        self.assertFalse(second.mod.loot_floor.value)


if __name__ == "__main__":
    unittest.main()
