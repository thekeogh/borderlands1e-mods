"""Flash API and map projection models; native Windows rendering is unverified."""
from copy import deepcopy
from enum import IntEnum
from pathlib import Path
import hashlib
import json
from types import SimpleNamespace as NS
import unittest

from test_atlas import Harness,Object,prop,function


class MovieModel(Object):
    def __init__(self,rows,api):
        super().__init__('Transient.StatusMenuExGFxMovie_0')
        self.Class=NS(_fields=lambda:api)
        self.MapHelper=NS(MapObjects=rows,bIsMinimap=False)
        self.values={}
        self.calls=[]
        self.next_depth=500
        self.depths={}
        self.arrays={'mapItems':[],'tooltipTitles':[],'tooltipBodies':[]}
        for row in rows:
            path=row.AS_IconPath
            p=row.TransformedLocation
            self.values[path+'._x']=p.X*1000+7
            self.values[path+'._y']=p.Y*600+12
            self.values[path+'._alpha']=100
    def GetVariableNumber(self,**kw):
        path=kw['path'];self.calls.append(('get',path))
        if path.endswith('.length') and path[:-7] in self.arrays:
            return True,len(self.arrays[path[:-7]])
        return (path in self.values,self.values.get(path,0))
    def GetVariableString(self,**kw):
        path=kw['Path'];array,_,index=path.rpartition('.')
        return self.arrays[array][int(index)] if array in self.arrays else self.values.get(path,'')
    def SetVariableNumber(self,**kw):
        self.calls.append(('set',kw['path'],kw['value']))
        self.values[kw['path']]=kw['value'];return True
    def Invoke(self,**kw):
        method,args=kw['method'],kw['args']
        self.calls.append(('invoke',method,args))
        if method.endswith('.getNextHighestDepth'):
            return NS(Type=2,N=self.next_depth+1)
        if method.endswith('.duplicateMovieClip'):
            parent=method.rsplit('.',2)[0]
            path=parent+'.'+args[0].S
            self.values[path+'._alpha']=100
            self.depths[path]=int(args[1].N)
            self.next_depth=max(self.next_depth,int(args[1].N))
        if method=='AddLandmark':
            self.next_depth+=1
            path=args[0].S.rpartition('.')[0]+'.'+args[4].S+str(self.next_depth)
            self.values[path+'._alpha']=100
            self.depths[path]=self.next_depth
            self.arrays['mapItems'].append(path)
            self.arrays['tooltipTitles'].append(args[5].S)
            self.arrays['tooltipBodies'].append(args[6].S)
            # The native root function returns ASValue's reflected string type.
            invoke=next(f for f in self.Class._fields() if f.Name in ('Invoke','InvokeMethod'))
            struct=next(p.Inner.Struct for p in invoke._properties() if p.Class.Name=='ArrayProperty')
            enum=struct._properties()[0].Enum._as_py()
            return NS(Type=int(enum.AS_String),S=path)
        if method=='UpdatePlayerWaypointTooltipText':
            for i,path in enumerate(self.arrays['mapItems']):
                if path==args[0].S:self.arrays['tooltipBodies'][i]=args[1].S
        if method.endswith('.splice'):
            array=self.arrays[method[:-7]];index,count=int(args[0].N),int(args[1].N)
            array[index:index+count]=[a.S for a in args[2:]]
        if method.endswith('.getDepth'):
            path=method.rsplit('.',1)[0]
            return NS(Type=2,N=self.depths.get(path,-1))
        if method.endswith('.removeMovieClip'):
            path=method.rsplit('.',1)[0]
            for key in list(self.values):
                if key.startswith(path+'.'):del self.values[key]
        return NS(Type=0,N=0)


