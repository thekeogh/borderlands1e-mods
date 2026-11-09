"""Register owned map-tooltip rows for the game's existing hover/focus query.

No labels are drawn directly and no cursor/controller behavior is replaced.
Original rows retain their values/order. Only rows for our verified Flash clips
are appended, updated or removed; no gameplay or mission state is modified.
"""

import math
from copy import deepcopy
import unrealsdk
from unrealsdk.hooks import prevent_hooking_direct_calls
from .native import kind,path_of,short_name,signature


def tooltip_plan(helper):
    prop = next((p for p in helper.Class._properties() if str(p.Name) == 'MapObjects'),None)
    if prop is None or kind(prop) != 'ArrayProperty' or kind(prop.Inner) != 'StructProperty':
        raise ValueError('MapObjects is not a reflected struct array')
    struct = prop.Inner.Struct
    fields = {str(p.Name):p for p in struct._properties()}
    required = {'Player':'ObjectProperty','Landmark':'ObjectProperty',
                'ClientInteractiveObject':'ObjectProperty','WPRI':'ObjectProperty',
                'bWaypoint':'BoolProperty','CustomObjectLoc':'StructProperty',
                'bIsDirty':'BoolProperty','TransformedLocation':'StructProperty',
                'Angle':'FloatProperty','AS_IconClipPath':'StrProperty',
                'AS_IconClipFrame':'StrProperty','AS_IconPath':'StrProperty',
                'TooltipTitle':'StrProperty','TooltipBody':'StrProperty'}
    if any(n not in fields or kind(fields[n]) != t for n,t in required.items()):
        raise ValueError('Unsupported native map tooltip row layout')
    if short_name(path_of(fields['CustomObjectLoc'].Struct)) != 'Vector':
        raise ValueError('Unsupported tooltip world position type')
    if short_name(path_of(fields['TransformedLocation'].Struct)) != 'Vector2D':
        raise ValueError('Unsupported tooltip map position type')
    refresh = next((f for f in helper.Class._fields() if str(f.Class.Name) == 'Function'
                    and str(f.Name) == 'UpdateMapTooltips'),None)
    if refresh is None:
        raise ValueError('Native UpdateMapTooltips is unavailable')
    parameters = signature(refresh)
    if (len(parameters) != 1 or parameters[0]['type'] != 'ObjectProperty'
            or parameters[0]['flags'] & 0x500):
        raise ValueError('Unsupported native UpdateMapTooltips signature')
    return {'struct':path_of(struct),'movie_arg':parameters[0]['name']}


def own_clip(path):
    return str(path).rsplit('.',1)[-1].startswith('_mission_atlas_')


def normalized_transform(helper):
    from .renderer import affine,row_location
    custom,actors = [],[]
    for row in helper.MapObjects:
        if own_clip(row.AS_IconPath):
            continue
        location = row_location(row)
        if location is None:
            continue
        uv = row.TransformedLocation
        values = (*location,float(uv.X),float(uv.Y))
        if not all(math.isfinite(v) for v in values):
            continue
        if getattr(row,'Landmark',None) is None and getattr(row,'ClientInteractiveObject',None) is None:
            custom.append(values)
        else:
            actors.append(values)
    anchors = custom if len(custom) >= 3 else custom+actors
    return affine(anchors[:8],tolerance=.003)


