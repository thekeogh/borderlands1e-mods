"""Captured Bone Head path with modeled native actors/pickups, not Windows execution."""

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace as NS
import tempfile
import unittest

from test_one_playthrough import Harness, Object, aid
from test_item_rewards import balance

DEATH = "WillowGame.WillowPawn:Died"
DROP = "WillowGame.WillowWeapon:DropFrom"


class CarriedLootTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.h = Harness(self.tmp.name)
        self.h.enable(12)
        self.fixture = json.loads((Path(__file__).parent / 'fixtures/bl1e_bonehead_carried.json').read_text())
        self.svc = self.h.runtime.loot.carried
        # Exact initializer signature captured by 4.5.1 on BL1E.
        self.svc.initializers = {kind: ('NewDefinitionData', 'InAdditionalQueryInterfaceSource',
                                      'bForceSelectNameParts') for kind in ('weapon', 'item')}
        self.pickups = []
        self.clones = []
        self.init_calls = []
        self.drop_calls = []
        self.destroy_calls = []
        self.fault = None
        self.boss = Object(self.fixture['death_before']['actor'])
        self.boss.Class = NS(Name='WillowAIPawn', _inherits=lambda cls: cls.Name == 'WillowAIPawn')
        self.boss.BalanceDefinitionState = NS(BalanceDefinition=Object(self.fixture['death_before']['balance']))
        self.boss.Allegiance = Object('gd_AI_Allegiance.HumanEnemy.Bandit')
        self.boss.Owner = None
        self.boss.InvManager = None
        self.boss.GetHealth = lambda: self.fail('must not call boss health')
        self.boss.GetExpLevel = lambda: self.fail('must not call boss level')
        data = self.fixture['drop_before']['definition_data']
        self.definition = Object(data['WeaponTypeDefinition'])
        self.definition.bUsesPlayerLevelRequirement = True
        self.definition.PlayerUseLevelBonus = aid(2)
        self.balance = balance(data['BalanceDefinition'])
        self.balance.InventoryDefinition = self.definition
        fields = {k: Object(v) if isinstance(v, str) else v for k,v in data.items()}
        fields['BalanceDefinition'] = self.balance
        fields['WeaponTypeDefinition'] = self.definition
        self.original = Object(self.fixture['drop_before']['object'])
        self.original.DefinitionData = NS(**fields)
        self.original.ExpLevel = self.fixture['drop_before']['internal_level']
        self.original.RarityLevel = 18
        self.original.Owner = self.boss
        self.original.Class = self.h.classes['WillowWeapon']
        self.original.bDeleteMe = False
        self.original.Quantity, self.original.AwesomeLevel, self.original.OwnerStatsID = 1, 0, 0
        self.original.MinRarityLevel, self.original.MaxRarityLevel = -1, 999
        self.retirement_fields(self.original)
        self.original.Destroy = lambda: self.fail('BL1E direct Destroy must not be used')
        self.boss.Weapon = self.original
        self.h.inventory.append(self.original)
        self.args = NS(StartLocation=NS(X=10,Y=20,Z=30), StartVelocity=NS(X=1,Y=2,Z=3),
                       bForceNoRBPhysics=False)
        old_find = self.h.sdk.find_all
        self.h.sdk.find_all = lambda name, **kw: self.pickups if name == 'WillowPickup' else old_find(name, **kw)
        self.h.pc.Spawn = self.spawn
        self.native_drop_count = 0

    @staticmethod
    def retirement_fields(actor):
        actor.LifeSpan = 0.0
        actor.bHidden = False
        actor.bPendingDelete = False
        actor.bPickupable = True
        actor.bStatic = actor.bNoDelete = False

    def expire(self):
        # Model the engine's own timeout cleanup; direct Destroy is refused.
        for pickup in self.pickups:
            if not pickup.bDeleteMe and 0 < pickup.LifeSpan <= 0.01:
                self.destroy_actor(pickup)
                if not pickup.Inventory.bDeleteMe:
                    self.destroy_actor(pickup.Inventory)
        for clone in self.clones:
            if not clone.bDeleteMe and 0 < clone.LifeSpan <= 0.01:
                self.destroy_actor(clone)

    def destroy_actor(self, actor):
        self.destroy_calls.append(actor)
        actor.bDeleteMe = actor.bPendingDelete = True
        return True

    def pickup(self, inventory):
        pickup = Object('World.Pickup_' + str(len(self.pickups)))
        pickup.Inventory = inventory
        pickup.bDeleteMe = False
        self.retirement_fields(pickup)
        pickup.Destroy = lambda: self.fail('BL1E direct Destroy must not be used')
        self.pickups.append(pickup)
        return pickup

    def spawn(self, cls):
        if self.fault == 'spawn': return None
        clone = Object('World.Replacement_' + str(len(self.clones)))
        clone.Class = cls
        clone.Owner = None
        clone.bDeleteMe = False
        self.retirement_fields(clone)
        clone.Destroy = lambda: self.fail('BL1E direct Destroy must not be used')
        def initialize(**values):
            self.init_calls.append((clone, values))
            if self.fault == 'initialize': raise RuntimeError('initializer failed')
            clone.DefinitionData = deepcopy(values['NewDefinitionData'])
            clone.ExpLevel = clone.DefinitionData.ManufacturerGradeIndex >> 16
            clone.RarityLevel = self.original.RarityLevel
            clone.damage = clone.ExpLevel * 10
            if self.fault == 'parts': clone.DefinitionData.BarrelPartDefinition = Object('Wrong.Barrel')
            if self.fault == 'rarity': clone.RarityLevel += 1
            if self.fault == 'level': clone.ExpLevel = 5
        def drop(location, velocity, no_physics):
            self.drop_calls.append((clone, location, velocity, no_physics))
            if self.fault == 'drop': raise RuntimeError('replacement drop failed')
            if self.fault != 'missing copy pickup': self.pickup(clone)
        clone.InitializeFromDefinitionData, clone.DropFrom = initialize, drop
        self.clones.append(clone)
        return clone

    def begin(self):
        self.h.callbacks[(DEATH,'PRE')](self.boss,NS(),None,None)

    def drop_original(self):
        data = vars(self.original.DefinitionData).copy()
        self.assertIsNone(self.h.callbacks[(DROP,'PRE')](self.original,self.args,None,None))
        self.assertEqual(vars(self.original.DefinitionData), data)
        self.assertEqual(self.original.ExpLevel, 5)  # Boss's gun never changes during combat/drop.
        self.native_drop_count += 1
        self.original.Owner = None  # Model the game's original detach/drop.
        old = self.pickup(self.original)
        self.assertIsNone(self.h.callbacks[(DROP,'POST_UNCONDITIONAL')](self.original,self.args,None,None))
        return old

    def end(self):
        self.boss.Weapon = None
        self.h.callbacks[(DEATH,'POST_UNCONDITIONAL')](self.boss,NS(),None,None)
        self.expire()

    def live_pickups(self):
        return [p for p in self.pickups if not p.bDeleteMe and not p.bPendingDelete and p.bPickupable]

    def test_captured_level_three_becomes_ten_only_after_native_death_drop(self):
        self.assertEqual(self.fixture['player_level'],12)
        self.assertEqual(self.fixture['drop_before']['internal_level'],5)
        original_data = vars(self.original.DefinitionData).copy()
        self.begin()
        old_pickup = self.drop_original()
        self.assertFalse(old_pickup.bDeleteMe)  # Retirement waits for native death iteration to finish.
        self.assertFalse(self.original.bDeleteMe)
        self.assertEqual(self.svc.changed,0)
        self.assertEqual(len(self.clones),1)
        self.end()
        clone = self.clones[0]
        self.assertEqual((clone.ExpLevel,clone.ExpLevel-2,clone.damage),(12,10,120))
        self.assertEqual(len(self.live_pickups()),1)
        self.assertIs(self.live_pickups()[0].Inventory,clone)
        self.assertTrue(old_pickup.bDeleteMe)
        self.assertTrue(self.original.bDeleteMe)
        self.assertEqual(vars(self.original.DefinitionData),original_data)
        self.assertEqual(self.original.ExpLevel,5)
        self.assertEqual(clone.RarityLevel,self.original.RarityLevel)
        for key,value in original_data.items():
            if key != 'ManufacturerGradeIndex': self.assertIs(getattr(clone.DefinitionData,key),value)
        self.assertEqual(clone.DefinitionData.ManufacturerGradeIndex,12 << 16)
        self.assertEqual(len(self.init_calls),1)
        self.assertIsNone(self.init_calls[0][1]['InAdditionalQueryInterfaceSource'])
        self.assertIs(self.init_calls[0][1]['bForceSelectNameParts'],False)
        self.assertEqual(self.native_drop_count,1)
        self.assertEqual(len(self.drop_calls),1)
        self.assertEqual(self.drop_calls[0][1:],(self.args.StartLocation,self.args.StartVelocity,False))
        self.assertEqual(self.svc.changed,1)
        self.assertEqual(self.svc.pending,{})
        self.assertEqual(self.h.runtime.loot.deaths,[])
        self.assertEqual(self.h.runtime.problems,[])

    def test_all_hostile_death_scopes_use_same_rule_without_boss_id_list(self):
        self.boss.BalanceDefinitionState.BalanceDefinition = Object('gd_Balance_Enemies_Creatures.Skags.Named.Pawn_Scar')
        self.balance.path = 'Native.Other.NamedUnique'
        self.begin(); self.drop_original(); self.end()
        self.assertEqual(self.svc.changed,1)
        self.assertEqual(self.live_pickups()[0].Inventory.ExpLevel-2,10)

    def test_failure_before_commit_keeps_original_pickup_and_cleans_copy(self):
        for fault in ('spawn','initialize','parts','rarity','level','drop','missing copy pickup'):
            with self.subTest(fault=fault):
                # Separate rig per failure; no accumulated actor/scoping effects.
                rig = CarriedLootTests('test_captured_level_three_becomes_ten_only_after_native_death_drop')
                rig.setUp()
                try:
                    rig.fault = fault
                    rig.begin(); old = rig.drop_original(); rig.end()
                    self.assertEqual(rig.live_pickups(),[old])
                    self.assertFalse(rig.original.bDeleteMe)
                    self.assertEqual(rig.original.ExpLevel,5)
                    self.assertEqual(rig.svc.changed,0)
                    self.assertEqual(rig.svc.pending,{})
                    self.assertTrue(rig.h.runtime.problems)
                    self.assertTrue(all(c.bDeleteMe for c in rig.clones))
                finally:
                    rig.doCleanups()

    def test_original_pickup_retirement_failure_preserves_original_without_duplicate(self):
        self.begin(); old = self.drop_original()
        old.bNoDelete = True
        self.end()
        self.assertEqual(self.live_pickups(),[old])
        self.assertFalse(self.original.bDeleteMe)
        self.assertTrue(self.clones[0].bDeleteMe)
        self.assertEqual(self.svc.changed,0)
        self.assertEqual(self.svc.pending,{})

    def test_native_expiry_cleans_inventory_once_without_direct_destroy(self):
        self.begin(); old = self.drop_original()
        self.end()
        self.assertEqual(self.destroy_calls.count(self.original),1)
        self.assertEqual(len(self.live_pickups()),1)
        self.assertEqual(self.svc.changed,1)

    def test_native_drop_failure_to_make_pickup_leaves_existing_item_untouched(self):
        self.begin()
        self.h.callbacks[(DROP,'PRE')](self.original,self.args,None,None)
        self.original.Owner = None
        self.h.callbacks[(DROP,'POST_UNCONDITIONAL')](self.original,self.args,None,None)
        self.end()
        self.assertEqual(self.clones,[])
        self.assertFalse(self.original.bDeleteMe)
        self.assertEqual(self.svc.changed,0)
        self.assertEqual(self.svc.skipped['original pickup not uniquely identified'],1)

    def test_player_and_live_enemy_drops_do_not_spawn_copies(self):
        self.assertIsNone(self.svc.prepare(self.original,self.args,self.h.pc))
        self.original.Owner = self.h.pc
        self.begin()
        self.assertIsNone(self.svc.prepare(self.original,self.args,self.h.pc))
        self.end()
        self.assertEqual(self.clones,[])

    def test_already_high_level_equipment_never_replaced(self):
        self.original.ExpLevel = 16
        self.begin()
        self.assertIsNone(self.svc.prepare(self.original,self.args,self.h.pc))
        self.end()
        self.assertEqual(self.clones,[])

    def test_mod_toggle_or_mission_scope_excludes_carried_floor(self):
        self.begin()
        self.h.mod.loot_floor.value = False
        self.assertIsNone(self.svc.prepare(self.original,self.args,self.h.pc))
        self.h.mod.loot_floor.value = True
        self.h.runtime.missions.scopes.append((object(),None,3,NS()))
        self.assertIsNone(self.svc.prepare(self.original,self.args,self.h.pc))
        self.h.runtime.missions.scopes.clear()
        self.end()
        self.assertEqual(self.clones,[])

    def test_disable_between_drop_and_commit_retires_only_uncommitted_copy(self):
        self.begin(); old = self.drop_original()
        self.h.mod.loot_floor.value = False
        self.end()
        self.assertEqual(self.live_pickups(),[old])
        self.assertFalse(self.original.bDeleteMe)
        self.assertTrue(self.clones[0].bDeleteMe)
        self.assertEqual(self.svc.pending,{})

    def test_non_equipment_and_interpolated_formats_remain_native(self):
        self.begin()
        self.definition.bMissionItem = True
        self.assertIsNone(self.svc.prepare(self.original,self.args,self.h.pc))
        self.definition.bMissionItem = False
        self.balance.bInterpolateExpLevel = True
        self.assertIsNone(self.svc.prepare(self.original,self.args,self.h.pc))
        self.end()
        self.assertEqual(self.clones,[])

    def test_item_drop_uses_same_floor_and_preserves_quantity(self):
        self.original.DefinitionData.ItemDefinition = self.definition
        self.original.DefinitionData.WeaponTypeDefinition = None
        self.original.Quantity = 2
        path = 'WillowGame.WillowItem:DropFrom'
        self.begin()
        self.h.callbacks[(path,'PRE')](self.original,self.args,None,None)
        self.original.Owner = None
        old = self.pickup(self.original)
        self.h.callbacks[(path,'POST_UNCONDITIONAL')](self.original,self.args,None,None)
        self.end()
        self.assertTrue(old.bDeleteMe)
        self.assertEqual(self.clones[0].ExpLevel-2,10)
        self.assertEqual(self.clones[0].Quantity,2)

    def test_low_level_carried_floor_is_never_zero_or_negative(self):
        for player in range(1,5):
            self.h.pc.level = player
            self.original.ExpLevel = 1
            self.begin()
            plan = self.svc.prepare(self.original,self.args,self.h.pc)
            self.assertEqual(plan['floor'],max(1,player-2))
            self.assertEqual(plan['data'].ManufacturerGradeIndex >> 16,max(1,player-2)+2)
            self.end()

    def test_replacement_grade_survives_modeled_save_and_copy(self):
        self.begin(); self.drop_original(); self.end()
        encoded = self.live_pickups()[0].Inventory.DefinitionData.ManufacturerGradeIndex
        saved = json.loads(json.dumps({'grade':encoded}))
        self.h.pc.level = 30
        # Native explicit-level format survives without any active floor/scopes.
        self.assertEqual((saved['grade'] >> 16)-2,10)
        self.assertEqual(saved['grade'] & 0xFFFF,0)
        self.assertEqual(self.svc.changed,1)

    def test_partial_expiry_setter_exception_keeps_verified_replacement(self):
        self.begin(); old = self.drop_original()
        class PartialExpiry(Object):
            @property
            def LifeSpan(self): return self.expiry
            @LifeSpan.setter
            def LifeSpan(self,value):
                self.expiry = value
                if value == 0.01 and self.fail_once:
                    self.fail_once = False
                    raise RuntimeError('expiry setter failed after scheduling')
        old.__class__ = PartialExpiry
        old.expiry = 0.0
        old.fail_once = True
        self.end()
        self.assertEqual(len(self.live_pickups()),1)
        self.assertIs(self.live_pickups()[0].Inventory,self.clones[0])
        self.assertEqual(self.svc.changed,1)
        self.assertTrue(self.original.bDeleteMe)
        self.assertEqual(self.svc.pending,{})

    def test_retirement_disables_pickup_immediately_and_keeps_no_cross_frame_references(self):
        self.begin(); old = self.drop_original()
        self.boss.Weapon = None
        self.h.callbacks[(DEATH,'POST_UNCONDITIONAL')](self.boss,NS(),None,None)
        self.assertFalse(old.bDeleteMe)  # Native expiry runs on a later engine tick.
        self.assertFalse(old.bPickupable)
        self.assertTrue(old.bHidden)
        self.assertEqual(old.LifeSpan,0.01)
        self.assertEqual(self.svc.pending,{})
        self.assertEqual(len(self.live_pickups()),1)
        self.assertIs(self.live_pickups()[0].Inventory,self.clones[0])
        self.assertEqual(self.svc.recent[-1]['retirement'],'native pickup expiry')
        self.expire()
        self.assertTrue(old.bDeleteMe)
        self.assertTrue(self.original.bDeleteMe)
        self.assertFalse(self.clones[0].bDeleteMe)

    def test_expiry_write_failure_restores_original_pickup_before_cleaning_copy(self):
        self.begin(); old = self.drop_original()
        class RefuseExpiry(Object):
            @property
            def LifeSpan(self): return self.expiry
            @LifeSpan.setter
            def LifeSpan(self,value):
                if value == 0.01: raise RuntimeError('expiry refused before scheduling')
                self.expiry = value
        old.__class__ = RefuseExpiry
        old.expiry = 0.0
        self.end()
        self.assertFalse(old.bHidden)
        self.assertTrue(old.bPickupable)
        self.assertEqual(old.LifeSpan,0.0)
        self.assertEqual(self.live_pickups(),[old])
        self.assertFalse(self.original.bDeleteMe)
        self.assertTrue(self.clones[0].bDeleteMe)
        self.assertEqual(self.svc.changed,0)

    def test_captured_level_fifteen_bone_shredder_was_native_not_a_successful_floor(self):
        fixture=json.loads((Path(__file__).parent/'fixtures/bl1e_carried_cleanup_failure.json').read_text())
        for case in fixture['cases']:
            self.assertEqual(case['bone_item']['required'],15)
            self.assertEqual(case['bone_item']['internal_level'],17)
            self.assertEqual(case['bone_item']['grade'],1)
            self.assertEqual(case['carried']['changed'],0)
            self.assertTrue(any('could not be retired' in msg for msg in case['errors']))
        self.h.pc.level=13
        self.original.ExpLevel=17
        self.original.DefinitionData.ManufacturerGradeIndex=1
        self.begin()
        self.assertIsNone(self.svc.prepare(self.original,self.args,self.h.pc))
        self.end()
        self.assertEqual(self.svc.changed,0)
        self.assertEqual(self.clones,[])

    def test_protected_original_pickup_skips_before_spawning_any_copy(self):
        self.begin()
        self.h.callbacks[(DROP,'PRE')](self.original,self.args,None,None)
        self.original.Owner=None
        old=self.pickup(self.original)
        old.bStatic=True
        self.h.callbacks[(DROP,'POST_UNCONDITIONAL')](self.original,self.args,None,None)
        self.end()
        self.assertEqual(self.clones,[])
        self.assertEqual(self.live_pickups(),[old])
        self.assertTrue(old.bPickupable)
        self.assertFalse(old.bHidden)
        self.assertEqual(self.svc.skipped['protected original pickup'],1)
        self.assertEqual(self.h.runtime.problems,[])

    def test_f10_records_general_carried_replacement_and_no_pending_actors(self):
        self.begin(); self.drop_original(); self.end()
        d=json.loads(self.h.mod.export_diagnostics().read_text())['loot_level_floor']['carried_death_loot']
        self.assertEqual(d['changed'],1)
        self.assertEqual(d['pending'],0)
        self.assertEqual(d['recent'][0]['old_internal_level'],5)
        self.assertEqual(d['recent'][0]['target_internal_level'],12)
        self.assertEqual(d['recent'][0]['floor'],10)


if __name__ == '__main__': unittest.main()
