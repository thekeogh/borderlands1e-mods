"""Captured Lady Finger mismatch; native static evaluation is explicitly modeled."""

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace as NS
import tempfile
import unittest

from test_one_playthrough import Harness, Object, aid
from test_item_rewards import balance, grade


class RequirementTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.h = Harness(self.tmp.name)
        self.fixture = json.loads((Path(__file__).parent/'fixtures/bl1e_lady_finger_requirement.json').read_text())
        self.definition = Object(self.fixture['item']['inventory_definition'])
        self.definition.bUsesPlayerLevelRequirement = True
        self.attribute = Object(self.fixture['bonus']['BaseValueAttribute'])
        self.attribute.Name = 'Proficiency_Pistol_LevelBonus'
        self.attribute.AttributeContextClass = None
        self.attribute.bIsSimpleAttribute = self.fixture['attribute']['fields']['bIsSimpleAttribute']
        self.attribute.ContextResolverChain = [NS(Class=NS(Name='NoContextNeededAttributeContextResolver'))]
        self.attribute.ValueResolverChain = [NS(Class=NS(Name='SimpleMathValueResolver'))]
        # Inferred from the captured 5 -> 3 native requirement, not captured evaluator output.
        self.attribute.native_value = 2
        self.definition.PlayerUseLevelBonus = NS(**self.fixture['bonus'])
        self.definition.PlayerUseLevelBonus.BaseValueAttribute = self.attribute
        self.convert = self.h.mod.prepare_definition_data.__globals__['internal_level']
        self.describe = self.convert.__globals__['describe']
        self.reward = balance(self.fixture['item']['fields']['DefinitionData']['BalanceDefinition'])
        self.reward.InventoryDefinition = self.definition
        self.reward.Manufacturers[0].Grades = [grade(4)]
        self.reward.Manufacturers[0].Grades[0].GradeModifiers.CustomInventoryDefinition = None
        self.data = NS(**{key:Object(value) if isinstance(value,str) else value
                         for key,value in self.fixture['item']['fields']['DefinitionData'].items()})
        self.data.BalanceDefinition = self.reward
        self.data.ManufacturerDefinition = self.reward.Manufacturers[0].Manufacturer
        self.data.WeaponTypeDefinition = self.definition
        self.data.ManufacturerGradeIndex = 0
        self.h.enable(6)

    def test_captured_failure_reproduces_fallback_underestimate(self):
        f = self.fixture
        self.assertEqual((f['player_level'],f['item']['native_required_level']), (6,3))
        self.assertEqual((f['floor_event']['floor'],f['floor_event']['packed_grade'] >> 16), (4,5))
        self.assertEqual(f['bonus']['BaseValueConstant'],1)
        self.assertEqual(f['item']['fields']['ExpLevel']-f['item']['native_required_level'],2)
        self.assertEqual(self.convert(self.definition,4),6)
        self.assertEqual(self.h.attribute_evaluations[-1],(self.definition.PlayerUseLevelBonus,None))
        self.assertEqual(self.definition.PlayerUseLevelBonus.BaseValueConstant,1)

    def test_grave_and_vendor_native_initializers_use_resolved_bonus(self):
        for source_kind in ('WillowInteractiveObject','WillowVendingMachine'):
            with self.subTest(source=source_kind):
                actor = Object('World.NewLadyFinger')
                actor.Owner = None
                actor.DefinitionData = deepcopy(self.data)
                query = Object('World.Source')
                cls = Object('WillowGame.'+source_kind)
                cls.Name = source_kind
                self.h.classes[source_kind] = cls
                query.Class = NS(Name=source_kind,_inherits=lambda c:c.Name==source_kind)
                query.Owner = None
                args = NS(InBalanceDef=self.reward,InManufacturer=self.data.ManufacturerDefinition,
                          InGradeIndex=0,InAdditionalQueryInterfaceSource=query)
                calls=[]
                def native(**values):
                    calls.append(values)
                    actor.ExpLevel = values['InGradeIndex'] >> 16
                    actor.required = actor.ExpLevel-self.attribute.native_value
                    actor.damage = actor.ExpLevel*10
                result=self.h.callbacks[('Engine.WillowInventory:InitializeInventory','PRE')](actor,args,None,native)
                self.assertIs(result,self.h.mod.Block)
                self.assertEqual(len(calls),1)
                self.assertEqual((actor.ExpLevel,actor.required,actor.damage),(6,4,60))
                self.assertEqual(actor.DefinitionData.ManufacturerGradeIndex,6 << 16)
                for key in vars(self.data):
                    if key!='ManufacturerGradeIndex':
                        self.assertIs(getattr(actor.DefinitionData,key),getattr(self.data,key))

    def test_mission_grade_and_packed_reward_both_follow_accepted_level(self):
        self.h.mission.ItemRewards=[self.reward]
        self.h.enable(20)
        self.h.accept()
        self.h.pc.level=30
        self.h.runtime.sync(self.h.pc)
        got=[]
        def native_reward():
            self.assertEqual(self.reward.Manufacturers[0].Grades[0].GradeModifiers.ExpLevel,22)
            args=NS(NewDefinitionData=self.data)
            path='WillowGame.WillowWeapon:InitializeFromDefinitionData'
            try:
                result=self.h.callbacks[(path,'PRE')](None,args,None,
                    lambda **values:got.append(values['NewDefinitionData']))
                self.assertIs(result,self.h.mod.Block)
            finally:
                self.h.callbacks[(path,'POST_UNCONDITIONAL')](None,args,None,None)
        self.h.reward(native=native_reward)
        self.assertEqual((got[0].ManufacturerGradeIndex >> 16)-2,20)
        self.assertEqual(self.reward.Manufacturers[0].Grades[0].GradeModifiers.ExpLevel,4)
        self.assertEqual(self.data.ManufacturerGradeIndex,0)

    def test_carried_pistol_conversion_uses_same_native_bonus(self):
        from test_carried_loot import CarriedLootTests
        rig=CarriedLootTests('test_captured_level_three_becomes_ten_only_after_native_death_drop')
        rig.setUp()
        try:
            rig.h.pc.level=6
            rig.definition=self.definition
            rig.balance=self.reward
            rig.original.DefinitionData=deepcopy(self.data)
            rig.original.ExpLevel=5
            rig.original.DefinitionData.ManufacturerGradeIndex=5 << 16
            rig.begin();rig.drop_original();rig.end()
            self.assertEqual(rig.svc.changed,1)
            self.assertEqual(rig.live_pickups()[0].Inventory.ExpLevel,6)
            self.assertEqual(rig.live_pickups()[0].Inventory.ExpLevel-2,4)
        finally:
            rig.doCleanups()

    def test_no_attribute_keeps_custom_constant_bonus(self):
        self.definition.PlayerUseLevelBonus.BaseValueAttribute=None
        self.assertEqual(self.convert(self.definition,4),5)
        self.assertEqual(self.h.attribute_evaluations,[])

    def test_native_evaluator_applies_scale_once(self):
        self.definition.PlayerUseLevelBonus.BaseValueScaleConstant=3
        self.assertEqual(self.convert(self.definition,4),10)
        self.assertEqual(len(self.h.attribute_evaluations),1)

    def test_captured_constant_gear_resolver_remains_supported(self):
        metadata=self.fixture['other_bonus_attributes']['gd_Balance.LevelLimits.Proficiency_Gear_LevelBonus']
        self.assertIn('ConstantAttributeValueResolver',metadata['fields']['ValueResolverChain'][0])
        self.attribute.Name='Proficiency_Gear_LevelBonus'
        self.attribute.ValueResolverChain[0].Class.Name='ConstantAttributeValueResolver'
        self.assertEqual(self.convert(self.definition,4),6)
        self.assertEqual(self.describe(self.definition)['resolved_bonus'],2)
        self.assertTrue(all(context is None for _bonus,context in self.h.attribute_evaluations))

    def test_context_dependent_or_unknown_resolvers_never_evaluated(self):
        self.attribute.ContextResolverChain[0].Class.Name='PawnAttributeContextResolver'
        with self.assertRaisesRegex(ValueError,'context-dependent'):self.convert(self.definition,4)
        self.assertEqual(self.h.attribute_evaluations,[])
        self.attribute.ContextResolverChain[0].Class.Name='NoContextNeededAttributeContextResolver'
        self.attribute.ValueResolverChain[0].Class.Name='CustomUnknownResolver'
        with self.assertRaisesRegex(ValueError,'context-dependent'):self.convert(self.definition,4)
        self.assertEqual(self.h.attribute_evaluations,[])

    def test_invalid_native_result_fails_before_item_mutation(self):
        for value in (float('nan'),float('inf'),1.5,-1):
            self.attribute.native_value=value
            with self.assertRaises(ValueError):self.convert(self.definition,4)
        self.assertEqual(self.data.ManufacturerGradeIndex,0)
        self.assertEqual(self.definition.PlayerUseLevelBonus.BaseValueConstant,1)

    def test_native_failure_does_not_fall_back_to_wrong_constant(self):
        def fail(*a):raise RuntimeError('native evaluator unavailable')
        self.h.classes['AttributeInitializationDefinition'].ClassDefaultObject.EvaluateInitializationData=fail
        with self.assertRaisesRegex(RuntimeError,'native evaluator unavailable'):self.convert(self.definition,4)
        report=self.describe(self.definition)
        self.assertIn('native evaluator unavailable',report['error'])
        self.assertNotIn('resolved_bonus',report)

    def test_f10_reports_resolved_bonus_independent_of_large_definition_graph(self):
        actor=Object('World.LadyFinger')
        actor.GetInventoryDefinition=lambda:self.definition
        actor.GetControllerPlayerExpLevelRequiredToUse=lambda _pc:3
        self.h.inventory.append(actor)
        report=json.loads(self.h.mod.export_diagnostics().read_text())
        use=report['economy']['use_level_bonuses'][self.definition.path]
        self.assertEqual(use['fallback_constant'],1)
        self.assertEqual(use['resolved_bonus'],2)
        self.assertEqual(use['resolution'],'native context-free attribute')
        self.assertEqual(use['contexts'],['NoContextNeededAttributeContextResolver'])
        self.assertFalse(report['partial'])

    def test_low_levels_and_all_item_types_share_native_static_conversion(self):
        for name in ('WeaponType_Repeater','Native.Shield','Native.ClassMod','Native.GrenadeMod'):
            self.definition.path=name
            for required in (1,2,4,69):
                self.assertEqual(self.convert(self.definition,required),required+2)
        self.assertTrue(all(context is None for _bonus,context in self.h.attribute_evaluations))


if __name__=='__main__':unittest.main()
