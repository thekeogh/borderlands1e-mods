"""Fixed PT3 grenade damage in the existing card/projectile damage slot.

Stock definitions remain native. Each live item's original scale and cached
damage are retained through a weak reference and restored outside PT3/disable.
No native initialization, damage interception or getter reinvocation is needed.
"""

from __future__ import annotations

import math

import unrealsdk
from unrealsdk.hooks import Type
from unrealsdk.unreal import WeakPointer
from mods_base import get_pc, hook

from . import balance, enemy_levels

GRENADE_DEFINITION = "gd_tunercuffs.A_Item.Item_GrenadeModulator"
PROJECTILE_FORMULA = "gd_Balance_HealthAndDamage.HealthAndDamage.ProjectileDamageFormula"


class GrenadeDamage:
    def __init__(self, sdk):
        self.sdk = sdk
        self.target_damage = None
        self.busy = False
        self.problems = []
        self.updated_slots = 0
        self._items = {}

    def problem(self, exc):
        message = f"{type(exc).__name__}: {exc}"
        if message not in self.problems and len(self.problems) < 12:
            self.problems.append(message)

    @staticmethod
    def damage_slot(item):
        if ("default__" in item._path_name().lower() or item.bDeleteMe or item.bPendingDelete):
            return None
        definition = item.DefinitionData.ItemDefinition
        if definition is None or definition._path_name().lower() != GRENADE_DEFINITION.lower():
            return None
        matches = [slot for slot in item.AttributeSlots if str(slot.SlotName) == "GrenadeDamage"]
        if len(matches) != 1:
            raise ValueError("Expected one GrenadeDamage slot")
        slot = matches[0]
        base, upgrade = slot.BaseModifierValue, slot.PerGradeUpgrade
        formula = base.InitializationDefinition
        if (formula is None or formula._path_name().lower() != PROJECTILE_FORMULA.lower()
                or base.BaseValueAttribute is not None or base.BaseValueConstant != 0
                or upgrade.BaseValueConstant != 0 or upgrade.BaseValueAttribute is not None
                or upgrade.InitializationDefinition is not None):
            raise ValueError("Unsupported grenade damage slot")
        return slot

    @staticmethod
    def matches(slot, record):
        return (math.isclose(float(slot.BaseModifierValue.BaseValueScaleConstant), record["written_scale"], rel_tol=1e-6)
                and math.isclose(float(slot.ComputedModifierValue), record["written_damage"], rel_tol=1e-6))

    @staticmethod
    def write(slot, scale, damage):
        old_scale = float(slot.BaseModifierValue.BaseValueScaleConstant)
        old_damage = float(slot.ComputedModifierValue)
        try:
            slot.BaseModifierValue.BaseValueScaleConstant = scale
            slot.ComputedModifierValue = damage
            if (not math.isclose(float(slot.BaseModifierValue.BaseValueScaleConstant), scale, rel_tol=1e-6)
                    or not math.isclose(float(slot.ComputedModifierValue), damage, rel_tol=1e-6, abs_tol=1e-6)):
                raise RuntimeError("Grenade damage write did not persist")
        except Exception:
            slot.BaseModifierValue.BaseValueScaleConstant = old_scale
            slot.ComputedModifierValue = old_damage
            raise

    def refresh_item(self, item, *, reinitialized=False):
        if item is None:
            return
        try:
            address = item._get_address()
            if address in _initializing and not reinitialized:
                return  # Never alter partially initialized native slots.
            record = self._items.get(address)
            if record is not None and record["ref"]() is None:
                self._items.pop(address, None)
                record = None
            slot = self.damage_slot(item)
            if slot is None:
                return
            if self.target_damage is None:
                if record is not None:
                    if self.matches(slot, record):
                        self.write(slot, record["native_scale"], record["native_damage"])
                    self._items.pop(address, None)
                return
            if reinitialized or record is None or not self.matches(slot, record):
                scale = float(slot.BaseModifierValue.BaseValueScaleConstant)
                damage = float(slot.ComputedModifierValue)
                if not math.isfinite(scale) or scale <= 0 or not math.isfinite(damage) or damage <= 0:
                    raise ValueError("Invalid native grenade damage")
                record = {"ref": WeakPointer(item), "native_scale": scale, "native_damage": damage,
                          "written_scale": scale, "written_damage": damage}
                self._items[address] = record
            if record["written_damage"] == self.target_damage and self.matches(slot, record):
                return
            scale = record["native_scale"] * self.target_damage / record["native_damage"]
            self.write(slot, scale, self.target_damage)
            record["written_scale"] = float(slot.BaseModifierValue.BaseValueScaleConstant)
            record["written_damage"] = float(slot.ComputedModifierValue)
            self.updated_slots += 1
        except Exception as exc:
            self.problem(exc)

    def refresh_inventory(self):
        try:
            # Only at load/setting changes; never a per-frame inventory scan.
            for item in self.sdk.find_all("WillowItem", exact=False):
                self.refresh_item(item)
            for address, record in list(self._items.items()):
                if record["ref"]() is None:
                    self._items.pop(address, None)
        except Exception as exc:
            self.problem(exc)

    def cloned_slots(self, first, second):
        """Carry the native baseline when the engine copies a boosted slot."""
        if first is None or second is None:
            return
        try:
            # Infer the tracked source from matching copied values, rather than
            # assuming which argument receives the native copy.
            for source, target in ((first, second), (second, first)):
                record = self._items.get(source._get_address())
                if record is None or record["ref"]() is None:
                    continue
                slot = self.damage_slot(target)
                original = self.damage_slot(source)
                if (slot is not None and original is not None and self.matches(original, record)
                        and self.matches(slot, record) and target.ExpLevel == source.ExpLevel
                        and target._get_address() not in self._items):
                    copied = dict(record)
                    copied["ref"] = WeakPointer(target)
                    self._items[target._get_address()] = copied
            self.refresh_item(first)
            self.refresh_item(second)
        except Exception as exc:
            self.problem(exc)

    def set_damage(self, target, *, refresh=True):
        if self.busy:
            return
        self.busy = True
        try:
            self.target_damage = target
            if target is None:
                # Restore all surviving tracked items, including dropped items
                # not returned by a later inventory enumeration.
                for record in list(self._items.values()):
                    self.refresh_item(record["ref"]())
                self._items = {address: record for address, record in self._items.items()
                               if record["ref"]() is not None}
            elif refresh:
                self.refresh_inventory()
        finally:
            self.busy = False

    def snapshot(self):
        value = balance.max_setting(enemy_levels.max_level.value)
        result = {"enabled": _enabled, "pt3_selected": _selected_pt3,
                  "pending_selection": _pending_selection, "max_level": value,
                  "configured_damage": balance.GRENADE_DAMAGE[value], "applied_damage": self.target_damage,
                  "updated_slots": self.updated_slots, "problems": list(self.problems), "items": []}
        try:
            for item in self.sdk.find_all("WillowItem", exact=False):
                slot = self.damage_slot(item)
                if slot is None:
                    continue
                result["items"].append({"path": item._path_name(), "level": int(item.ExpLevel),
                                        "computed_damage": float(slot.ComputedModifierValue),
                                        "slot_scale": float(slot.BaseModifierValue.BaseValueScaleConstant)})
                if len(result["items"]) >= 64:
                    break
        except Exception as exc:
            result["read_error"] = repr(exc)
        return result


