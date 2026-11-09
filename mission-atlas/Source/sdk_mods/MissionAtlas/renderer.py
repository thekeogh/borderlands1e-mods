"""Duplicate the captured native objective clip in its own Flash map container.

The game still positions its own icons. Three non-collinear native map icons
calibrate world XY to that same container, so native pan/zoom/rotation remain the
reference. Only Mission Atlas clips are moved, faded or removed.
"""

import math
from .native import kind, path_of, short_name, signature
from .tooltips import Tooltips
import unrealsdk
from unrealsdk.hooks import prevent_hooking_direct_calls

PREFIX = '_mission_atlas_'


def finite_xy(value):
    point = float(value.X), float(value.Y)
    if not all(math.isfinite(v) for v in point):
        raise ValueError('Non-finite map coordinates')
    return point


def affine(anchors,tolerance=3):
    """Fit and validate native world-to-clip coordinates; never guess map axes."""
    if len(anchors) < 3:
        raise ValueError('Need three native map icons for coordinate calibration')
    first = anchors[0]
    second = max(anchors[1:], key=lambda a: (a[0]-first[0])**2+(a[1]-first[1])**2)
    dx, dy = second[0]-first[0], second[1]-first[1]
    third = max(anchors, key=lambda a: abs(dx*(a[1]-first[1])-dy*(a[0]-first[0])))
    ex, ey = third[0]-first[0], third[1]-first[1]
    det = dx*ey-dy*ex
    if abs(det) < 1:
        raise ValueError('Native map anchor positions are collinear')
    coefficients = []
    for axis in (2, 3):
        v, w = second[axis]-first[axis], third[axis]-first[axis]
        a, b = (v*ey-w*dy)/det, (dx*w-ex*v)/det
        coefficients.append((a, b, first[axis]-a*first[0]-b*first[1]))
    if max(abs(a)+abs(b) for a,b,_ in coefficients) < 1e-10:
        raise ValueError('Native icon clips have no usable positions')
    for x,y,u,v in anchors:
        actual = project(coefficients, x, y)
        if math.hypot(actual[0]-u, actual[1]-v) > tolerance:
            raise ValueError('Native map icons do not share an affine coordinate space')
    return coefficients


def project(coefficients, x, y):
    return tuple(a*x+b*y+c for a,b,c in coefficients)


def reflected_functions(movie):
    return {str(fn.Name): fn for fn in movie.Class._fields() if str(fn.Class.Name) == 'Function'}