class Tooltips:
    def __init__(self,problem,counts):
        self.problem,self.counts = problem,counts
        self.plan = None  # Primitive descriptions only; no retained native rows.
        self.hover_plan = None
        self.helper_address = None
        self.paths = set()
        self.last_payload = None
        self.last_error = None
        self.retry_after = 0
        self.next_hover_query = 0

    def hover_enabled(self,movie):
        # Disabling the duplicated clip also disables its native rollover/focus
        # behavior. Keep it enabled, but remove activation handlers explicitly.
        from .renderer import Flash,flash_plan
        if self.hover_plan is None:
            self.hover_plan = flash_plan(movie)
        flash = Flash(movie,self.hover_plan)
        for path in self.paths:
            flash.set_enabled(path,True)
            for handler in ('onPress','onRelease','onReleaseOutside'):
                flash.set_number(path+'.'+handler,0)

    def refresh(self,helper,movie):
        # Match native icon behavior before binding/updating native tooltips.
        self.hover_enabled(movie)
        try:
            with prevent_hooking_direct_calls():
                helper.UpdateMapTooltips(**{self.plan['movie_arg']:movie})
            # Native Flash UpdateLandmark uses this exact guard. A controller
            # crosshair query must never hide an active mouse rollover tooltip.
            from .renderer import Flash
            flash = Flash(movie,self.hover_plan)
            if not flash.boolean('bMouseTooltipActive'):
                flash.invoke('CheckCrosshair')
        finally:
            # Clean activation handlers even if a native bind failed halfway.
            self.hover_enabled(movie)
        self.counts['tooltip_refreshes'] += 1

    def remove_flash(self,movie,plan,paths):
        """Remove only owned entries from Flash's three parallel arrays.

        Native entries keep their values and relative order. If a splice fails,
        restore any already-removed values at the same index before reporting it.
        """
        if not paths or 'GetVariableString' not in plan:
            return
        from .renderer import Flash
        flash = Flash(movie,plan)
        arrays = ('mapItems','tooltipTitles','tooltipBodies')
        try:
            lengths = [flash.number(a+'.length') for a in arrays]
            if len(set(lengths)) != 1 or not 0 <= lengths[0] <= 4096 or int(lengths[0]) != lengths[0]:
                raise ValueError('Flash tooltip arrays are not aligned')
            # Only hide a mouse label when the game's own hit-test says the
            # cursor is over the owned clip being removed.
            if flash.boolean('bMouseTooltipActive'):
                for path in paths:
                    if not own_clip(path):
                        continue
                    hit = flash.invoke(path+'.hitTest',flash.number('_root._xmouse'),flash.number('_root._ymouse'),True)
                    if 'boolean' in plan['Invoke'] and int(hit.Type) == plan['Invoke']['boolean'] and hit.B:
                        flash.invoke('ShowTooltipMouse',0,False)
                        break
            for i in range(int(lengths[0])-1,-1,-1):
                path = flash.string('mapItems.'+str(i))
                if path not in paths or not own_clip(path):
                    continue
                values = [path]+[flash.string(a+'.'+str(i)) for a in arrays[1:]]
                length_before = flash.number('mapItems.length')
                try:
                    for array,value in zip(arrays,values):
                        flash.invoke(array+'.splice',i,1)
                except Exception:
                    # A native call can throw after taking effect. Read back
                    # each array length before deciding whether to undo it.
                    for array,value in reversed(list(zip(arrays,values))):
                        length = flash.number(array+'.length')
                        if length == length_before-1:
                            flash.invoke(array+'.splice',i,0,value)
                        elif length != length_before:
                            raise ValueError('Flash tooltip splice could not be rolled back')
                    raise
            if not flash.boolean('bMouseTooltipActive'):
                flash.invoke('CheckCrosshair')
        except Exception as exc:
            self.problem('remove owned Flash tooltip entries',exc)

    def clear(self,movie=None):
        helper = getattr(movie,'MapHelper',None) if movie is not None else None
        removed = False
        try:
            if helper is not None and self.paths:
                before = [deepcopy(r) for r in helper.MapObjects]
                kept = [r for r in before if str(r.AS_IconPath) not in self.paths]
                if len(kept) != len(before):
                    try:
                        helper.MapObjects = kept
                    except Exception:
                        helper.MapObjects = before
                        raise
                    self.counts['tooltip_rows_removed'] += len(before)-len(kept)
                    removed = True
        except Exception as exc:
            # Keep primitive ownership on failure so a later cleanup can retry.
            self.last_error = str(exc)
            self.problem('remove owned tooltip rows',exc)
            return False
        self.paths.clear()
        self.last_payload = None
        self.last_error = None
        self.retry_after = 0
        self.counts['registered_tooltips'] = 0
        if removed and self.plan is not None:
            try:
                self.refresh(helper,movie)
            except Exception as exc:
                self.last_error = str(exc)
                self.problem('refresh after removing tooltip rows',exc)
        return True

    def sync(self,movie,points,clips,verified,now):
        if now < self.retry_after:
            return
        helper = getattr(movie,'MapHelper',None)
        if helper is None or getattr(helper,'bIsMinimap',False):
            return
        self.next_hover_query = now+.1
        if not any(p['key'] in verified and p['key'] in clips for p in points):
            self.clear(movie)
            return
        try:
            if helper._get_address() != self.helper_address:
                self.paths.clear()
                self.plan = None
                self.hover_plan = None
                self.last_payload = None
                self.helper_address = helper._get_address()
            if self.plan is None:
                self.plan = tooltip_plan(helper)
            from .renderer import project
            transform = normalized_transform(helper)
            data = []
            for point in points:
                key = point['key']
                if key not in verified or key not in clips:
                    continue
                path = clips[key]
                if not own_clip(path):
                    raise ValueError('Refusing tooltip registration for an unowned clip')
                u,v = project(transform,point['x'],point['y'])
                data.append((path,str(point['label']),point['x'],point['y'],point.get('z',0),u,v))
            before = list(helper.MapObjects)
            native = [r for r in before if str(r.AS_IconPath) not in self.paths]
            wanted = {r[0] for r in data}
            template = next((r for r in native if not own_clip(r.AS_IconPath)
                             and str(r.AS_IconClipFrame) == 'objective'),None)
            if template is None:
                raise ValueError('No native objective tooltip template')
            title = str(template.TooltipTitle)
            if not title:
                raise ValueError('Native objective tooltip has no title')
            payload = (title,tuple((p,label,x,y,z,round(u,6),round(v,6)) for p,label,x,y,z,u,v in data))
            registered = {str(r.AS_IconPath) for r in before if str(r.AS_IconPath) in self.paths}
            labels = {p:label for p,label,*_ in data}
            labels_match = all(str(r.TooltipTitle) == title and str(r.TooltipBody) == labels[str(r.AS_IconPath)]
                               for r in before if str(r.AS_IconPath) in wanted)
            if payload == self.last_payload and registered == wanted and labels_match:
                # This is a hover query, not merely metadata registration.
                # Coordinates/labels can remain unchanged while focus moves.
                # Renderer.update already limits this work to ten Hz.
                self.refresh(helper,movie)
                self.last_error,self.retry_after = None,0
                return
            rows = []
            for path,label,x,y,z,u,v in data:
                rows.append(unrealsdk.make_struct(self.plan['struct'],
                    Player=None,Landmark=None,ClientInteractiveObject=None,WPRI=None,
                    bWaypoint=False,bIsDirty=False,Angle=0.0,
                    CustomObjectLoc=unrealsdk.make_struct('Vector',X=x,Y=y,Z=z),
                    TransformedLocation=unrealsdk.make_struct('Vector2D',X=u,Y=v),
                    AS_IconClipPath=str(template.AS_IconClipPath),
                    AS_IconClipFrame=str(template.AS_IconClipFrame),AS_IconPath=path,
                    TooltipTitle=title,TooltipBody=label))
            # WrappedStruct array elements can be views into native storage.
            # Stage Python-owned copies before resizing/replacing that array;
            # their UObject fields remain original references.
            backup = [deepcopy(r) for r in before]
            replacement = [r for r in backup if str(r.AS_IconPath) not in self.paths]+rows
            try:
                helper.MapObjects = replacement
            except Exception:
                # Native property assignment is synchronous. Restore its exact
                # previous UI data if copying the replacement array fails.
                helper.MapObjects = backup
                raise
            self.counts['tooltip_rows_written'] += len(rows)
            self.paths,self.last_payload = wanted,payload
            self.counts['registered_tooltips'] = len(rows)
            self.last_error = None
            from .renderer import Flash,flash_plan
            if self.hover_plan is None:
                self.hover_plan = flash_plan(movie)
            flash = Flash(movie,self.hover_plan)
            for path,label,*_ in data:
                flash.invoke('UpdatePlayerWaypointTooltipText',path,label)
            self.refresh(helper,movie)
        except Exception as exc:
            self.last_error = str(exc)
            self.retry_after = now+3
            self.problem('register map tooltip rows',exc)

    def poll_hover(self,movie,now):
        if not self.paths or self.plan is None or now < max(self.next_hover_query,self.retry_after):
            return
        self.next_hover_query = now+.1
        helper = getattr(movie,'MapHelper',None)
        if helper is None or getattr(helper,'bIsMinimap',False) or helper._get_address() != self.helper_address:
            return
        try:
            from .renderer import Flash
            flash = Flash(movie,self.hover_plan)
            path = next(iter(self.paths))
            # The status menu object can outlive its Flash map. Missing clips
            # must not trigger queries against a closed/replaced map.
            if flash.number(path+'._alpha') <= 0:
                return
            getter = self.hover_plan.get('GetVariableBool')
            if getter is not None:
                root = path.split('.maps.',1)[0]
                with prevent_hooking_direct_calls():
                    visible = movie.GetVariableBool(**{getter['path']:root+'._visible'})
                if not visible:
                    return
            self.refresh(helper,movie)
            self.last_error = None
        except Exception as exc:
            self.last_error,self.retry_after = str(exc),now+3
            self.problem('query stationary map focus',exc)


    def describe(self,helper):
        rows = []
        for row in helper.MapObjects:
            if str(row.AS_IconPath) in self.paths:
                rows.append({'clip':str(row.AS_IconPath),'title':str(row.TooltipTitle),'body':str(row.TooltipBody),
                             'world':{axis:float(getattr(row.CustomObjectLoc,axis)) for axis in 'XYZ'},
                             'map':{axis:float(getattr(row.TransformedLocation,axis)) for axis in 'XY'}})
        return rows

    def interaction_snapshot(self,movie):
        from .renderer import Flash
        if self.hover_plan is None:
            return {}
        flash = Flash(movie,self.hover_plan)
        bool_path = self.hover_plan.get('GetVariableBool',{}).get('path')
        registry = {}
        registry_report = {}
        if 'GetVariableString' in self.hover_plan:
            try:
                lengths = {a:flash.number(a+'.length') for a in ('mapItems','tooltipTitles','tooltipBodies')}
                registry_report['lengths'] = lengths
                registry_report['aligned'] = len(set(lengths.values())) == 1
                length = lengths['mapItems']
                if not 0 <= length <= 4096 or int(length) != length:
                    raise ValueError('Invalid Flash tooltip registry length')
                for i in range(int(length)):
                    path = flash.string('mapItems.'+str(i))
                    if path in self.paths:
                        registry[path] = {'index':i,'title':flash.string('tooltipTitles.'+str(i)),
                                          'body':flash.string('tooltipBodies.'+str(i))}
            except Exception as exc:
                registry_report['error'] = str(exc)
        records = []
        for path in sorted(self.paths):
            record = {'clip':path,'enabled_requested':True}
            if 'GetVariableString' in self.hover_plan:
                record['flash_registration'] = registry.get(path)
            for name in ('_width','_height','_currentframe'):
                try:
                    record[name] = flash.number(path+'.'+name)
                except Exception as exc:
                    record[name] = {'error':str(exc)}
            if bool_path is not None:
                try:
                    with prevent_hooking_direct_calls():
                        record['enabled'] = bool(movie.GetVariableBool(**{bool_path:path+'.enabled'}))
                except Exception as exc:
                    record['enabled'] = {'error':str(exc)}
            records.append(record)
        return {'clips':records,'flash_registry':registry_report}
