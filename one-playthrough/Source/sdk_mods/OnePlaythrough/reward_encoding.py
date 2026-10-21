"""Preserve native item levels when reward previews are copied or saved.

Non-interpolated BL1 definition data packs an explicit internal level in the
upper 16 bits of ManufacturerGradeIndex; the original grade stays in the low
16 bits. A captured BL1E item uses 0x00460005 for internal level 70 / grade 5.
WillowTree's native save LevelIndex is the corresponding explicit-level field.
"""

from copy import deepcopy

from .rewards import internal_level


def pack_level(index, level):
    if not 1 <= level <= 0x7FFF:
        raise ValueError("Reward internal level does not fit the native signed grade field")
    return (int(level) << 16) | (int(index) & 0xFFFF)


def initializer_specs(sdk):
    """Find actual loaded initializer functions and input struct names.

    Reflect instead of assuming BL2 parameter names or registering a guessed
    native signature. No actor methods or item generation run during discovery.
    """
    found = {}
    for name in ("WillowWeapon", "WillowItem", "WillowInventory"):
        try:
            cls = sdk.find_class(name)
        except ValueError:
            continue
        for function in cls._fields():
            if str(function.Class.Name) != "Function" or not str(function.Name).startswith("Initialize"):
                continue
            parameters, inputs = [], []
            has_return, unsupported = False, False
            for prop in function._properties():
                flags = int(prop.PropertyFlags)
                if not flags & 0x80:
                    continue
                if flags & 0x400:
                    has_return = True
                    continue
                if flags & 0x100:
                    unsupported = True  # Do not lose native output parameters.
                inputs.append(str(prop.Name))
                if str(prop.Class.Name) != "StructProperty":
                    continue
                fields = {str(field.Name) for field in prop.Struct._properties()}
                if {"BalanceDefinition", "ManufacturerGradeIndex"} <= fields:
                    parameters.append(str(prop.Name))
            if parameters and not unsupported:
                path = f"{function.Outer._path_name()}:{function.Name}"
                found[path] = (tuple(parameters), tuple(inputs), has_return)
    return [(path, *spec) for path, spec in sorted(found.items())]


def prepare_definition_data(runtime, args, parameter):
    """Encode a mission reward input BEFORE native stats/ownership initialization."""
    if not runtime.enabled:
        return
    data = getattr(args, parameter)
    balance = data.BalanceDefinition
    if balance is None:
        return
    level = runtime.missions.item_reward_level(balance)
    if level is None:
        return  # World loot, vendors and save loads outside reward generation.
    if getattr(balance, "bInterpolateExpLevel", False):
        return  # This native format already stores the level, not a grade index.
    definition = getattr(data, "WeaponTypeDefinition", None) or getattr(data, "ItemDefinition", None)
    if definition is None or getattr(definition, "bUsesPlayerLevelRequirement", True) is False:
        return
    internal = internal_level(definition, level)
    packed = pack_level(data.ManufacturerGradeIndex, internal)
    if packed == data.ManufacturerGradeIndex:
        return
    # Copy the input struct; never reinitialize an existing item, edit a shared
    # balance, or write to an arbitrary caller's original definition-data object.
    copied = deepcopy(data)
    copied.ManufacturerGradeIndex = packed
    stats = runtime.missions.item_encoding
    stats["encoded"] += 1
    stats["recent"].append({"balance": balance._path_name(), "mission_level": level,
                            "internal_level": internal, "old_grade": data.ManufacturerGradeIndex,
                            "packed_grade": packed})
    del stats["recent"][:-12]
    return copied
