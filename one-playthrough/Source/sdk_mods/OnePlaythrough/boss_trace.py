"""Temporary Bone Head/Bone Shredder diagnostics. Property reads only.

Do not change gear, invoke actor methods, replay drops or retain actor references.
Capture the original carried gun and ownership transitions before pickup copies
obscure the path. Keep these observations bounded and only export them via F10.
"""

from itertools import islice

TARGET = "gd_customweapons.weapons.customweap_smg_boneshredder"
PARTS = ("WeaponTypeDefinition", "BalanceDefinition", "ManufacturerDefinition", "ManufacturerGradeIndex",
         "BodyPartDefinition", "GripPartDefinition", "MagazinePartDefinition", "BarrelPartDefinition",
         "SightPartDefinition", "StockPartDefinition", "ActionPartDefinition", "AccessoryPartDefinition",
         "MaterialPartDefinition", "PrefixPartDefinition", "TitlePartDefinition")


def path(value):
    return value._path_name() if value is not None else None


def scalar(value):
    return value if value is None or isinstance(value, (bool, int, float, str)) else path(value)


def export_records(value):
    # F10 limits deeply nested reflected arrays. These records already contain
    # bounded primitives only; indexed maps preserve their ownership/parts data.
    if isinstance(value, list):
        return {str(index): export_records(row) for index, row in enumerate(value)}
    if isinstance(value, dict):
        return {key: export_records(row) for key, row in value.items()}
    return value


class BossTrace:
    def __init__(self, runtime):
        self.runtime = runtime
        self.decisions = []
        self.drops = []
        self.deaths = []
        self.targets = set()

    def active(self):
        return self.runtime.enabled and self.runtime.loot.selected()

    @staticmethod
    def is_target(data):
        balance = getattr(data, "BalanceDefinition", None)
        return balance is not None and balance._path_name().lower() == TARGET

    def item(self, obj):
        data = getattr(obj, "DefinitionData", None)
        owners, owner = [], getattr(obj, "Owner", None)
        seen = set()
        for _ in range(6):
            if owner is None:
                break
            name = path(owner)
            if name in seen:
                break
            seen.add(name)
            state = getattr(owner, "BalanceDefinitionState", None)
            owners.append({"path": name,
                           "balance": path(getattr(state, "BalanceDefinition", None))})
            owner = getattr(owner, "Owner", None)
        return {"object": path(obj), "owner_chain": owners,
                "internal_level": getattr(obj, "ExpLevel", None),
                "definition_data": {key: scalar(getattr(data, key, None)) for key in PARTS}}

    def native(self, obj, args, decision):
        if not self.active():
            return
        try:
            balance = getattr(args, "InBalanceDef", None)
            if balance is None or balance._path_name().lower() != TARGET:
                return
            self.decisions.append({"decision": decision, "item": self.item(obj),
                "balance": path(balance), "grade": args.InGradeIndex,
                "query": path(args.InAdditionalQueryInterfaceSource),
                "query_balance": path(getattr(getattr(args.InAdditionalQueryInterfaceSource,
                                                       "BalanceDefinitionState", None), "BalanceDefinition", None)),
                "definition_scopes": len(self.runtime.loot.native.definition_scopes),
                "reward_scopes": len(self.runtime.missions.scopes),
                "player_level": self.runtime.regions.level})
            del self.decisions[:-24]
        except Exception as exc:
            self.runtime.problem("Bone Shredder native trace", exc)

    def drop(self, obj, phase):
        if not self.active():
            return
        try:
            if not self.is_target(getattr(obj, "DefinitionData", None)):
                return
            self.drops.append({"phase": phase, "player_level": self.runtime.regions.level,
                               "item": self.item(obj)})
            del self.drops[:-16]
        except Exception as exc:
            self.runtime.problem("Bone Shredder drop trace", exc)

    def death(self, actor, phase):
        if not self.active():
            return
        try:
            state = getattr(actor, "BalanceDefinitionState", None)
            balance = path(getattr(state, "BalanceDefinition", None)) or ""
            name = path(actor)
            if "bonehead" not in balance.lower() and name not in self.targets:
                return
            if len(self.targets) < 4:
                self.targets.add(name)
            items, seen = [], set()
            def add(obj):
                if obj is None or not self.is_target(getattr(obj, "DefinitionData", None)):
                    return
                key = path(obj)
                if key not in seen and len(items) < 16:
                    seen.add(key)
                    items.append(self.item(obj))
            add(getattr(actor, "Weapon", None))
            manager = getattr(actor, "InvManager", None)
            node = getattr(manager, "InventoryChain", None)
            chain_seen = set()
            for _ in range(48):
                if node is None or path(node) in chain_seen:
                    break
                chain_seen.add(path(node))
                add(node)
                node = getattr(node, "Inventory", None)
            # Scan only at Bone Head's death, not every ordinary enemy kill.
            # Include detached guns to correlate the same actor before/after drop.
            for obj in islice(self.runtime.sdk.find_all("WillowInventory"), 1024):
                add(obj)
            self.deaths.append({"phase": phase, "actor": name, "balance": balance,
                "player_level": self.runtime.regions.level,
                "weapon": path(getattr(actor, "Weapon", None)),
                "inventory_manager": path(manager), "bone_shredders": items})
            del self.deaths[:-8]
        except Exception as exc:
            self.runtime.problem("Bone Head death trace", exc)

    def snapshot(self):
        return {"target": TARGET, "native_decisions": export_records(self.decisions),
                "drops": export_records(self.drops), "deaths": export_records(self.deaths)}
