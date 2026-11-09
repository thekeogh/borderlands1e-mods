"""Deferred native map setup must render without a movement/input event."""
from unittest.mock import patch
from types import SimpleNamespace as NS
import unittest

from test_atlas import Harness,Object,prop,function
import test_renderer as renderer_models


class InitialRenderTests(unittest.TestCase):
    def setUp(self):
        self.h=Harness();self.addCleanup(self.h.close)
        self.h.atlas.ready=True
        self.movie=Object('Transient.Menu',MapHelper=None)
        self.h.objects['StatusMenuExGFxMovie']=[self.movie]
        self.callback=self.h.atlas.map_callback('Menu:SetupMapPage','SetupMapPage',[])
    def fake_update(self,movie,points,opacity,now,force):
        self.h.atlas.renderer.last_update=now
        if movie.MapHelper is None:
            self.h.atlas.renderer.last_error='No native objective icon template on this map'
        else:
            self.h.atlas.renderer.last_error=None
            self.h.atlas.renderer.clips={'other':'_mission_atlas_test'}
    def test_viewport_retry_completes_without_any_pan_or_input_callback(self):
        self.h.atlas.renderer.update=self.fake_update
        with patch.object(self.h.runtime.time,'monotonic',return_value=100):
            self.callback(self.movie,NS(),None,None)
        self.assertIsNotNone(self.h.atlas.pending_movie)
        self.movie.MapHelper=NS(bIsMinimap=False)
        with patch.object(self.h.runtime.time,'monotonic',return_value=100.11):self.h.atlas.poll()
        self.assertIsNone(self.h.atlas.pending_movie)
        self.assertEqual(self.h.atlas.counts['initial_renders_completed'],1)
        self.assertEqual(self.h.atlas.counts['initial_render_retries'],1)
        self.assertEqual(self.h.atlas.counts['point_scans'],1)
        self.assertFalse(any('PanMap' in k for k in self.h.atlas.counts))
    def test_retry_is_bounded_and_does_not_scan_every_frame(self):
        self.h.atlas.renderer.update=self.fake_update
        with patch.object(self.h.runtime.time,'monotonic',return_value=100):self.callback(self.movie,NS(),None,None)
        for i in range(1,90):
            with patch.object(self.h.runtime.time,'monotonic',return_value=100+i/1000):self.h.atlas.poll()
        self.assertEqual(self.h.atlas.counts['initial_render_retries'],0)
        with patch.object(self.h.runtime.time,'monotonic',return_value=106):self.h.atlas.poll()
        self.assertIsNone(self.h.atlas.pending_movie)
        self.assertEqual(self.h.atlas.counts['initial_render_timeouts'],1)
    def test_close_and_disable_cancel_pending_initial_work(self):
        self.h.atlas.renderer.update=self.fake_update
        with patch.object(self.h.runtime.time,'monotonic',return_value=100):self.callback(self.movie,NS(),None,None)
        self.h.pc.bStatusMenuOpen=False
        with patch.object(self.h.runtime.time,'monotonic',return_value=100.11):self.h.atlas.poll()
        self.assertIsNone(self.h.atlas.pending_movie)
        self.h.atlas.pending_movie=self.movie._get_address()
        self.h.atlas.disable()
        self.assertIsNone(self.h.atlas.pending_movie)
    def test_applyflash_completion_renders_eagerly_and_skips_minimap(self):
        self.h.atlas.renderer.update=self.fake_update
        helper=NS(bIsMinimap=False);self.movie.MapHelper=helper
        self.h.atlas.pending_movie=self.movie._get_address()
        with patch.object(self.h.runtime.time,'monotonic',return_value=100):
            self.h.atlas.helper_applied(helper,NS(Movie=self.movie),None,None)
        self.assertIsNone(self.h.atlas.pending_movie)
        self.assertEqual(self.h.atlas.counts['initial_renders_completed'],1)
        helper.bIsMinimap=True
        self.h.atlas.helper_applied(helper,NS(Movie=self.movie),None,None)
        self.assertEqual(self.h.atlas.counts['map_helper_applied'],1)
    def test_reentrant_applyflash_does_not_duplicate_rendering(self):
        helper=NS(bIsMinimap=False);self.movie.MapHelper=helper
        self.h.atlas.pending_movie=self.movie._get_address()
        calls=[]
        def update(*args):
            calls.append(1)
            self.h.atlas.helper_applied(helper,NS(Movie=self.movie),None,None)
            self.fake_update(*args)
        self.h.atlas.renderer.update=update
        self.h.atlas.render_movie(self.movie,100,True)
        self.assertEqual(calls,[1]);self.assertFalse(self.h.atlas.rendering)
    def test_real_captured_applyflash_signature_gets_a_focused_hook(self):
        fn=function('ApplyFlash',[prop('Movie',PropertyClass=Object('GearboxFramework.GearboxGFxMovie'))],'WillowGame.WillowGFxHelperMap')
        cls=Object('WillowGame.WillowGFxHelperMap',_properties=lambda:[],_fields=lambda:[fn])
        self.h.classes['WillowGFxHelperMap']=cls
        self.h.atlas.discover()
        self.assertTrue(any(p=='WillowGame.WillowGFxHelperMap:ApplyFlash' and i.endswith('.MapReady') for p,t,i in self.h.callbacks))


class StartupIntegrationTests(unittest.TestCase):
    def test_delayed_native_icons_create_verified_diamond_without_panning(self):
        # Reuse the supported Flash API model and real captured map anchors.
        rig=renderer_models.RendererTests('test_captured_world_positions_calibrate_without_assumed_axis_direction')
        rig.setUp()
        try:
            atlas=rig.h.atlas;atlas.ready=True
            movie=rig.movie
            rig.h.objects['StatusMenuExGFxMovie']=[movie]
            rows=list(movie.MapHelper.MapObjects)
            movie.MapHelper.MapObjects=[]
            callback=atlas.map_callback('Menu:SetupMapPage','SetupMapPage',[])
            with patch.object(rig.h.runtime.time,'monotonic',return_value=100):callback(movie,NS(),None,None)
            self.assertIsNotNone(atlas.pending_movie)
            self.assertEqual(atlas.counts['clips_created'],0)
            movie.MapHelper.MapObjects=rows
            with patch.object(rig.h.runtime.time,'monotonic',return_value=100.11):atlas.poll()
            self.assertEqual(atlas.counts['clips_created'],1)
            self.assertIsNone(atlas.pending_movie)
            self.assertIsNone(atlas.renderer.last_error)
            self.assertEqual(atlas.counts['initial_renders_completed'],1)
            self.assertFalse(any('PanMap' in k for k in atlas.counts))
        finally:
            rig.doCleanups()

if __name__=='__main__':unittest.main()
