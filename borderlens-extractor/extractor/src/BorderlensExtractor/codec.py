"""Typed raw reflection. UObject references stay references, never recursive dumps."""

import math

from .policy import LIMITS, SKIP_FIELDS


def path(obj):
    return obj._path_name()


class Reflector:
    def __init__(self, emit, reference, limits=None):
        self.emit, self.reference = emit, reference
        self.limits = dict(LIMITS, **(limits or {}))
        self.schemas = set()
        self.stats = {'read_errors':0,'truncated':0,'unsupported':0}
        self.nodes = 0
        self.issues = []

    def issue(self, kind, location, **details):
        self.stats[kind] += 1
        record = {'$type':kind,'at':location,**details}
        if len(self.issues)<200:
            self.issues.append(record)
        return record

    def field_meta(self, prop):
        name = str(prop.Name)
        data = {'name':name,'type':str(prop.Class.Name)}
        for source, target in (('PropertyFlags','flags'),('ArrayDim','array_dim')):
            try:
                val = int(getattr(prop,source))
                data[target] = hex(val) if source=='PropertyFlags' else val
            except (AttributeError,TypeError,ValueError):
                pass
        for source, target in (('Struct','struct'),('PropertyClass','object_class'),('Enum','enum')):
            try:
                obj = getattr(prop,source)
                if obj is not None:
                    data[target] = path(obj)
                    if source == 'Enum':
                        data['enum_values'] = {name:int(member) for name,member in obj._as_py().__members__.items()}
            except AttributeError:
                pass
        try:data['inner_type'] = str(prop.Inner.Class.Name)
        except AttributeError:pass
        return data

    def schema(self, struct, kind):
        key = kind+':'+path(struct)
        props = list(struct._properties())
        excluded = SKIP_FIELDS if kind == 'class' else ()
        if key not in self.schemas:
            fields = []
            for prop in props:
                if str(prop.Name) in excluded:continue
                try:fields.append(self.field_meta(prop))
                except Exception as exc:
                    fields.append({'name':str(prop.Name),'error':str(exc)[:500]})
                    self.issue('read_errors',path(struct)+'.'+str(prop.Name),
                               error_type=type(exc).__name__,message=str(exc)[:500])
            self.emit({'record_type':kind+'_schema','id':key,'path':path(struct),
                       'super':path(struct.SuperField) if getattr(struct,'SuperField',None) is not None else None,
                       'fields':fields})
            self.schemas.add(key)
        return [str(p.Name) for p in props if str(p.Name) not in excluded]

    def value(self, value, location, depth=0):
        self.nodes += 1
        if self.nodes>self.limits['nodes']:
            return self.issue('truncated',location,reason='record node limit')
        if value is None or isinstance(value,(bool,int)):
            return value
        if isinstance(value,float):
            return value if math.isfinite(value) else {'$type':'nonfinite','value':str(value)}
        if isinstance(value,str):
            if len(value)>self.limits['string']:
                return self.issue('truncated',location,reason='string limit',length=len(value),prefix=value[:512])
            return value
        if type(value).__name__ == 'FName':
            return {'$type':'name','value':str(value)}
        if hasattr(value,'_path_name'):
            cls = path(value.Class)
            self.reference(value,location)
            return {'$ref':path(value),'class':cls}
        if depth>=self.limits['depth']:
            return self.issue('truncated',location,reason='depth limit')
        if isinstance(value,(tuple,list)) or type(value).__name__=='WrappedArray':
            length = len(value)
            count = min(length,self.limits['array'],max(0,self.limits['nodes']-self.nodes))
            items = [self.value(value[i],location+'['+str(i)+']',depth+1) for i in range(count)]
            result = {'$type':'array','length':length,'items':items,'truncated':count<length}
            if count<length:self.issue('truncated',location,reason='array/node limit',length=length,written=count)
            return result
        if isinstance(value,dict):
            return {str(k):self.value(v,location+'.'+str(k),depth+1) for k,v in value.items()}
        struct = getattr(value,'_type',None)
        if struct is not None and hasattr(struct,'_properties'):
            fields = {}
            for name in self.schema(struct,'struct'):
                fields[name] = self.read(value,name,location+'.'+name,depth+1)
            return {'$type':'struct','struct':path(struct),'fields':fields}
        return self.issue('unsupported',location,python_type=type(value).__name__)

    def read(self, obj, name, location, depth=0):
        try:return self.value(getattr(obj,name),location,depth)
        except Exception as exc:
            return self.issue('read_errors',location,error_type=type(exc).__name__,message=str(exc)[:1000])

    def object(self, obj, kind='object', allowed=None, context=None):
        self.nodes, self.issues = 0, []
        names = self.schema(obj.Class,'class')
        if allowed is not None:names = [n for n in names if allowed(n)]
        identity = path(obj)
        fields = {name:self.read(obj,name,identity+'.'+name) for name in names}
        return {'record_type':kind,'id':kind+':'+identity.casefold(),'path':identity,
                'class':path(obj.Class),'name':str(obj.Name),
                'outer':path(obj.Outer) if getattr(obj,'Outer',None) is not None else None,
                'is_default':str(obj.Name).startswith('Default__'),'context':context,
                'properties':fields,'issues':list(self.issues),'complete':not self.issues}
