"""Modeled SDK tests; these do not establish native Windows/game safety."""

import importlib.util
import json
import re
from pathlib import Path
import sys
import tempfile
import types
import unittest
import zipfile

SOURCE = Path(__file__).resolve().parents[1]/'src'/'BorderlensExtractor'
VERSION = re.search(r'^version = "([^"]+)"', (SOURCE/'pyproject.toml').read_text(), re.M).group(1)
FIXTURE = json.loads((Path(__file__).parent/'fixtures'/'capture-0.1.0-gaps.json').read_text())
PACKAGE = '_borderlens_test'
pkg = types.ModuleType(PACKAGE)
pkg.__path__ = [str(SOURCE)]
sys.modules[PACKAGE] = pkg

def module(name):
    return __import__(PACKAGE+'.'+name, fromlist=[name])

policy = module('policy')
Reflector = module('codec').Reflector
Dataset, Bundle = module('storage').Dataset, module('storage').Bundle
Job = module('job').Job
Engine = module('engine').Engine


class Class:
    def __init__(self, name, fields=(), base=None):
        self.Name, self.fields, self.SuperField = name, list(fields), base
    def _path_name(self):return 'WillowGame.'+self.Name
    def _properties(self):
        return [types.SimpleNamespace(Name=n, Class=types.SimpleNamespace(Name='ObjectProperty' if 'Definition' in n else 'IntProperty'),
                    PropertyFlags=0, ArrayDim=1) for n in self.fields]
    def _inherits(self, base):
        return self is base or (self.SuperField is not None and self.SuperField._inherits(base))


class Object:
    def __init__(self, path, cls, **fields):
        self.path, self.Class = path, cls
        self.Name = path.rsplit('.',1)[-1]
        self.Outer = None
        self.ObjectFlags = 0
        self.__dict__.update(fields)
    def _path_name(self):return self.path
    def _get_address(self):return id(self)


class SDK:
    def __init__(self):
        self.actor = Class('Actor')
        self.definition = Class('WeaponDefinition', ['DisplayName','Damage','ItemDefinition','Parts'])
        self.pool = Class('ItemPoolDefinition', ['Items','AIPawnArchetype'])
        self.pawn = Class('WillowAIPawn', ['InventoryDefinition','Health'], self.actor)
        self.classes = [self.actor,self.definition,self.pool,self.pawn]
        self.objects = []
        self.packages, self.loads = set(), []
        self.on_load = None
    def find_class(self, name):
        return next(c for c in self.classes if name in (c.Name,c._path_name()))
    def find_all(self, name, exact=False):
        if name == 'Class':return list(self.classes)
        return [o for o in self.objects if name in (o.Class.Name,o.Class._path_name())]
    def find_object(self, cls, path):
        if cls == 'Package' and path in self.packages:return True
        obj = next((o for o in self.objects if o.path == path and cls in (o.Class.Name,o.Class._path_name())),None)
        if obj is None:raise ValueError('Object not found: '+path)
        return obj
    def load_package(self, name):
        self.loads.append(name)
        if self.on_load:self.on_load(name)
        self.packages.add(name)
        return True
    def weapon(self, name='gd_test.Weapon', **kwargs):
        obj = Object(name, self.definition, DisplayName='Test', Damage=12.5, ItemDefinition=None, Parts=[], **kwargs)
        self.objects.append(obj)
        return obj


def metadata(scope='loaded'):
    return {'format_version':1,'extractor_version':VERSION,
            'configuration':{'scope':scope,'plan':'test'},
            'session':{'map':'TestMap','mods':[]}}


def pump(job):
    for _ in range(2000):
        job.tick()
        if job.state in ('complete','failed'):return
    raise AssertionError('Job did not finish')


def records(directory):
    manifest = json.loads((directory/'manifest.json').read_text())
    return [row for chunk in manifest['chunks'] for row in json.loads((directory/chunk['file']).read_text())]


