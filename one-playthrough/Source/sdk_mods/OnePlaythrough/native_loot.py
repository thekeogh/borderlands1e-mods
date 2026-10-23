"""Level-only floor at BL1E's captured native inventory initialization boundary.

Fresh pool/vendor inventory bypasses InitializeFromDefinitionData. Hook the
captured Engine.WillowInventory.InitializeInventory before native stat building;
never reinitialize an actor or reroll a pool. Definition-data reconstruction
(save loads, pickups and player-drop copies) is excluded by its enclosing scope.
"""

from copy import deepcopy

from .rewards import inherited
from .boss_trace import BossTrace

PATH = "Engine.WillowInventory:InitializeInventory"
REQUIRED = {"InBalanceDef", "InManufacturer", "InGradeIndex", "InAdditionalQueryInterfaceSource"}


def spec(sdk):
    for fn in sdk.find_class("WillowInventory")._fields():
        if str(fn.Class.Name) != "Function" or str(fn.Name) != "InitializeInventory":
            continue
        path = f"{fn.Outer._path_name()}:{fn.Name}"
        if path != PATH:
            continue
        inputs, has_return = [], False
        for prop in fn._properties():
            flags = int(prop.PropertyFlags)
            if not flags & 0x80:
                continue
            if flags & 0x400:
                has_return = True
            elif flags & 0x100:
                raise ValueError("Unsupported native inventory output parameter")
            else:
                inputs.append(str(prop.Name))
        if not REQUIRED <= set(inputs):
            raise ValueError("Native inventory initializer signature changed")
        return path, tuple(inputs), has_return
    raise ValueError("Captured native inventory initializer not found")


class NativeLoot:
    def __init__(self, runtime, loot):
        self.runtime, self.loot = runtime, loot
        self.definition_scopes = []
        self.signature = None
        self.calls = 0
        self.skipped = {}
        self.recent = []
        self.boss_trace = BossTrace(runtime)

    def enter_definition(self):
        token = object()
        self.definition_scopes.append(token)
        return token

    def exit_definition(self, token):
        self.definition_scopes[:] = [t for t in self.definition_scopes if t is not token]

    def owner_kind(self, obj, query, pc):
        """Read identity/Owner links only; do not execute inventory or actor methods."""
        pawn = getattr(pc, "Pawn", None)
        manager = getattr(pawn, "InvManager", None)
        kind = "world loot"
        for query_only, root in ((False, getattr(obj, "Owner", None)), (True, query)):
            seen = set()
            for _ in range(6):
                if root is None or id(root) in seen:
                    break
                seen.add(id(root))
                if root == pc or root == pawn or root == manager or self.loot.is_a(root, "WillowPlayerPawn"):
                    if query_only:
                        break  # Attribute query context is not item ownership.
                    return "player"
                if self.loot.is_a(root, "WillowAIPawn") or self.loot.is_a(root, "WillowVehicle"):
                    dying = any(address == root._get_address() for _, address in self.loot.deaths)
                    scope = self.loot.scopes[-1][1] if self.loot.scopes else None
                    confirmed_loot = (scope is not None and scope["kind"] == "enemy"
                                      and scope["source"] == root._path_name())
                    if not (dying or confirmed_loot):
                        return "live/neutral enemy"
                    kind = "enemy"
                elif self.loot.is_a(root, "WillowVendingMachine"):
                    kind = "vendor"
                elif self.loot.is_a(root, "WillowInteractiveObject"):
                    kind = "container"
                root = getattr(root, "Owner", None)
        return kind

    def plan(self, obj, args, pc):
        if not self.runtime.enabled or not self.loot.selected():
            return None
        self.calls += 1
        if self.definition_scopes:
            self.boss_trace.native(obj, args, "definition-data reconstruction")
            self.loot.count(self.skipped, "definition-data reconstruction")
            return None
        if self.runtime.missions.scopes:
            self.boss_trace.native(obj, args, "mission reward")
            self.loot.count(self.skipped, "mission reward")
            return None
        player = self.runtime.level(pc)
        if player is None:
            self.boss_trace.native(obj, args, "no player context")
            return None
        kind = self.owner_kind(obj, args.InAdditionalQueryInterfaceSource, pc)
        if kind in ("player", "live/neutral enemy"):
            self.boss_trace.native(obj, args, kind)
            self.loot.count(self.skipped, kind)
            return None
        original = getattr(obj, "DefinitionData", None)
        if original is None or args.InBalanceDef is None:
            self.boss_trace.native(obj, args, "no equipment definition data")
            self.loot.count(self.skipped, "no equipment definition data")
            return None
        original = deepcopy(original)  # Rollback must not retain a write-through native view.
        # Probe the original native inputs, including the actual chosen grade and
        # manufacturer. No parent balance or selected item part is changed.
        probe = deepcopy(original)
        probe.BalanceDefinition = args.InBalanceDef
        probe.ManufacturerDefinition = args.InManufacturer
        probe.ManufacturerGradeIndex = args.InGradeIndex
        field = "WeaponTypeDefinition" if hasattr(probe, "WeaponTypeDefinition") else "ItemDefinition"
        if getattr(probe, field, None) is None:
            definition = next((getattr(b, "InventoryDefinition", None) for b in inherited(args.InBalanceDef)
                               if getattr(b, "InventoryDefinition", None) is not None), None)
            if definition is None:
                self.boss_trace.native(obj, args, "definition not ready")
                self.loot.count(self.skipped, "definition not ready")
                return None
            setattr(probe, field, definition)
        scope = {"kind": kind, "source": obj._path_name(), "floor": self.loot.minimum(player, probe)}
        prepared = self.loot.prepare_data(probe, scope)
        if prepared is None:
            self.boss_trace.native(obj, args, "native level retained or unsupported")
            return None
        self.boss_trace.native(obj, args, "raise planned")
        # Persist only the selected level: all original UObject identities and
        # part fields remain exactly as native generation supplied them.
        encoded = deepcopy(original)
        encoded.ManufacturerGradeIndex = prepared.ManufacturerGradeIndex
        self.recent.append({**scope, "owner": self.path(getattr(obj, "Owner", None)),
                            "query": self.path(args.InAdditionalQueryInterfaceSource),
                            "balance": args.InBalanceDef._path_name(), "old_grade": args.InGradeIndex,
                            "packed_grade": encoded.ManufacturerGradeIndex})
        del self.recent[:-16]
        return original, encoded

    @staticmethod
    def path(value):
        return value._path_name() if value is not None else None

    def snapshot(self):
        return {"signature": self.signature, "calls": self.calls,
                "definition_scopes": len(self.definition_scopes),
                "skipped": dict(self.skipped), "recent": list(self.recent),
                "boss_trace": self.boss_trace.snapshot()}
