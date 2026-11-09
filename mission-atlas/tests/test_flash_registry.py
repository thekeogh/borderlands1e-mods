"""Regression for the native Flash registry absent from pre-0.1.8 builds."""

from copy import deepcopy
import unittest

from test_atlas import function,prop
import test_tooltips as models


class FlashRegistryTests(unittest.TestCase):
    def setUp(self):
        self.rig=models.TooltipTests('test_mission_label_is_metadata_and_is_hidden_without_hover')
        self.rig.setUp();self.addCleanup(self.rig.doCleanups)
        self.movie=self.rig.movie;self.renderer=self.rig.renderer
        self.rig.rig.api.append(function('GetVariableString',[
            prop('Path','StrProperty'),prop('ReturnValue','StrProperty',0x580)],'GFxUI.GFxMovie'))
        for row in self.rig.helper.MapObjects:
            self.movie.arrays['mapItems'].append(row.AS_IconPath)
            self.movie.arrays['tooltipTitles'].append(row.TooltipTitle)
            self.movie.arrays['tooltipBodies'].append(row.TooltipBody)
        self.original=deepcopy(self.movie.arrays)

    def test_creation_registers_path_title_and_body_in_parallel_arrays(self):
        self.rig.update();path=self.renderer.clips['OtherWaypoint']
        self.assertTrue(path.rsplit('.',1)[-1].startswith('_mission_atlas_'))
        self.assertEqual(self.movie.arrays['mapItems'][-1],path)
        self.assertEqual(self.movie.arrays['tooltipTitles'][-1],'Objective')
        self.assertEqual(self.movie.arrays['tooltipBodies'][-1],'Other Mission')
        self.assertTrue(any(c[0]=='invoke' and c[1]==path+'.gotoAndStop' and c[2][0].S=='objective'
                            for c in self.movie.calls))
        for array,values in self.original.items():self.assertEqual(self.movie.arrays[array][:-1],values)

    def test_unreal_rows_and_enabled_clips_alone_do_not_create_flash_tooltips(self):
        self.rig.update();row=self.rig.own_rows()[0]
        self.rig.helper.mouse=(row.TransformedLocation.X,row.TransformedLocation.Y)
        self.rig.helper.UpdateMapTooltips(Movie=self.movie)
        self.assertEqual(self.rig.helper.visible_label,'Other Mission')
        self.movie.arrays=deepcopy(self.original)
        self.rig.helper.UpdateMapTooltips(Movie=self.movie)
        self.assertIsNone(self.rig.helper.visible_label)

    def test_label_edit_updates_the_registered_flash_body(self):
        self.rig.update();self.rig.points[0]['label']='Renamed Mission'
        self.rig.update(10.2)
        self.assertEqual(self.movie.arrays['tooltipBodies'][-1],'Renamed Mission')
        self.assertEqual(len(self.movie.arrays['mapItems']),len(self.original['mapItems'])+1)

    def test_removal_preserves_native_and_other_mod_registry_entries(self):
        self.rig.update()
        additions={'mapItems':'_level0.map.maps.other_mod_marker','tooltipTitles':'Other mod','tooltipBodies':'External'}
        for array,value in additions.items():self.movie.arrays[array].append(value)
        self.rig.points=[];self.rig.update(10.2)
        for array,values in self.original.items():self.assertEqual(self.movie.arrays[array],values+[additions[array]])

    def test_remove_one_mission_keeps_the_other_owned_label(self):
        self.rig.points.append({'key':'Second','x':20000.,'y':30000.,'z':0.,'label':'Second Mission'})
        self.rig.update();second=self.renderer.clips['Second']
        self.rig.points=self.rig.points[1:];self.rig.update(10.2)
        self.assertEqual(self.movie.arrays['mapItems'],self.original['mapItems']+[second])
        self.assertEqual(self.movie.arrays['tooltipBodies'],self.original['tooltipBodies']+['Second Mission'])

    def test_partial_splice_failure_restores_native_parallel_array_alignment(self):
        self.rig.update();before=deepcopy(self.movie.arrays)
        original=self.movie.Invoke
        def fail(**kw):
            if kw['method']=='tooltipTitles.splice' and len(kw['args'])==2:
                raise RuntimeError('native splice failed')
            return original(**kw)
        self.movie.Invoke=fail
        self.renderer.tooltips.remove_flash(self.movie,self.renderer.plan,set(self.renderer.clips.values()))
        self.assertEqual(self.movie.arrays,before)

    def test_splice_throwing_after_side_effect_is_also_rolled_back(self):
        self.rig.update();before=deepcopy(self.movie.arrays)
        original=self.movie.Invoke
        def fail(**kw):
            result=original(**kw)
            if kw['method']=='tooltipTitles.splice' and len(kw['args'])==2:
                raise RuntimeError('native splice threw after side effect')
            return result
        self.movie.Invoke=fail
        self.renderer.tooltips.remove_flash(self.movie,self.renderer.plan,set(self.renderer.clips.values()))
        self.assertEqual(self.movie.arrays,before)

    def test_foreign_path_cannot_be_removed_even_if_requested(self):
        self.rig.update();before=deepcopy(self.movie.arrays)
        self.renderer.tooltips.remove_flash(self.movie,self.renderer.plan,{self.original['mapItems'][0]})
        self.assertEqual(self.movie.arrays,before)

    def test_controller_query_preserves_active_mouse_tooltip(self):
        self.rig.rig.api.append(function('GetVariableBool',[
            prop('Path','StrProperty'),prop('ReturnValue','BoolProperty',0x580)],'GFxUI.GFxMovie'))
        self.movie.GetVariableBool=lambda **kw:kw['Path']=='bMouseTooltipActive'
        self.rig.update()
        self.assertFalse(any(c[0]=='invoke' and c[1]=='CheckCrosshair' for c in self.movie.calls))

    def test_report_shows_actual_flash_registration(self):
        self.rig.update()
        report=self.renderer.tooltips.interaction_snapshot(self.movie)
        self.assertTrue(report['flash_registry']['aligned'])
        self.assertEqual(report['clips'][0]['flash_registration']['body'],'Other Mission')


if __name__=='__main__':unittest.main()
