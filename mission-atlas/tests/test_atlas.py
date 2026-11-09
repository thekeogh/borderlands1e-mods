"""Native-interface models; no Windows engine/map renderer is executed."""
from contextlib import nullcontext
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace as NS
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'Source/sdk_mods/MissionAtlas'

class Object:
    def __init__(self, path, **values):
        self.path = path
        self.__dict__.update(values)
    def __deepcopy__(self,memo): return self # UObject copies retain native identity.
    def _path_name(self): return self.path
    def _get_address(self): return id(self)

def prop(name, kind='ObjectProperty', flags=0x80, **extra):
    return NS(Name=name, Class=NS(Name=kind), PropertyFlags=flags, **extra)

def function(name, fields, owner='WillowGame.WillowWaypoint'):
    return Object(owner + '.' + name, Name=name, Class=NS(Name='Function'), _properties=lambda: fields)

class Harness:
    def __init__(self):
        self.saved = dict(sys.modules)
        self.callbacks, self.messages, self.objects, self.classes = {}, [], {}, {}
        self.hooks = ModuleType('unrealsdk.hooks')
        self.hooks.Block = object()
        self.hooks.Type = NS(PRE='PRE', POST='POST', POST_UNCONDITIONAL='POST_UNCONDITIONAL')
        self.hooks.prevent_hooking_direct_calls = nullcontext
        def add(path, timing, identifier, callback):
            self.callbacks[(path, timing, identifier)] = callback
            return True
        self.hooks.add_hook = add
        self.hooks.remove_hook = lambda p,t,i: self.callbacks.pop((p,t,i), None)
        self.sdk = ModuleType('unrealsdk')
        self.sdk.logging = NS(info=self.messages.append, error=self.messages.append)
        self.sdk.make_struct = lambda name, **values: NS(**values)
        self.sdk.find_all = lambda name: self.objects.get(name, [])
        def find(name):
            if name not in self.classes: raise ValueError(name)
            return self.classes[name]
        self.sdk.find_class = find
        sys.modules['unrealsdk'] = self.sdk
        sys.modules['unrealsdk.hooks'] = self.hooks
        package = ModuleType('atlas_test'); package.__path__ = [str(SOURCE)]
        sys.modules['atlas_test'] = package
        for name in ('policy','native','runtime'):
            spec = importlib.util.spec_from_file_location('atlas_test.'+name, SOURCE/(name+'.py'))
            module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module
            spec.loader.exec_module(module); setattr(self,name,module)
        self.world = Object('World.WorldInfo', GetMapName=lambda:'Arid_Badlands_P', NetMode=0)
        self.pc = Object('World.PC', Pawn=Object('World.Pawn'), WorldInfo=self.world,
                         GetCurrentPlaythrough=lambda:0, bStatusMenuOpen=True)
        self.active, self.other = self.mission('Active'), self.mission('Other')
        self.pc.MissionPlaythroughData = [NS(MissionList=[NS(MissionDef=self.active, Status=1),NS(MissionDef=self.other, Status=1)])]
        self.pc.MissionTracker = Object('World.Tracker', ActiveMission=self.active)
        self.atlas = self.runtime.Atlas(lambda:self.pc, lambda:True, lambda:55)
        self.atlas.enabled = True
        self.actor, self.tracked_actor = self.waypoint(self.other.TargetWaypointDefinition), self.waypoint(self.active.TargetWaypointDefinition)
        self.objects['WillowWaypoint'] = [self.actor,self.tracked_actor]
    def close(self):
        self.atlas.disable()
        for name in list(sys.modules):
            if name.startswith('atlas_test') or name in ('unrealsdk', 'unrealsdk.hooks'):
                if name in self.saved:
                    sys.modules[name] = self.saved[name]
                else:
                    sys.modules.pop(name, None)
    def definition(self,name,map='Arid_Badlands_P'):
        return Object('gd_waypoints.'+name, PersistentLevelName=map,SubLevelName='')
    def mission(self,name):
        return Object('gd_missions.'+name, MissionName=name,bDoNotResolveWaypoint=False,
                      TargetWaypointDefinition=self.definition(name),TurnInWaypointDefinition=self.definition(name+'TurnIn'))
    def waypoint(self,definition):
        properties=[prop('WaypointDefinition',PropertyClass=Object('WillowGame.WaypointDefinition')),
                    prop('MapIconColor','StructProperty',Struct=Object('Core.Object.Color'))]
        return Object('World.'+definition.path.rsplit('.',1)[-1], WorldInfo=self.world,
                      bDeleteMe=False,bPendingDelete=False,WaypointDefinition=definition,Location=NS(X=10 if 'Active' in definition.path else 20,Y=30,Z=40),
                      MapIconColor=NS(R=255,G=255,B=255,A=255),Class=NS(_properties=lambda:properties))

