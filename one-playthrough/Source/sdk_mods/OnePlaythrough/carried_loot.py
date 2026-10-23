"""Floor NPC-carried death loot using a fresh copy of its exact definition data.

Prepare only inside a confirmed hostile Died scope. Let the original DropFrom
finish and detach normally. Initialize a new actor once, preserving every selected
part/name/rarity, then drop it with the original native physics arguments. Retire
the original pickup only at Died POST, after its native inventory iteration ends.
Failure before retirement leaves the original pickup intact and cleans the copy.
"""

from copy import deepcopy
from itertools import islice

from unrealsdk.hooks import prevent_hooking_direct_calls

from .rewards import inherited, internal_level
from .reward_encoding import pack_level

KNOWN_INPUTS = {"NewDefinitionData", "InAdditionalQueryInterfaceSource", "bForceSelectNameParts"}
COPY_FIELDS = ("AwesomeLevel", "Quantity", "OwnerStatsID", "MinRarityLevel", "MaxRarityLevel")
RETIRE_LIFESPAN = 0.01


class CarriedLoot:
    def __init__(self, runtime, loot):
        self.runtime, self.loot = runtime, loot
        self.initializers = {}
        self.pending = {}
        self.prepared = self.changed = 0
        self.skipped = {}
        self.recent = []
        self.retirements = []

    def configure(self, specs):
        for path, data, inputs, _returns in specs:
            if (data != ("NewDefinitionData",) or "NewDefinitionData" not in inputs
                    or not set(inputs) <= KNOWN_INPUTS):
                continue
            if path == "WillowGame.WillowWeapon:InitializeFromDefinitionData":
                self.initializers["weapon"] = inputs
            elif path == "WillowGame.WillowItem:InitializeFromDefinitionData":
                self.initializers["item"] = inputs

    def skip(self, reason):
        self.loot.count(self.skipped, reason)
        return None

    def prepare(self, obj, args, pc):
        if not self.runtime.enabled or not self.loot.selected():
            return None
        if self.runtime.missions.scopes:
            return self.skip("mission reward scope")
        # Ownership is captured BEFORE DropFrom detaches the original inventory.
        owner, visited, death = getattr(obj, "Owner", None), set(), None
        for _ in range(6):
            if owner is None:
                break
            address = owner._get_address()
            if address in visited:
                break
            visited.add(address)
            death = next(((token, owner._path_name()) for token, dying in reversed(self.loot.deaths)
                          if dying is not None and dying == address), None)
            if death is not None:
                break
            owner = getattr(owner, "Owner", None)
        if death is None:
            return None  # Player drops, live NPC weapon changes and unrelated actors.
        player = self.runtime.level(pc)
        data = getattr(obj, "DefinitionData", None)
        if player is None or data is None:
            return None
        balance = getattr(data, "BalanceDefinition", None)
        definition = getattr(data, "WeaponTypeDefinition", None) or getattr(data, "ItemDefinition", None)
        if balance is None or definition is None or not getattr(definition, "bUsesPlayerLevelRequirement", False):
            return None
        if getattr(definition, "bMissionItem", False) or getattr(definition, "bPlayerUseItemOnPickup", False):
            return None
        if any("storagedeckupgrade" in row._path_name().lower() or "itemgrade_sdu_" in row._path_name().lower()
               for row in inherited(balance)):
            return None
        if getattr(balance, "bInterpolateExpLevel", False):
            return self.skip("interpolated carried equipment")
        kind = "weapon" if getattr(data, "WeaponTypeDefinition", None) is not None else "item"
        if kind not in self.initializers:
            return self.skip("unsupported carried initializer")
        current = int(obj.ExpLevel)
        target = internal_level(definition, self.loot.minimum(player, data))
        if current >= target:
            return None
        encoded = deepcopy(data)
        encoded.ManufacturerGradeIndex = pack_level(data.ManufacturerGradeIndex, target)
        self.prepared += 1
        return {"token": death[0], "owner": death[1], "original": obj._path_name(),
                "balance": balance._path_name(), "data": encoded, "kind": kind,
                "floor": self.loot.minimum(player, data), "old_internal_level": current,
                "target_internal_level": target,
                "location": deepcopy(args.StartLocation), "velocity": deepcopy(args.StartVelocity),
                "no_physics": args.bForceNoRBPhysics,
                "fields": {name: getattr(obj, name) for name in COPY_FIELDS if hasattr(obj, name)},
                "rarity": getattr(obj, "RarityLevel", None)}

    def pickups(self, inventory, include_retired=False):
        return [obj for obj in islice(self.runtime.sdk.find_all("WillowPickup"), 2048)
                if not self.dead(obj) and (include_retired or getattr(obj, "bPickupable", True))
                and getattr(obj, "Inventory", None) == inventory]

    @staticmethod
    def same_definition(expected, actual):
        names = ([str(p.Name) for p in expected._type._properties()] if hasattr(expected, "_type")
                 else list(vars(expected)))
        return all(getattr(expected, name) == getattr(actual, name) for name in names)

    @staticmethod
    def dead(actor):
        return actor is None or bool(getattr(actor, "bDeleteMe", False) or getattr(actor, "bPendingDelete", False))

    @staticmethod
    def scheduled(actor, pickup):
        life = float(getattr(actor, "LifeSpan", 0))
        return (0 < life <= RETIRE_LIFESPAN and bool(getattr(actor, "bHidden", False))
                and (not pickup or not bool(getattr(actor, "bPickupable", True))))

    def record_retirement(self, actor, pickup, outcome):
        try:
            self.retirements.append({"actor": actor._path_name(), "pickup": pickup, "outcome": outcome,
                "flags": {name: getattr(actor, name, None) for name in
                          ("bStatic", "bNoDelete", "bDeleteMe", "bPendingDelete", "bHidden", "bPickupable", "LifeSpan")}})
            del self.retirements[:-16]
        except Exception as exc:
            self.runtime.problem("carried retirement trace", exc)

    def retire(self, actor, pickup=False):
        """BL1E refuses direct Destroy; let its native loot-expiry path clean up.

        Change only newly dropped/replacement actors. Disable retired pickups now,
        hide them, and schedule native expiry. Do not hold a wrapper until next tick.
        """
        if self.dead(actor):
            return True
        if self.scheduled(actor, pickup):
            return True
        if getattr(actor, "bStatic", False) or getattr(actor, "bNoDelete", False):
            self.record_retirement(actor, pickup, "protected actor")
            return False
        fields = ("LifeSpan", "bHidden", "bPickupable") if pickup else ("LifeSpan", "bHidden")
        old = {name: getattr(actor, name) for name in fields}
        try:
            actor.bHidden = True
            if pickup:
                actor.bPickupable = False
            actor.LifeSpan = RETIRE_LIFESPAN  # Last: expiry is the commit point.
            if not self.scheduled(actor, pickup):
                raise RuntimeError("Native expiry state did not retain retirement fields")
            self.record_retirement(actor, pickup, "native expiry scheduled")
            return True
        except Exception as exc:
            if self.scheduled(actor, pickup):
                self.runtime.problem("carried loot retirement", exc)
                self.record_retirement(actor, pickup, "native expiry scheduled after setter error")
                return True
            # No expiry was committed: restore the original usable pickup.
            for name in fields:
                setattr(actor, name, old[name])
            self.record_retirement(actor, pickup, "retirement rolled back")
            raise

    def cleanup_copy(self, clone):
        if clone is None:
            return
        pickups = self.pickups(clone, include_retired=True)
        for pickup in pickups:
            if not self.retire(pickup, pickup=True):
                self.runtime.problem("carried loot cleanup", RuntimeError("Replacement pickup could not be removed"))
        # Attached inventory is left to its pickup's normal expiry lifecycle.
        # Only a copy which never produced a pickup needs its own expiry.
        if not pickups and not self.dead(clone) and getattr(clone, "Owner", None) is not None:
            self.runtime.problem("carried loot cleanup", RuntimeError("Refused expiry of an owned replacement"))
            return
        if not pickups and not self.retire(clone):
            self.runtime.problem("carried loot cleanup", RuntimeError("Replacement inventory could not be removed"))

    def finish_drop(self, original, plan, pc):
        if plan is None or not self.runtime.enabled or not self.loot.selected():
            return
        clone = None
        try:
            # Only operate after the native drop really detached its inventory.
            if getattr(original, "Owner", None) is not None or self.dead(original):
                return self.skip("original drop did not detach")
            pickups = self.pickups(original)
            if len(pickups) != 1:
                return self.skip("original pickup not uniquely identified")
            if getattr(pickups[0], "bStatic", False) or getattr(pickups[0], "bNoDelete", False):
                self.record_retirement(pickups[0], True, "protected original pickup")
                return self.skip("protected original pickup")
            if not any(token is plan["token"] for token, _address in self.loot.deaths):
                return self.skip("death scope ended before replacement")
            with prevent_hooking_direct_calls():
                clone = pc.Spawn(original.Class)
                if clone is None:
                    raise RuntimeError("Native inventory spawn returned no actor")
                for name, value in plan["fields"].items():
                    setattr(clone, name, value)
                values = {"NewDefinitionData": deepcopy(plan["data"]),
                          "InAdditionalQueryInterfaceSource": None, "bForceSelectNameParts": False}
                clone.InitializeFromDefinitionData(**{name: values[name] for name in self.initializers[plan["kind"]]})
            if not self.same_definition(plan["data"], clone.DefinitionData):
                raise RuntimeError("Native carried copy changed selected definition parts")
            if int(clone.ExpLevel) < plan["target_internal_level"]:
                raise RuntimeError("Native carried copy did not retain its encoded level")
            if plan["rarity"] is not None and clone.RarityLevel != plan["rarity"]:
                raise RuntimeError("Native carried copy changed rarity")
            for name in ("Quantity", "OwnerStatsID"):
                if name in plan["fields"]:
                    setattr(clone, name, plan["fields"][name])
            with prevent_hooking_direct_calls():
                clone.DropFrom(plan["location"], plan["velocity"], plan["no_physics"])
            copies = self.pickups(clone)
            if len(copies) != 1 or getattr(clone, "Owner", None) is not None:
                raise RuntimeError("Native carried copy did not create one detached pickup")
            entry = {"plan": plan, "original": original, "old_pickup": pickups[0],
                     "clone": clone, "new_pickup": copies[0], "replacement": clone._path_name()}
            self.pending.setdefault(plan["token"], []).append(entry)
        except Exception as exc:
            self.runtime.problem("carried loot replacement", exc)
            try:
                self.cleanup_copy(clone)
            except Exception as cleanup_error:
                self.runtime.problem("carried loot cleanup", cleanup_error)

    def commit(self, token):
        # Died native code has now finished using the original inventory chain.
        # No timer/callback delay and no permanently retained actor references.
        for entry in self.pending.pop(token, []):
            committed = False
            try:
                if not self.runtime.enabled or not self.loot.selected():
                    self.cleanup_copy(entry["clone"])
                    continue
                if self.dead(entry["new_pickup"]) or self.dead(entry["clone"]):
                    raise RuntimeError("Replacement vanished before death-drop commit")
                try:
                    committed = self.retire(entry["old_pickup"], pickup=True)
                except Exception:
                    committed = self.dead(entry["old_pickup"]) or self.scheduled(entry["old_pickup"], True)
                    if not committed:
                        raise
                    self.runtime.problem("carried loot commit", RuntimeError("Original pickup expiry committed but setter raised"))
                if not committed:
                    raise RuntimeError("Original pickup could not be retired")
                self.changed += 1
                self.loot.raised += 1
                p = entry["plan"]
                self.recent.append({key: p[key] for key in ("owner", "original", "balance", "floor",
                                    "old_internal_level", "target_internal_level")})
                self.recent[-1]["replacement"] = entry["replacement"]
                self.recent[-1]["retirement"] = "native pickup expiry"
                del self.recent[:-16]
            except Exception as exc:
                self.runtime.problem("carried loot commit", exc)
                if not committed:
                    try:
                        self.cleanup_copy(entry["clone"])
                    except Exception as cleanup_error:
                        self.runtime.problem("carried loot cleanup", cleanup_error)

    def snapshot(self):
        return {"initializers": dict(self.initializers), "prepared": self.prepared, "changed": self.changed,
                "pending": sum(map(len, self.pending.values())), "skipped": dict(self.skipped),
                "recent": list(self.recent), "retirements": list(self.retirements)}