def flash_plan(movie):
    functions = reflected_functions(movie)
    alternatives = {'Invoke':('Invoke','InvokeMethod'),
                    'GetVariableNumber':('GetVariableNumber','GetVariableFloat'),
                    'SetVariableNumber':('SetVariableNumber','SetVariableFloat')}
    actual = {role:next((name for name in names if name in functions),None) for role,names in alternatives.items()}
    missing = [role for role,name in actual.items() if name is None]
    if missing:
        raise ValueError('Map movie lacks Flash API: '+', '.join(missing))
    plan = {}
    for name in ('Invoke','GetVariableNumber','SetVariableNumber'):
        fn = functions[actual[name]]
        fields = signature(fn)
        inputs = [p for p in fields if not p['flags'] & 0x500]
        outs = [p for p in fields if p['flags'] & 0x100 and not p['flags'] & 0x400]
        returns = [p for p in fields if p['flags'] & 0x400]
        strings = [p for p in inputs if p['type'] == 'StrProperty']
        if len(strings) != 1:
            raise ValueError(name+' needs one reflected string path')
        spec = {'path': strings[0]['name'], 'native':actual[name]}
        if name == 'Invoke':
            arrays = [p for p in inputs if p['type'] == 'ArrayProperty']
            if len(inputs) != 2 or len(arrays) != 1 or outs or len(returns) != 1:
                raise ValueError('Unsupported Flash Invoke signature')
            prop = next(p for p in fn._properties() if str(p.Name) == arrays[0]['name'])
            if kind(prop.Inner) != 'StructProperty':
                raise ValueError('Flash Invoke arguments are not ASValue structs')
            struct = prop.Inner.Struct
            if returns[0].get('struct') != path_of(struct):
                raise ValueError('Flash Invoke return is not the argument ASValue type')
            members = {str(p.Name): p for p in struct._properties()}
            if not {'Type','N','S'}.issubset(members):
                raise ValueError('Unknown ASValue layout')
            enum = getattr(members['Type'], 'Enum', None)
            if enum is None:
                raise ValueError('ASValue Type has no reflected enum')
            values = {n.lower(): int(v) for n,v in enum._as_py().__members__.items()}
            numbers = [v for n,v in values.items() if n.endswith('number')]
            texts = [v for n,v in values.items() if n.endswith('string')]
            if len(numbers) != 1 or len(texts) != 1:
                raise ValueError('Cannot resolve ASValue number/string types')
            booleans = [v for n,v in values.items() if n.endswith('boolean')]
            spec.update(args=arrays[0]['name'], struct=path_of(struct), number=numbers[0], string=texts[0])
            if len(booleans) == 1 and 'B' in members:
                spec['boolean'] = booleans[0]
        elif name == 'GetVariableNumber':
            # SDK returns (native return, output params...) when outputs exist.
            if len(inputs) != 1 or len(returns) != 1:
                raise ValueError('Unsupported GetVariableNumber signature')
            if not outs and returns[0]['type'] == 'FloatProperty':
                spec['out'] = False
            elif len(outs) == 1 and outs[0]['type'] == 'FloatProperty' and returns[0]['type'] == 'BoolProperty':
                spec['out'] = True
            else:
                raise ValueError('Unsupported GetVariableNumber outputs')
        else:
            numbers = [p for p in inputs if p['type'] == 'FloatProperty']
            if len(inputs) != 2 or len(numbers) != 1 or outs:
                raise ValueError('Unsupported SetVariableNumber signature')
            spec['value'] = numbers[0]['name']
        plan[name] = spec
    setter = functions.get('SetVariableBool')
    if setter is not None:
        fields = signature(setter)
        inputs = [p for p in fields if not p['flags'] & 0x500]
        strings = [p for p in inputs if p['type'] == 'StrProperty']
        booleans = [p for p in inputs if p['type'] == 'BoolProperty']
        if len(inputs) == 2 and len(strings) == 1 and len(booleans) == 1 and not any(
                p['flags'] & 0x100 and not p['flags'] & 0x400 for p in fields):
            plan['SetVariableBool'] = {'native':'SetVariableBool','path':strings[0]['name'],'value':booleans[0]['name']}
    getter = functions.get('GetVariableBool')
    if getter is not None:
        fields = signature(getter)
        if (len(fields) == 2 and fields[0]['type'] == 'StrProperty'
                and not fields[0]['flags'] & 0x500 and fields[1]['type'] == 'BoolProperty'
                and fields[1]['flags'] & 0x400):
            plan['GetVariableBool'] = {'path':fields[0]['name']}
    getter = functions.get('GetVariableString')
    if getter is not None:
        fields = signature(getter)
        if (len(fields) == 2 and fields[0]['type'] == 'StrProperty'
                and not fields[0]['flags'] & 0x500 and fields[1]['type'] == 'StrProperty'
                and fields[1]['flags'] & 0x400):
            plan['GetVariableString'] = {'path':fields[0]['name']}
    return plan


class Flash:
    def __init__(self, movie, plan):
        self.movie, self.plan = movie, plan

    def number(self, path):
        spec = self.plan['GetVariableNumber']
        with prevent_hooking_direct_calls():
            result = getattr(self.movie,spec['native'])(**{spec['path']: path})
        if spec['out']:
            ok, value = result
            if not ok:
                raise ValueError('Missing native icon coordinate: '+path)
        else:
            value = result
        value = float(value)
        if not math.isfinite(value):
            raise ValueError('Non-finite Flash property: '+path)
        return value

    def set_number(self, path, value):
        spec = self.plan['SetVariableNumber']
        with prevent_hooking_direct_calls():
            result = getattr(self.movie,spec['native'])(**{spec['path']: path, spec['value']: float(value)})
        if result is False:
            raise ValueError('Flash property could not be set: '+path)

    def set_enabled(self,path,enabled):
        spec = self.plan.get('SetVariableBool')
        if spec is None:
            self.set_number(path+'.enabled',int(enabled))
            return
        with prevent_hooking_direct_calls():
            result = getattr(self.movie,spec['native'])(**{spec['path']:path+'.enabled',spec['value']:bool(enabled)})
        if result is False:
            raise ValueError('Flash enabled state could not be set: '+path)

    def string(self,path):
        spec = self.plan.get('GetVariableString')
        if spec is None:
            raise ValueError('No reflected Flash string getter')
        with prevent_hooking_direct_calls():
            return str(self.movie.GetVariableString(**{spec['path']:path}))

    def boolean(self,path):
        spec = self.plan.get('GetVariableBool')
        if spec is None:
            return False
        with prevent_hooking_direct_calls():
            return bool(self.movie.GetVariableBool(**{spec['path']:path}))

    def invoke(self, path, *args):
        spec = self.plan['Invoke']
        values = []
        for value in args:
            if isinstance(value,bool) and 'boolean' in spec:
                fields = {'Type':spec['boolean'], 'B':value}
            else:
                fields = {'Type':spec['string'], 'S':value} if isinstance(value,str) else {'Type':spec['number'], 'N':float(value)}
            values.append(unrealsdk.make_struct(spec['struct'], **fields))
        with prevent_hooking_direct_calls():
            return getattr(self.movie,spec['native'])(**{spec['path']:path, spec['args']:values})

    def depth(self, parent):
        result = self.invoke(parent+'.getNextHighestDepth')
        if int(result.Type) != self.plan['Invoke']['number']:
            raise ValueError('Flash map container did not return its next depth')
        depth = float(result.N)
        if not math.isfinite(depth) or depth < 0 or depth > 0xFFFFFF or depth != int(depth):
            raise ValueError('Invalid next Flash depth')
        return int(depth)


