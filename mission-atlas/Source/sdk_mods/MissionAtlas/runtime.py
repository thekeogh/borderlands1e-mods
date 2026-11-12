"""Cached mission positions, focused map events and manual native diagnostics."""

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import json
import math
import time

import unrealsdk
from unrealsdk import logging
from unrealsdk.hooks import Type, add_hook, remove_hook

from .native import hook_path, kind, path_of, signature, flash_function
from .policy import waypoint_for, select_waypoint
from .renderer import Renderer

VERSION = '0.1.10'
CLASSES = ('StatusMenuExGFxMovie','WillowGFxHelperMap','MissionTracker',
           'WillowWaypoint','WillowPlayerController','WaypointDefinition','WillowPlayerReplicationInfo')
MAP_METHODS = {'SetupMapPage','extUpdateMapPage','MapUpdateBehavior','PanMap',
               'HandleMapInputKey','HandleMapInputAxis'}
MISSION_EVENTS = {'SetActiveMission','PlayerSetMissionToTrack','SetMissionStatus',
                  'ClientAddMission','UpdateMissionObjective','UpdateMissionStatus','UpdateObjective',
                  'NotifyMissionObjectiveObservers','ServerSetActiveMission'}
def default_object(obj):
    return 'default__' in obj._path_name().lower()


def brief(value, depth=0):
    """No methods on arbitrary actors; cap every branch of exported data."""
    if isinstance(value, float) and not math.isfinite(value):
        return {'nonfinite': str(value)}
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if hasattr(value, '_path_name'):
        return path_of(value)
    if depth < 3:
        if isinstance(value, (list, tuple)) or type(value).__name__ == 'WrappedArray':
            return [brief(value[i], depth + 1) for i in range(min(len(value), 24))]
        struct = getattr(value, '_type', None)
        if struct is not None and hasattr(struct, '_properties'):
            result = {}
            for prop in list(struct._properties())[:24]:
                name = str(prop.Name)
                try:
                    result[name] = brief(getattr(value, name), depth + 1)
                except Exception as exc:
                    result[name] = {'error': str(exc)}
            return result
        try:
            return [brief(v, depth + 1) for v in list(value)[:24]]
        except TypeError:
            pass
        result = {}
        for name in ('X', 'Y', 'Z', 'R', 'G', 'B', 'A'):
            if hasattr(value, name):
                result[name] = brief(getattr(value, name), depth + 1)
        if result:
            return result
    return str(value)[:160]


