"""Bounded, read-only observations to diagnose BL1E loot-generation coverage.

No native functions are called, replayed or blocked by these probes. Keep native
metadata and scalar/path samples only; do not retain live actor references.
"""

import re

MAX_HOOKS = 80
MAX_SAMPLES = 64
ACTORS = {"WillowInteractiveObject", "WillowInventory", "WillowItem", "WillowWeapon", "WillowEquipAbleItem"}


def specs(sdk, excluded):
    found = {}
    classes = [cls for cls in sdk.find_all("Class")
               if str(cls.Name) in ACTORS or re.search(r"loot|itempool", str(cls.Name), re.I)]
    classes.sort(key=lambda cls: (str(cls.Name) not in ACTORS, str(cls.Name)))
    for cls in classes:
        for fn in cls._fields():
            if str(fn.Class.Name) != "Function":
                continue
            name = str(fn.Name)
            if not re.search(r"loot|inventory|spawn|generate|apply|initializ|oncreate|dropfrom|usedby|open", name, re.I):
                continue
            owner = str(fn.Outer.Name)
            if owner not in ACTORS and not re.search(r"loot|itempool", owner, re.I):
                continue  # Never hook generic inherited Engine.Actor:Spawn, etc.
            path = f"{fn.Outer._path_name()}:{name}"
            if path in excluded:
                continue
            inputs = tuple(str(p.Name) for p in fn._properties()
                           if int(p.PropertyFlags) & 0x80 and not int(p.PropertyFlags) & 0x400)
            found[path] = inputs
            if len(found) >= MAX_HOOKS:
                return sorted(found.items())
    return sorted(found.items())


def simple(value):
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:240]
    if hasattr(value, "_path_name"):
        return value._path_name()
    if hasattr(value, "BalanceDefinition") and hasattr(value, "ManufacturerGradeIndex"):
        return {"balance": simple(value.BalanceDefinition), "grade": value.ManufacturerGradeIndex}
    return type(value).__name__


class LootTrace:
    def __init__(self, runtime):
        self.runtime = runtime
        self.hooks = []
        self.events = {}
        self.initializer_calls = 0
        self.scoped_initializer_calls = 0
        self.equipment_initializers = 0
        self.equipment_samples = []
        self.initializer_signatures = []

    def active(self):
        return self.runtime.enabled and self.runtime.loot.selected()

    def event(self, path, obj, args, inputs):
        if not self.active():
            return
        try:
            kind = str(obj.Class.Name) if obj is not None else "static"
            source = getattr(args, "ContextSource", None)
            definition = getattr(obj, "InteractiveObjectDefinition", None) if obj is not None else None
            if definition is None and source is not None:
                definition = getattr(source, "InteractiveObjectDefinition", None)
            category = simple(definition) or (str(source.Class.Name) if source is not None else "")
            key = path + "|" + kind + "|" + category
            if key in self.events:
                self.events[key]["count"] += 1
                return
            if len(self.events) >= MAX_SAMPLES:
                return
            self.events[key] = {"function": path, "count": 1, "object": simple(obj),
                                "class": kind, "interactive_definition": simple(definition),
                                "arguments": {name: simple(getattr(args, name)) for name in inputs[:10]}}
        except Exception as exc:
            self.runtime.problem("loot trace", exc)

    def initializer(self, obj, args, parameters, inputs):
        if not self.active():
            return
        try:
            self.initializer_calls += 1
            loot = self.runtime.loot
            scope = loot.scopes[-1][1] if loot.scopes else None
            if scope is not None:
                self.scoped_initializer_calls += 1
            for name in parameters:
                data = getattr(args, name)
                definition = getattr(data, "WeaponTypeDefinition", None) or getattr(data, "ItemDefinition", None)
                if definition is None or not getattr(definition, "bUsesPlayerLevelRequirement", False):
                    continue
                self.equipment_initializers += 1
                self.equipment_samples.append({"object": simple(obj),
                    "balance": simple(getattr(data, "BalanceDefinition", None)),
                    "definition": simple(definition), "grade": data.ManufacturerGradeIndex,
                    "loot_scope": dict(scope) if scope is not None else None,
                    "reward_scopes": len(self.runtime.missions.scopes),
                    "arguments": {key: simple(getattr(args, key)) for key in inputs if key not in parameters}})
                del self.equipment_samples[:-16]
        except Exception as exc:
            self.runtime.problem("loot initializer trace", exc)

    def snapshot(self):
        chests = []
        try:
            for obj in self.runtime.sdk.find_all("WillowInteractiveObject"):
                definition = getattr(obj, "InteractiveObjectDefinition", None)
                if definition is None or not re.search(r"chest|crate_metal", definition._path_name(), re.I):
                    continue
                chests.append({"object": obj._path_name(), "definition": definition._path_name(),
                               "class": str(obj.Class.Name), "usable": getattr(obj, "bCanBeUsed", None)})
                if len(chests) >= 24:
                    break
        except Exception as exc:
            self.runtime.problem("loot chest trace", exc)
        return {"hooks": list(self.hooks), "events": list(self.events.values()),
                "initializer_signatures": list(self.initializer_signatures),
                "initializer_calls": self.initializer_calls,
                "scoped_initializer_calls": self.scoped_initializer_calls,
                "equipment_initializers": self.equipment_initializers,
                "equipment_samples": list(self.equipment_samples), "chests": chests}
