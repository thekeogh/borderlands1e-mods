"""Captured-definition regressions; native spawning/reward calls are modeled."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest

from test_one_playthrough import Harness, Object, aid

FIXTURE = json.loads((Path(__file__).parent/'fixtures/bl1e_catalog_audit.json').read_text())


def captured():
    objects = {r['path'].lower():Object(r['path']) for r in FIXTURE['objects']}
    def convert(v):
        if isinstance(v,dict):
            if '$ref' in v:
                key = v['$ref'].lower()
                return objects.setdefault(key,Object(v['$ref']))
            if v.get('$type') == 'array':return [convert(x) for x in v['items']]
            if v.get('$type') == 'struct':return NS(**{k:convert(x) for k,x in v['fields'].items()})
        return v
    for row in FIXTURE['objects']:
        obj = objects[row['path'].lower()]
        obj.Class = Object(row['class'])
        obj.Outer = Object(row['path'].rsplit('.',1)[0])
        for k,v in row['properties'].items():setattr(obj,k,convert(v))
    return objects


class CatalogAudit(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.h = Harness(tmp.name)
        self.h.enable(10)
        self.data = captured()
        self.svc = self.h.runtime.spawns
        self.native_level = self.svc.plan.__globals__['native_level']
        self.hostile = self.svc.plan.__globals__['hostile']
        self.exact = Object('gd_Balance.EnemyLevel.EnemyLevel_GameStage_exact')
        self.h.sdk.find_object = lambda *args:self.exact
        def construct(cls, outer, name, template_obj):
            clone = Object(outer.path+'.'+name)
            clone.DefaultExpLevel = deepcopy(template_obj.DefaultExpLevel)
            clone.Grades = deepcopy(template_obj.Grades)
            return clone
        self.h.sdk.construct_object = construct

    def test_deferred_death_flags_are_captured_native_boolean_properties(self):
        fields=FIXTURE["native_property_metadata"]["WillowGame.WillowAIPawn"]
        self.assertEqual({p["name"]:p["type"] for p in fields},
                         {name:"BoolProperty" for name in ("bIsDead","bPlayedDeath","bDeleteMe","bPendingDelete")})

    def test_captured_engineer_turret_uses_humanoid_enemy_allegiance(self):
        definition = self.data['gd_balance_skillactors.turret.pawn_balance_scorpio_crimsonlance']
        self.assertNotIn('_enemies',definition.path.lower())
        self.assertTrue(self.hostile(NS(),definition,definition.AIPawnArchetype))
        self.assertFalse(self.hostile(NS(),definition,
            self.data['gd_automatedturret.pawnarchetype.pawn_automatedturret_scorpio']))

    def test_custom_humanoid_death_scope_does_not_require_enemies_in_balance_path(self):
        self.h.runtime.loot.is_a = lambda obj,name:name=='WillowAIPawn'
        pawn = self.data['gd_automatedturret.pawnarchetype.pawn_automatedturret_scorpio_crimsonlance']
        pawn.BalanceDefinitionState = NS(BalanceDefinition=self.data['gd_balance_skillactors.turret.pawn_balance_scorpio_crimsonlance'])
        self.assertTrue(self.h.runtime.loot.enemy(pawn))
        token = self.h.runtime.loot.dying(pawn)
        self.assertEqual(self.h.runtime.loot.deaths[-1][1],pawn._get_address())
        self.h.runtime.loot.end_death(token)
        self.assertEqual(self.h.runtime.loot.deaths,[])

    def test_mission_moe_factory_is_named_and_never_rolls_ordinary_bonus(self):
        factory = self.data['z0_missiondata.population.pd_alphaskag_named1:populationfactorybalancedaipawn_20']
        original = factory.PawnBalanceDefinition
        self.assertTrue(self.hostile(factory,original,original.AIPawnArchetype))
        self.svc.roll = lambda:self.fail('Mission-specific Moe must not use ordinary bonus RNG')
        for difficulty in ('Easy','Normal','Hard'):
            self.h.mod.enemy_difficulty.value = difficulty
            stage,clone = self.svc.plan(factory,10,30)
            self.assertEqual(stage,30)  # Keep the native 29-35 Moe grade eligible.
            definition = clone or original
            eligible = [g for g in definition.Grades
                        if g.GameStageRequirement.MinGameStage <= stage <= g.GameStageRequirement.MaxGameStage]
            self.assertEqual([g.GradeModifiers.DisplayName for g in eligible],['Moe'])
            self.assertEqual([g.GradeModifiers.ExpLevel for g in eligible],[32])
            self.assertIs(factory.PawnBalanceDefinition,original)

    def test_named_floor_raises_low_moe_grades_without_changing_native_bands(self):
        factory = self.data['z0_missiondata.population.pd_alphaskag_named1:populationfactorybalancedaipawn_20']
        original = factory.PawnBalanceDefinition
        before = deepcopy(original.Grades)
        stage,clone = self.svc.plan(factory,60,80)
        self.assertEqual(stage,80)
        self.assertTrue(all(g.GradeModifiers.ExpLevel ==60 for g in clone.Grades))
        self.assertEqual([(g.GameStageRequirement.MinGameStage,g.GameStageRequirement.MaxGameStage) for g in clone.Grades],
                         [(g.GameStageRequirement.MinGameStage,g.GameStageRequirement.MaxGameStage) for g in original.Grades])
        self.assertEqual([g.GradeModifiers.ExpLevel for g in original.Grades],
                         [g.GradeModifiers.ExpLevel for g in before])

    def test_rare_no_grade_definition_never_lowers_naturally_higher_default(self):
        definition = Object('Custom.EnemyDefinition')
        definition.DefaultExpLevel = aid(0)
        definition.DefaultExpLevel.BaseValueAttribute = Object('gd_Balance.EnemyLevel.EnemyLevel_GameStage_plus5')
        definition.Grades=[]
        definition.Class=Object('WillowGame.AIPawnBalanceDefinition')
        definition.Outer=Object('Custom')
        definition.AIPawnArchetype=Object('Custom.Pawn')
        definition.AIPawnArchetype.Allegiance=Object('gd_allegiance.HumanoidEnemy.BanditAllegiance')
        factory=NS(PawnBalanceDefinition=definition)
        for ticket in (50,70,99):
            self.svc.roll=lambda:ticket
            stage,clone=self.svc.plan(factory,10,10)
            self.assertEqual(self.native_level((clone or definition).DefaultExpLevel,stage),15)

    def test_native_floor_query_restores_original_mission_minimum_then_live_patch(self):
        source=self.data['z0_missions.missions.m_owedmoneydebt']
        mission=self.h.mission
        mission.MinimumLevel=source.MinimumLevel
        # Reset so Patches records the captured original rather than the harness's.
        self.h.runtime.missions.patches.restore()
        mission.MinimumLevel=source.MinimumLevel
        observed=[]
        def refresh(_pc):
            observed.append(mission.MinimumLevel)
            mission.ExpLevel=mission.GameStage=16
        mission.RefreshRewardGameStage=refresh
        self.h.runtime.missions.floors.clear()
        self.h.runtime.missions.apply(mission,self.h.pc)
        self.assertEqual(mission.MinimumLevel,0)
        self.h.pc.level=20
        self.h.runtime.missions.apply(mission,self.h.pc)
        self.assertEqual(observed,[10,10])
        self.assertEqual(mission.MinimumLevel,0)
        self.h.mod.on_disable()
        self.assertEqual(mission.MinimumLevel,10)


if __name__=='__main__':unittest.main()
