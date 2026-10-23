"""Floor freshly generated chest/death loot without rerolling any pool.

Pool hooks only delimit native generation. They never change the pool, stage,
AwesomeLevel, probabilities or RNG. The existing item initializer encodes a floor
in the selected equipment's definition data before its native stats are built.
Unknown contexts/formats are left native and summarized by manual diagnostics.
"""

from copy import deepcopy

from .rewards import inherited, internal_level
from .reward_encoding import pack_level
from .spawns import hostile
from .loot_trace import LootTrace
from .native_loot import NativeLoot
from .carried_loot import CarriedLoot

POOL_FUNCTIONS = {"SpawnBalancedInventoryFromPool", "SpawnBalancedInventoryFromInventoryBalanceDefinition"}
CONTEXT_NAMES = {"contextsource", "contextsourceobject", "contextobject", "incontextsource", "context"}
CHESTS = ("interactiveobj_treasurechest", "interactiveobj_crate_metal", "interactiveobj_crimson_chest")


def pool_specs(sdk):
    """Read loaded native signatures; never guess argument positions or invoke RNG."""
    cls = sdk.find_class("ItemPool")
    result = []
    for function in cls._fields():
        if str(function.Class.Name) != "Function" or str(function.Name) not in POOL_FUNCTIONS:
            continue
        inputs = [p for p in function._properties()
                  if int(p.PropertyFlags) & 0x80 and not int(p.PropertyFlags) & 0x400]
        contexts = [str(p.Name) for p in inputs if str(p.Name).lower() in CONTEXT_NAMES
                    and str(p.Class.Name) in ("ObjectProperty", "InterfaceProperty")]
        result.append((f"{function.Outer._path_name()}:{function.Name}",
                       contexts[0] if len(contexts) == 1 else None,
                       tuple(str(p.Name) for p in inputs)))
    return sorted(result)


class Loot:
    @staticmethod
    def minimum(player, _data=None):
        return max(1, player - 2)

    def __init__(self, runtime):
        self.runtime = runtime
        self.selected = lambda: True
        self.scopes = []
        self.deaths = []
        self.classes = {}
        self.hooks = []
        self.seen = self.raised = 0
        self.skipped = {}
        self.contexts = {}
        self.recent = []
        self.trace = LootTrace(runtime)
        self.native = NativeLoot(runtime, self)
        self.carried = CarriedLoot(runtime, self)

    def count(self, table, key):
        if key in table or len(table) < 24:
            table[key] = table.get(key, 0) + 1

    def is_a(self, obj, name):
        if obj is None:
            return False
        if name not in self.classes:
            try:
                self.classes[name] = self.runtime.sdk.find_class(name)
            except ValueError:
                self.classes[name] = None
        cls = self.classes[name]
        return cls is not None and obj.Class._inherits(cls)

    def enemy(self, obj):
        if not (self.is_a(obj, "WillowAIPawn") or self.is_a(obj, "WillowVehicle")):
            return False
        state = getattr(obj, "BalanceDefinitionState", None)
        definition = getattr(state, "BalanceDefinition", None)
        return hostile(obj, definition, obj)

    def dying(self, source):
        # Read-only scope: never rewrite a live enemy's carried weapon/stats.
        token = object()
        self.deaths.append((token, source._get_address() if self.enemy(source) else None))
        return token

    def end_death(self, token):
        self.deaths[:] = [row for row in self.deaths if row[0] is not token]

    def source_kind(self, source):
        if self.is_a(source, "WillowInteractiveObject"):
            definition = getattr(source, "InteractiveObjectDefinition", None)
            name = definition._path_name().lower() if definition is not None else ""
            return "chest" if any(chest in name for chest in CHESTS) else None
        if self.enemy(source):
            if any(address == source._get_address() for _, address in self.deaths):
                return "enemy"
            # Some native death loot is deferred until after Died returns.
            health = getattr(source, "GetHealth", None)
            if callable(health) and health() <= 0:
                return "enemy"
        return None

    def enter(self, source, pc):
        token, scope = object(), None
        try:
            if self.runtime.enabled and self.selected() and not self.runtime.missions.scopes:
                kind = self.source_kind(source) if source is not None else None
                label = kind or (str(source.Class.Name) if source is not None else "no context")
                self.count(self.contexts, label)
                if kind is not None:
                    player = self.runtime.level(pc)
                    if player is not None:
                        scope = {"kind": kind, "source": source._path_name(), "floor": max(1, player - 2),
                                 "player_level": player}
        except Exception as exc:
            self.runtime.problem("loot context", exc)
        # Even a vendor/unknown nested call shadows an outer loot scope.
        self.scopes.append((token, scope))
        return token

    def exit(self, token):
        self.scopes[:] = [row for row in self.scopes if row[0] is not token]

    def skip(self, reason):
        self.count(self.skipped, reason)
        return None

    def prepare(self, data):
        if (not self.runtime.enabled or not self.selected() or not self.scopes
                or self.runtime.missions.scopes):
            return None
        scope = self.scopes[-1][1]
        if scope is None:
            return None
        return self.prepare_data(data, {**scope, "floor": self.minimum(scope["player_level"], data)})

    def prepare_data(self, data, scope):
        """Select only a higher explicit level; caller supplies a verified scope."""
        balance = getattr(data, "BalanceDefinition", None)
        definition = getattr(data, "WeaponTypeDefinition", None) or getattr(data, "ItemDefinition", None)
        if (balance is None or definition is None
                or not getattr(definition, "bUsesPlayerLevelRequirement", False)
                or getattr(definition, "bMissionItem", False)
                or getattr(definition, "bPlayerUseItemOnPickup", False)):
            return None
        chain = inherited(balance)
        if any("storagedeckupgrade" in item._path_name().lower()
               or "itemgrade_sdu_" in item._path_name().lower() for item in chain):
            return None
        self.seen += 1
        if getattr(balance, "bInterpolateExpLevel", False):
            return self.skip("interpolated format")
        index = int(data.ManufacturerGradeIndex)
        current = (index >> 16) & 0xFFFF
        if not current:
            source = next((item for item in chain if getattr(item, "Manufacturers", ())), None)
            manufacturer = getattr(data, "ManufacturerDefinition", None)
            row = next((row for row in source.Manufacturers if row.Manufacturer == manufacturer), None) if source else None
            grade = index & 0xFFFF
            if row is None or grade >= len(row.Grades):
                return self.skip("unknown manufacturer grade")
            current = int(row.Grades[grade].GradeModifiers.ExpLevel)
            if current <= 0:
                return self.skip("dynamic native item level")
        target = internal_level(definition, scope["floor"])
        if current >= target:
            return None  # Never lower a native item, including above-player drops.
        copied = deepcopy(data)
        copied.ManufacturerGradeIndex = pack_level(index, target)
        self.raised += 1
        self.recent.append({**scope, "balance": balance._path_name(), "native_internal_level": current,
                            "target_internal_level": target, "packed_grade": copied.ManufacturerGradeIndex})
        del self.recent[:-12]
        return copied

    def clear(self):
        self.scopes.clear()
        self.deaths.clear()

    def snapshot(self):
        return {"enabled": self.selected(), "minimum": "max(1, player level - 2) for all equipment",
                "pool_hooks": self.hooks, "active_scopes": len(self.scopes),
                "death_scopes": len(self.deaths), "equipment_seen": self.seen,
                "raised": self.raised, "contexts": dict(self.contexts),
                "skipped": dict(self.skipped), "recent": list(self.recent),
                "native_initializer": self.native.snapshot(),
                "carried_death_loot": self.carried.snapshot(),
                "trace": self.trace.snapshot()}
