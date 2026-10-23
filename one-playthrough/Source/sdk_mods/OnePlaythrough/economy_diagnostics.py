"""Bounded manual stock/pricing inspection; never generates or changes items."""

from collections import deque
from .requirements import describe as describe_use_bonus


MAX_DEFINITIONS = 600
MAX_INVENTORY = 300
MAX_VENDORS = 50
SKIP_FIELDS = {"Class", "Outer", "Name", "ObjectFlags", "InternalIndex"}
VENDOR_TERMS = ("inventory", "item", "stock", "pool", "balance", "stage", "level",
                "cost", "cash", "price", "markup", "definition", "region", "shop",
                "timer", "remaining", "disabled", "active")
INVENTORY_TERMS = ("cash", "level", "definition", "attribute", "quantity", "owner")
PLAYER_TERMS = ("exp", "level", "currency", "savegame")


def collect(sdk, pc, serialize, read):
    result = {"vendors": [], "inventory": [], "definitions": {}, "player": {}, "truncations": [],
              "use_level_bonuses": {}}
    pending = deque()
    queued = set()

    def truncated(label):
        if label not in result["truncations"]:
            result["truncations"].append(label)

    def queue(obj):
        # Follow data definitions/resolvers only. Never follow actor ownership,
        # controller/world references or class metadata into unrelated objects.
        cls = getattr(obj, "Class", None)
        if cls is None or not str(cls.Name).endswith(("Definition", "Resolver", "Table", "Curve", "Lookup")):
            return
        path = obj._path_name()
        if path in queued:
            return
        if len(queued) >= MAX_DEFINITIONS:
            truncated("definition limit")
            return
        queued.add(path)
        pending.append(obj)

    def value(obj):
        return serialize(obj, on_reference=queue)

    def fields(obj, terms=None, context=None):
        cls = getattr(obj, "Class", None) or getattr(obj, "_type", None)
        if cls is None or not hasattr(cls, "_properties"):
            return {}
        path = context or obj._path_name()
        properties = read(f"{path} properties", lambda: list(cls._properties()), [])
        output = {}
        for prop in properties:
            name = str(prop.Name)
            if name in SKIP_FIELDS or (terms is not None and not any(t in name.lower() for t in terms)):
                continue
            output[name] = read(f"{path}.{name}", lambda name=name: value(getattr(obj, name)))
        return output

    def objects(class_name):
        # find_all is read-only; do not load packages or reroll a machine.
        return read(f"find {class_name}", lambda: list(sdk.find_all(class_name, exact=False)), [])

    def live(obj):
        return "default__" not in obj._path_name().lower()

    for vendor in objects("WillowVendingMachine"):
        if not live(vendor):
            continue
        if len(result["vendors"]) >= MAX_VENDORS:
            truncated("vendor limit")
            break
        path = vendor._path_name()
        result["vendors"].append({"path": path, "fields": fields(vendor, VENDOR_TERMS)})

    for item in objects("WillowInventory"):
        if not live(item):
            continue
        if len(result["inventory"]) >= MAX_INVENTORY:
            truncated("inventory limit")
            break
        path = item._path_name()
        cls = getattr(item, "Class", None)
        record = {"path": path, "class": str(cls.Name) if cls is not None else None,
                  "fields": fields(item, INVENTORY_TERMS)}
        # These existing inventory queries are also used by the original
        # diagnostics/card mod. No item initialization or reward functions run.
        query = getattr(item, "GetInventoryDefinition", None)
        if callable(query):
            def inventory_definition():
                definition = query()
                if definition is not None:
                    name = definition._path_name()
                    if name not in result["use_level_bonuses"] and len(result["use_level_bonuses"]) < 40:
                        result["use_level_bonuses"][name] = read(f"{name} use bonus",
                            lambda: describe_use_bonus(definition))
                return value(definition)
            record["inventory_definition"] = read(f"{path} definition", inventory_definition)
        query = getattr(item, "GetControllerPlayerExpLevelRequiredToUse", None)
        if pc is not None and callable(query):
            record["native_required_level"] = read(f"{path} required level", lambda: query(pc))
        result["inventory"].append(record)

    # Include the tutorial Shield_Intro/Shield_Stock balance definitions even
    # when a failed generation left no runtime item pointing to them. Also read
    # the loaded native cash formulas; prices themselves are not changed.
    for class_name in ("InventoryBalanceDefinition", "ItemPoolDefinition", "WillowInventoryDefinition",
                       "InventoryAttributeDefinition", "AttributeInitializationDefinition", "AttributeDefinition"):
        for obj in objects(class_name):
            name = obj._path_name().lower()
            if "default__" not in name and (
                any(term in name for term in ("shield", "vending", "vendor", "healthvial", "healthpack"))
                or name.startswith(("gd_balance_inventory.", "gd_currency."))
            ):
                queue(obj)

    if pc is not None:
        for label, obj in (("controller", pc), ("pawn", getattr(pc, "Pawn", None)),
                           ("replication", getattr(pc, "PlayerReplicationInfo", None)),
                           ("profile", getattr(pc, "LastLoadedProfile", None))):
            if obj is not None:
                result["player"][label] = fields(obj, PLAYER_TERMS, f"player.{label}")

    while pending:
        obj = pending.popleft()
        path = obj._path_name()
        result["definitions"][path] = {"class": str(obj.Class.Name), "fields": fields(obj)}
    return result
