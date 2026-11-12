"""Debug difficulty bypasses only hostile level inputs, never shared identities."""

from copy import deepcopy
from types import SimpleNamespace as NS
import tempfile
import unittest

from test_one_playthrough import Harness,Object,aid
from test_settings import SDKSettingsMod
import test_floors_and_rare as models


class DebugDifficultyTests(unittest.TestCase):
    def setUp(self):
        self.rig=models.Rare('test_all_presets_produce_exact_weighted_levels')
        self.rig.setUp();self.addCleanup(self.rig.doCleanups)
        self.h=self.rig.h
        self.svc=self.h.runtime.spawns
        self.h.mod.enemy_difficulty.value='Debug'

    def test_player_minus_thirty_is_clamped_to_one_at_all_relevant_levels(self):
        for player in (1,2,5,16,29,30,31,32,36,40,69):
            with self.subTest(player=player):
                self.h.enable(player)
                self.rig.args.GameStage=80
                result=self.rig.spawn()
                self.assertEqual(result.level,max(1,player-30))
                self.assertEqual(self.rig.calls[-1][4],80)
                self.assertIs(self.rig.factory.PawnBalanceDefinition,self.rig.definition)

    def test_debug_has_no_random_roll_and_all_tickets_give_same_level(self):
        for ticket in range(100):self.assertEqual(self.rig.spawn(ticket).level,1)
        self.svc.roll=lambda:self.fail('Debug must not roll')
        self.h.mod.create_pawn(self.rig.factory,self.rig.args,None,self.rig.native)
        self.assertEqual(self.rig.calls[-1][4],20)

    def test_named_bosses_across_base_game_and_dlcs_ignore_their_normal_floor(self):
        names=self.svc.plan.__globals__['named_enemy'].__globals__['BALANCE_NAMES']
        self.svc.roll=lambda:self.fail('Debug named enemy must not roll')
        for path in names:
            self.rig.definition.path=path
            stage,clone=self.svc.plan(self.rig.factory,16,80)
            self.assertEqual(stage,80)
            self.assertEqual(clone.DefaultExpLevel.BaseValueConstant,1)
            self.assertTrue(all(g.GradeModifiers.ExpLevel==1 for g in clone.Grades))

    def test_high_fixed_negative_and_dynamic_inputs_are_replaced_only_on_private_clone(self):
        definition=self.rig.definition
        definition.DefaultExpLevel=aid(99)
        definition.DefaultExpLevel.InitializationDefinition=Object('Custom.DynamicLevel')
        definition.Grades.extend(deepcopy(definition.Grades[0]) for _ in range(3))
        for grade,level in zip(definition.Grades,(-25,0,5,99)):grade.GradeModifiers.ExpLevel=level
        before=deepcopy(definition.Grades)
        stage,clone=self.svc.plan(self.rig.factory,20,60)
        self.assertEqual(stage,60)
        self.assertEqual(clone.DefaultExpLevel.BaseValueConstant,1)
        self.assertIsNone(clone.DefaultExpLevel.InitializationDefinition)
        self.assertEqual([g.GradeModifiers.ExpLevel for g in clone.Grades],[1]*4)
        for original,copied,expected in zip(definition.Grades,clone.Grades,before):
            self.assertEqual(original.GradeModifiers.ExpLevel,expected.GradeModifiers.ExpLevel)
            self.assertEqual(vars(copied.GameStageRequirement),vars(original.GameStageRequirement))
            self.assertEqual(copied.GradeModifiers.HealthMultiplier,original.GradeModifiers.HealthMultiplier)
            self.assertEqual(copied.GradeModifiers.DamageMultiplier,original.GradeModifiers.DamageMultiplier)
        self.assertEqual(definition.DefaultExpLevel.BaseValueConstant,99)

    def test_no_grade_definition_uses_low_exact_default(self):
        self.rig.definition.Grades=[]
        stage,clone=self.svc.plan(self.rig.factory,20,60)
        self.assertEqual(stage,60)
        self.assertEqual(clone.DefaultExpLevel.BaseValueConstant,1)

    def test_debug_constant_level_does_not_need_native_stage_attribute(self):
        self.h.sdk.find_object=lambda *args:None
        self.assertEqual(self.rig.spawn().level,1)

    def test_ordinary_and_named_hostile_vehicles_follow_debug_level(self):
        archetype=self.rig.definition.AIPawnArchetype
        factory=NS(VehicleBalanceDefinition=self.rig.definition,VehicleArchetype=archetype)
        self.svc.roll=lambda:self.fail('Debug vehicle must not roll')
        for path in ('Native.Vehicle','gd_cheetahspaw.vehiclearchetype.mad_mel'):
            archetype.path=path
            stage,clone=self.svc.plan(factory,20,60,vehicle=True)
            self.assertEqual(stage,60)
            self.assertEqual(clone.DefaultExpLevel.BaseValueConstant,1)
            self.assertEqual(clone.Grades[0].GradeModifiers.ExpLevel,1)
            self.assertIs(factory.VehicleBalanceDefinition,self.rig.definition)

    def test_friendly_neutral_player_and_unknown_allegiances_are_untouched(self):
        for allegiance in ('Native.Friendly.NPC','Native.Neutral','Native.Player',None):
            self.rig.definition.AIPawnArchetype.Allegiance=Object(allegiance) if allegiance else None
            stage,clone=self.svc.plan(self.rig.factory,20,60)
            self.assertEqual(stage,60)
            self.assertIsNone(clone)

    def test_switching_back_to_very_hard_keeps_original_weights_and_old_debug_pawn(self):
        old=self.rig.spawn()
        self.h.mod.enemy_difficulty.value='Very Hard'
        new=self.rig.spawn(99)
        self.assertEqual((old.level,new.level),(1,25))
        self.assertEqual(old.definition.DefaultExpLevel.BaseValueConstant,1)
        self.assertEqual(self.svc.snapshot()['ordinary_tickets'],
                         {'native':0,'+1':0,'+2':0,'+3':40,'+4':58,'+5':2})
        self.h.mod.enemy_difficulty.value='Debug'
        self.assertEqual(self.rig.spawn().level,1)
        self.assertEqual(new.definition.Grades[0].GradeModifiers.ExpLevel,0)

    def test_switching_back_restores_named_plus_three_minimum(self):
        self.rig.definition.path='gd_Balance_Enemies_Humans.Bandits.Named.Pawn_Balance_Bonehead'
        old=self.rig.spawn()
        self.h.mod.enemy_difficulty.value='Normal'
        self.assertEqual(self.rig.spawn().level,23)
        self.assertEqual(old.definition.Grades[0].GradeModifiers.ExpLevel,1)

    def test_disable_and_native_failure_restore_factory_without_retry(self):
        calls=[]
        def fail(*args):
            calls.append(args)
            raise RuntimeError('native debug spawn failed')
        result=self.h.mod.create_pawn(self.rig.factory,self.rig.args,None,fail)
        self.assertIs(result[0],self.h.mod.Block)
        self.assertEqual(len(calls),1)
        self.assertIs(self.rig.factory.PawnBalanceDefinition,self.rig.definition)
        self.h.mod.on_disable()
        self.assertEqual(self.rig.spawn().level,19)

    def test_debug_diagnostics_report_fixed_rule_and_no_tickets(self):
        report=self.svc.snapshot()
        self.assertEqual(report['difficulty'],'Debug')
        self.assertEqual(report['ordinary_tickets'],{})
        self.assertEqual(report['native_floor'],'exactly max(1, player level - 30)')
        self.assertEqual(report['named_level'],report['native_floor'])

    def test_debug_setting_persists_and_normal_remains_default(self):
        with tempfile.TemporaryDirectory() as folder:
            first=Harness(folder,registration_factory=SDKSettingsMod,in_menu=True)
            self.assertEqual(first.mod.enemy_difficulty.value,'Normal')
            first.mod.enemy_difficulty.value='Debug'
            first.registered_mod.save_settings()
            second=Harness(folder,registration_factory=SDKSettingsMod,in_menu=True)
            self.assertEqual(second.mod.enemy_difficulty.value,'Debug')
            self.assertEqual(second.runtime.spawns.selected_difficulty(),'Debug')


if __name__=='__main__':unittest.main()
