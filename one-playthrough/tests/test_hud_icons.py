"""HUD frame/API models using the supplied GfxHUD asset's actual clip layout."""

from enum import IntEnum
from pathlib import Path
from types import SimpleNamespace as NS
import json
import tempfile
import unittest
from unittest.mock import patch

from test_one_playthrough import Harness,Object

ICON='p1.ring.dangerous'


def prop(name,kind,flags=0x80,**extra):
    return NS(Name=name,Class=NS(Name=kind),PropertyFlags=flags,**extra)


def function(name,parameters):
    return NS(Name=name,Class=NS(Name='Function'),_properties=lambda:parameters)


class Movie(Object):
    def __init__(self):
        super().__init__('Transient.WillowHUDGFxMovie_0')
        enum=IntEnum('CapturedASValue',{'AS_Undefined':0,'AS_Null':1,'AS_Number':2,'AS_String':3,'AS_Boolean':4})
        struct=Object('GFxUI.GFxMovie:ASValue')
        struct._properties=lambda:[prop('Type','ByteProperty',Enum=NS(_as_py=lambda:enum)),prop('S','StrProperty')]
        self.functions=[function(name,[prop('Path','StrProperty'),prop('ReturnValue',result,0x580)])
                        for name,result in [('GetVariableNumber','FloatProperty'),
                                            ('GetVariableString','StrProperty'),('GetVariableBool','BoolProperty')]]
        self.functions.append(function('Invoke',[
            prop('Method','StrProperty'),prop('Args','ArrayProperty',Inner=prop('Inner','StructProperty',Struct=struct)),
            prop('ReturnValue','StructProperty',0x580,Struct=struct)]))
        self.Class=NS(_fields=lambda:self.functions)
        self.values={ICON+'._totalframes':4,ICON+'._currentframe':2,
                     'p1.ring._visible':True,'p1.ring.elevel.text':'41',ICON+'.ename.text':'Bandit'}
        self.calls=[]
        self.fail=False
    def GetVariableNumber(self,**kw):return self.values.get(kw['Path'],0)
    def GetVariableString(self,**kw):return self.values.get(kw['Path'],'')
    def GetVariableBool(self,**kw):return self.values.get(kw['Path'],False)
    def Invoke(self,**kw):
        self.calls.append(kw)
        if self.fail:raise RuntimeError('native HUD invocation failed')
        label=kw['Args'][0].S
        self.values[ICON+'._currentframe']={'dangerous':2,'deadly':3}[label]


class HudIconTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.h=Harness(tmp.name);self.h.enable(36)
        self.addCleanup(self.h.mod.on_disable)
        self.svc=self.h.runtime.hud_icons
        self.movie=Movie()
        self.scans=0
        find_all=self.h.sdk.find_all
        def find(cls,*args,**kw):
            if cls=='WillowHUDGFxMovie':
                self.scans+=1
                return [self.movie]
            return find_all(cls,*args,**kw)
        self.h.sdk.find_all=find
        self.h.sdk.find_object=lambda cls,path:self.movie if path==self.movie.path else None
        self.h.sdk.make_struct=lambda path,**fields:NS(**fields)

    def update(self):self.svc.update(self.h.pc)

    def test_plus_five_warning_uses_actual_deadly_frame_and_string_enum(self):
        self.update()
        self.assertEqual(self.movie.values[ICON+'._currentframe'],3)
        call=self.movie.calls[0]
        self.assertEqual(call['Method'],ICON+'.gotoAndStop')
        self.assertEqual((call['Args'][0].Type,call['Args'][0].S),(3,'deadly'))
        self.assertEqual(self.svc.changed,1)

    def test_below_plus_five_and_above_plus_five_stay_native(self):
        for level in (36,37,39,40,42,43,50):
            self.movie.values['p1.ring.elevel.text']=str(level)
            self.update()
        self.assertEqual(self.movie.calls,[])

    def test_friendly_normal_existing_skull_and_hidden_rings_are_untouched(self):
        for frame in (0,1,3,4):
            self.movie.values[ICON+'._currentframe']=frame;self.update()
        self.movie.values[ICON+'._currentframe']=2
        self.movie.values['p1.ring._visible']=False;self.update()
        self.assertEqual(self.movie.calls,[])

    def test_repeated_frames_do_not_repeat_override_until_native_resets_icon(self):
        self.update()
        for _ in range(20):self.update()
        self.assertEqual(len(self.movie.calls),1)
        self.movie.values[ICON+'._currentframe']=2
        self.update()
        self.assertEqual(len(self.movie.calls),2)

    def test_disable_restores_only_the_owned_current_target(self):
        self.update();self.h.mod.on_disable()
        self.assertEqual(self.movie.values[ICON+'._currentframe'],2)
        self.assertEqual(self.movie.calls[-1]['Args'][0].S,'dangerous')

    def test_changed_target_or_native_plus_six_skull_is_not_restored(self):
        for field,value in [('p1.ring.elevel.text','42'),(ICON+'.ename.text','Other Bandit')]:
            self.movie.values['p1.ring.elevel.text']='41'
            self.movie.values[ICON+'.ename.text']='Bandit'
            self.movie.values[ICON+'._currentframe']=2
            self.update();calls=len(self.movie.calls)
            self.movie.values[field]=value
            self.svc.restore()
            self.assertEqual(len(self.movie.calls),calls)

    def test_player_level_up_removes_owned_plus_five_override(self):
        self.update();self.h.pc.level=37;self.update()
        self.assertEqual(self.movie.values[ICON+'._currentframe'],2)
        self.assertIsNone(self.svc.owned)

    def test_mod_disabled_menu_and_other_playthroughs_do_not_override(self):
        self.h.runtime.enabled=False;self.update()
        self.h.runtime.enabled=True;self.h.pc.bStatusMenuOpen=True;self.update()
        self.h.pc.bStatusMenuOpen=False;self.h.pc.pt=1;self.update()
        self.assertEqual(self.movie.calls,[])

    def test_invalid_enemy_level_text_is_never_guessed(self):
        for text in ('','unknown','41x','LV 41','-1','4.1'):
            self.movie.values['p1.ring.elevel.text']=text;self.update()
        self.assertEqual(self.movie.calls,[])

    def test_archetype_and_unknown_clip_layout_are_not_modified(self):
        self.movie.path='GfxHUD.hud_instance';self.update()
        self.assertEqual(self.movie.calls,[])
        self.movie.path='Transient.WillowHUDGFxMovie_0'
        self.movie.values[ICON+'._totalframes']=6;self.svc.next_discovery=0;self.update()
        self.assertEqual(self.movie.calls,[])

    def test_reflection_and_object_scan_are_cached_after_hud_discovery(self):
        self.update()
        self.movie.Class._fields=lambda:self.fail('Per-frame HUD reflection')
        for _ in range(20):self.update()
        self.assertEqual(self.scans,1)

    def test_unsupported_api_skips_override_and_records_manual_diagnostic(self):
        self.movie.functions[0]._properties=lambda:[prop('Path','StrProperty'),prop('ReturnValue','BoolProperty',0x580)]
        self.update()
        self.assertEqual(self.movie.calls,[])
        self.assertIn('Unsupported HUD GetVariableNumber signature',str(self.h.runtime.problems))

    def test_native_failure_is_not_retried_in_same_frame_and_backs_off(self):
        self.movie.fail=True;self.update()
        for _ in range(10):self.update()
        self.assertEqual(len(self.movie.calls),1)
        self.assertIn('native HUD invocation failed',self.svc.last_error)

    def test_readback_failure_is_reported_without_claiming_change(self):
        self.movie.Invoke=lambda **kw:self.movie.calls.append(kw)
        self.update()
        self.assertEqual(self.svc.changed,0)
        self.assertIn('readback failed',self.svc.last_error)
        self.assertEqual(len(self.movie.calls),1)

    def test_viewport_hook_runs_presentation_only_and_manual_export_has_state(self):
        self.h.globals[0].LevelDifference_Impossible=5
        policy=self.h.runtime.spawns.snapshot()
        callback=self.h.callbacks[('Engine.GameViewportClient:PostRender','POST')]
        callback(None,None,None,None)
        self.assertEqual(self.svc.changed,1)
        self.assertEqual(self.h.globals[0].LevelDifference_Impossible,5)
        self.assertEqual(self.h.runtime.spawns.snapshot(),policy)
        report=json.loads(self.h.mod.export_diagnostics().read_text())
        self.assertEqual(report['hud_icons']['changed'],1)
        self.assertEqual(report['hud_icons']['last_state']['level'],41)
        self.assertEqual(report['hud_icons']['rule'],'native warning to small skull at exactly player level +5')

    def test_cached_service_contains_only_primitive_movie_identity(self):
        self.update()
        self.assertIsInstance(self.svc.movie_path,str)
        self.assertIsInstance(self.svc.movie_address,int)
        json.dumps(self.svc.snapshot(),allow_nan=False)

    def test_destroyed_cached_movie_is_rediscovered_after_travel(self):
        self.update()
        def missing(*args):raise ValueError('Movie was unloaded')
        self.h.sdk.find_object=missing
        self.movie=Movie()
        self.svc.next_discovery=0
        self.update()
        self.assertEqual(self.svc.movie_address,self.movie._get_address())
        self.assertEqual(self.movie.values[ICON+'._currentframe'],3)

    def test_unrecognized_display_text_is_retained_for_manual_diagnostics(self):
        self.movie.values['p1.ring.elevel.text']='unknown'
        self.update()
        self.assertEqual(self.svc.snapshot()['last_state']['level_text'],'unknown')
        self.assertEqual(self.movie.calls,[])

    def test_asset_contract_identifies_the_actual_skull_frame(self):
        contract=json.loads((Path(__file__).parent/'fixtures/bl1e_hud_icon_contract.json').read_text())
        self.assertEqual(contract['icon_path'],ICON)
        self.assertEqual(contract['frames'],{'normal':1,'dangerous':2,'deadly':3,'friendly':4})
        self.assertEqual(contract['skull_parent_frame'],3)
        self.assertEqual(contract['enemy_level_path'],'p1.ring.elevel.text')


if __name__=='__main__':unittest.main()
