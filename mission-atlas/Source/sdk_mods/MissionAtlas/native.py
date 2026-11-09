"""Native reflection helpers. No inferred marker API or hot-path actor schemas."""

def path_of(obj):
    return obj._path_name() if obj is not None else None


def short_name(path):
    return str(path).replace(':', '.').rsplit('.', 1)[-1]


def kind(prop):
    return str(prop.Class.Name)


def signature(function):
    fields = []
    for prop in function._properties():
        flags = int(prop.PropertyFlags)
        if not flags & 0x80:
            continue
        row = {'name': str(prop.Name), 'type': kind(prop), 'flags': flags}
        if row['type'] == 'ArrayProperty':
            row['inner_type'] = kind(prop.Inner)
            if row['inner_type'] == 'ObjectProperty':
                row['object_class'] = path_of(prop.Inner.PropertyClass)
        elif row['type'] == 'ObjectProperty':
            row['object_class'] = path_of(getattr(prop, 'PropertyClass', None))
        elif row['type'] == 'StructProperty':
            row['struct'] = path_of(prop.Struct)
        fields.append(row)
    return fields


def hook_path(function):
    # BL1E reports UFunction paths as Package.Class:Function. Splitting on the
    # last dot corrupts that into Package:Class:Function (the 0.1.0 failure).
    outer = getattr(function, 'Outer', None)
    if outer is not None:
        return outer._path_name() + ':' + str(function.Name)
    raw = function._path_name()
    if ':' in raw:
        return raw
    owner, _, name = raw.rpartition('.')
    return owner + ':' + name



def flash_function(function):
    path = hook_path(function)
    owner,_,name = path.rpartition(':')
    return ('gfx' in owner.lower() and
            name.startswith(('Invoke','GetVariable','SetVariable','ActionScript')))