class PolicyTests(unittest.TestCase):
    def test_bundled_plan_and_unsafe_names(self):
        plan = policy.validate_plan(json.loads((SOURCE/'package-plan.json').read_text()))
        self.assertGreater(len(plan),48)
        names={r['name'] for r in plan}
        self.assertNotIn('gd_grenademods',names)
        self.assertNotIn('gd_classmods',names)
        self.assertIn('gd_grenades',names)
        self.assertIn('dlc3_gd_customweapons',names)
        for name in FIXTURE['unfollowed_classes']:
            self.assertTrue(policy.data_class(name.rsplit('.',1)[-1]),name)
        for name in ('Arid_P','gd_Test_P','../gd_test','C:/gd_test','dlc3_map_dynamic','Engine',''):
            self.assertFalse(policy.valid_package(name),name)
        for rows in ([{'name':'gd_test'},{'name':'GD_TEST'}],[{'name':'Arid_P'}]):
            with self.assertRaises(ValueError):policy.validate_plan({'format_version':1,'packages':rows})


class LookupTests(unittest.TestCase):
    def test_capture_nested_paths_recover_by_exact_class_and_release(self):
        sdk=SDK()
        for row in FIXTURE['nested_objects']:
            cls = Class(row['class'].rsplit('.',1)[-1])
            sdk.classes.append(cls)
            sdk.objects.append(Object(row['path'],cls))
        def native_lookup_missing(*_):raise ValueError('native nested lookup misses')
        sdk.find_object=native_lookup_missing
        engine=Engine(sdk)
        for obj in sdk.objects:
            engine.pin(obj)
            self.assertIs(engine.find(engine.descriptor(obj)),obj)
        self.assertEqual(engine.lookup_counts['class_scan'],len(FIXTURE['nested_objects']))
        self.assertEqual(engine.release(),[])
        self.assertTrue(all(obj.ObjectFlags==0 for obj in sdk.objects))

    def test_separator_variant_is_checked_against_identity(self):
        sdk=SDK();obj=sdk.weapon('gd_test.Weapon:Inner')
        def native_lookup(cls, path):
            if path=='gd_test.Weapon.Inner':return obj
            raise ValueError('not found')
        sdk.find_object=native_lookup
        engine=Engine(sdk)
        self.assertIs(engine.find(engine.descriptor(obj)),obj)
        self.assertEqual(engine.lookup_counts['normalized'],1)

    def test_wrong_native_result_and_same_short_name_are_rejected(self):
        sdk=SDK();wanted=sdk.weapon('gd_test.Owner:Inner')
        other=sdk.weapon('gd_other.Owner:Inner')
        sdk.find_object=lambda *args:other
        engine=Engine(sdk)
        self.assertIs(engine.find(engine.descriptor(wanted)),wanted)
        self.assertEqual(engine.lookup_counts['class_scan'],1)
        row=engine.descriptor(wanted);sdk.objects.remove(wanted)
        self.assertIsNone(engine.find(row))
        self.assertEqual(engine.lookup_counts['missing'],1)