class RendererTests(unittest.TestCase):
    def setUp(self):
        self.h=Harness();self.addCleanup(self.h.close)
        import sys
        self.module=sys.modules['atlas_test.renderer']
        types=IntEnum('ASType',{'AS_Undefined':0,'AS_Null':1,'AS_Number':2,'AS_Boolean':3,'AS_String':4})
        fields=[prop('Type','ByteProperty',Enum=NS(_as_py=lambda:types)),prop('N','FloatProperty'),prop('S','StrProperty')]
        asvalue=Object('GFxUI.GFxMovie:ASValue',_properties=lambda:fields)
        invoke=function('Invoke',[prop('method','StrProperty'),prop('args','ArrayProperty',Inner=prop('Inner','StructProperty',Struct=asvalue)),prop('ReturnValue','StructProperty',0x580,Struct=asvalue)],'GFxUI.GFxMovie')
        get=function('GetVariableNumber',[prop('path','StrProperty'),prop('value','FloatProperty',0x180),prop('ReturnValue','BoolProperty',0x580)],'GFxUI.GFxMovie')
        put=function('SetVariableNumber',[prop('path','StrProperty'),prop('value','FloatProperty'),prop('ReturnValue','BoolProperty',0x580)],'GFxUI.GFxMovie')
        # This is a supported interface model, not a claimed captured signature.
        self.api=[invoke,get,put]
        fixture=json.loads((Path(__file__).parent/'fixtures/bl1e-mapobjects-0.1.1.json').read_text())
        rows=[]
        for raw in fixture['custom_map_objects']:
            raw=dict(raw);raw['CustomObjectLoc']=NS(**raw['CustomObjectLoc']);raw['TransformedLocation']=NS(**raw['TransformedLocation'])
            rows.append(NS(**raw))
        self.rows=rows
        self.movie=MovieModel(rows,self.api)
        self.points=[{'key':'OtherWaypoint','x':10000.,'y':20000.,'label':'Other Mission'}]
        self.renderer=self.h.atlas.renderer

    def test_captured_world_positions_calibrate_without_assumed_axis_direction(self):
        anchors=[(r.CustomObjectLoc.X,r.CustomObjectLoc.Y,r.TransformedLocation.X,r.TransformedLocation.Y) for r in self.rows]
        coefficients=self.module.affine(anchors)
        for x,y,u,v in anchors:
            a,b=self.module.project(coefficients,x,y)
            self.assertAlmostEqual(a,u);self.assertAlmostEqual(b,v)
        # Captured Trash map is rotated relative to world XY.
        self.assertGreater(abs(coefficients[0][1]),abs(coefficients[0][0])*100)

    def test_degenerate_or_inconsistent_anchor_data_is_rejected(self):
        with self.assertRaises(ValueError):self.module.affine([(0,0,0,0),(1,1,1,1),(2,2,2,2)])
        with self.assertRaises(ValueError):self.module.affine([(0,0,0,0),(100,0,100,0),(0,100,0,100),(50,50,999,999)])
        with self.assertRaises(ValueError):self.module.affine([(0,0,0,0),(100,0,0,0),(0,100,0,0)])

    def test_only_own_flash_clips_change_and_native_mapobjects_are_untouched(self):
        before=deepcopy([vars(r) for r in self.rows]);native_values=dict(self.movie.values)
        self.renderer.update(self.movie,self.points,55,10)
        self.assertIsNone(self.renderer.last_error)
        self.assertEqual(self.h.atlas.counts['clips_created'],1)
        self.assertEqual(before,[vars(r) for r in self.rows])
        for key,value in native_values.items():self.assertEqual(self.movie.values[key],value)
        path=self.renderer.clips['OtherWaypoint']
        self.assertIn('._mission_atlas_',path)
        self.assertEqual(self.movie.values[path+'._alpha'],55)
        self.assertEqual(self.movie.values[path+'.enabled'],0)
        sets=[c[1] for c in self.movie.calls if c[0]=='set']
        self.assertTrue(all('._mission_atlas_' in p for p in sets))

    def test_pan_and_zoom_update_own_positions_without_new_clips(self):
        self.renderer.update(self.movie,self.points,55,10)
        path=self.renderer.clips['OtherWaypoint'];x=self.movie.values[path+'._x'];y=self.movie.values[path+'._y']
        for row in self.rows:
            key=row.AS_IconPath
            self.movie.values[key+'._x']=self.movie.values[key+'._x']*1.5+20
            self.movie.values[key+'._y']=self.movie.values[key+'._y']*1.5-30
        self.renderer.update(self.movie,self.points,55,10.2)
        self.assertAlmostEqual(self.movie.values[path+'._x'],x*1.5+20)
        self.assertAlmostEqual(self.movie.values[path+'._y'],y*1.5-30)
        self.assertEqual(self.h.atlas.counts['clips_created'],1)

    def test_high_frequency_calls_are_throttled_and_stationary_clips_not_rewritten(self):
        self.renderer.update(self.movie,self.points,55,10)
        calls=len(self.movie.calls)
        for i in range(90):self.renderer.update(self.movie,self.points,55,10+i/1000)
        self.assertEqual(len(self.movie.calls),calls)
        sets=sum(c[0]=='set' for c in self.movie.calls)
        self.renderer.update(self.movie,self.points,55,10.2)
        self.assertEqual(sum(c[0]=='set' for c in self.movie.calls),sets)

    def test_removed_missions_remove_only_owned_clips(self):
        self.renderer.update(self.movie,self.points,55,10)
        path=self.renderer.clips['OtherWaypoint']
        self.renderer.update(self.movie,[],55,10.2)
        self.assertEqual(self.renderer.clips,{})
        self.assertFalse(any(k.startswith(path+'.') for k in self.movie.values))
        self.assertEqual(self.h.atlas.counts['clips_removed'],1)

    def test_reset_and_disable_clean_owned_icons(self):
        self.renderer.update(self.movie,self.points,55,10)
        self.h.objects['StatusMenuExGFxMovie']=[self.movie]
        self.h.atlas.disable()
        self.assertEqual(self.renderer.clips,{})
        self.assertFalse(any('._mission_atlas_' in k for k in self.movie.values))

    def test_minimap_never_gets_extra_clips(self):
        self.movie.MapHelper.bIsMinimap=True
        self.renderer.update(self.movie,self.points,55,10)
        self.assertEqual(self.renderer.clips,{})
        self.assertEqual(self.movie.calls,[])

    def test_missing_api_is_reported_and_failed_probes_back_off(self):
        self.movie.Class=NS(_fields=lambda:[])
        self.renderer.update(self.movie,self.points,55,10)
        self.assertIn('lacks Flash API',self.renderer.last_error)
        self.movie.Class=NS(_fields=lambda:self.fail('Probe retried on mouse movement'))
        self.renderer.update(self.movie,self.points,55,10.2)

    def test_unknown_asvalue_enum_fails_without_native_calls(self):
        struct=self.api[0]._properties()[1].Inner.Struct
        struct._properties()[0].Enum=None
        self.renderer.update(self.movie,self.points,55,10)
        self.assertIn('enum',self.renderer.last_error)
        self.assertEqual(self.movie.calls,[])

    def test_native_creation_exception_is_not_retried(self):
        original=self.movie.Invoke;attempts=[]
        def fail(**values):
            if values['method']=='AddLandmark':
                attempts.append(values['method']);raise RuntimeError('native creation failed')
            return original(**values)
        self.movie.Invoke=fail
        self.renderer.update(self.movie,self.points,55,10)
        self.renderer.update(self.movie,self.points,55,10.2)
        self.assertEqual(len(attempts),1)
        self.assertEqual(self.h.atlas.counts['clips_created'],0)

    def test_readback_failure_does_not_claim_creation(self):
        original=self.movie.SetVariableNumber
        def missing(**values):
            if values['path'].endswith('._alpha'):return False
            return original(**values)
        self.movie.SetVariableNumber=missing
        self.renderer.update(self.movie,self.points,55,10)
        self.assertIsNotNone(self.renderer.last_error)
        self.assertEqual(self.h.atlas.counts['clips_created'],0)

    def test_scalar_getter_variant_is_supported(self):
        self.api[1]._properties=lambda:[prop('path','StrProperty'),prop('ReturnValue','FloatProperty',0x580)]
        self.movie.GetVariableNumber=lambda **kw:self.movie.values[kw['path']]
        self.renderer.update(self.movie,self.points,55,10)
        self.assertIsNone(self.renderer.last_error)

    def test_verified_clips_rebuild_after_native_container_replacement(self):
        self.renderer.update(self.movie,self.points,55,10)
        previous=self.renderer.clips['OtherWaypoint']
        for key in list(self.movie.values):
            if '._mission_atlas_' in key:del self.movie.values[key]
        self.renderer.update(self.movie,self.points,55,11.2)
        self.assertIsNone(self.renderer.last_error)
        self.assertNotEqual(self.renderer.clips['OtherWaypoint'],previous)
        self.assertEqual(self.h.atlas.counts['clips_created'],2)

    def test_multiple_icons_use_unique_names_and_native_next_depth(self):
        points=self.points+[{'key':'Second','x':20000,'y':30000,'label':'Second'}]
        self.renderer.update(self.movie,points,55,10)
        creates=[c for c in self.movie.calls if c[0]=='invoke' and c[1]=='AddLandmark']
        self.assertEqual(len(creates),2)
        self.assertEqual(len({c[2][4].S for c in creates}),2)
        self.assertEqual(len(set(self.movie.depths.values())),2)

    def test_reflected_float_and_invokemethod_aliases(self):
        aliases={'Invoke':'InvokeMethod','GetVariableNumber':'GetVariableFloat','SetVariableNumber':'SetVariableFloat'}
        for fn in self.api:
            original=fn.Name
            fn.Name=aliases[original]
            setattr(self.movie,fn.Name,getattr(self.movie,original))
        self.renderer.update(self.movie,self.points,55,10)
        self.assertIsNone(self.renderer.last_error)
        self.assertEqual(self.h.atlas.counts['clips_created'],1)

    def test_no_points_clean_existing_clips_even_without_native_template(self):
        self.renderer.update(self.movie,self.points,55,10)
        self.movie.MapHelper.MapObjects=[]
        self.renderer.update(self.movie,[],55,10.2)
        self.assertEqual(self.renderer.clips,{})
        self.assertEqual(self.h.atlas.counts['visible_extra_clips'],0)
        self.assertIsNone(self.renderer.last_error)

    def test_actual_captured_bl1e_flash_signature_and_string_enum(self):
        fixture=json.loads((Path(__file__).parent/'fixtures/bl1e-waypoint-groups-0.1.2.json').read_text())
        members=fixture['asvalue']['properties'][0]['enum_values']
        enum=IntEnum('CapturedASType',members)
        struct=Object('GFxUI.GFxMovie:ASValue',_properties=lambda:[prop('Type','ByteProperty',Enum=NS(_as_py=lambda:enum)),prop('N','FloatProperty'),prop('S','StrProperty'),prop('B','BoolProperty')])
        functions=[]
        for path,parameters in fixture['flash_functions'].items():
            fields=[]
            for field in parameters:
                extra={}
                if field['type']=='StructProperty':extra['Struct']=struct
                if field['type']=='ArrayProperty':extra['Inner']=prop('Inner','StructProperty',Struct=struct)
                fields.append(prop(field['name'],field['type'],field['flags'],**extra))
            owner,_,name=path.rpartition(':')
            functions.append(function(name,fields,owner))
        self.movie.Class=NS(_fields=lambda:functions)
        original=self.movie.Invoke
        self.movie.Invoke=lambda **kw:original(method=kw['Method'],args=kw['Args'])
        self.movie.GetVariableNumber=lambda **kw:self.movie.values.get(kw['Path'],0)
        def put(**kw):self.movie.values[kw['Path']]=kw['F']
        self.movie.SetVariableNumber=put
        self.renderer.update(self.movie,self.points,55,10)
        self.assertIsNone(self.renderer.last_error)
        self.assertEqual(self.renderer.plan['Invoke']['string'],3)
        self.assertEqual(self.h.atlas.counts['clips_created'],1)

    def test_nested_enum_struct_schemas_can_be_exported(self):
        self.h.classes['StatusMenuExGFxMovie']=Object('WillowGame.StatusMenuExGFxMovie',_fields=lambda:self.api,_properties=lambda:[])
        self.h.atlas.discover()
        schema=self.h.atlas.schemas['GFxUI.GFxMovie:ASValue']
        self.assertEqual(schema['properties'][0]['enum_values']['AS_Number'],2)

if __name__=='__main__':unittest.main()