class AtlasTests(unittest.TestCase):
    def setUp(self):
        self.h=Harness();self.addCleanup(self.h.close)

    def test_mission_map_status_and_tracked_filters(self):
        self.assertEqual([p['actor'] for p in self.h.atlas.collect()],[self.h.actor._path_name()])
        for status in (0,3,4,99):
            self.h.pc.MissionPlaythroughData[0].MissionList[1].Status=status
            self.assertEqual(self.h.atlas.collect(),[])
        self.h.pc.MissionPlaythroughData[0].MissionList[1].Status=1
        self.h.other.TargetWaypointDefinition.PersistentLevelName='OtherMap'
        self.assertEqual(self.h.atlas.collect(),[])

    def test_shared_tracked_and_script_suppressed_locations_stay_native(self):
        self.h.other.bDoNotResolveWaypoint=True
        self.assertEqual(self.h.atlas.collect(),[])
        self.h.other.bDoNotResolveWaypoint=False
        self.h.other.TargetWaypointDefinition=self.h.active.TargetWaypointDefinition
        self.assertEqual(self.h.atlas.collect(),[])

    def test_turn_in_option_and_current_playthrough(self):
        self.h.pc.MissionPlaythroughData[0].MissionList[1].Status=2
        handin=self.h.waypoint(self.h.other.TurnInWaypointDefinition)
        self.h.objects['WillowWaypoint'].append(handin)
        self.assertEqual([p['actor'] for p in self.h.atlas.collect()],[handin._path_name()])
        self.h.atlas.include_turn_ins=lambda:False
        self.assertEqual(self.h.atlas.collect(),[])
        self.h.pc.GetCurrentPlaythrough=lambda:9
        self.assertEqual(self.h.atlas.collect(),[])

    def test_world_owned_tracker_and_invalid_actors(self):
        self.h.pc.MissionTracker=None
        tracker=Object('World.Tracker',Owner=Object('World.Game'),WorldInfo=self.h.world,ActiveMission=self.h.active)
        self.h.objects['MissionTracker']=[tracker]
        self.assertEqual([p['actor'] for p in self.h.atlas.collect()],[self.h.actor._path_name()])
        self.h.actor.bPendingDelete=True
        self.assertEqual(self.h.atlas.collect(),[])
        self.h.actor.bPendingDelete=False;self.h.actor.WorldInfo=Object('Other.World')
        self.assertEqual(self.h.atlas.collect(),[])

    def test_cache_does_not_rescan_on_pan_or_hold_native_actor_wrappers(self):
        points=self.h.atlas.points_for(self.h.pc,10)
        self.assertEqual(len(points),1)
        for i in range(100):self.h.atlas.points_for(self.h.pc,10+i/1000)
        self.assertEqual(self.h.atlas.counts['point_scans'],1)
        self.assertFalse(any(hasattr(v,'_path_name') for p in points for v in p.values()))
        self.assertIsInstance(points[0]['x'],float)
        self.h.atlas.invalidate()
        self.h.atlas.points_for(self.h.pc,10.2)
        self.assertEqual(self.h.atlas.counts['point_scans'],2)

    def test_colon_paths_and_captured_map_methods(self):
        data=json.loads((Path(__file__).parent/'fixtures/bl1e-trash-map-0.1.0.json').read_text())
        functions=[]
        for entry in data['map_functions']:
            fields=[prop(p['name'],p['type'],p['flags']) for p in entry['parameters']]
            fn=function(entry['name'],fields,entry['owner'])
            fn.path=entry['owner']+':'+entry['name'];fn.Outer=Object(entry['owner'])
            self.assertEqual(self.h.native.hook_path(fn),fn.path)
            functions.append(fn)
        cls=Object('WillowGame.StatusMenuExGFxMovie',_properties=lambda:[],_fields=lambda:functions)
        self.h.classes['StatusMenuExGFxMovie']=cls
        self.h.atlas.discover()
        self.assertEqual(len(self.h.callbacks),6) # exactly one post per function
        self.assertTrue(all(t=='POST_UNCONDITIONAL' for p,t,i in self.h.callbacks))
        self.h.atlas.discover();self.assertEqual(len(self.h.callbacks),6)

    def test_duplicate_failure_does_not_abort_helper_discovery(self):
        fn=function('PanMap',[],'WillowGame.StatusMenuExGFxMovie')
        self.h.classes['StatusMenuExGFxMovie']=Object('WillowGame.StatusMenuExGFxMovie',_properties=lambda:[],_fields=lambda:[fn])
        self.h.classes['WillowGFxHelperMap']=Object('WillowGame.WillowGFxHelperMap',_properties=lambda:[],_fields=lambda:[])
        old=self.h.runtime.add_hook
        self.h.runtime.add_hook=lambda *a:False
        try:self.h.atlas.discover()
        finally:self.h.runtime.add_hook=old
        self.assertIn('WillowGame.WillowGFxHelperMap',self.h.atlas.schemas)
        self.assertTrue(self.h.atlas.errors)

    def test_legacy_hooks_removed_and_function_ids_unique(self):
        removed=[]
        old=self.h.runtime.remove_hook
        self.h.runtime.remove_hook=lambda p,t,i:removed.append((p,t,i))
        try:
            self.h.atlas.clean_legacy('WillowGame.StatusMenuExGFxMovie:PanMap')
        finally:self.h.runtime.remove_hook=old
        self.assertTrue(any(i=='MissionAtlas.Observe' for p,t,i in removed))
        self.h.atlas.install('A:One','POST','Map',lambda *a:None)
        self.h.atlas.install('A:Two','POST','Map',lambda *a:None)
        ids=[i for p,t,i in self.h.atlas.installed]
        self.assertEqual(len(ids),len(set(ids)))

    def test_f9_map_fallback_and_no_mission_edits(self):
        calls=[];self.h.atlas.export_callback=lambda:calls.append(1)
        self.h.atlas.renderer.update=lambda *a:None
        cb=self.h.atlas.map_callback('Map:Key','HandleMapInputKey',[])
        movie=Object('Movie',MapHelper=None)
        before=[(r.MissionDef,r.Status) for r in self.h.pc.MissionPlaythroughData[0].MissionList]
        cb(movie,NS(ukey='F9',uevent=0),None,None)
        cb(movie,NS(ukey='F9',uevent=1),None,None)
        self.assertEqual(calls,[1])
        self.assertEqual(before,[(r.MissionDef,r.Status) for r in self.h.pc.MissionPlaythroughData[0].MissionList])
        self.assertIs(self.h.pc.MissionTracker.ActiveMission,self.h.active)

    def test_no_periodic_reflection_after_initial_discovery_is_ready(self):
        self.h.atlas.ready=True
        self.h.atlas.discover=lambda:self.fail('Unexpected per-pan discovery')
        self.h.atlas.poll()

    def test_manual_report_has_renderer_errors_and_cached_points(self):
        self.h.atlas.points_for(self.h.pc,10)
        with tempfile.TemporaryDirectory() as folder:
            report=json.loads(self.h.atlas.export(folder).read_text())
        self.assertEqual(report['version'],'0.1.9')
        self.assertEqual(len(report['cached_points']),1)
        self.assertIn('renderer',report)
        self.assertEqual(len(report['waypoints']),2)

    def test_entrypoint_registers_lifecycle_and_map_travel_cleanup(self):
        base=ModuleType('mods_base')
        def option(identifier,*args,**kw):return NS(identifier=identifier,value=args[0] if args else None,**kw)
        base.ButtonOption=base.BoolOption=base.SliderOption=option
        base.SETTINGS_DIR=Path('/tmp/mission-atlas-test-settings');base.get_pc=lambda:self.h.pc
        base.hook=lambda *a,**kw:lambda fn:fn
        base.keybind=lambda *a,**kw:lambda fn:fn
        registered={};base.build_mod=lambda **kw:registered.update(kw)
        old=sys.modules.get('mods_base');sys.modules['mods_base']=base
        try:
            spec=importlib.util.spec_from_file_location('atlas_test',SOURCE/'__init__.py',submodule_search_locations=[str(SOURCE)])
            module=importlib.util.module_from_spec(spec);sys.modules['atlas_test']=module;spec.loader.exec_module(module)
            registered['on_enable']();self.assertTrue(module.atlas.enabled)
            module.map_change(None,None,None,None)
            registered['on_disable']();self.assertFalse(module.atlas.enabled)
            self.assertEqual(len(registered['options']),3)
        finally:
            if old is None:sys.modules.pop('mods_base',None)
            else:sys.modules['mods_base']=old

    def test_post_map_callback_never_replays_or_blocks_native_pan(self):
        self.h.atlas.renderer.update=lambda *a:None
        callback=self.h.atlas.map_callback('Map:PanMap','PanMap',[])
        result=callback(Object('Movie',MapHelper=None),NS(),True,lambda:self.fail('Native pan replayed'))
        self.assertIsNone(result)

    def test_nonfinite_struct_serialization_is_valid_json(self):
        value=NS(_type=NS(_properties=lambda:[prop('N','FloatProperty')]),N=float('nan'))
        result=self.h.runtime.brief(value)
        self.assertEqual(result,{'N':{'nonfinite':'nan'}})
        json.dumps(result,allow_nan=False)

if __name__=='__main__':unittest.main()
