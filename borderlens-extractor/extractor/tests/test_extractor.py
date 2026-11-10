"""Modeled SDK tests; these do not establish native Windows/game safety."""

import importlib.util
import json
import re
import struct
from pathlib import Path
import sys
import tempfile
import types
import unittest
import zipfile
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1]/'src'/'BorderlensExtractor'
VERSION = re.search(r'^version = "([^"]+)"', (SOURCE/'pyproject.toml').read_text(), re.M).group(1)
FIXTURE = json.loads((Path(__file__).parent/'fixtures'/'capture-0.1.0-gaps.json').read_text())
INDEX_FIXTURE = json.loads((Path(__file__).parent/'fixtures'/'capture-0.2.0-indexing-gaps.json').read_text())
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
catalogue = module('catalogue')
installation = module('installation')


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
        self.assertIn('gd_SledgeBoss',names)
        self.assertIn('gd_Balance_Enemies_Creatures',names)
        self.assertIn('DLC4_Tartarus_Stat_Missions',names)
        self.assertEqual(len(plan),219)
        for name in ('gd_EchoCallerIDs','dlc3_gd_balance_enemies','dlc4_gd_Balance_Enemies',
                     'dlc3_MissionNPCs','dlc4_EchoCallerIDs','dlc5_registrationstationlist'):
            self.assertIn(name,names)
        for cls in ('TeleportOutpostLookupObject','LevelDependencyList'):
            self.assertTrue(policy.data_class(cls))
        self.assertFalse(policy.data_class('World'))
        self.assertTrue(policy.binding_field('AIPawnName'))
        for name in FIXTURE['unfollowed_classes']:
            self.assertTrue(policy.data_class(name.rsplit('.',1)[-1]),name)
        for name in ('Arid_P','gd_Test_P','../gd_test','C:/gd_test','dlc3_map_dynamic','Engine','',
                     'DLC4_Tartarus_Stat_P','dlc1_Missions_P','dlc4_arbitrary_map','dlc5_arbitrary',
                     'dlc4_EchoCallerIDs_P','Z0_Arbitrary'):
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

    def test_identity_counts_recovered_from_chunks_after_stale_summary(self):
        ds=Dataset(self.root,metadata(),max_records=1)
        ds.add({'id':'identity:x','record_type':'catalogue_identity','category':'character','names':[{'name':'Boss'}]})
        ds.add({'id':'identity:y','record_type':'catalogue_identity','category':'region','names':[]})
        ds.manifest['catalogue']={'categories':{},'named_records':0}
        ds.checkpoint(status='paused')
        recovered=Dataset(self.root,metadata(),resume=True)
        self.assertEqual(recovered.catalogue,{'categories':{'character':1,'region':1},'named_records':1,'unnamed_records':1})