class Atlas:
    def __init__(self, get_pc, include_turn_ins, opacity):
        self.get_pc, self.include_turn_ins, self.opacity = get_pc, include_turn_ins, opacity
        self.enabled = False
        self.installed, self.seen, self.cleaned = [], set(), set()
        self.schemas, self.errors = {}, []
        self.counts = Counter()
        self.export_callback = None
        self.last_discovery = -1e10
        self.scanning, self.ready, self.rendering = False, False, False
        self.selection_details = []
        self.pending_movie, self.pending_until, self.next_initial_retry = None, 0, 0
        self.points, self.cache_key, self.cache_until = [], None, -1e10
        self.renderer = Renderer(self.problem,self.counts)

    def problem(self, context, exc):
        text = f'{context}: {type(exc).__name__}: {exc}'
        if text not in self.errors and len(self.errors) < 24:
            self.errors.append(text)

    def objects(self, cls):
        try:
            return [o for o in unrealsdk.find_all(cls) if not default_object(o)]
        except ValueError:
            return []

    def tracked(self, pc):
        result = set()
        trackers = self.objects('MissionTracker')
        direct = getattr(pc,'MissionTracker',None)
        if direct is not None:
            trackers = [direct]
        for tracker in trackers:
            world, owner = getattr(tracker,'WorldInfo',None), getattr(tracker,'Owner',None)
            if tracker != direct and world is not None and world != pc.WorldInfo:
                continue
            if tracker != direct and world is None and owner not in (None,pc):
                continue
            active = getattr(tracker,'ActiveMission',None)
            if active is not None:
                result.add(active._path_name().lower())
        pri = getattr(pc,'PlayerReplicationInfo',None)
        active = getattr(pri,'ActiveMission',None) or getattr(pc,'ActiveMission',None)
        if active is not None:
            result.add(active._path_name().lower())
        return result

    def missions(self, pc):
        data = pc.MissionPlaythroughData
        index = int(pc.GetCurrentPlaythrough())
        return list(data[index].MissionList) if 0 <= index < len(data) else []

    def collect(self):
        self.selection_details = []
        for name in ('selected_definitions','candidate_actors','selected_missions'):
            self.counts[name] = 0
        pc = self.get_pc()
        if pc is None or pc.Pawn is None:
            return []
        world, tracked = pc.WorldInfo,self.tracked(pc)
        current_map = world.GetMapName()
        if not tracked:
            self.counts['missing_tracked_mission'] += 1
            return []
        selected, reserved, seen_missions = [],set(),set()
        for row in self.missions(pc):
            if row.MissionDef is None:
                continue
            mission_key = row.MissionDef._path_name().lower()
            if mission_key in seen_missions:
                continue
            seen_missions.add(mission_key)
            definition = waypoint_for(row,current_map,set(),self.include_turn_ins())
            if definition is None:
                continue
            path = definition._path_name().lower()
            if row.MissionDef._path_name().lower() in tracked:
                reserved.add(path)
            else:
                selected.append((row,path))
        grouped = {}
        for actor in self.objects('WillowWaypoint'):
            if (getattr(actor,'bDeleteMe',False) or getattr(actor,'bPendingDelete',False)
                    or getattr(actor,'WorldInfo',None) != world):
                continue
            definition = getattr(actor,'WaypointDefinition',None)
            definitions = [definition] if definition is not None else getattr(actor,'WaypointDefinitions',[])
            for definition in definitions:
                if definition is not None:
                    grouped.setdefault(definition._path_name().lower(),[]).append(actor)
        points, count = [],0
        for row,path in selected:
            if path in reserved:
                continue
            candidates = grouped.get(path,[])
            count += len(candidates)
            actor,reason = select_waypoint(row,candidates)
            mission = row.MissionDef
            key = mission._path_name().lower()
            self.selection_details.append({'mission':key,'candidate_count':len(candidates),
                                            'reason':reason,'actor':path_of(actor)})
            if actor is None:
                continue
            location = actor.Location
            x,y,z = float(location.X),float(location.Y),float(location.Z)
            if not all(math.isfinite(v) for v in (x,y,z)):
                continue
            points.append({'key':key,'actor':actor._path_name(),'number':int(getattr(actor,'WaypointNumber',0)),
                           'selection':reason,'x':x,'y':y,'z':z,'label':str(mission.MissionName)})
        self.counts['selected_definitions'] = len({p for _,p in selected if p not in reserved})
        self.counts['candidate_actors'],self.counts['selected_missions'] = count,len(points)
        return points

    def invalidate(self, *_):
        self.cache_until = -1e10

    def points_for(self, pc, now):
        key = (pc._get_address(),pc.WorldInfo._get_address(),str(pc.WorldInfo.GetMapName()),self.include_turn_ins())
        if key == self.cache_key and now < self.cache_until:
            return self.points
        self.points = self.collect()
        self.cache_key,self.cache_until = key,now+1
        self.counts['point_scans'] += 1
        return self.points

    def render_movie(self,movie,now,force=False):
        if self.rendering:
            return
        if not force and now-self.renderer.last_update < .1:
            return
        pc = self.get_pc()
        if pc is None or pc.Pawn is None:
            return
        self.rendering = True
        try:
            points = self.points_for(pc,now)
            self.renderer.update(movie,points,float(self.opacity()),now,force)
        finally:
            self.rendering = False
        if self.pending_movie == movie._get_address():
            self.next_initial_retry = now+.1
            no_markers_needed = not points and self.counts['selected_definitions'] == 0
            if self.renderer.last_error is None and (self.renderer.clips or no_markers_needed):
                # A missing helper is not a completed initial render.
                if getattr(movie,'MapHelper',None) is not None:
                    self.pending_movie = None
                    self.counts['initial_renders_completed'] += 1

    def helper_applied(self,helper,args,_ret,_func):
        if not self.enabled or getattr(helper,'bIsMinimap',False):
            return
        movie = args.Movie
        if movie is None or getattr(movie,'MapHelper',None) != helper:
            return
        try:
            self.counts['map_helper_applied'] += 1
            now = time.monotonic()
            pending = self.pending_movie == movie._get_address()
            if pending and now < self.next_initial_retry:
                return
            self.render_movie(movie,now,force=pending)
        except Exception as exc:
            self.problem('render after native map ApplyFlash',exc)

    def map_callback(self, path, name, fields):
        def after(movie,args,ret,_func):
            if not self.enabled:
                return
            self.counts[path] += 1
            try:
                if (name == 'HandleMapInputKey' and str(args.ukey).lower() == 'f9'
                        and int(args.uevent) == 0 and self.export_callback is not None):
                    self.export_callback()
                pc = self.get_pc()
                if pc is None or pc.Pawn is None:
                    return
                force = name == 'SetupMapPage'
                if force:
                    self.renderer.reset(movie)
                    self.invalidate()
                now = time.monotonic()
                if force:
                    self.pending_movie = movie._get_address()
                    self.pending_until,self.next_initial_retry = now+5,now
                pending = self.pending_movie == movie._get_address()
                self.render_movie(movie,now,force=force or (pending and now >= self.next_initial_retry))
            except Exception as exc:
                self.problem('update extra map icons',exc)
        return after

    def clean_legacy(self, path):
        if path in self.cleaned:
            return
        self.cleaned.add(path)
        for version in ('012','013','014','015','016','017','018'):
            for suffix in ('Map','Invalidate','MapReady'):
                remove_hook(path,Type.POST_UNCONDITIONAL,'MissionAtlas.'+version+'.'+path+'.'+suffix)
        # 0.1.1 could install a hook then lose bookkeeping after a duplicate.
        # Remove only our known old identifiers, including the malformed path.
        for old_path in (path,path.replace('.',':',1)):
            for timing,suffix in ((Type.PRE,'MapBefore'),(Type.PRE,'Supply'),(Type.PRE,'MarkerWriter'),
                                  (Type.POST_UNCONDITIONAL,'MapAfter'),(Type.POST_UNCONDITIONAL,'Observe'),
                                  (Type.POST_UNCONDITIONAL,'DiagnosticKey')):
                remove_hook(old_path,timing,'MissionAtlas.'+suffix)

    def install(self, path, timing, suffix, callback):
        key = path,timing,suffix
        if key in self.seen:
            return True
        identifier = 'MissionAtlas.019.'+path+'.'+suffix
        # Replace our exact ID on reload; never abort other interfaces when one
        # registration fails. Function-specific IDs avoid alias collisions.
        remove_hook(path,timing,identifier)
        if not add_hook(path,timing,identifier,callback):
            self.problem('install '+path,RuntimeError('Native hook registration rejected'))
            return False
        self.seen.add(key)
        self.installed.append((path,timing,identifier))
        return True



    def property_schema(self, prop):
        result = {'name':str(prop.Name),'type':kind(prop)}
        if kind(prop) == 'ObjectProperty':
            result['object_class'] = path_of(prop.PropertyClass)
        elif kind(prop) == 'StructProperty':
            result['struct'] = path_of(prop.Struct)
            self.capture_struct(prop.Struct)
        elif kind(prop) == 'ArrayProperty':
            result['inner_type'] = kind(prop.Inner)
            if kind(prop.Inner) == 'ObjectProperty':
                result['object_class'] = path_of(prop.Inner.PropertyClass)
            elif kind(prop.Inner) == 'StructProperty':
                result['struct'] = path_of(prop.Inner.Struct)
                self.capture_struct(prop.Inner.Struct)
        if getattr(prop,'Enum',None) is not None:
            result['enum_values'] = {n:int(v) for n,v in prop.Enum._as_py().__members__.items()}
        return result

    def capture_struct(self, struct):
        path = path_of(struct)
        if path in self.schemas or len(self.schemas) >= 100 or not hasattr(struct,'_properties'):
            return
        self.schemas[path] = entry = {'kind':'struct','properties':[]}
        for prop in struct._properties():
            try:
                entry['properties'].append(self.property_schema(prop))
            except Exception as exc:
                entry['properties'].append({'name':str(prop.Name),'error':str(exc)})

    def discover(self):
        if self.scanning:
            return
        self.scanning, self.last_discovery = True, time.monotonic()
        try:
            for name in CLASSES:
                try:
                    cls = unrealsdk.find_class(name)
                except ValueError:
                    continue
                if cls is None:
                    continue
                schema = self.schemas.setdefault(path_of(cls),{'properties':[],'functions':{},'raw_function_paths':{}})
                schema['properties'] = []
                for p in cls._properties():
                    try:
                        schema['properties'].append(self.property_schema(p))
                    except Exception as exc:
                        schema['properties'].append({'name':str(p.Name),'error':str(exc)})
                for fn in cls._fields():
                    if str(fn.Class.Name) != 'Function':
                        continue
                    path = hook_path(fn)
                    if not any(t in path.lower() for t in ('map','waypoint','mission')) and not flash_function(fn):
                        continue
                    self.clean_legacy(path)
                    try:
                        fields = signature(fn)
                        schema['raw_function_paths'][path] = fn._path_name()
                        schema['functions'][path] = fields
                        schema.setdefault('function_flags',{})[path] = int(getattr(fn,'FunctionFlags',0))
                        for p in fn._properties():
                            if kind(p) == 'StructProperty':self.capture_struct(p.Struct)
                            elif kind(p) == 'ArrayProperty' and kind(p.Inner) == 'StructProperty':self.capture_struct(p.Inner.Struct)
                        owner,_,method = path.rpartition(':')
                        if owner == 'WillowGame.StatusMenuExGFxMovie' and method in MAP_METHODS:
                            self.install(path,Type.POST_UNCONDITIONAL,'Map',self.map_callback(path,method,fields))
                        elif (owner == 'WillowGame.WillowGFxHelperMap' and method == 'ApplyFlash'
                              and len(fields) == 1 and fields[0]['name'] == 'Movie'
                              and fields[0]['type'] == 'ObjectProperty'):
                            self.install(path,Type.POST_UNCONDITIONAL,'MapReady',self.helper_applied)
                        elif owner in ('WillowGame.WillowPlayerController','WillowGame.MissionTracker') and method in MISSION_EVENTS:
                            self.install(path,Type.POST_UNCONDITIONAL,'Invalidate',self.invalidate)
                    except Exception as exc:
                        schema['functions'][path] = {'error':str(exc)}
                        self.problem('discover '+path,exc)
            self.ready = any(p.endswith(':SetupMapPage') for p,_,_ in self.installed) and 'WillowGame.WillowGFxHelperMap' in self.schemas
        except Exception as exc:
            self.problem('discover interfaces',exc)
        finally:
            self.scanning = False

    def enable(self):
        self.enabled = True
        self.discover()
        logging.info('[Mission Atlas] Loaded '+VERSION+'; cached map objective overlay. F9 exports diagnostics.')

    def reset_rendering(self):
        self.pending_movie = None
        for movie in self.objects('StatusMenuExGFxMovie'):
            if movie._get_address() == self.renderer.movie_address:
                self.renderer.reset(movie)
                break
        else:
            self.renderer.reset()
        self.invalidate()

    def disable(self):
        self.enabled = False
        self.reset_rendering()
        for path,timing,identifier in reversed(self.installed):
            remove_hook(path,timing,identifier)
        self.installed.clear()
        self.seen.clear()

    def poll(self):
        if not self.enabled:
            return
        pc = self.get_pc()
        if pc is None:
            return
        now = time.monotonic()
        if not self.ready and getattr(pc,'bStatusMenuOpen',False) and now-self.last_discovery > 5:
            self.discover()
        if self.pending_movie is None:
            service = self.renderer.tooltips
            if (getattr(pc,'bStatusMenuOpen',False) and service.paths and not self.rendering
                    and now >= max(service.next_hover_query,service.retry_after)):
                for movie in self.objects('StatusMenuExGFxMovie'):
                    if movie._get_address() == self.renderer.movie_address:
                        self.rendering = True
                        try:
                            service.poll_hover(movie,now)
                        finally:
                            self.rendering = False
                        break
            return
        if now > self.pending_until or not getattr(pc,'bStatusMenuOpen',False):
            if now > self.pending_until:
                self.counts['initial_render_timeouts'] += 1
            self.pending_movie = None
            return
        if now < self.next_initial_retry:
            return
        self.next_initial_retry = now+.1
        # Only during the bounded startup retry window, never every idle/pan
        # frame. Hold no movie wrapper between frames.
        for movie in self.objects('StatusMenuExGFxMovie'):
            if movie._get_address() == self.pending_movie:
                self.counts['initial_render_retries'] += 1
                self.render_movie(movie,now,force=True)
                break

    def instance_snapshot(self, obj, tokens):
        record = {'object':path_of(obj),'properties':{}}
        for prop in obj.Class._properties():
            name = str(prop.Name)
            if any(t in name.lower() for t in tokens):
                try:record['properties'][name] = brief(getattr(obj,name))
                except Exception as exc:record['properties'][name] = {'error':str(exc)}
        return record

    def snapshot(self):
        pc = self.get_pc()
        result = {'version':VERSION,'enabled':self.enabled,'ready':self.ready,'native_rendering_verified':False,
                  'hooks':[{'path':p,'timing':str(t),'identifier':i} for p,t,i in self.installed],
                  'schemas':self.schemas,'counts':dict(self.counts),'errors':list(self.errors),
                  'cached_points':list(self.points),'waypoint_selection':list(self.selection_details),
                  'pending_initial_render':self.pending_movie is not None,'renderer':{'plan':self.renderer.plan,'clips':dict(self.renderer.clips),
                                                            'last_error':self.renderer.last_error,
                                                            'tooltips':{'registered':sorted(self.renderer.tooltips.paths),
                                                                        'last_error':self.renderer.tooltips.last_error}},
                  'missions':[],'waypoints':[],'map_helpers':[],'map_ui':[],'tooltip_rows':[]}
        if pc is None or pc.Pawn is None:
            return result
        result.update(map=pc.WorldInfo.GetMapName(),tracked=sorted(self.tracked(pc)),net_mode=int(pc.WorldInfo.NetMode))
        for cls,key in (('WillowGFxHelperMap','map_helpers'),('StatusMenuExGFxMovie','map_ui')):
            result[key] = [self.instance_snapshot(o,('map','waypoint','icon','marker','min','max','scale','zoom','view','center','pos','bound','active'))
                           for o in self.objects(cls)[:4]]
        for movie in self.objects('StatusMenuExGFxMovie'):
            if movie._get_address() == self.renderer.movie_address and getattr(movie,'MapHelper',None) is not None:
                result['tooltip_rows'] = self.renderer.tooltips.describe(movie.MapHelper)
                result['tooltip_interaction'] = self.renderer.tooltips.interaction_snapshot(movie)
                break
        for row in self.missions(pc):
            m = row.MissionDef
            if m is not None:
                result['missions'].append({'mission':path_of(m),'name':str(m.MissionName),'status':int(row.Status),
                                           'objectives':brief(getattr(row,'Objectives',None)),
                                           'objective_requirements':[int(o.ObjectiveCount) for o in getattr(m,'Objectives',[])],
                                           'target':self.definition_snapshot(getattr(m,'TargetWaypointDefinition',None)),
                                           'turn_in':self.definition_snapshot(getattr(m,'TurnInWaypointDefinition',None))})
        for actor in self.objects('WillowWaypoint')[:150]:
            result['waypoints'].append({'actor':path_of(actor),'definition':path_of(getattr(actor,'WaypointDefinition',None)),
                                        'number':int(getattr(actor,'WaypointNumber',0)),'location':brief(actor.Location)})
        return result

    def definition_snapshot(self, definition):
        if definition is None:return None
        return {'path':path_of(definition),'map':str(definition.PersistentLevelName),'sublevel':str(definition.SubLevelName)}

    def export(self, folder):
        logging.info('[Mission Atlas] Diagnostic export requested.')
        try:
            self.discover()
            return self.write_report(folder)
        except Exception as exc:
            self.problem('diagnostic export',exc)
            logging.error(f'[Mission Atlas] Diagnostic export failed: {exc}')
            return None

    def write_report(self,folder,label=None):
        try:
            folder = Path(folder);folder.mkdir(parents=True,exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
            prefix = 'mission-atlas-'+(label+'-' if label else '')
            path = folder/f'{prefix}{stamp}.json'
            path.write_text(json.dumps(self.snapshot(),indent=2,allow_nan=False),encoding='utf-8')
            logging.info(f'[Mission Atlas] Diagnostics saved: {path}')
            return path
        except Exception as exc:
            self.problem('diagnostic export',exc)
            logging.error(f'[Mission Atlas] Diagnostic export failed: {exc}')
            return None
