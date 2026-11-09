"""Native tooltip-row integration models; Windows hover/focus still needs testing."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import json
import math
import sys
import tempfile
import unittest

from test_atlas import Object,prop,function
import test_renderer as models


class Helper(Object):
    def __init__(self,rows,cls):
        super().__init__('Transient.WillowGFxHelperMap_0',Class=cls,bIsMinimap=False)
        self._rows=rows
        self.fail_next=False
        self.refreshes=0
        self.mouse=None
        self.controller_focus=None
        self.visible_label=None
    @property
    def MapObjects(self):return self._rows
    @MapObjects.setter
    def MapObjects(self,value):
        if self.fail_next:
            self.fail_next=False;self._rows=list(value[:1]);raise RuntimeError('native copy failed')
        self._rows=list(value)
    def UpdateMapTooltips(self,**kw):
        self.refreshes+=1
        focus=self.mouse if self.mouse is not None else self.controller_focus
        self.visible_label=None
        if focus is None:return
        # A model of native hover-only lookup, not the game's measured hitbox.
        for row in self.MapObjects:
            uv=row.TransformedLocation
            if math.hypot(uv.X-focus[0],uv.Y-focus[1]) < .0001:
                movie=kw.get('Movie')
                if (movie is not None and str(row.AS_IconPath).rsplit('.',1)[-1].startswith('_mission_atlas_')
                        and (not movie.values.get(row.AS_IconPath+'.enabled',0)
                             or row.AS_IconPath not in movie.arrays['mapItems'])):
                    continue
                if movie is not None and row.AS_IconPath in movie.arrays['mapItems']:
                    i=movie.arrays['mapItems'].index(row.AS_IconPath)
                    self.visible_label=movie.arrays['tooltipBodies'][i]
                else:self.visible_label=row.TooltipBody or row.TooltipTitle
                break


class TooltipTests(unittest.TestCase):
    def setUp(self):
        self.rig=models.RendererTests('test_captured_world_positions_calibrate_without_assumed_axis_direction')
        self.rig.setUp();self.addCleanup(self.rig.doCleanups)
        self.h=self.rig.h;self.renderer=self.rig.renderer;self.movie=self.rig.movie
        self.module=sys.modules['atlas_test.tooltips']
        # This row layout comes from the actual uploaded BL1E schema.
        required={'Player':'ObjectProperty','Landmark':'ObjectProperty','ClientInteractiveObject':'ObjectProperty','WPRI':'ObjectProperty',
                  'bWaypoint':'BoolProperty','CustomObjectLoc':'StructProperty','bIsDirty':'BoolProperty',
                  'TransformedLocation':'StructProperty','Angle':'FloatProperty','AS_IconClipPath':'StrProperty',
                  'AS_IconClipFrame':'StrProperty','AS_IconPath':'StrProperty','TooltipTitle':'StrProperty','TooltipBody':'StrProperty'}
        fields=[]
        for name,kind in required.items():
            extra={}
            if name=='CustomObjectLoc':extra['Struct']=Object('Core.Object:Vector')
            if name=='TransformedLocation':extra['Struct']=Object('Core.Object:Vector2D')
            fields.append(prop(name,kind,**extra))
        struct=Object('WillowGame.WillowGFxHelperMap:MapObjectData',_properties=lambda:fields)
        array=prop('MapObjects','ArrayProperty',Inner=prop('Inner','StructProperty',Struct=struct))
        refresh=function('UpdateMapTooltips',[prop('Movie')],'WillowGame.WillowGFxHelperMap')
        cls=Object('WillowGame.WillowGFxHelperMap',_properties=lambda:[array],_fields=lambda:[refresh])
        self.helper=Helper(list(self.rig.rows),cls);self.movie.MapHelper=self.helper
        self.points=[{'key':'OtherWaypoint','x':10000.,'y':20000.,'z':1500.,'label':'Other Mission'}]
        self.original=deepcopy([vars(r) for r in self.helper.MapObjects])
    def update(self,now=10):self.renderer.update(self.movie,self.points,55,now)
    def own_rows(self):return [r for r in self.helper.MapObjects if self.module.own_clip(r.AS_IconPath)]

    def test_normal_updates_do_not_sample_diagnostic_geometry(self):
        self.update()
        self.renderer.tooltips.interaction_snapshot=lambda *_:self.fail('Periodic diagnostic sampling')
        self.update(11.2)
        self.renderer.tooltips.poll_hover(self.movie,12.4)

    def test_manual_export_does_not_install_temporary_flash_tracers(self):
        self.update()
        self.h.objects['StatusMenuExGFxMovie']=[self.movie]
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(self.h.atlas,'snapshot',return_value={'manual':True}):
                with patch.object(self.h.runtime,'add_hook') as add:
                    report=self.h.atlas.export(folder)
                    self.assertIsNotNone(report)
                    add.assert_not_called()
            self.assertEqual(len(list(Path(folder).glob('*.json'))),1)

    def test_mission_label_is_metadata_and_is_hidden_without_hover(self):
        self.update()
        self.assertIsNone(self.renderer.tooltips.last_error)
        rows=self.own_rows();self.assertEqual(len(rows),1)
        self.assertEqual(rows[0].TooltipTitle,'Objective');self.assertEqual(rows[0].TooltipBody,'Other Mission')
        self.assertIsNone(self.helper.visible_label)
        # Text is passed only to the native registry functions, not painted as
        # a permanent label beside the marker.
        calls=[c for c in self.movie.calls if 'Other Mission' in str(c)]
        self.assertTrue(calls)
        self.assertTrue(all(c[0]=='invoke' and c[1] in ('AddLandmark','UpdatePlayerWaypointTooltipText') for c in calls))
    def test_mouse_hover_shows_name_and_leaving_clears_it(self):
        self.update();row=self.own_rows()[0]
        self.helper.mouse=(row.TransformedLocation.X,row.TransformedLocation.Y)
        self.helper.UpdateMapTooltips(Movie=self.movie)
        self.assertEqual(self.helper.visible_label,'Other Mission')
        self.helper.mouse=None;self.helper.UpdateMapTooltips(Movie=self.movie)
        self.assertIsNone(self.helper.visible_label)
    def test_controller_focus_uses_the_same_native_lookup(self):
        self.update();row=self.own_rows()[0]
        self.helper.controller_focus=(row.TransformedLocation.X,row.TransformedLocation.Y)
        self.helper.UpdateMapTooltips(Movie=self.movie)
        self.assertEqual(self.helper.visible_label,'Other Mission')
        self.helper.controller_focus=(99,99);self.helper.UpdateMapTooltips(Movie=self.movie)
        self.assertIsNone(self.helper.visible_label)
    def test_native_rows_order_values_and_active_tooltip_are_unchanged(self):
        self.update()
        native=[vars(r) for r in self.helper.MapObjects if not self.module.own_clip(r.AS_IconPath)]
        self.assertEqual(native,self.original)
        row=self.rig.rows[-1]
        self.helper.mouse=(row.TransformedLocation.X,row.TransformedLocation.Y)
        self.helper.UpdateMapTooltips(Movie=self.movie)
        self.assertEqual(self.helper.visible_label,row.TooltipBody or row.TooltipTitle)
    def test_rows_reference_only_verified_own_clips_and_world_position(self):
        self.update();row=self.own_rows()[0]
        self.assertEqual(row.AS_IconPath,self.renderer.clips['OtherWaypoint'])
        self.assertEqual(row.CustomObjectLoc.Z,1500)
        self.assertIsNone(row.Player);self.assertIsNone(row.Landmark)
        self.assertIsNone(row.ClientInteractiveObject);self.assertIsNone(row.WPRI)
        self.assertFalse(row.bWaypoint);self.assertFalse(row.bIsDirty)
    def test_unchanged_rows_still_query_focus_without_duplicate_registration(self):
        self.update();refreshes=self.helper.refreshes
        writes=self.h.atlas.counts['tooltip_rows_written']
        self.update(10.2);self.update(10.4)
        self.assertEqual(len(self.own_rows()),1)
        self.assertEqual(self.helper.refreshes,refreshes+2)
        self.assertEqual(self.h.atlas.counts['tooltip_rows_written'],writes)
    def test_stationary_marker_hover_enter_and_leave_use_render_updates(self):
        self.update();row=self.own_rows()[0]
        self.helper.mouse=(row.TransformedLocation.X,row.TransformedLocation.Y)
        self.update(10.2)
        self.assertEqual(self.helper.visible_label,'Other Mission')
        self.helper.mouse=None;self.update(10.4)
        self.assertIsNone(self.helper.visible_label)
    def test_stationary_controller_focus_uses_render_updates(self):
        self.update();row=self.own_rows()[0]
        self.helper.controller_focus=(row.TransformedLocation.X,row.TransformedLocation.Y)
        self.update(10.2)
        self.assertEqual(self.helper.visible_label,'Other Mission')
        self.helper.controller_focus=None;self.update(10.4)
        self.assertIsNone(self.helper.visible_label)
    def test_hover_queries_remain_throttled_at_ten_hz(self):
        self.update();refreshes=self.helper.refreshes
        for i in range(1,90):self.update(10+i/1000)
        self.assertEqual(self.helper.refreshes,refreshes)
    def test_typed_enabled_setter_is_used_when_native_interface_supports_it(self):
        self.rig.api.append(function('SetVariableBool',[prop('Path','StrProperty'),prop('B','BoolProperty')],'GFxUI.GFxMovie'))
        writes=[]
        def setter(**kw):
            writes.append(kw);self.movie.values[kw['Path']]=kw['B']
        self.movie.SetVariableBool=setter
        self.update()
        self.assertTrue(writes)
        self.assertTrue(all(type(w['B']) is bool and w['B'] for w in writes))
    def test_idle_viewport_queries_focus_without_pan_or_actor_rescan(self):
        self.update();row=self.own_rows()[0]
        self.h.objects['StatusMenuExGFxMovie']=[self.movie]
        self.h.atlas.ready=True
        self.helper.controller_focus=(row.TransformedLocation.X,row.TransformedLocation.Y)
        scans=self.h.atlas.counts['point_scans']
        with patch.object(self.h.runtime.time,'monotonic',return_value=10.2):self.h.atlas.poll()
        self.assertEqual(self.helper.visible_label,'Other Mission')
        self.assertEqual(self.h.atlas.counts['point_scans'],scans)
        self.assertFalse(self.h.atlas.rendering)
        calls=self.helper.refreshes
        for i in range(1,80):
            with patch.object(self.h.runtime.time,'monotonic',return_value=10.2+i/1000):self.h.atlas.poll()
        self.assertEqual(self.helper.refreshes,calls)
    def test_closed_menu_and_unloaded_clips_do_not_query_hover(self):
        self.update();service=self.renderer.tooltips
        self.h.objects['StatusMenuExGFxMovie']=[self.movie]
        self.h.atlas.ready=True;self.h.pc.bStatusMenuOpen=False
        calls=self.helper.refreshes
        with patch.object(self.h.runtime.time,'monotonic',return_value=10.2):self.h.atlas.poll()
        self.assertEqual(self.helper.refreshes,calls)
        self.h.pc.bStatusMenuOpen=True
        path=self.renderer.clips['OtherWaypoint'];self.movie.values[path+'._alpha']=0
        with patch.object(self.h.runtime.time,'monotonic',return_value=10.4):self.h.atlas.poll()
        self.assertEqual(self.helper.refreshes,calls)
    def test_hidden_native_map_does_not_query_hover(self):
        self.rig.api.append(function('GetVariableBool',[prop('Path','StrProperty'),prop('ReturnValue','BoolProperty',0x580)],'GFxUI.GFxMovie'))
        self.movie.GetVariableBool=lambda **kw:False
        self.update();calls=self.helper.refreshes
        self.renderer.tooltips.poll_hover(self.movie,10.2)
        self.assertEqual(self.helper.refreshes,calls)
    def test_idle_query_failure_backs_off_and_keeps_diamonds(self):
        self.update()
        def failure(**kw):raise RuntimeError('native UI not ready')
        self.helper.UpdateMapTooltips=failure
        self.renderer.tooltips.poll_hover(self.movie,10.2)
        self.assertGreater(self.renderer.tooltips.retry_after,13)
        self.assertEqual(len(self.renderer.clips),1)
    def test_label_or_objective_changes_update_existing_metadata(self):
        self.update()
        self.points[0].update(label='Next objective mission',x=15000)
        self.update(10.2)
        self.assertEqual(len(self.own_rows()),1)
        self.assertEqual(self.own_rows()[0].TooltipBody,'Next objective mission')
        self.assertEqual(self.own_rows()[0].CustomObjectLoc.X,15000)
    def test_mission_removal_clears_hover_and_only_its_owned_rows(self):
        self.update();r=self.own_rows()[0]
        self.helper.mouse=(r.TransformedLocation.X,r.TransformedLocation.Y)
        self.helper.UpdateMapTooltips(Movie=self.movie);self.assertIsNotNone(self.helper.visible_label)
        self.points=[];self.update(10.2)
        self.assertEqual(self.own_rows(),[]);self.assertIsNone(self.helper.visible_label)
        self.assertEqual([vars(r) for r in self.helper.MapObjects],self.original)
    def test_disabling_removes_owned_rows_and_preserves_external_additions(self):
        self.update()
        external=deepcopy(self.rig.rows[0]);external.AS_IconPath='_level0.map.maps.other_mod_icon'
        self.helper.MapObjects.append(external)
        self.h.objects['StatusMenuExGFxMovie']=[self.movie]
        self.h.atlas.disable()
        self.assertEqual(self.own_rows(),[])
        self.assertEqual(self.helper.MapObjects[-1].AS_IconPath,external.AS_IconPath)
        self.assertEqual([vars(r) for r in self.helper.MapObjects[:-1]],self.original)
    def test_native_rebuild_re_registers_missing_tooltip_rows(self):
        self.update();self.helper.MapObjects=[r for r in self.helper.MapObjects if not self.module.own_clip(r.AS_IconPath)]
        self.update(10.2)
        self.assertEqual(len(self.own_rows()),1)
    def test_partial_native_assignment_failure_restores_original_array(self):
        self.helper.fail_next=True;self.update()
        self.assertEqual([vars(r) for r in self.helper.MapObjects],self.original)
        self.assertIsNotNone(self.renderer.tooltips.last_error)
        self.assertIsNone(self.renderer.last_error) # optional tooltip failure doesn't stop diamonds
        self.assertEqual(self.h.atlas.counts['clips_created'],1)
    def test_own_tooltip_rows_never_become_calibration_anchors_or_templates(self):
        self.update();row=self.own_rows()[0]
        row.CustomObjectLoc.X=999999;row.TransformedLocation.X=-999
        self.points[0]['label']='Updated'
        self.update(10.2)
        self.assertIsNone(self.renderer.last_error)
        self.assertIsNone(self.renderer.tooltips.last_error)
        self.assertEqual(self.own_rows()[0].TooltipBody,'Updated')
    def test_unknown_tooltip_interface_fails_safely_without_affecting_diamonds(self):
        self.helper.Class=Object('Unknown.Helper',_properties=lambda:[],_fields=lambda:[])
        self.update()
        self.assertEqual([vars(r) for r in self.helper.MapObjects],self.original)
        self.assertIsNotNone(self.renderer.tooltips.last_error)
        self.assertIsNone(self.renderer.last_error)
    def test_cleanup_assignment_failure_retains_ownership_for_retry(self):
        self.update();paths=set(self.renderer.tooltips.paths)
        self.helper.fail_next=True
        self.assertFalse(self.renderer.tooltips.clear(self.movie))
        self.assertEqual(self.renderer.tooltips.paths,paths)
        self.assertEqual(len(self.own_rows()),1)
        self.assertTrue(self.renderer.tooltips.clear(self.movie))
        self.assertEqual(self.own_rows(),[])
    def test_native_label_changes_are_corrected_only_on_owned_rows(self):
        self.update();self.own_rows()[0].TooltipBody='Wrong cached label'
        self.update(10.2)
        self.assertEqual(self.own_rows()[0].TooltipBody,'Other Mission')
        self.assertEqual([vars(r) for r in self.helper.MapObjects if not self.module.own_clip(r.AS_IconPath)],self.original)
    def test_transient_native_refresh_failure_can_recover_without_duplicate_rows(self):
        original=self.helper.UpdateMapTooltips
        self.helper.UpdateMapTooltips=lambda **kw:(_ for _ in ()).throw(RuntimeError('UI not ready'))
        self.update();self.assertIsNotNone(self.renderer.tooltips.last_error)
        self.helper.UpdateMapTooltips=original
        self.update(14)
        self.assertEqual(len(self.own_rows()),1)
        self.assertIsNone(self.renderer.tooltips.last_error)
    def test_tooltip_rows_are_exported_with_world_and_normalized_coordinates(self):
        self.update();rows=self.renderer.tooltips.describe(self.helper)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['title'],'Objective')
        self.assertEqual(rows[0]['body'],'Other Mission')
        self.assertEqual(rows[0]['world']['Z'],1500)
        self.assertTrue(all(math.isfinite(v) for v in rows[0]['map'].values()))

    def test_native_array_views_are_copied_before_array_storage_is_replaced(self):
        class InvalidatingHelper(Helper):
            @Helper.MapObjects.setter
            def MapObjects(self,value):
                for old in self._rows:old.AS_IconPath='FREED_NATIVE_STORAGE'
                self._rows=list(value)
        self.helper.__class__=InvalidatingHelper
        expected=[r.AS_IconPath for r in self.helper.MapObjects]
        self.update()
        self.assertIsNone(self.renderer.tooltips.last_error)
        native=[r.AS_IconPath for r in self.helper.MapObjects if not self.module.own_clip(r.AS_IconPath)]
        self.assertEqual(native,expected)
    def test_copying_native_ui_rows_keeps_their_original_actor_references(self):
        original=self.helper.MapObjects[0]
        actor=Object('World.NativeLandmark',Location=original.CustomObjectLoc)
        original.Landmark=actor
        self.update()
        self.assertIsNone(self.renderer.tooltips.last_error)
        self.assertIs(self.helper.MapObjects[0].Landmark,actor)

    def test_hover_is_enabled_but_activation_handlers_are_disabled(self):
        self.update();path=self.renderer.clips['OtherWaypoint']
        self.assertEqual(self.movie.values[path+'.enabled'],1)
        for handler in ('onPress','onRelease','onReleaseOutside'):
            self.assertEqual(self.movie.values[path+'.'+handler],0)
        self.assertNotIn(path+'.onRollOver',self.movie.values)
        self.assertNotIn(path+'.onRollOut',self.movie.values)
        self.assertNotIn(path+'.onSetFocus',self.movie.values)
        self.assertNotIn(path+'.onKeyDown',self.movie.values)
    def test_native_binding_cannot_reenable_click_actions_but_focus_bindings_survive(self):
        original=self.helper.UpdateMapTooltips
        focus=lambda:None
        def bind(**kw):
            for path in self.renderer.tooltips.paths:
                self.movie.values[path+'.onPress']=lambda:None
                self.movie.values[path+'.onSetFocus']=focus
                self.movie.values[path+'.onRollOver']=focus
            original(**kw)
        self.helper.UpdateMapTooltips=bind
        self.update();path=self.renderer.clips['OtherWaypoint']
        self.assertEqual(self.movie.values[path+'.onPress'],0)
        self.assertIs(self.movie.values[path+'.onSetFocus'],focus)
        self.assertIs(self.movie.values[path+'.onRollOver'],focus)
    def test_native_header_is_localized_and_mission_is_in_nonempty_body(self):
        template=next(r for r in self.helper.MapObjects if r.AS_IconClipFrame=='objective')
        template.TooltipTitle='Localized Objective'
        self.update();row=self.own_rows()[0]
        self.assertEqual(row.TooltipTitle,'Localized Objective')
        self.assertEqual(row.TooltipBody,'Other Mission')
    def test_interaction_report_records_only_own_clip_geometry(self):
        self.update();path=self.renderer.clips['OtherWaypoint']
        self.movie.values[path+'._width']=18;self.movie.values[path+'._height']=18
        self.movie.values[path+'._currentframe']=7
        report=self.renderer.tooltips.interaction_snapshot(self.movie)
        self.assertEqual(report['clips'][0]['_width'],18)
        self.assertEqual(report['clips'][0]['_currentframe'],7)
        self.assertEqual(report['clips'][0]['clip'],path)

    def test_normal_discovery_never_installs_global_flash_observers(self):
        cls=Object('WillowGame.StatusMenuExGFxMovie',_properties=lambda:[],_fields=lambda:self.rig.api)
        self.h.classes['StatusMenuExGFxMovie']=cls
        self.h.atlas.discover()
        self.assertFalse(any(p.startswith('GFxUI.GFxMovie:') for p,t,i in self.h.callbacks))

    def test_captured_empty_body_registration_now_matches_native_tooltip_format(self):
        raw=json.loads((Path(__file__).parent/'fixtures/bl1e-tooltip-registration-0.1.4.json').read_text())
        self.assertEqual(raw['registered_tooltips'],6)
        self.assertTrue(all(r['body']=='' for r in raw['tooltip_rows']))
        mission=raw['tooltip_rows'][0]['title']
        self.points[0]['label']=mission;self.update()
        row=self.own_rows()[0]
        self.assertEqual(row.TooltipTitle,self.rig.rows[-1].TooltipTitle)
        self.assertEqual(row.TooltipBody,mission)
        self.assertEqual(self.movie.values[row.AS_IconPath+'.enabled'],1)
    def test_native_binding_failure_still_removes_activation_handlers(self):
        def failure(**kw):
            for path in self.renderer.tooltips.paths:self.movie.values[path+'.onPress']=lambda:None
            raise RuntimeError('native bind failed halfway')
        self.helper.UpdateMapTooltips=failure;self.update()
        path=self.renderer.clips['OtherWaypoint']
        self.assertEqual(self.movie.values[path+'.onPress'],0)

    def test_unverified_or_foreign_clips_do_not_get_tooltip_rows(self):
        service=self.renderer.tooltips
        service.sync(self.movie,self.points,{'OtherWaypoint':'_level0.map.maps._mission_atlas_99'},set(),10)
        self.assertEqual(self.own_rows(),[])
        service.sync(self.movie,self.points,{'OtherWaypoint':'_level0.map.maps.native'}, {'OtherWaypoint'},11)
        self.assertEqual(self.own_rows(),[])
        self.assertIsNotNone(service.last_error)

if __name__=='__main__':unittest.main()
