"""Incremental data-only export; no actor/value wrappers survive a frame."""

from collections import deque
import time

from . import policy
from .codec import Reflector
from .engine import Engine
from .storage import Dataset, Bundle, utc


class Job:
    def __init__(self, sdk, directory, metadata, packages, resume=False, limits=None):
        self.limits = dict(policy.LIMITS,**(limits or {}))
        self.engine = Engine(sdk)
        self.dataset = Dataset(directory,metadata,self.limits['chunk_records'],self.limits['chunk_bytes'],resume)
        self.codec = Reflector(self.dataset.add,self.reference,self.limits)
        self.codec.schemas.update(key for key in self.dataset.ids if key.startswith(('class:','struct:')))
        self.packages = packages if metadata['configuration']['scope']=='catalogue' else []
        self.context = metadata['session']
        self.queue, self.queued = deque(), set()
        self.external = dict(self.dataset.manifest.get('external_references', {}))
        self.failures = list(self.dataset.manifest.get('failures', []))
        self.missing = list(self.dataset.manifest.get('missing_objects', []))
        self.codec.stats.update(self.dataset.manifest.get('serialization', {}))
        prior_lookup = self.dataset.manifest.get('lookup', {})
        self.engine.lookup_counts.update(prior_lookup.get('counts', {}))
        self.engine.lookup_recoveries = list(prior_lookup.get('recoveries', []))
        self.binding_count = 0
        self.read_count = 0
        self.phase = 'discover'
        self.state = 'running'
        self.scans = deque()
        self.worlds = deque(policy.WORLD_CLASSES)
        self.package_index = 0
        self.package_results = list(self.dataset.manifest.get('package_results',[]))
        self.quarantined = {r['name'].casefold() for r in self.package_results if r['status']=='loading'}
        for row in self.package_results:
            if row['status']=='loading':row['status']='interrupted_quarantined'
        self.bundle = None
        self.last_checkpoint = time.monotonic()
        self.max_step_ms = 0.0
        self.busy = False
        self.note = ''
        self.class_inventory = set(self.dataset.manifest.get('discovered_classes', []))
        try:
            inventory = sorted(obj._path_name() for obj in self.engine.sdk.find_all('Package'))
            self.dataset.manifest.setdefault('package_inventory', []).append(
                {'session':len(self.dataset.manifest['sessions'])-1,'loaded_at_start':inventory})
        except Exception as exc:self.record_failure('package inventory', 'Package', exc)
        if self.dataset.capture_complete:
            self.phase = 'archive'
            self.dataset.checkpoint(status='complete')
            self.bundle = Bundle(self.dataset)

    def record_failure(self, stage, identity, exc):
        row = {'stage':stage,'identity':identity,'error':repr(exc)[:1500]}
        if len(self.failures)<1000:self.failures.append(row)
        self.note = stage+': '+identity

    def enqueue(self, obj, kind='object'):
        descriptor = self.engine.descriptor(obj,kind)
        key = kind+':'+descriptor['path'].casefold()
        if kind != 'object':key += '@'+str(self.context.get('map', '')).casefold()
        if key in self.dataset.ids or key in self.queued:return
        cap = self.limits['bindings'] if kind!='object' else self.limits['objects']
        count = self.binding_count if kind!='object' else len(self.queued)
        if count>=cap:
            self.external['object/binding limit'] = self.external.get('object/binding limit',0)+1
            return
        if kind=='object':self.engine.pin(obj)
        else:self.binding_count += 1
        self.queue.append(descriptor)
        self.queued.add(key)

    def reference(self, obj, location):
        if sum(self.external.values())+len(self.queued)>=self.limits['references']:
            self.external['reference limit'] = self.external.get('reference limit',0)+1
            return
        if self.engine.is_actor(obj):
            # Read referenced pawn/vehicle templates as narrow binding evidence,
            # without retaining or pinning actors, or calling their methods.
            if location.lower().endswith(('aipawnarchetype','vehiclearchetype')):
                self.enqueue(obj,'archetype_binding')
            else:self.external['actor reference'] = self.external.get('actor reference',0)+1
            return
        if policy.data_class(str(obj.Class.Name)):
            self.enqueue(obj)
        else:
            name = str(obj.Class.Name)
            self.external[name] = self.external.get(name,0)+1

    def progress(self):
        return {'state':self.state,'phase':self.phase,'note':self.note,'records':dict(self.dataset.counts),
                'queued':len(self.queue),'packages_processed':self.package_index,'packages_planned':len(self.packages),
                'directory':str(self.dataset.directory),'max_step_ms':round(self.max_step_ms,2)}

    def checkpoint(self, status=None):
        self.dataset.checkpoint(status=status or self.state,phase=self.phase,
            package_results=self.package_results,failures=list(self.failures),missing_objects=list(self.missing),
            external_references=dict(self.external),serialization=dict(self.codec.stats),
            discovered_classes=sorted(self.class_inventory),
            lookup={'counts':dict(self.engine.lookup_counts),
                    'recoveries':list(self.engine.lookup_recoveries)},progress=self.progress())
        self.last_checkpoint = time.monotonic()

    def discover(self):
        classes = self.engine.classes()
        self.class_inventory.update(classes)
        self.scans = deque(classes)
        self.phase = 'scan'
        self.note = 'discovering loaded data classes'

    def step(self):
        if self.phase=='discover':
            self.discover()
            return
        if self.queue:
            row = self.queue.popleft()
            obj = self.engine.find(row)
            if obj is None:
                if len(self.missing)<1000:self.missing.append(row)
                return
            record = self.codec.object(obj,row['kind'],policy.binding_field if row['kind']!='object' else None,
                                       {'session':len(self.dataset.manifest['sessions'])-1,
                                        'map':self.context.get('map'),
                                        'source_package':row['path'].split('.',1)[0]})
            if row['kind'] != 'object':
                record['id'] += '@'+str(self.context.get('map', '')).casefold()
            self.dataset.add(record)
            self.read_count += 1
            self.note = row['path']
            return
        if self.scans:
            cls = self.scans.popleft()
            self.note = 'scan '+cls
            try:
                for obj in self.engine.scan(cls):
                    if not self.engine.is_actor(obj):self.enqueue(obj)
            except Exception as exc:self.record_failure('class scan',cls,exc)
            return
        if self.worlds:
            name = self.worlds.popleft()
            self.note = 'map bindings '+name
            try:
                for obj in self.engine.sdk.find_all(name):
                    if not str(obj.Name).startswith('Default__'):self.enqueue(obj,'world_binding')
            except Exception as exc:self.record_failure('map binding scan',name,exc)
            return
        if self.package_index<len(self.packages):
            row = self.packages[self.package_index]
            self.package_index += 1
            name = row['name']
            self.note = 'loading '+name
            if name.casefold() in self.quarantined:
                self.package_results.append({**row,'status':'quarantined_after_interruption'})
                return
            result = {**row,'status':'loading','started_utc':utc()}
            self.package_results.append(result)
            # Persist the exact next native load before invoking it. A crash can
            # then be resumed with that package quarantined instead of retried.
            self.phase = 'package_load'
            self.checkpoint()
            try:result['status'] = self.engine.package(name)
            except Exception as exc:
                result['status'] = 'failed'
                result['error'] = repr(exc)[:1500]
            result['finished_utc'] = utc()
            self.phase = 'discover'
            self.checkpoint()
            return
        self.finish()

    def tick(self):
        if self.state!='running' or self.busy:return
        self.busy = True
        start = time.monotonic()
        try:
            if self.phase=='archive':
                if self.bundle.step():
                    self.state, self.phase = 'complete','complete'
                return
            for _ in range(self.limits['frame_records']):
                self.step()
                if self.state!='running' or self.phase=='archive':break
                if (time.monotonic()-start)*1000>=self.limits['frame_ms']:break
            if self.phase!='archive' and time.monotonic()-self.last_checkpoint>=2:
                self.checkpoint()
        except Exception as exc:
            self.record_failure('export',self.note,exc)
            self.state = 'failed'
            self.engine.release()
            if self.bundle:self.bundle.close()
            try:self.checkpoint('failed')
            except Exception:pass  # Preserve the original failure even if disk writes fail.
        finally:
            self.max_step_ms = max(self.max_step_ms,(time.monotonic()-start)*1000)
            self.busy = False

    def pause(self, reason='user pause', release=False):
        if self.state!='running':return
        self.state, self.note = 'paused',reason
        if self.phase=='archive':
            if release:self.engine.release()
            return
        if release:
            self.engine.release()
            self.phase = 'discover'
        self.checkpoint('paused')

    def resume(self):
        if self.state=='paused':self.state = 'running'

    def finish(self, reason=None):
        if self.phase=='archive' or self.state=='complete':return
        if reason:
            self.dataset.manifest['coverage']['limitations'].append(reason)
        releases = self.engine.release()
        if releases:self.failures.extend(releases)
        self.phase, self.state = 'archive','running'
        coverage = self.dataset.manifest['coverage']
        coverage['data_issues'] = bool(self.failures or self.missing or any(self.codec.stats.values()))
        coverage['unconfirmed_packages'] = sum(r['status'] not in ('loaded','already_present') for r in self.package_results)
        coverage['limits_hit'] = sorted(k for k in self.external if 'limit' in k)
        coverage['catalogue_complete'] = False
        self.checkpoint('complete')
        self.bundle = Bundle(self.dataset)

    def close(self):
        if self.bundle:self.bundle.close()
        self.engine.release()