_policy = GrenadeDamage(unrealsdk)
_enabled = False
_selected_pt3 = False
_pending_selection = None
_initializing = {}


def set_mode(pt3, *, refresh=True, max_value=None, explicit=True):
    global _selected_pt3, _pending_selection
    _selected_pt3 = bool(pt3)
    if explicit:
        _pending_selection = bool(pt3)
    value = balance.max_setting(enemy_levels.max_level.value if max_value is None else max_value)
    _policy.set_damage(balance.GRENADE_DAMAGE[value] if _enabled and pt3 else None, refresh=refresh)


def change_max_level(_option, value):
    # Option callbacks run before option.value changes.
    set_mode(_selected_pt3, max_value=value, explicit=False)


def reset_loading():
    global _pending_selection
    _pending_selection = None
    set_mode(False, refresh=False, explicit=False)


def sync_runtime():
    global _pending_selection
    if not _enabled or _policy.busy:
        return
    try:
        pc = get_pc()
        if pc is None or pc.Pawn is None:
            return
        pt3 = pc.GetCurrentPlaythrough() == 2
        if _pending_selection is not None:
            if pt3 != _pending_selection:
                return
            _pending_selection = None
        set_mode(pt3, refresh=False, explicit=False)
    except Exception as exc:
        _policy.problem(exc)


def on_enable():
    global _enabled, _pending_selection
    _enabled = True
    _pending_selection = None
    pc = get_pc()
    set_mode(pc is not None and pc.Pawn is not None and pc.GetCurrentPlaythrough() == 2, explicit=False)


def on_disable():
    global _enabled, _selected_pt3, _pending_selection
    _enabled = _selected_pt3 = False
    _pending_selection = None
    _policy.set_damage(None)
    _initializing.clear()


@hook("WillowGame.WillowPlayerController:OnExpLevelChange", Type.POST)
@hook("WillowGame.WillowPlayerController:ClientSetProfileLoaded", Type.POST)
def player_ready(obj, _args, _ret, _func):
    if _enabled and obj == get_pc():
        sync_runtime()
        _policy.refresh_inventory()


@hook("WillowGame.WillowItem:InitializeAttributeSlots", Type.PRE)
def before_slots(obj, _args, _ret, _func):
    if _enabled:
        address = obj._get_address()
        _initializing[address] = _initializing.get(address, 0) + 1
        sync_runtime()


@hook("WillowGame.WillowItem:InitializeAttributeSlots", Type.POST)
def after_slots(obj, _args, _ret, _func):
    if _enabled and not _policy.busy:
        _policy.refresh_item(obj, reinitialized=True)


@hook("WillowGame.WillowItem:InitializeAttributeSlots", Type.POST_UNCONDITIONAL)
def finish_slots(obj, _args, _ret, _func):
    address = obj._get_address()
    count = _initializing.get(address, 0)
    if count > 1:
        _initializing[address] = count - 1
    else:
        _initializing.pop(address, None)


@hook("WillowGame.WillowItem:GetAttributeSlotModifierValue", Type.PRE)
def damage_read(obj, args, _ret, _func):
    if str(args.SlotName) == "GrenadeDamage" and _enabled and not _policy.busy:
        sync_runtime()
        _policy.refresh_item(obj)


@hook("WillowGame.WillowItem:CloneAttributeSlotData", Type.POST)
def slots_cloned(obj, args, _ret, _func):
    if _enabled and not _policy.busy:
        _policy.cloned_slots(obj, args.NewItem)


HOOKS = [player_ready, before_slots, after_slots, finish_slots, damage_read, slots_cloned]
