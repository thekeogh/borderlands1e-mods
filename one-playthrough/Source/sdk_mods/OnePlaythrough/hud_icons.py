"""Presentation-only +5 skull, using the supplied BL1E HUD asset contract.

GfxHUD's primary-player ring has a four-frame `dangerous` clip: warning=2,
deadly/skull=3, friendly=4. Its sibling `elevel` contains the displayed enemy
level. Never change enemy data or the shared Globals difficulty thresholds.
"""

import math
import re
import time

from unrealsdk.hooks import prevent_hooking_direct_calls

MOVIE_CLASS = 'WillowHUDGFxMovie'
ICON = 'p1.ring.dangerous'
LEVEL = 'p1.ring.elevel.text'
NAME = ICON+'.ename.text'


def api_plan(movie):
    """Reflect and check the native GFx API once per live movie, not per frame."""
    functions = {str(f.Name):f for f in movie.Class._fields() if str(f.Class.Name)=='Function'}
    plan = {}
    for name,result_type in (('GetVariableNumber','FloatProperty'),
                             ('GetVariableString','StrProperty'),('GetVariableBool','BoolProperty')):
        fn = functions.get(name)
        if fn is None:
            raise ValueError('HUD lacks '+name)
        fields = [p for p in fn._properties() if int(p.PropertyFlags)&0x80]
        inputs = [p for p in fields if not int(p.PropertyFlags)&0x500]
        outputs = [p for p in fields if int(p.PropertyFlags)&0x500]
        if (len(inputs)!=1 or str(inputs[0].Class.Name)!='StrProperty' or len(outputs)!=1
                or not int(outputs[0].PropertyFlags)&0x400 or str(outputs[0].Class.Name)!=result_type):
            raise ValueError('Unsupported HUD '+name+' signature')
        plan[name] = str(inputs[0].Name)
    fn = functions.get('Invoke')
    if fn is None:
        raise ValueError('HUD lacks Invoke')
    fields = [p for p in fn._properties() if int(p.PropertyFlags)&0x80]
    inputs = [p for p in fields if not int(p.PropertyFlags)&0x500]
    outputs = [p for p in fields if int(p.PropertyFlags)&0x500]
    strings = [p for p in inputs if str(p.Class.Name)=='StrProperty']
    arrays = [p for p in inputs if str(p.Class.Name)=='ArrayProperty']
    if (len(inputs)!=2 or len(strings)!=1 or len(arrays)!=1 or len(outputs)!=1
            or not int(outputs[0].PropertyFlags)&0x400 or str(outputs[0].Class.Name)!='StructProperty'
            or str(arrays[0].Inner.Class.Name)!='StructProperty'):
        raise ValueError('Unsupported HUD Invoke signature')
    struct = arrays[0].Inner.Struct
    if outputs[0].Struct._path_name()!=struct._path_name():
        raise ValueError('HUD Invoke ASValue types differ')
    members = {str(p.Name):p for p in struct._properties()}
    if 'Type' not in members or 'S' not in members or str(members['S'].Class.Name)!='StrProperty':
        raise ValueError('Unsupported HUD ASValue layout')
    enum = members['Type'].Enum._as_py().__members__
    texts = [int(v) for k,v in enum.items() if k.lower().endswith('string')]
    if len(texts)!=1:
        raise ValueError('Cannot resolve HUD ASValue string enum')
    plan['Invoke'] = {'path':str(strings[0].Name),'args':str(arrays[0].Name),
                      'struct':struct._path_name(),'string':texts[0]}
    return plan