class CodecTests(unittest.TestCase):
    def test_typed_references_structs_and_schemas(self):
        sdk = SDK()
        other = sdk.weapon('gd_test.Other')
        struct_type = Class('PartRule',['Name','Weight','Definition'])
        struct = types.SimpleNamespace(_type=struct_type,Name='Rule name',Weight=2.0,Definition=other)
        obj = sdk.weapon()
        obj.Parts, obj.ItemDefinition = [struct], other
        emitted, refs = [], []
        codec = Reflector(emitted.append,lambda o,p:refs.append((o._path_name(),p)))
        row = codec.object(obj)
        self.assertTrue(row['complete'])
        self.assertEqual(row['properties']['ItemDefinition']['$ref'],other.path)
        self.assertEqual(row['properties']['Parts']['items'][0]['fields']['Weight'],2.0)
        self.assertEqual({s['record_type'] for s in emitted},{'class_schema','struct_schema'})
        self.assertEqual(row['properties']['Parts']['items'][0]['fields']['Name'],'Rule name')
        self.assertEqual(len(refs),2)
        codec.object(obj)
        self.assertEqual(len(emitted),2)

    def test_errors_truncation_and_nonfinite_are_explicit(self):
        sdk = SDK();obj = sdk.weapon()
        obj.Parts = list(range(8));obj.DisplayName = 'longstring'
        obj.Damage = float('nan')
        del obj.ItemDefinition
        codec = Reflector(lambda r:None,lambda o,p:None, {'array':2,'string':4})
        row = codec.object(obj)
        self.assertFalse(row['complete'])
        self.assertTrue(row['properties']['Parts']['truncated'])
        self.assertEqual(row['properties']['ItemDefinition']['$type'],'read_errors')
        self.assertEqual(row['properties']['Damage']['$type'],'nonfinite')
        json.dumps(row, allow_nan=False)

    def test_recursion_and_node_budget(self):
        codec = Reflector(lambda r:None,lambda o,p:None, {'depth':2,'nodes':8})
        deep=[];deep.append(deep)
        result=codec.value(deep,'array')
        self.assertEqual(result['items'][0]['items'][0]['$type'],'truncated')
        codec.value(object(),'unsupported')
        self.assertEqual(codec.stats['unsupported'],1)


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2]/'temp'/'tests')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'run'
    def test_checkpoint_resume_bundle_only_current_chunks(self):
        ds=Dataset(self.root,metadata(),max_records=2)
        for i in range(3):ds.add({'id':str(i),'record_type':'object','value':i})
        ds.checkpoint(status='paused')
        (self.root/'unrelated.txt').write_text('must not bundle')
        resumed=Dataset(self.root,metadata(),resume=True)
        self.assertEqual(resumed.ids,{'0','1','2'})
        self.assertFalse(resumed.add({'id':'1','record_type':'object'}))
        resumed.checkpoint(status='complete')
        bundle=Bundle(resumed)
        while not bundle.step():pass
        with zipfile.ZipFile(bundle.output) as z:
            self.assertEqual(len(z.namelist()),3)
            self.assertIsNone(z.testzip())
            self.assertFalse(any('unrelated' in n for n in z.namelist()))
    def test_corruption_and_config_version_rejected(self):
        ds=Dataset(self.root,metadata(),max_records=1)
        ds.add({'id':'x','record_type':'object'})
        changed=metadata();changed['extractor_version']='9'
        with self.assertRaises(ValueError):Dataset(self.root,changed,resume=True)
        changed=metadata('catalogue')
        with self.assertRaises(ValueError):Dataset(self.root,changed,resume=True)
        (self.root/ds.manifest['chunks'][0]['file']).write_text('[]')
        with self.assertRaisesRegex(ValueError,'Corrupt'):Dataset(self.root,metadata(),resume=True)
    def test_path_escape_rejected(self):
        ds=Dataset(self.root,metadata())
        ds.manifest['chunks']=[{'file':'../other.json','sha256':'','records':0}]
        ds.checkpoint()
        with self.assertRaisesRegex(ValueError,'Unsafe'):Dataset(self.root,metadata(),resume=True)
    def test_provenance_change_recorded(self):
        Dataset(self.root,metadata())
        meta=metadata();meta['session']['mods']=[{'name':'Changed','enabled':True}]
        ds=Dataset(self.root,meta,resume=True)
        self.assertTrue(any('provenance is mixed' in s for s in ds.manifest['coverage']['limitations']))