class CatalogueTests(unittest.TestCase):
    def test_real_capture_npc_callers_mission_givers_and_travel_references(self):
        sources=INDEX_FIXTURE['records']
        seeds=[seed for record in sources for seed in catalogue.identities(record)]
        names={n['name'] for r in seeds for n in r['names']}
        self.assertTrue({'Dr. Zed','Marcus Kincaid','Scooter','Patricia Tannis','Guardian Angel',
                         'Moxxi','T.K. Baha','Fyrestone Bounty Board','Athena'} <= names)
        self.assertEqual(len({r['id'] for r in seeds}),len(seeds))
        self.assertTrue(all(r['source_record'] in {s['id'] for s in sources} for r in seeds))
        board=next(r for r in seeds if any(n['name']=='Fyrestone Bounty Board' for n in r['names']))
        self.assertEqual(board['category'],'mission_giver')
        self.assertIsNone(board['character_role'])
        self.assertIsNone(board['asset_path'])
        caller=next(r for r in seeds if any(n['name']=='Dr. Zed' for n in r['names']))
        self.assertEqual(caller['category'],'contact')
        npc=next(r for r in seeds if r.get('asset_path')=='gd_MissionNPCs.DrZed')
        self.assertEqual(npc['category'],'npc')
        self.assertEqual(npc['names'],[])
        for source in sources:
            if source['class']=='WillowGame.MissionDefinition':
                primary=next(r for r in seeds if r['id']=='identity:'+source['id'])
                self.assertEqual([n['name'] for n in primary['names']],[source['properties']['MissionName']])
        locations=[r for r in seeds if r['category']=='location']
        self.assertTrue(locations)
        self.assertTrue(all(not r['names'] and r['internal_identifiers'] for r in locations))
        self.assertTrue(any(r['identifier_kind']=='object_path' and '.TheWorld' in r['asset_path_hint'] for r in locations))
        maps=[r for r in seeds if r['category']=='map']
        self.assertTrue(maps)
        self.assertTrue(all(r['names']==[] and r['asset_path'] is None for r in maps))

    def test_reference_labels_do_not_guess_aliases_or_entity_origin(self):
        source={'id':'object:dlc3_missions.test','path':'dlc3_Missions.Test','name':'Test',
                'class':'WillowGame.MissionDefinition','complete':True,
                'properties':{'MissionName':'Test','MissionGiver':'Tannis',
                              'PickUpMapName':{'$type':'name','value':'Test_P'}}}
        first=list(catalogue.identities(source))
        giver=next(r for r in first if r['category']=='mission_giver')
        map_seed=next(r for r in first if r['category']=='map')
        self.assertEqual(map_seed['asset_path_hint'],'Test_P')
        self.assertEqual(map_seed['names'],[])
        self.assertIsNone(giver['origin_hint'])
        self.assertEqual(giver['source_origin_hint'],'dlc3')
        source['properties']['MissionGiver']='Patricia Tannis'
        replacement=next(r for r in catalogue.identities(source) if r['category']=='mission_giver')
        self.assertEqual(giver['id'],replacement['id'])
        self.assertEqual([n['name'] for n in replacement['names']],['Patricia Tannis'])
        self.assertEqual(list(catalogue.identities(dict(source,is_default=True))),[])

    def test_grade_names_are_evidence_not_boss_or_family_classification(self):
        row={'record_type':'object','id':'object:gd_test.balance','path':'gd_test.Balance',
             'name':'Balance','class':'WillowGame.AIPawnBalanceDefinition','complete':True,
             'properties':{'Grades':{'$type':'array','items':[
                 {'$type':'struct','fields':{'GradeModifiers':{'$type':'struct','fields':{'DisplayName':'Bone Head'}}}},
                 {'$type':'struct','fields':{'GradeModifiers':{'$type':'struct','fields':{'DisplayName':'Badass Bruiser'}}}}]}}}
        seed=catalogue.identity(row)
        self.assertEqual(seed['category'],'character')
        self.assertEqual([n['name'] for n in seed['names']],['Bone Head','Badass Bruiser'])
        self.assertEqual(seed['names'][0]['field'],'Grades[0].GradeModifiers.DisplayName')
        self.assertEqual(seed['asset_path'],row['path'])
        self.assertEqual(seed['source_record'],row['id'])
        self.assertIsNone(seed['is_boss'])
        self.assertIsNone(seed['is_named_enemy'])
        self.assertIsNone(seed['origin_hint'])
        self.assertEqual(catalogue.identity(dict(row,properties={}))['id'],seed['id'])
        self.assertIsNone(catalogue.identity(dict(row,is_default=True)))

    def test_no_names_invented_from_enums_asset_paths_or_references(self):
        row={'id':'object:dlc3_gd_test.class','path':'dlc3_gd_test.Class','name':'Class',
             'class':'WillowGame.PlayerClassDefinition','complete':False,
             'properties':{'CharacterName':1,'ItemDefinition':{'$ref':'gd_test.Boss','class':'DisplayName'},
                           'DisplayName':{'$type':'read_errors','message':'missing'},
                           'MasteredDisplayName':"%s's %n"}}
        seed=catalogue.identity(row)
        self.assertEqual(seed['names'],[])
        self.assertEqual(seed['category'],'character_class')
        self.assertEqual(seed['origin_hint'],'dlc3')
        self.assertFalse(seed['source_complete'])