class HudIcons:
    def __init__(self,runtime):
        self.runtime = runtime
        self.movie_path = None
        self.movie_address = None
        self.plan = None
        self.next_discovery = 0
        self.retry_after = 0
        self.owned = None
        self.changed = 0
        self.restored = 0
        self.last_state = None
        self.last_error = None

    def read(self,movie,method,path):
        with prevent_hooking_direct_calls():
            value = getattr(movie,method)(**{self.plan[method]:path})
        if method=='GetVariableNumber':
            value = float(value)
            if not math.isfinite(value):
                raise ValueError('Non-finite HUD property: '+path)
        return value

    def frame(self,movie,label):
        spec = self.plan['Invoke']
        value = self.runtime.sdk.make_struct(spec['struct'],Type=spec['string'],S=label)
        with prevent_hooking_direct_calls():
            movie.Invoke(**{spec['path']:ICON+'.gotoAndStop',spec['args']:[value]})

    def movie(self,now):
        sdk = self.runtime.sdk
        if self.movie_path is not None:
            try:
                movie = sdk.find_object(MOVIE_CLASS,self.movie_path)
            except ValueError:
                movie = None
            if movie is not None and movie._get_address()==self.movie_address:
                return movie
            self.movie_path,self.movie_address,self.plan,self.owned = None,None,None,None
        if now < self.next_discovery:
            return None
        self.next_discovery = now+1
        for movie in sdk.find_all(MOVIE_CLASS):
            path = movie._path_name()
            if not path.lower().startswith('transient.'):
                continue  # Never operate on the package's HUD archetype/CDO.
            self.plan = api_plan(movie)
            if self.read(movie,'GetVariableNumber',ICON+'._totalframes')!=4:
                continue
            self.movie_path,self.movie_address = path,movie._get_address()
            return movie
        return None

    def context(self,movie):
        frame = self.read(movie,'GetVariableNumber',ICON+'._currentframe')
        self.last_state = {'frame':frame}
        if frame not in (1,2,3,4):
            return None
        text = str(self.read(movie,'GetVariableString',LEVEL)).strip()
        self.last_state['level_text'] = text
        if re.fullmatch(r'[0-9]{1,3}',text) is None:
            return None
        return {'frame':int(frame),'level':int(text),'level_text':text}

    def undo(self,movie,context):
        previous = self.owned
        self.owned = None
        if (previous is not None and context is not None and context['frame']==3
                and context['level']==previous['level']
                and str(self.read(movie,'GetVariableString',NAME))==previous['name']):
            self.frame(movie,'dangerous')
            self.restored += 1

    def update(self,pc):
        if not self.runtime.enabled:
            return
        now = time.monotonic()
        if now < self.retry_after or getattr(pc,'bStatusMenuOpen',False):
            return
        player = self.runtime.level(pc)
        if player is None:
            self.restore()
            return
        try:
            movie = self.movie(now)
            if movie is None:
                return
            context = self.context(movie)
            if context is not None:
                self.last_state = dict(context,player=player)
            if context is None:
                self.owned = None
                return
            if context['level']-player!=5:
                # +6 and higher keep their native skull and scaling. A changed
                # target/name/frame is never restored using stale ownership.
                if context['level']-player < 5:
                    self.undo(movie,context)
                else:
                    self.owned = None
                return
            if context['frame']!=2 or not self.read(movie,'GetVariableBool','p1.ring._visible'):
                return  # Normal/friendly/native skull states are untouched.
            name = str(self.read(movie,'GetVariableString',NAME))
            self.owned = {'level':context['level'],'name':name}
            self.frame(movie,'deadly')
            if self.read(movie,'GetVariableNumber',ICON+'._currentframe')!=3:
                self.owned = None
                raise ValueError('HUD skull frame readback failed')
            self.changed += 1
            self.last_error = None
        except Exception as exc:
            self.last_error = str(exc)
            self.retry_after = now+3
            self.runtime.problem('HUD +5 skull',exc)

    def restore(self):
        try:
            if self.owned is not None and self.movie_path is not None:
                movie = self.runtime.sdk.find_object(MOVIE_CLASS,self.movie_path)
                if movie is not None and movie._get_address()==self.movie_address:
                    self.undo(movie,self.context(movie))
        except Exception as exc:
            self.runtime.problem('restore HUD skull',exc)
        finally:
            self.owned = None
            self.movie_path,self.movie_address,self.plan = None,None,None
            self.next_discovery,self.retry_after = 0,0

    def snapshot(self):
        return {'rule':'native warning to small skull at exactly player level +5',
                'movie':self.movie_path,'changed':self.changed,'restored':self.restored,
                'last_state':self.last_state,'last_error':self.last_error,'api':self.plan}