class JobTests(unittest.TestCase):
    setUp = StorageTests.setUp
    def test_graph_loads_bindings_and_cleanup(self):
        sdk=SDK();obj=sdk.weapon()
        pawn=Object('TestMap.Boss',sdk.pawn, InventoryDefinition=obj,Health=999)
        sdk.objects.append(pawn)
        pool=Object('gd_test.Pool',sdk.pool,Items=[obj],AIPawnArchetype=pawn)
        sdk.objects.append(pool)
        sdk.on_load=lambda _:sdk.weapon('gd_added.Second')
        job=Job(sdk,self.root,metadata('catalogue'),[{'name':'gd_added','group':'test','evidence':'fixture'}])
        pump(job)
        self.assertEqual(job.state,'complete',job.failures)
        self.assertEqual(sdk.loads,['gd_added'])
        self.assertTrue(all(o.ObjectFlags==0 for o in sdk.objects))
        raw=records(self.root)
        self.assertTrue(any(r.get('path')=='gd_added.Second' for r in raw))
        binding=next(r for r in raw if r['record_type']=='archetype_binding')
        self.assertNotIn('Health',binding['properties'])
        self.assertFalse(job.dataset.manifest['coverage']['catalogue_complete'])
        self.assertTrue(job.bundle.output.exists())
        self.assertEqual(obj.Damage,12.5)
    def test_expression_and_source_factory_graph_is_followed(self):
        sdk=SDK();weapon=sdk.weapon()
        tree_cls=Class('ExpressionTree',['NextNode'])
        node_cls=Class('ExpressionTreeNode_Attribute',['OperandDefinition'])
        eval_cls=Class('AttributeExpressionEvaluator',['Expression'])
        factory_cls=Class('PopulationFactoryBalancedAIPawn',['AIPawnArchetype','LootDefinition'])
        sdk.classes.extend([tree_cls,node_cls,eval_cls,factory_cls])
        node=Object('gd_test.Rule:Node',node_cls,OperandDefinition=weapon)
        tree=Object('gd_test.Rule:Tree',tree_cls,NextNode=node)
        evaluator=Object('gd_test.Evaluator',eval_cls,Expression=tree)
        pawn=Object('gd_test.BossTemplate',sdk.pawn,InventoryDefinition=weapon,Health=1000)
        factory=Object('gd_test.Factory',factory_cls,AIPawnArchetype=pawn,LootDefinition=evaluator)
        sdk.objects.extend([node,tree,evaluator,pawn,factory])
        job=Job(sdk,self.root,metadata(),[])
        pump(job)
        self.assertEqual(job.state,'complete',job.failures)
        raw=records(self.root)
        object_paths={r['path'] for r in raw if r['record_type']=='object'}
        self.assertTrue({node.path,tree.path,evaluator.path,factory.path} <= object_paths)
        binding=next(r for r in raw if r['record_type']=='archetype_binding')
        self.assertNotIn('Health',binding['properties'])
        self.assertEqual(binding['context']['source_package'],'gd_test')
        self.assertEqual(pawn.ObjectFlags,0)
        self.assertTrue(all(obj.ObjectFlags==0 for obj in sdk.objects))

    def test_pause_retains_assets_disable_restores_only_our_pins(self):
        sdk=SDK();ours=sdk.weapon();already=sdk.weapon('gd_test.Rooted')
        already.ObjectFlags=policy.ROOT_SET|8
        job=Job(sdk,self.root,metadata(),[])
        job.enqueue(ours);job.enqueue(already)
        self.assertTrue(ours.ObjectFlags & policy.ROOT_SET)
        job.pause();job.tick()
        self.assertEqual(job.read_count,0)
        job.resume();job.pause(release=True);job.close()
        self.assertEqual(ours.ObjectFlags,0)
        self.assertEqual(already.ObjectFlags,policy.ROOT_SET|8)
    def test_missing_asset_and_package_failure_visible(self):
        sdk=SDK();obj=sdk.weapon()
        job=Job(sdk,self.root,metadata('catalogue'),[{'name':'gd_fail'}])
        job.enqueue(obj);sdk.objects.remove(obj)
        def fail(_):raise RuntimeError('load failed')
        sdk.on_load=fail
        pump(job)
        self.assertEqual(job.state,'complete')
        self.assertEqual(job.package_results[0]['status'],'failed')
        self.assertEqual(len(job.missing),1)
        self.assertTrue(job.dataset.manifest['coverage']['data_issues'])
    def test_interrupted_native_load_quarantined_on_resume(self):
        sdk=SDK()
        def interrupted(_):raise KeyboardInterrupt()
        sdk.on_load=interrupted
        job=Job(sdk,self.root,metadata('catalogue'),[{'name':'gd_interrupt'}])
        with self.assertRaises(KeyboardInterrupt):pump(job)
        self.assertEqual(json.loads((self.root/'manifest.json').read_text())['package_results'][-1]['status'],'loading')
        job.close();sdk.on_load=None
        resumed=Job(sdk,self.root,metadata('catalogue'),[{'name':'gd_interrupt'}],resume=True)
        pump(resumed)
        self.assertEqual(sdk.loads,['gd_interrupt'])
        self.assertEqual(resumed.package_results[-1]['status'],'quarantined_after_interruption')
    def test_completed_capture_can_rebuild_zip_without_loading(self):
        sdk=SDK();sdk.weapon()
        job=Job(sdk,self.root,metadata(),[]);pump(job)
        job.bundle.output.unlink()
        resumed=Job(sdk,self.root,metadata(),[],resume=True)
        self.assertEqual(resumed.phase,'archive')
        pump(resumed)
        self.assertTrue(resumed.bundle.output.exists())
        self.assertEqual(sdk.loads,[])
    def test_export_exception_releases_assets_and_saves_failure(self):
        sdk=SDK();obj=sdk.weapon()
        job=Job(sdk,self.root,metadata(),[])
        job.enqueue(obj)
        def fail(*args, **kwargs):raise RuntimeError('reflection failed')
        job.codec.object=fail
        pump(job)
        self.assertEqual(job.state,'failed')
        self.assertEqual(obj.ObjectFlags,0)
        self.assertEqual(json.loads((self.root/'manifest.json').read_text())['status'],'failed')

    def test_reused_path_does_not_clear_another_objects_flags(self):
        sdk=SDK();obj=sdk.weapon()
        engine=Engine(sdk);engine.pin(obj)
        sdk.objects.remove(obj)
        replacement=sdk.weapon();replacement.ObjectFlags=policy.ROOT_SET|32
        engine.release()
        self.assertEqual(replacement.ObjectFlags,policy.ROOT_SET|32)

    def test_limit_and_partial_finish(self):
        sdk=SDK();sdk.weapon();sdk.weapon('gd_test.Second')
        job=Job(sdk,self.root,metadata(),[],limits={'objects':1})
        for obj in sdk.objects:job.enqueue(obj)
        self.assertEqual(len(job.queue),1)
        job.finish('fixture early end');pump(job)
        self.assertEqual(job.state,'complete')
        self.assertIn('fixture early end',job.dataset.manifest['coverage']['limitations'])
        self.assertTrue(all(o.ObjectFlags==0 for o in sdk.objects))