class InstallationTests(unittest.TestCase):
    setUp = StorageTests.setUp

    def fixture(self):
        game=Path(self.temp.name)/'Game'
        content=game/'WillowGame'/'CookedPC'
        text=game/'WillowGame'/'Localization'/'INT'
        content.mkdir(parents=True);text.mkdir(parents=True)
        # Header summary only: the scanner must never interpret this as load permission.
        prefix=b'\xc1\x83\x2a\x9e'+struct.pack('<HHi',584,57,200)+struct.pack('<i',5)+b'None\0'
        (content/'UnvisitedBossMap.umap').write_bytes(prefix+struct.pack('<7I',0x20000,20,200,30,400,10,800))
        (content/'gd_UnreviewedBoss.upk').write_bytes(b'unknown-header')
        loc=text/'gd_Balance_Enemies_Humans.int'
        loc.write_text('[Boss]\nAIPawnName="Unvisited Boss"\nDescription="not a name"\n'
                       '[Balance]\nGrades=(GradeModifiers=(DisplayName="Bone Head"),Other=1)\n'
                       'Grades[1].GradeModifiers.DisplayName="Badass Bruiser"\n'
                       '[Empty]\nDisplayName="None"\n',encoding='utf-8')
        (text/'dlc3_Missions.int').write_bytes('[Mission]\nMissionName="Café Test"\n'.encode('utf-16'))
        (game/'WillowGame'/'SaveData').mkdir()
        (game/'WillowGame'/'SaveData'/'Private.int').write_text('[Private]\nDisplayName="Excluded"')
        return game,loc

    def test_unloaded_names_inventory_encoding_and_source_integrity(self):
        game,loc=self.fixture()
        scan=installation.InstallationScan(game,policy.LIMITS,0)
        raw=[r for r in scan.iterator if r is not None]
        seeds=[r for r in raw if r['record_type']=='catalogue_identity']
        names={n['name'] for r in seeds for n in r['names']}
        self.assertEqual(names,{'Unvisited Boss','Bone Head','Badass Bruiser','Café Test'})
        self.assertEqual(scan.summary['status'],'complete')
        self.assertEqual(scan.summary['packages'],2)
        self.assertEqual(scan.summary['localisation_files'],2)
        self.assertEqual(scan.summary['named_sections'],3)
        source=next(r for r in raw if r['record_type']=='localisation_file' and r['file'].endswith(loc.name))
        boss=next(r for r in seeds if r['section']=='Boss')
        self.assertEqual(boss['source_record'],source['id'])
        self.assertEqual(boss['source_sha256'],source['sha256'])
        self.assertIsNone(boss['asset_path'])
        self.assertEqual(boss['identity_status'],'localisation_candidate')
        self.assertEqual(boss['category'],'character')
        self.assertTrue(all(not r['loaded_by_scan'] for r in raw if r['record_type']=='package_file'))
        header=next(r['header'] for r in raw if r['record_type']=='package_file' and r['file'].endswith('.umap'))
        self.assertEqual(header['file_version'],584)
        self.assertEqual(header['export_count'],30)
        self.assertTrue(header['contains_map'])

    def test_full_job_never_loads_installed_maps_or_unreviewed_packages(self):
        game,_=self.fixture();sdk=SDK()
        job=Job(sdk,self.root,metadata('catalogue'),[{'name':'gd_reviewed'}],installation_root=game)
        pump(job)
        self.assertEqual(job.state,'complete',job.failures)
        self.assertEqual(sdk.loads,['gd_reviewed'])
        self.assertEqual(job.dataset.manifest['catalogue']['categories']['character'],2)
        self.assertEqual(job.dataset.manifest['catalogue']['named_records'],3)
        self.assertFalse(job.dataset.manifest['catalogue']['complete'])
        self.assertEqual(job.dataset.manifest['installation_scans'][0]['status'],'complete')
        with zipfile.ZipFile(job.bundle.output) as archive:
            bundled=[r for n in archive.namelist() if '/data/' in n for r in json.loads(archive.read(n))]
        self.assertTrue(any(r.get('section')=='Boss' for r in bundled))
        self.assertFalse(any(r.get('file','').endswith('Private.int') for r in bundled))

    def test_resume_retains_changed_localisation_evidence_and_identity_locator(self):
        game,loc=self.fixture();sdk=SDK()
        job=Job(sdk,self.root,metadata('catalogue'),[],installation_root=game)
        while job.phase=='installation':job.step()
        job.pause();job.close()
        before=next(r for r in records(self.root) if r.get('section')=='Boss')
        loc.write_text('[Boss]\nAIPawnName="Renamed Boss"\n')
        resumed=Job(sdk,self.root,metadata('catalogue'),[],resume=True,installation_root=game)
        pump(resumed)
        both=[r for r in records(self.root) if r.get('section')=='Boss']
        self.assertEqual(len(both),2)
        self.assertEqual(both[0]['locator_id'],both[1]['locator_id'])
        self.assertNotEqual(both[0]['id'],both[1]['id'])
        self.assertEqual(both[0],before)
        self.assertEqual({r['names'][0]['name'] for r in both},{'Unvisited Boss','Renamed Boss'})
        self.assertEqual(resumed.dataset.manifest['catalogue']['named_records'],4)

    def test_interrupted_scan_rescans_without_duplicate_unchanged_seeds(self):
        game,_=self.fixture();sdk=SDK()
        job=Job(sdk,self.root,metadata('catalogue'),[],installation_root=game)
        for _ in range(200):
            job.step()
            if job.identity_count:break
        self.assertEqual(job.phase,'installation')
        job.pause();job.close()
        resumed=Job(sdk,self.root,metadata('catalogue'),[],resume=True,installation_root=game)
        pump(resumed)
        raw=records(self.root)
        self.assertEqual(len({r['id'] for r in raw}),len(raw))
        self.assertEqual(resumed.dataset.manifest['catalogue']['named_records'],3)
        self.assertEqual(resumed.dataset.manifest['installation_scans'][0]['status'],'interrupted')

    def test_scan_limits_and_unknown_installation_are_explicit(self):
        game,_=self.fixture()
        scan=installation.InstallationScan(game,dict(policy.LIMITS,localisation_bytes=4),0)
        raw=[r for r in scan.iterator if r is not None]
        self.assertEqual(scan.summary['status'],'partial')
        self.assertTrue(scan.summary['limits_hit'])
        self.assertTrue(any(r.get('status')=='size_limit' for r in raw))
        scan=installation.InstallationScan(None,policy.LIMITS,0)
        self.assertEqual(list(scan.iterator),[])
        self.assertEqual(scan.summary['status'],'unavailable')
        self.assertTrue(scan.summary['errors'])
        scan=installation.InstallationScan(game,dict(policy.LIMITS,installation_files=1),0)
        list(scan.iterator)
        self.assertTrue(scan.summary['limits_hit'])

    def test_symlinked_content_is_not_followed(self):
        game,_=self.fixture()
        outside=Path(self.temp.name)/'Outside';outside.mkdir()
        (outside/'secret.int').write_text('[Secret]\nAIPawnName="Excluded"\n')
        (game/'WillowGame'/'CookedPC'/'Linked').symlink_to(outside,target_is_directory=True)
        scan=installation.InstallationScan(game,policy.LIMITS,0)
        raw=[r for r in scan.iterator if r is not None]
        self.assertEqual(scan.summary['skipped_symlinks'],1)
        self.assertFalse(any(r.get('section')=='Secret' for r in raw))

    def test_localisation_tuple_escapes_repeated_sections_and_limits(self):
        text='[A]\nDisplayName="Moxxi\\\"s Café"\nDisplayName="Second"\n[A]\nItemName="Third"\n'
        sections=[r for r in installation.localisation_sections(text,max_names=1) if r is not None]
        self.assertEqual(sections[0][1][0]['name'],'Moxxi"s Café')
        self.assertEqual(sections[0][2],1)
        self.assertEqual(sections[1][1][0]['name'],'Third')
        sections=[r for r in installation.localisation_sections('[A]\nDisplayName="'+('x'*100)+'"',max_line=30) if r]
        self.assertEqual(sections[0][2],1)

    def test_unquoted_names_and_per_object_class_sections(self):
        game,loc=self.fixture()
        loc.write_text('[SomePawn WillowAIPawn]\nAIPawnName=Badass (Fire), Mark II\n')
        english=loc.with_name('Extra.ENG')
        english.write_text('[Vehicle VehicleSpawnStationVehicleDefinition]\nVehicleName=Test Runner\n')
        scan=installation.InstallationScan(game,policy.LIMITS,0)
        raw=[r for r in scan.iterator if r is not None]
        pawn=next(r for r in raw if r.get('section')=='SomePawn WillowAIPawn')
        self.assertEqual(pawn['names'][0]['name'],'Badass (Fire), Mark II')
        self.assertEqual(pawn['class_hint'],'WillowAIPawn')
        self.assertEqual(pawn['asset_path_hint'],'gd_Balance_Enemies_Humans.SomePawn')
        self.assertEqual(pawn['category'],'character')
        vehicle=next(r for r in raw if r.get('section')=='Vehicle VehicleSpawnStationVehicleDefinition')
        self.assertEqual(vehicle['category'],'vehicle')
        self.assertEqual(vehicle['names'][0]['name'],'Test Runner')

    def test_caller_quest_and_map_labels_keep_distinct_categories_and_sources(self):
        game,loc=self.fixture()
        loc.write_text('[Contact EchoCallerIDDefinition]\nCallerName=Dr. Zed\n'
                       '[Quest MissionDefinition]\nMissionName=Test Quest\nMissionGiver=Fyrestone Bounty Board\n'
                       'PickUpMapName=Arid_P\nTargetFastTravelStation=Fyrestone\n'
                       '[Station TeleportOutpostLookupObject]\nOutpostDisplayName=Fyrestone\n')
        scan=installation.InstallationScan(game,policy.LIMITS,0)
        raw=[r for r in scan.iterator if r is not None]
        seeds=[r for r in raw if r['record_type']=='catalogue_identity' and r.get('source_file','').endswith(loc.name)]
        contact=next(r for r in seeds if r['category']=='contact')
        self.assertEqual(contact['names'][0]['name'],'Dr. Zed')
        mission=next(r for r in seeds if r['category']=='mission')
        self.assertEqual([n['name'] for n in mission['names']],['Test Quest'])
        self.assertEqual(len(mission['related_fields']),3)
        giver=next(r for r in seeds if r['category']=='mission_giver')
        self.assertEqual(giver['identity_status'],'localisation_field_candidate')
        self.assertEqual(giver['names'][0]['name'],'Fyrestone Bounty Board')
        self.assertIsNone(giver['asset_path'])
        self.assertIsNone(giver['source_asset_path'])
        self.assertEqual(giver['source_identity'],mission['id'])
        self.assertEqual(giver['source_line'],5)
        map_seed=next(r for r in seeds if r['category']=='map')
        self.assertEqual(map_seed['names'],[])
        self.assertEqual(map_seed['internal_identifiers'][0]['value'],'Arid_P')
        self.assertEqual(map_seed['asset_path_hint'],'Arid_P')
        station=next(r for r in seeds if r.get('class_hint')=='TeleportOutpostLookupObject')
        self.assertEqual(station['category'],'location')
        self.assertEqual(station['names'][0]['name'],'Fyrestone')

    def test_repeated_localisation_reference_fields_survive_reindex(self):
        source={'id':'identity:localisation:test:hash','names':[
                    {'name':'First','field':'MissionGiver','line':2},
                    {'name':'Second','field':'MissionGiver','line':2}],
                'source_record':'file:test@0','source_file':'test.int','source_sha256':'hash',
                'section':'Test','section_occurrence':1,'source_complete':True}
        first=list(catalogue.localisation_identities(source))
        self.assertEqual(len(first),3)
        self.assertEqual(first[0]['names'],[])
        self.assertNotEqual(first[1]['id'],first[2]['id'])
        self.assertEqual(list(catalogue.localisation_identities(first[0])),first)

    def test_header_prefix_endian_unknown_and_diagnostic_bounds(self):
        for endian,magic in (('<',b'\xc1\x83\x2a\x9e'),('>',b'\x9e\x2a\x83\xc1')):
            raw=magic+struct.pack(endian+'IIi',584 | 57 << 16,100,0)+struct.pack(endian+'7I',0,3,80,4,120,2,180)
            summary=installation.header_info(raw)
            self.assertEqual(summary['file_version'],584)
            self.assertEqual(summary['licensee_version'],57)
            self.assertEqual(summary['import_count'],2)
        self.assertEqual(installation.header_info(b'other')['summary_status'],'unrecognized')
        self.assertEqual(installation.header_info(raw[:8])['summary_status'],'unrecognized')
        scan=installation.InstallationScan(None,policy.LIMITS,0)
        for _ in range(205):
            scan.error('file',ValueError('bad'))
            scan.limit('limit')
        self.assertEqual(len(scan.summary['errors']),200)
        self.assertEqual(scan.summary['error_omissions'],5)
        self.assertEqual(len(scan.summary['limits_hit']),200)
        self.assertEqual(scan.summary['limit_omissions'],5)

    def test_installation_detected_from_embedded_executable(self):
        game,_=self.fixture()
        executable=game/'Binaries'/'Win64'/'BorderlandsGOTY.exe'
        with patch.object(installation.sys,'executable',str(executable)):
            self.assertEqual(installation.game_root(),game)


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

    def test_unreferenced_pawn_templates_after_package_load_have_name_seeds(self):
        sdk=SDK()
        special=Class('SpecialBossPawn',['AIPawnName','InventoryDefinition','Health'],sdk.pawn)
        sdk.classes.append(special)
        pawn=Object('gd_Character.Boss',special,AIPawnName='Unvisited Boss',InventoryDefinition=None,Health=1234)
        sdk.on_load=lambda _:sdk.objects.append(pawn)
        job=Job(sdk,self.root,metadata('catalogue'),[{'name':'gd_Character'}])
        pump(job)
        self.assertEqual(job.state,'complete',job.failures)
        raw=records(self.root)
        binding=next(r for r in raw if r['record_type']=='archetype_binding')
        self.assertNotIn('Health',binding['properties'])
        self.assertEqual(binding['properties']['AIPawnName'],'Unvisited Boss')
        seed=next(r for r in raw if r['record_type']=='catalogue_identity' and r['asset_path']==pawn.path)
        self.assertEqual(seed['category'],'character')
        self.assertEqual(seed['names'][0]['name'],'Unvisited Boss')
        self.assertEqual(pawn.ObjectFlags,0)

    def test_travel_lookup_object_and_level_list_are_exported_without_loading_maps(self):
        sdk=SDK()
        lookup_cls=Class('EmergencyTeleportOutpostLookup',['OutpostLookupList'])
        station_cls=Class('TeleportOutpostLookupObject',['OutpostName','OutpostDisplayName'])
        levels_cls=Class('LevelDependencyList',['PersistentLevelName','SubLevelName'])
        sdk.classes.extend([lookup_cls,station_cls,levels_cls])
        station=Object('gd_test.Travel:Station',station_cls,OutpostName='Fyrestone',OutpostDisplayName='Fyrestone')
        lookup=Object('gd_test.Travel',lookup_cls,OutpostLookupList=[station])
        levels=Object('gd_test.Levels',levels_cls,PersistentLevelName='Arid_P',SubLevelName='Arid_Spawnbox')
        sdk.objects.extend([station,lookup,levels])
        job=Job(sdk,self.root,metadata(),[])
        job.engine.classes=lambda:[lookup_cls._path_name(),levels_cls._path_name()]
        pump(job)
        self.assertEqual(job.state,'complete',job.failures)
        raw=records(self.root)
        seed=next(r for r in raw if r['record_type']=='catalogue_identity' and r.get('asset_path')==station.path)
        self.assertEqual(seed['category'],'location')
        self.assertEqual(seed['names'][0]['name'],'Fyrestone')
        self.assertTrue(any(r.get('category')=='map' and r.get('asset_path_hint')=='Arid_P' for r in raw))
        self.assertEqual(sdk.loads,[])
        self.assertTrue(all(o.ObjectFlags==0 for o in sdk.objects))

    def test_resume_rebuilds_seeds_when_source_committed_before_chunk_boundary_crash(self):
        source=next(r for r in INDEX_FIXTURE['records'] if r['class']=='WillowGame.MissionDefinition')
        ds=Dataset(self.root,metadata(),max_records=1)
        ds.add(source);ds.checkpoint(status='paused')
        job=Job(SDK(),self.root,metadata(),[],resume=True)
        self.assertEqual(job.phase,'reindex')
        pump(job)
        raw=records(self.root)
        expected=list(catalogue.identities(source))
        self.assertEqual({r['id'] for r in raw},{source['id']}|{r['id'] for r in expected})
        self.assertEqual(job.dataset.counts['catalogue_identity'],len(expected))
        self.assertEqual(job.dataset.manifest['catalogue']['named_records'],sum(bool(r['names']) for r in expected))

    def test_resume_recovers_localised_field_seeds_from_committed_primary(self):
        source={'record_type':'catalogue_identity','id':'identity:localisation:test:hash','category':'mission',
                'identity_status':'localisation_candidate','names':[{'name':'Quest','field':'MissionName','line':2},
                    {'name':'Dr. Zed','field':'MissionGiver','line':3}],
                'source_record':'file:test@0','source_file':'test.int','source_sha256':'hash',
                'section':'Quest MissionDefinition','section_occurrence':1,'source_complete':True}
        expected=list(catalogue.localisation_identities(source))
        ds=Dataset(self.root,metadata(),max_records=1)
        ds.add({'record_type':'localisation_file','id':'file:test@0'})
        ds.add(expected[0]);ds.checkpoint(status='paused')
        job=Job(SDK(),self.root,metadata(),[],resume=True);pump(job)
        raw=records(self.root)
        child=next(r for r in raw if r.get('category')=='mission_giver')
        self.assertEqual(child,expected[1])
        self.assertEqual(job.dataset.counts['catalogue_identity'],2)

    def test_identity_limit_and_early_installation_finish_are_visible(self):
        sdk=SDK();sdk.weapon();sdk.weapon('gd_test.Second')
        job=Job(sdk,self.root,metadata(),[],limits={'identities':1})
        pump(job)
        self.assertEqual(job.dataset.counts['catalogue_identity'],1)
        self.assertIn('identity limit',job.dataset.manifest['coverage']['limits_hit'])
        other=Path(self.temp.name)/'early'
        early=Job(sdk,other,metadata('catalogue'),[])
        early.finish('Ended before installed-content scan');pump(early)
        self.assertEqual(early.installation.summary['status'],'partial')
        self.assertFalse(early.dataset.manifest['catalogue']['complete'])

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

    def test_stale_status_files_deleted_without_further_writes(self):
        self.run_lifecycle(archive=True, stale_status='delete')

    def test_locked_status_files_cannot_stop_export(self):
        self.run_lifecycle(archive=True, stale_status='locked')

    def test_world_change_detection_without_status_file(self):
        self.run_lifecycle(archive=False, world_change=True)

    def test_partial_finish_logs_without_status_file(self):
        self.run_lifecycle(archive=False, early=True)

    def run_lifecycle(self, archive, missing=None, stale_status=None, world_change=False, early=False):
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
            status_files=[Path(temp)/'BorderlensExtractor'/name for name in ('status.json','status.json.tmp')]
            if stale_status:
                status_files[0].parent.mkdir(parents=True)
                for path in status_files:path.write_text('obsolete')
            original_open,original_unlink=Path.open,Path.unlink
            def status_safe_open(path,mode='r',*args,**kwargs):
                if path.name in ('status.json','status.json.tmp') and any(c in mode for c in 'wax+'):
                    raise AssertionError('Status files must never be written')
                return original_open(path,mode,*args,**kwargs)
            def status_unlink(path,*args,**kwargs):
                if stale_status=='locked' and path in status_files:raise PermissionError('Windows file is locked')
                return original_unlink(path,*args,**kwargs)
            open_guard=patch.object(Path,'open',new=status_safe_open)
            unlink_guard=patch.object(Path,'unlink',new=status_unlink)
            open_guard.start();unlink_guard.start()
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
                self.assertTrue(all(p.exists() == (stale_status=='locked') for p in status_files))
                if stale_status=='locked':
                    self.assertEqual(sum('Could not delete obsolete' in line for line in logs),2)
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
                loaded.show_status()
                self.assertTrue(any('"records"' in line for line in logs))
                if world_change:
                    previous=loaded.job
                    world.path='OtherMap.TheWorld.PersistentLevel.WorldInfo'
                    loaded.last_world_check=loaded.time.monotonic()-2
                    loaded.on_render(None,None,None,None)
                    self.assertIsNone(loaded.job,logs)
                    self.assertEqual(previous.state,'paused')
                    self.assertTrue(any('Export stopped for world change' in line for line in logs))
                    self.assertTrue(all(o.ObjectFlags==0 for o in sdk.objects))
                    return
                if early:loaded.finish_early()
                with patch.object(loaded.time,'monotonic',return_value=loaded.last_log+11):
                    loaded.on_render(None,None,None,None)
                self.assertTrue(any(' records; ' in line for line in logs))
                for _ in range(1000):
                    loaded.on_render(None,None,None,None)
                    if loaded.job.state=='complete':break
                self.assertEqual(loaded.job.state,'complete',logs)
                self.assertTrue(loaded.job.bundle.output.exists())
                self.assertEqual(sdk.loads,[])
                self.assertTrue(all(p.exists() == (stale_status=='locked') for p in status_files))
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
                unlink_guard.stop();open_guard.stop()
                for name,value in saved.items():
                    if value is None:sys.modules.pop(name,None)
                    else:sys.modules[name]=value
                for name in list(sys.modules):
                    if name.startswith('BorderlensExtractor.'):sys.modules.pop(name,None)


if __name__=='__main__':unittest.main()
