"""One waypoint per mission; requirements below are explicit policy models."""
from pathlib import Path
from types import SimpleNamespace as NS
import json
import unittest
from test_atlas import Harness,Object


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.h=Harness();self.addCleanup(self.h.close)
    def actors(self,numbers):
        result=[]
        for n in numbers:
            a=self.h.waypoint(self.h.other.TargetWaypointDefinition)
            a.WaypointNumber=n;a.path+='_'+str(n);result.append(a)
        return result
    def row(self,current,required):
        self.h.other.Objectives=[NS(ObjectiveCount=n) for n in required]
        return NS(MissionDef=self.h.other,Status=1,Objectives=[NS(CurrentAmount=n) for n in current])
    def test_one_point_for_sequential_objectives_and_completed_steps_skipped(self):
        actors=self.actors([3,1,2])
        for current,wanted in (([0,0,0],1),([1,0,0],2),([1,1,0],3)):
            row=self.row(current,[1,1,1]);actor,reason=self.h.policy.select_waypoint(row,actors)
            self.assertEqual(actor.WaypointNumber,wanted);self.assertEqual(reason,'first-unfinished')
    def test_partial_kill_or_item_count_is_still_the_current_objective(self):
        row=self.row([2,0],[5,1]);actor,_=self.h.policy.select_waypoint(row,self.actors([1,2]))
        self.assertEqual(actor.WaypointNumber,1)
    def test_generic_zero_marker_represents_multi_objective_mission(self):
        row=self.row([0,0,0,0],[1]*4)
        actor,reason=self.h.policy.select_waypoint(row,self.actors([3,0,1,2]))
        self.assertEqual(actor.WaypointNumber,0);self.assertEqual(reason,'mission-wide')
    def test_unknown_counts_fall_back_to_one_stable_real_location(self):
        row=NS(MissionDef=self.h.other,Status=1,Objectives=[NS(CurrentAmount=0)])
        actors=self.actors([5,2,1,3,4])
        actor,reason=self.h.policy.select_waypoint(row,actors)
        self.assertEqual(actor.WaypointNumber,1);self.assertEqual(reason,'lowest-number-fallback')
    def test_known_unloaded_current_step_does_not_reveal_a_future_step(self):
        row=self.row([1,0,0],[1]*3)
        actor,reason=self.h.policy.select_waypoint(row,self.actors([3]))
        self.assertIsNone(actor);self.assertEqual(reason,'current-waypoint-unloaded')
    def test_ready_to_turn_in_uses_hand_in_marker_without_objective_index(self):
        row=self.row([1,1],[1,1]);row.Status=2
        actor,_=self.h.policy.select_waypoint(row,self.actors([0]))
        self.assertEqual(actor.WaypointNumber,0)
    def test_duplicate_log_rows_do_not_duplicate_mission_markers(self):
        rows=self.h.pc.MissionPlaythroughData[0].MissionList
        rows.append(rows[1])
        points=self.h.atlas.collect()
        self.assertEqual(len(points),1)
        self.assertEqual(points[0]['key'],self.h.other._path_name().lower())
    def test_point_key_stays_with_mission_when_current_waypoint_changes(self):
        rows=self.h.pc.MissionPlaythroughData[0].MissionList
        row=self.row([0,0],[1,1]);rows[1]=row
        self.h.objects['WillowWaypoint']+=self.actors([1,2])
        # Remove the harness's generic point so progress selects numbered actors.
        self.h.objects['WillowWaypoint'].remove(self.h.actor)
        p1=self.h.atlas.collect()[0]
        row.Objectives[0].CurrentAmount=1
        p2=self.h.atlas.collect()[0]
        self.assertEqual(p1['key'],p2['key']);self.assertNotEqual(p1['actor'],p2['actor'])
    def test_captured_fifteen_actor_groups_collapse_to_six_extra_missions(self):
        raw=json.loads((Path(__file__).parent/'fixtures/bl1e-waypoint-groups-0.1.2.json').read_text())
        self.h.world.GetMapName=lambda:raw['map']
        definitions={};rows=[]
        for m in raw['missions']:
            mission=self.h.mission(m['name']);mission.path=m['mission']
            for field,key in (('TargetWaypointDefinition','target'),('TurnInWaypointDefinition','turn_in')):
                d=m[key];definition=definitions.setdefault(d['path'],Object(d['path'],PersistentLevelName=d['map'],SubLevelName=d['sublevel']))
                setattr(mission,field,definition)
            # Native required counts weren't present in this report. Exercise
            # the explicit one-location fallback, not fabricated game counts.
            rows.append(NS(MissionDef=mission,Status=m['status'],Objectives=[NS(**o) for o in m['objectives']]))
        self.h.pc.MissionPlaythroughData=[NS(MissionList=rows)]
        self.h.pc.MissionTracker.ActiveMission=next(r.MissionDef for r in rows if r.MissionDef.path.lower() in raw['tracked'])
        actors=[]
        for a in raw['waypoints']:
            if a['definition'] in definitions:
                actor=self.h.waypoint(definitions[a['definition']]);actor.path=a['actor']
                actor.WaypointNumber=a['number'];actor.Location=NS(**a['location']);actors.append(actor)
        self.h.objects['WillowWaypoint']=actors
        points=self.h.atlas.collect()
        self.assertEqual(raw['counts']['visible_extra_clips'],15)
        self.assertEqual(len(points),6)
        self.assertEqual(len({p['key'] for p in points}),6)
        self.assertTrue(all(p['key'] not in raw['tracked'] for p in points))
        self.assertEqual(self.h.atlas.counts['candidate_actors'],15)

if __name__=='__main__':unittest.main()