class EntryTests(unittest.TestCase):
    def test_packaged_sdkmod_lifecycle(self):
        self.run_lifecycle(archive=True)

    def test_manual_keybind_and_frame_lifecycle(self):
        self.run_lifecycle(archive=False)

    def test_deleted_export_folder_starts_fresh(self):
        self.run_lifecycle(archive=True, missing='folder')

    def test_deleted_export_manifest_starts_fresh(self):
        self.run_lifecycle(archive=False, missing='manifest')

    def run_lifecycle(self, archive, missing=None):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2]/'temp'/'tests') as temp:
            sdk=SDK();sdk.weapon()
            actor=sdk.actor
            pawn=Object('TestMap.Pawn',actor)
            world=Object('TestMap.TheWorld.PersistentLevel.WorldInfo',actor,NetMode=0,
                StreamingLevels=[types.SimpleNamespace(PackageName='Arid_P', LoadedLevel=Object('Arid_P.TheWorld.PersistentLevel',actor))])
            pc=types.SimpleNamespace(Pawn=pawn,WorldInfo=world,LastLoadedProfile=types.SimpleNamespace(ExpLevel=1))
            logs=[];registration={}
            stub=types.ModuleType('unrealsdk')
            for name in ('find_class','find_all','find_object','load_package'):setattr(stub,name,getattr(sdk,name))
            stub.logging=types.SimpleNamespace(info=logs.append,error=logs.append)
            hooks=types.ModuleType('unrealsdk.hooks');hooks.Type=types.SimpleNamespace(POST=1)
            base=types.ModuleType('mods_base')
            base.SETTINGS_DIR=Path(temp)
            base.get_pc=lambda:pc
            base.get_ordered_mod_list=lambda:[]
            base.hook=lambda *a,**k:lambda fn:fn
            base.keybind=lambda *a,**k:lambda fn:fn
            class Option:
                def __init__(self, name, **kwargs):self.__dict__.update(kwargs)
            base.ButtonOption=base.SpinnerOption=Option
            def build_mod(**kwargs):
                registration.update(kwargs)
                loaded.__version__=VERSION;loaded.__version_info__=tuple(map(int,VERSION.split('.')))
            base.build_mod=build_mod
            saved={n:sys.modules.get(n) for n in ('mods_base','unrealsdk','unrealsdk.hooks','BorderlensExtractor')}
            sys.modules.update({'mods_base':base,'unrealsdk':stub,'unrealsdk.hooks':hooks})
            try:
                if archive:
                    bundle=Path(temp)/'BorderlensExtractor.sdkmod'
                    with zipfile.ZipFile(bundle,'w') as z:
                        for path in SOURCE.iterdir():
                            if path.is_file():z.write(path,'BorderlensExtractor/'+path.name)
                    spec=importlib.machinery.PathFinder.find_spec('BorderlensExtractor',[str(bundle)])
                else:
                    spec=importlib.util.spec_from_file_location('BorderlensExtractor',SOURCE/'__init__.py',submodule_search_locations=[str(SOURCE)])
                loaded=importlib.util.module_from_spec(spec);sys.modules['BorderlensExtractor']=loaded
                if hasattr(spec.loader,'exec_module'):spec.loader.exec_module(loaded)
                else:exec(spec.loader.get_code('BorderlensExtractor'),loaded.__dict__)
                self.assertIsNone(loaded.job)
                loaded.scope.value='Loaded data only'
                if missing is not None:
                    stale=loaded.EXPORTS/'removed-export'
                    if missing=='manifest':stale.mkdir(parents=True)
                    (loaded.SETTINGS/'latest.json').write_text(json.dumps({'directory':stale.name}))
                loaded.export_key()
                self.assertIsNotNone(loaded.job,logs)
                self.assertEqual(loaded.job.state,'running',logs)
                if missing is not None:
                    self.assertNotEqual(loaded.job.dataset.directory,stale)
                    self.assertTrue(any('manifest is missing' in line for line in logs))
                    if missing=='manifest':self.assertTrue(stale.is_dir())
                self.assertEqual(loaded.job.context['streaming_levels'][0]['package'],'Arid_P')
                loaded.export_key();self.assertEqual(loaded.job.state,'paused')
                loaded.export_key()
                for _ in range(1000):
                    loaded.on_render(None,None,None,None)
                    if loaded.job.state=='complete':break
                self.assertEqual(loaded.job.state,'complete',logs)
                self.assertTrue(loaded.job.bundle.output.exists())
                self.assertEqual(sdk.loads,[])
                self.assertTrue((Path(temp)/'BorderlensExtractor'/'status.json').exists())
                self.assertTrue(any('ZIP ready' in l for l in logs))
                old = loaded.job.dataset.directory
                manifest = loaded.job.dataset.manifest
                manifest['extractor_version'] = '0.1.0'
                manifest['status'] = 'paused'
                (old/'manifest.json').write_text(json.dumps(manifest))
                loaded.export_key()
                self.assertEqual(loaded.job.state,'running',logs)
                self.assertNotEqual(loaded.job.dataset.directory,old)
                self.assertEqual(loaded.job.dataset.manifest['extractor_version'],VERSION)
                self.assertEqual(json.loads((old/'manifest.json').read_text())['extractor_version'],'0.1.0')
                registration['on_disable']()
                self.assertIsNone(loaded.job)
            finally:
                for name,value in saved.items():
                    if value is None:sys.modules.pop(name,None)
                    else:sys.modules[name]=value
                for name in list(sys.modules):
                    if name.startswith('BorderlensExtractor.'):sys.modules.pop(name,None)


if __name__=='__main__':unittest.main()