def row_location(row):
    for field in ('Landmark', 'ClientInteractiveObject'):
        actor = getattr(row, field, None)
        if actor is not None and not getattr(actor,'bDeleteMe',False) and not getattr(actor,'bPendingDelete',False):
            return finite_xy(actor.Location)
    custom = row.CustomObjectLoc
    if any(float(getattr(custom, axis)) != 0 for axis in 'XYZ'):
        return finite_xy(custom)
    return None


def anchors_for(helper, flash, parent):
    custom, actors = [], []
    for row in helper.MapObjects:
        path = str(row.AS_IconPath)
        if path.rpartition('.')[0] != parent or path.rsplit('.',1)[-1].startswith(PREFIX):
            continue
        world = row_location(row)
        if world is None:
            continue
        entry = (world,path)
        if getattr(row,'Landmark',None) is None and getattr(row,'ClientInteractiveObject',None) is None:
            custom.append(entry)
        else:
            actors.append(entry)
    # Captured New-U / unknown / objective rows have explicit world positions.
    # Prefer these to actor icons that may use actor-specific location offsets.
    selected = custom if len(custom) >= 3 else custom+actors
    return [(*world,flash.number(path+'._x'),flash.number(path+'._y')) for world,path in selected[:8]]


class Renderer:
    def __init__(self, problem, counts):
        self.problem, self.counts = problem, counts
        self.tooltips = Tooltips(problem,counts)
        self.plan = None  # Primitive signature descriptions only; no native wrappers.
        self.movie_address = None
        self.clips = {}
        self.serial = 0
        self.positions = {}
        self.applied_opacity = {}
        self.verified = set()
        self.next_clip_check = 0
        self.last_update = -1e10
        self.last_error = None
        self.resetting = False

    def reset(self, movie=None):
        if self.resetting:
            return
        self.resetting = True
        try:
            if movie is not None and self.plan:
                self.tooltips.remove_flash(movie,self.plan,set(self.clips.values()))
            self.tooltips.clear(movie)
            if movie is not None and movie._get_address() == self.movie_address and self.plan:
                flash = Flash(movie,self.plan)
                for path in list(self.clips.values()):
                    try:
                        flash.invoke(path+'.removeMovieClip')
                        self.counts['clips_removed'] += 1
                    except Exception as exc:
                        self.problem('remove extra Flash icon',exc)
            self.clips.clear()
            self.positions.clear()
            self.applied_opacity.clear()
            self.verified.clear()
            self.last_error = None
            self.last_update = -1e10

        finally:
            self.resetting = False

    def update(self, movie, points, opacity, now, force=False):
        if self.resetting:
            return
        interval = 3 if self.last_error else .1
        if not force and now-self.last_update < interval:
            return
        self.last_update = now
        helper = getattr(movie,'MapHelper',None)
        if helper is None or getattr(helper,'bIsMinimap',False):
            return
        if not points:
            self.reset(movie)
            self.last_update = now
            self.counts['visible_extra_clips'] = 0
            return
        try:
            address = movie._get_address()
            if address != self.movie_address:
                self.clips.clear()
                self.positions.clear()
                self.applied_opacity.clear()
                self.verified.clear()
                self.plan = None
                self.movie_address = address
            if self.plan is None:
                self.plan = flash_plan(movie)
            flash = Flash(movie,self.plan)
            template_row = next((r for r in helper.MapObjects
                             if str(r.AS_IconClipFrame) == 'objective' and str(r.AS_IconPath)
                             and not str(r.AS_IconPath).rsplit('.',1)[-1].startswith(PREFIX)),None)
            if template_row is None:
                self.reset(movie)
                self.counts['visible_extra_clips'] = 0
                raise ValueError('No native objective icon template on this map')
            template = str(template_row.AS_IconPath)
            template_frame = str(template_row.AS_IconClipFrame)
            template_title = str(template_row.TooltipTitle)
            # reset() can replace MapObjects storage; retain primitive template
            # values before checking whether a previous Flash scene disappeared.
            template_row = None
            parent = template.rpartition('.')[0]
            transform = affine(anchors_for(helper,flash,parent))
            self.counts['anchor_calibrations'] += 1
            if self.verified and now >= self.next_clip_check:
                self.next_clip_check = now+1
                first = next(iter(self.verified))
                try:
                    exists = abs(flash.number(self.clips[first]+'._alpha')-self.applied_opacity[first]) <= .5
                except ValueError:
                    exists = False
                if not exists:
                    # Native map setup can replace its Flash container. These
                    # were verified clips, so rebuilding is a new scene, not a
                    # retry of a failed/unknown creation.
                    self.reset(movie)
            wanted = {p['key'] for p in points}
            for key in list(self.clips):
                if key not in wanted:
                    self.tooltips.remove_flash(movie,self.plan,{self.clips[key]})
                    flash.invoke(self.clips.pop(key)+'.removeMovieClip')
                    self.positions.pop(key,None)
                    self.applied_opacity.pop(key,None)
                    self.verified.discard(key)
                    self.counts['clips_removed'] += 1
            for point in points:
                key = point['key']
                path = self.clips.get(key)
                creating = path is None
                if path is None:
                    self.serial += 1
                    name = PREFIX+str(self.serial)+'_'
                    depth = flash.depth(parent)
                    path = parent+'.'+name+str(depth)
                    # Own the name before invocation. If creation throws after
                    # side effects, never retry it; subsequent cleanup is safe.
                    self.clips[key] = path
                    # Verified in the uploaded status-menu asset: AddLandmark
                    # binds rollover handlers AND appends the clip/title/body
                    # to Flash's parallel arrays used by CheckCrosshair.
                    # Its frame argument also determines the instance name.
                    # A private frame token guarantees a private instance;
                    # select the native objective visual explicitly afterward.
                    result = flash.invoke('AddLandmark',template,0,0,0,name,
                                          template_title,str(point['label']))
                    if int(result.Type) != self.plan['Invoke']['string'] or str(result.S) != path:
                        raise ValueError('Native AddLandmark returned an unexpected owned path')
                    flash.invoke(path+'.gotoAndStop',template_frame)
                x,y = project(transform,point['x'],point['y'])
                previous = self.positions.get(key)
                if previous is None or math.hypot(x-previous[0],y-previous[1]) > .05:
                    flash.set_number(path+'._x',x)
                    flash.set_number(path+'._y',y)
                    self.positions[key] = (x,y)
                if self.applied_opacity.get(key) != opacity:
                    flash.set_number(path+'._alpha',opacity)
                    self.applied_opacity[key] = opacity
                if creating:
                    flash.set_number(path+'._visible',1)
                    flash.set_number(path+'.enabled',0) # no copied click handlers
                    if abs(flash.number(path+'._alpha')-opacity) > .5:
                        raise ValueError('Extra Flash clip creation could not be verified')
                    placed = flash.invoke(path+'.getDepth')
                    if int(placed.Type) != flash.plan['Invoke']['number'] or int(placed.N) != depth:
                        raise ValueError('Extra MovieClip depth could not be verified')
                    self.verified.add(key)
                    self.counts['clips_created'] += 1
            self.tooltips.sync(movie,points,self.clips,self.verified,now)
            self.counts['visible_extra_clips'] = len(self.clips)
            self.last_error = None
            self.last_update = now
        except Exception as exc:
            # Back off failed probes for three seconds rather than repeating
            # native reflection and coordinate queries on every mouse move.
            self.last_error = str(exc)
            self.last_update = now
            if isinstance(exc,ValueError) and str(exc) == 'No native objective icon template on this map':
                self.counts['waiting_for_native_template'] += 1
            else:
                self.problem('render map objective clips',exc)
