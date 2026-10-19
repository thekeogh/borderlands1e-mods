"""Reversible reflected data edits; no actor methods or attribute reinitialization."""

KEEP_ALIVE = 0x4000


def resolve(root, path):
    for part in path:
        root = root[part] if isinstance(part, int) else getattr(root, part)
    return root


class Patches:
    def __init__(self):
        self.fields = {}
        self.pins = {}

    def pin(self, obj):
        if obj is None or not hasattr(obj, "ObjectFlags"):
            return
        key = obj._get_address()
        if key not in self.pins:
            self.pins[key] = (obj, bool(obj.ObjectFlags & KEEP_ALIVE))
            obj.ObjectFlags |= KEEP_ALIVE

    def set(self, root, path, value):
        path = tuple(path)
        parent = resolve(root, path[:-1])
        name = path[-1]
        old = getattr(parent, name)
        key = (root._get_address(), path)
        if old == value:
            return
        if key not in self.fields:
            self.pin(root)
            self.pin(old)
            self.fields[key] = [root, path, old, value]
        else:
            self.fields[key][3] = value
        setattr(parent, name, value)

    def stage(self, root, path, level):
        for name, value in (("BaseValueConstant", float(level)), ("BaseValueAttribute", None),
                            ("InitializationDefinition", None), ("BaseValueScaleConstant", 1.0)):
            self.set(root, (*path, name), value)

    def restore(self):
        errors = []
        for root, path, original, ours in reversed(list(self.fields.values())):
            try:
                parent = resolve(root, path[:-1])
                if getattr(parent, path[-1]) == ours:
                    setattr(parent, path[-1], original)
            except Exception as exc:
                errors.append(repr(exc))
        self.fields.clear()
        for obj, was_pinned in self.pins.values():
            try:
                if not was_pinned:
                    obj.ObjectFlags &= ~KEEP_ALIVE
            except Exception as exc:
                errors.append(repr(exc))
        self.pins.clear()
        return errors
