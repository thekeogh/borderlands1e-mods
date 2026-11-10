"""Bounded, manual inspection. No UI writes, definition edits or equip actions."""

from datetime import datetime, timezone
import json
from pathlib import Path

from mods_base import get_ordered_mod_list, get_pc
from unrealsdk import find_all, logging

from .levels import level_details


def reference(obj):
    return obj._path_name() if obj is not None else None


def bonus_data(bonus):
    return {"constant": float(bonus.BaseValueConstant),
            "scale": float(bonus.BaseValueScaleConstant),
            "attribute": reference(bonus.BaseValueAttribute),
            "initialization": reference(bonus.InitializationDefinition)}


def definition_data(weapon):
    definition = weapon.GetInventoryDefinition()
    bonus = definition.PlayerUseLevelBonus
    result = {"object": reference(definition), **bonus_data(bonus),
              "uses_player_level_requirement": bool(definition.bUsesPlayerLevelRequirement)}
    attribute = bonus.BaseValueAttribute
    if attribute is not None:
        result["context_class"] = reference(attribute.AttributeContextClass)
        result["simple"] = bool(attribute.bIsSimpleAttribute)
        result["contexts"] = [str(row.Class.Name) for row in attribute.ContextResolverChain][:8]
        result["resolvers"] = []
        for row in list(attribute.ValueResolverChain)[:8]:
            entry = {"class": str(row.Class.Name), "object": reference(row)}
            for name in ("Arg1Option", "Operand"):
                value = getattr(row, name, None)
                if value is not None:
                    entry[name] = int(value)
            for name in ("Arg1Attribute", "Argument", "ConstantValue"):
                value = getattr(row, name, None)
                if value is not None:
                    entry[name] = bonus_data(value) if hasattr(value, "BaseValueConstant") else str(value)
            result["resolvers"].append(entry)
    return result


def export(settings_dir, version, enabled, stats, errors, recent_cards, hooks):
    from . import CARD_PREFIXES, card_items

    pc = get_pc()
    if pc is None or pc.Pawn is None:
        logging.warning("[Consistent Weapon Levels] Load a character before exporting.")
        return None
    report = {"format_version": 3, "version": version, "enabled": enabled,
              "captured_utc": datetime.now(timezone.utc).isoformat(),
              "stats": dict(stats), "errors": list(errors), "export_errors": [],
              "recent_cards": recent_cards, "hooks": {}, "player": {},
              "weapons": [], "definitions": {}, "live_cards": [], "loaded_mods": [], "limits": []}

    def read(label, getter):
        try:
            return getter()
        except Exception as exc:
            if len(report["export_errors"]) < 40:
                report["export_errors"].append({"context": label,
                    "error": f"{type(exc).__name__}: {exc}"})
            return None

    report["hooks"] = {h.hook_identifier: read(h.hook_identifier, h.get_active_count) for h in hooks}
    for mod in list(read("loaded mods", get_ordered_mod_list) or [])[:100]:
        report["loaded_mods"].append(read("mod metadata", lambda: {
            "name": str(mod.name), "version": str(mod.version), "enabled": bool(mod.is_enabled)}))
    pawn = pc.Pawn
    current = getattr(pawn, "Weapon", None)
    report["player"] = {"level": read("player level", lambda: int(pawn.GetExpLevel())),
                        "current_weapon": reference(current)}
    equipped = set()
    item = getattr(getattr(pawn, "InvManager", None), "InventoryChain", None)
    while item is not None and len(equipped) < 100:
        path = reference(item)
        if path in equipped:
            break
        equipped.add(path)
        item = getattr(item, "Inventory", None)
    if current is not None:
        equipped.add(reference(current))
    report["player"]["equipped_inventory"] = sorted(equipped)
    for weapon in find_all("WillowWeapon"):
        if weapon.Owner != pawn:
            continue
        if len(report["weapons"]) >= 100:
            report["limits"].append("100 owned weapons")
            break
        path = reference(weapon)
        row = {"object": path, "equipped": path in equipped,
               "current_weapon": weapon == current, "internal_level": int(weapon.ExpLevel)}
        row["name"] = read(path + " name", lambda: weapon.GetShortHumanReadableName())
        row["native_level_with_controller"] = read(path + " native requirement",
            lambda: int(weapon.GetControllerPlayerExpLevelRequiredToUse(pc)))
        row.update(read(path + " ordinary requirement", lambda: level_details(weapon)) or
                   {"ordinary_required_level": None, "resolution": "error"})
        row["can_be_used_by_player"] = read(path + " usability", lambda: bool(weapon.CanBeUsedBy(pawn)))
        # This native check returns its boolean plus the output required level.
        # Recording both lets a new export distinguish display errors from locks.
        row["native_level_requirement_check"] = read(path + " level check",
            lambda: weapon.IsLevelRequirementMet(pc))
        definition = read(path + " definition", lambda: weapon.GetInventoryDefinition())
        if definition is not None:
            key = reference(definition)
            row["definition"] = key
            if key not in report["definitions"]:
                report["definitions"][key] = read(key, lambda: definition_data(weapon))
        report["weapons"].append(row)
    # Inspect live cards without rebuilding them. The history remains useful if
    # opening the Mods menu has already hidden or destroyed the inventory movie.
    for kind, prefixes in CARD_PREFIXES.items():
        movies = read("find " + kind, lambda: list(find_all(kind))) or []
        for movie in movies[:4]:
            if "default__" in reference(movie).lower():
                continue
            cards = {path: reference(item) for path, item in
                     (read(reference(movie) + " card items", lambda: card_items(movie)) or [])}
            for prefix in prefixes:
                field = prefix + ".requirement.requirement"
                report["live_cards"].append({"movie": reference(movie), "card": prefix,
                    "weapon": cards.get(prefix),
                    "field_name": read(field, lambda: movie.GetVariableString(field + "._name")),
                    "text": read(field, lambda: movie.GetVariableString(field + ".text"))})
    directory = Path(settings_dir) / "ConsistentWeaponLevels"
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    path = directory / f"weapon-levels-{stamp}.json"
    path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return path
