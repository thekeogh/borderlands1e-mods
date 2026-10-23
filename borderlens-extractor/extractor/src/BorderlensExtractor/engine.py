"""Main-thread adapter; queued descriptors and pin records contain primitives only."""

from . import policy


def canonical(path):
    """StaticFindObject and GetPathName can differ on nested ':' separators."""
    return path.replace(':', '.').casefold()


class Engine:
    def __init__(self, sdk):
        self.sdk = sdk
        self.pins = {}
        self.pin_errors = []
        self.lookup_counts = {'direct':0, 'normalized':0, 'class_scan':0, 'missing':0}
        self.lookup_recoveries = []

    def is_actor(self, obj):
        return obj.Class._inherits(self.sdk.find_class('Actor'))

    def descriptor(self, obj, kind='object'):
        return {'path':obj._path_name(), 'class':obj.Class._path_name(),
                'kind':kind, 'address':obj._get_address()}

    def matches(self, obj, row):
        # A short name or reused full path must never resolve to an unrelated
        # object. Addresses are process-local checks, never cross-run cursors.
        return (obj is not None
                and canonical(obj._path_name()) == canonical(row['path'])
                and obj.Class._path_name().casefold() == row['class'].casefold()
                and ('address' not in row or obj._get_address() == row['address']))

    def recovered(self, method, row):
        self.lookup_counts[method] += 1
        if len(self.lookup_recoveries) < 100:
            self.lookup_recoveries.append({'path':row['path'], 'class':row['class'], 'method':method})

    def find(self, row):
        variants = [row['path']]
        if ':' in row['path']:
            variants.append(row['path'].replace(':', '.'))
        for index, name in enumerate(variants):
            try:obj = self.sdk.find_object(row['class'], name)
            except ValueError:continue
            if self.matches(obj, row):
                if index:self.recovered('normalized', row)
                else:self.lookup_counts['direct'] += 1
                return obj
        # Exact-class enumeration avoids ambiguous native name resolution.
        # All wrappers are consumed here; no native objects are cached.
        try:
            for obj in self.sdk.find_all(row['class'], exact=True):
                if self.matches(obj, row):
                    self.recovered('class_scan', row)
                    return obj
        except ValueError:pass  # The class/package may itself have unloaded.
        self.lookup_counts['missing'] += 1
        return None

    def classes(self):
        result = {}
        actor = self.sdk.find_class('Actor')
        for cls in self.sdk.find_all('Class'):
            if policy.data_class(str(cls.Name)) and not cls._inherits(actor):
                result[cls._path_name()] = str(cls.Name)
        return sorted(result)

    def scan(self, cls):
        return self.sdk.find_all(cls, exact=True)

    def package(self, name):
        # A Package object may be a linker placeholder, not a fully loaded
        # package. Explicitly load each reviewed root even when it is present.
        result = self.sdk.load_package(name)
        return 'loaded' if result is not None else 'not_confirmed'

    def pin(self, obj):
        if self.is_actor(obj):return
        key = obj._path_name()
        if key in self.pins:return
        flags = int(obj.ObjectFlags)
        if flags & policy.ROOT_SET:return
        self.pins[key] = {'path':key,'class':obj.Class._path_name(),'address':obj._get_address()}
        obj.ObjectFlags = flags | policy.ROOT_SET

    def release(self):
        for row in list(self.pins.values()):
            try:
                obj = self.find(row)
                if obj is not None:
                    obj.ObjectFlags = int(obj.ObjectFlags) & ~policy.ROOT_SET
                else:
                    self.pin_errors.append({'path':row['path'], 'error':'Pinned object could not be resolved for release'})
            except Exception as exc:
                self.pin_errors.append({'path':row['path'],'error':repr(exc)[:500]})
        self.pins.clear()
        return list(self.pin_errors)
