"""Read BL1/BL1E pricing definitions and reflected function signatures.

No Unreal properties are assigned, inventories created, or currency granted.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Any

import unrealsdk
from unrealsdk.unreal import UObject, WrappedStruct

MAX_OBJECTS = 2000
MAX_DEPTH = 16
MAX_ARRAY = 2048
MAX_INVENTORIES = 500
PACKAGES = ("gd_Balance_Inventory", "gd_currency", "d_attributes", "gd_globals")
ROOT_CLASSES = (
    "InventoryAttributeDefinition", "AttributeInitializationDefinition",
    "AttributeDefinition", "WillowInventoryDefinition", "ItemPartDefinition",
    "InventoryBalanceDefinition", "GlobalsDefinition", "MissionDefinition",
)
SCHEMA_CLASSES = (
    "WillowInventory", "WillowWeapon", "WillowItem", "WillowEquipAbleItem",
    "WillowUsableItem", "WillowVendingMachine", "VendingMachineGFxMovie",
    "WillowPlayerController", "WillowPlayerReplicationInfo",
    "WillowInventoryManager", "WillowGlobals", "MissionDefinition",
    "WillowInventoryDefinition", "ItemDefinition", "InventoryAttributeDefinition",
    "AttributeDefinition", "AttributeInitializationDefinition", "GlobalsDefinition",
    "WillowAIPawn", "WillowVehicle", "PopulationFactoryBalancedAIPawn",
    "PopulationFactoryWillowVehicle", "AIPawnBalanceDefinition", "PawnAllegiance",
)
FUNCTION_TERMS = (
    "cash", "cost", "price", "currency", "monetary", "reward", "respec",
    "initialize", "createitem", "createweapon", "clone", "grade", "level",
    "givento", "usedby", "useitem", "buy", "sell", "purchase",
    "value", "evaluate", "resolve", "calculate", "mission",
    "gamestage", "population", "restore", "enemy", "hostile",
)
SKIP_PROPERTIES = {"Class", "Outer", "Name", "ObjectFlags", "InternalIndex"}


class Exporter:
    def __init__(self) -> None:
        self.pending: deque[Any] = deque()
        self.queued: set[str] = set()
        self.objects: dict[str, Any] = {}
        self.errors: list[str] = []
        self.truncations: list[str] = []

    def error(self, context: str, exc: Exception) -> None:
        self.errors.append(f"{context}: {type(exc).__name__}: {exc}")

    def queue(self, obj: Any) -> None:
        path = obj._path_name()
        if path in self.queued:
            return
        # Follow data definitions and their resolvers, never actor/owner chains.
        if not str(obj.Class.Name).endswith(("Definition", "Resolver", "Table", "Curve", "Lookup")):
            return
        if len(self.queued) >= MAX_OBJECTS:
            if "object limit" not in self.truncations:
                self.truncations.append("object limit")
            return
        self.queued.add(path)
        self.pending.append(obj)

    def value(self, value: Any, depth: int = 0) -> Any:
        if isinstance(value, float) and not math.isfinite(value):
            return {"nonfinite": str(value)}
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, UObject):
            self.queue(value)
            return {"ref": value._path_name(), "class": str(value.Class.Name)}
        if depth >= MAX_DEPTH:
            self.truncations.append("nested value depth")
            return {"truncated": str(type(value).__name__)}
        if isinstance(value, WrappedStruct):
            return {"struct": value._type._path_name(), "fields": self.fields(value, value._type, depth + 1)}
        if isinstance(value, (tuple, list)) or type(value).__name__ == "WrappedArray":
            length = len(value)
            result = [self.value(value[i], depth + 1) for i in range(min(length, MAX_ARRAY))]
            if length > MAX_ARRAY:
                self.truncations.append(f"array length {length}")
                result.append({"omitted": length - MAX_ARRAY})
            return result
        return str(value)

    def fields(self, obj: Any, schema: Any, depth: int = 0) -> dict[str, Any]:
        result = {}
        for prop in schema._properties():
            name = str(prop.Name)
            if name in SKIP_PROPERTIES:
                continue
            try:
                result[name] = self.value(getattr(obj, name), depth)
            except Exception as exc:
                self.error(f"{schema._path_name()}.{name}", exc)
        return result

    def drain(self) -> None:
        while self.pending:
            obj = self.pending.popleft()
            path = obj._path_name()
            try:
                self.objects[path] = {"class": str(obj.Class.Name), "fields": self.fields(obj, obj.Class)}
            except Exception as exc:
                self.error(path, exc)

    def property_schema(self, prop: Any) -> dict[str, Any]:
        result = {"name": str(prop.Name), "type": str(prop.Class.Name)}
        for name in ("PropertyFlags", "ArrayDim"):
            result[name] = int(getattr(prop, name))
        for name in ("Struct", "PropertyClass", "Enum", "Inner"):
            try:
                target = getattr(prop, name)
            except AttributeError:
                continue
            if target is not None:
                result[name] = target._path_name()
                if name == "Inner":
                    result["inner_type"] = str(target.Class.Name)
        return result

    def class_schema(self, cls: Any) -> dict[str, Any]:
        properties = [self.property_schema(prop) for prop in cls._properties()]
        functions = {}
        for parent in cls._superfields():
            for field in parent._fields():
                if str(field.Class.Name) != "Function":
                    continue
                if not any(term in str(field.Name).lower() for term in FUNCTION_TERMS):
                    continue
                functions[field._path_name()] = {
                    "flags": int(field.FunctionFlags),
                    "fields": [self.property_schema(prop) for prop in field._properties()],
                }
        return {"properties": properties, "functions": functions}


def economic_root(path: str) -> bool:
    path = path.lower()
    return (
        path.startswith(("gd_balance_inventory.", "gd_currency.", "gd_globals."))
        or "cash" in path or "currency" in path or "cost_" in path
        or path.startswith("z0_missions.missions.")
    )


def collect(sdk: Any, pc: Any) -> dict[str, Any]:
    """Build an inert Python snapshot while all UObject access is synchronous."""
    export = Exporter()
    context = {}
    for label, getter in (
        ("playthrough_index", lambda: int(pc.GetCurrentPlaythrough())),
        ("character_level", lambda: int(pc.Pawn.GetExpLevel())),
        ("wallet", lambda: int(pc.PlayerReplicationInfo.CurrencyOnHand)),
        ("map", lambda: str(pc.WorldInfo.GetMapName())),
    ):
        try:
            context[label] = getter()
        except Exception as exc:
            export.error(label, exc)

    for package in PACKAGES:
        try:
            sdk.load_package(package)
        except Exception as exc:
            export.error(f"load {package}", exc)

    schemas = {}
    for name in SCHEMA_CLASSES:
        try:
            schemas[name] = export.class_schema(sdk.find_class(name))
        except Exception as exc:
            export.error(f"class {name}", exc)

    for name in ROOT_CLASSES:
        try:
            for obj in sdk.find_all(name, exact=False):
                if economic_root(obj._path_name()):
                    export.queue(obj)
        except Exception as exc:
            export.error(f"roots {name}", exc)

    inventory = []
    try:
        for item in sdk.find_all("WillowInventory", exact=False):
            path = item._path_name()
            if "default__" in path.lower():
                continue
            if len(inventory) >= MAX_INVENTORIES:
                export.truncations.append("runtime inventory limit")
                break
            record = {"path": path, "class": str(item.Class.Name)}
            for name in ("CashValue", "ExpLevel", "DefinitionData", "AttributeSlots", "Quantity"):
                try:
                    record[name] = export.value(getattr(item, name))
                except AttributeError:
                    pass
                except Exception as exc:
                    export.error(f"{path}.{name}", exc)
            try:
                record["inventory_definition"] = export.value(item.GetInventoryDefinition())
            except Exception as exc:
                export.error(f"{path}.GetInventoryDefinition", exc)
            inventory.append(record)
    except Exception as exc:
        export.error("runtime inventories", exc)

    vendors = []
    try:
        for vendor in sdk.find_all("WillowVendingMachine", exact=False):
            fields = {}
            for prop in vendor.Class._properties():
                name = str(prop.Name)
                if any(term in name.lower() for term in ("cash", "cost", "price", "markup", "inventory", "definition", "gamestage")):
                    try:
                        fields[name] = export.value(getattr(vendor, name))
                    except Exception as exc:
                        export.error(f"vendor.{name}", exc)
            vendors.append({"path": vendor._path_name(), "fields": fields})
    except Exception as exc:
        export.error("runtime vendors", exc)

    export.drain()
    return {
        "format_version": 1,
        "captured_utc": datetime.now(timezone.utc).isoformat(),
        "context": context,
        "class_schemas": schemas,
        "runtime_inventory": inventory,
        "runtime_vendors": vendors,
        "definitions": export.objects,
        "errors": export.errors,
        "truncations": sorted(set(export.truncations)),
    }


def write_snapshot(snapshot: dict[str, Any], directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    path = directory / f"pt3-economy-{stamp}.json"
    # Exclusive creation protects existing exports, even on timestamp collision.
    with path.open("x", encoding="utf-8") as stream:
        json.dump(snapshot, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    return path
