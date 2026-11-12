"""Manual, read-only economy inspection. No background transaction history."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Any

from .economy import FORMULA_INPUTS

MAX_INVENTORY = 400
MAX_VENDORS = 40
MAX_DEFINITIONS = 240
MAX_ARRAY = 256
MAX_DEPTH = 14
MAX_NODES = 40000
MONEY_FIELDS = {
    "ValueFormula", "BaseValueMode", "RoundingMode", "ConditionalInitialization",
    "RandomVariance", "RangeRestriction", "CashValue", "BaseCashValueModifier",
    "CashValueModifier", "AttributeSlotBaseGrade", "AttributeSlotEffectMode",
    "AttributeSlotEffects", "AttributeSlotUpgrades", "ExternalAttributeEffects",
    "Attribute", "AttributeDataType", "AttributeContextClass", "ValueResolverChain",
    "ContextResolverChain", "ConstantValue", "InventoryPartList", "ObjectArchetype",
}


def wallet(pc: Any) -> int | None:
    try:
        return int(pc.PlayerReplicationInfo.CurrencyOnHand)
    except Exception:
        return None


class Reader:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.truncations: set[str] = set()
        self.pending: deque[Any] = deque()
        self.queued: set[str] = set()
        self.definitions: dict[str, Any] = {}
        self.nodes = 0

    def read(self, context: str, getter: Any, default: Any = None) -> Any:
        try:
            return getter()
        except Exception as exc:
            message = f"{context}: {type(exc).__name__}: {exc}"
            if len(self.errors) < 60:
                self.errors.append(message)
            return default

    def queue(self, obj: Any) -> None:
        if obj is None or not str(obj.Class.Name).endswith(("Definition", "Resolver", "Table", "Curve")):
            return
        path = obj._path_name()
        if path in self.queued:
            return
        if len(self.queued) >= MAX_DEFINITIONS:
            self.truncations.add("definition limit")
            return
        self.queued.add(path)
        self.pending.append(obj)

    def value(self, value: Any, depth: int = 0) -> Any:
        self.nodes += 1
        if self.nodes > MAX_NODES:
            self.truncations.add("node limit")
            return {"truncated": "node limit"}
        if isinstance(value, float) and not math.isfinite(value):
            return {"nonfinite": str(value)}
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if hasattr(value, "_path_name") and hasattr(value, "Class"):
            self.queue(value)
            return {"ref": value._path_name(), "class": str(value.Class.Name)}
        if depth >= MAX_DEPTH:
            self.truncations.add("depth limit")
            return {"truncated": "depth limit"}
        if isinstance(value, dict):
            return {str(k): self.value(v, depth + 1) for k, v in value.items()}
        schema = getattr(value, "_type", None)
        if schema is not None and hasattr(schema, "_properties"):
            return {"struct": schema._path_name(), "fields": {
                str(prop.Name): self.read(str(prop.Name), lambda prop=prop:
                                         self.value(getattr(value, str(prop.Name)), depth + 1))
                for prop in schema._properties()}}
        if isinstance(value, (list, tuple)) or type(value).__name__ == "WrappedArray":
            result = [self.value(value[i], depth + 1) for i in range(min(len(value), MAX_ARRAY))]
            if len(value) > MAX_ARRAY:
                self.truncations.add("array limit")
                result.append({"omitted": len(value) - MAX_ARRAY})
            return result
        return str(value)

    def fields(self, obj: Any, names: Any) -> dict[str, Any]:
        return {name: self.read(f"{obj._path_name()}.{name}", lambda name=name: self.value(getattr(obj, name)))
                for name in names}

    def drain(self) -> None:
        while self.pending:
            obj = self.pending.popleft()
            path = obj._path_name()
            properties = self.read(path + " properties", lambda: list(obj.Class._properties()), [])
            names = [str(prop.Name) for prop in properties if str(prop.Name) in MONEY_FIELDS]
            self.definitions[path] = {"class": str(obj.Class.Name), "fields": self.fields(obj, names)}


def collect(sdk: Any, pc: Any, economy: Any, *, version: str,
            mods: list[Any], hooks: list[Any], game: str) -> dict[str, Any]:
    reader = Reader()
    # Capture the policy before following bounded item graphs.
    # No packages are loaded and no native item/price/reward functions are called.
    result = {
        "format_version": 1, "captured_utc": datetime.now(timezone.utc).isoformat(),
        "mod": {"name": "Economy Buster", "version": version, "author": "keogh"},
        "game": game, "sdk_version": getattr(sdk, "__version__", "unknown"),
        "economy": reader.value(economy.snapshot()),
        "context": {"character_loaded": pc is not None and getattr(pc, "Pawn", None) is not None,
                    "wallet": wallet(pc)},
        "loaded_mods": [], "hooks": [], "runtime_inventory": [], "runtime_vendors": [],
    }
    if pc is not None:
        for name, getter in (("character_level", lambda: int(pc.Pawn.GetExpLevel())),
                             ("playthrough_index", lambda: int(pc.GetCurrentPlaythrough())),
                             ("map", lambda: str(pc.WorldInfo.GetMapName()))):
            result["context"][name] = reader.read(name, getter)
    for mod in mods:
        result["loaded_mods"].append(reader.read("loaded mod", lambda mod=mod: {
            "name": mod.name, "version": mod.version, "author": mod.author, "enabled": mod.is_enabled}))
    for callback in hooks:
        result["hooks"].append(reader.read("hook status", lambda callback=callback: {
            "identifier": callback.hook_identifier, "active_count": callback.get_active_count()}))
    for path, _name, _expected in FORMULA_INPUTS:
        obj = reader.read(path, lambda path=path: sdk.find_object("AttributeInitializationDefinition", path))
        reader.queue(obj)
    for class_name, target, limit in (("WillowInventory", "runtime_inventory", MAX_INVENTORY),
                                      ("WillowVendingMachine", "runtime_vendors", MAX_VENDORS)):
        objects = reader.read(class_name, lambda: sdk.find_all(class_name, exact=False), [])
        for obj in objects:
            if not reader.read("live object", lambda: economy.live(obj), False):
                continue
            if len(result[target]) >= limit:
                reader.truncations.add(target + " limit")
                break
            names = ("CashValue", "ExpLevel", "Quantity", "DefinitionData", "Owner")
            if target == "runtime_vendors":
                properties = reader.read("vendor properties", lambda: list(obj.Class._properties()), [])
                names = [str(prop.Name) for prop in properties if any(term in str(prop.Name).lower()
                         for term in ("cash", "cost", "price", "markup", "inventory", "definition", "gamestage"))]
            else:
                names = [name for name in names if hasattr(obj, name)]
                if reader.read("currency classification", lambda: economy.is_currency(obj), False):
                    if hasattr(obj, "AttributeSlots"):
                        names.append("AttributeSlots")
            result[target].append({"path": obj._path_name(), "class": str(obj.Class.Name),
                                   "fields": reader.fields(obj, names)})
    reader.drain()
    result.update(definitions=reader.definitions, errors=reader.errors,
                  truncations=sorted(reader.truncations))
    return result


def write_snapshot(snapshot: dict[str, Any], directory: Path) -> Path:
    # Serialize first, so invalid reports cannot leave an incomplete JSON file.
    data = json.dumps(snapshot, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    path = directory / f"economy-buster-{stamp}.json"
    with path.open("x", encoding="utf-8") as stream:
        stream.write(data)
    return path
