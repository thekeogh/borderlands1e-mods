"""Level-1 cash formulas for PT3, grounded in the supplied BL1E export.

Only money formula inputs and cached item cash values change. Item/mission
levels, packed manufacturer grades, stats and wallet transactions stay native.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import unrealsdk
from unrealsdk import logging
from mods_base import get_pc, hook
from unrealsdk.hooks import Type

KEEP_ALIVE = 0x4000
CURRENCY_FORMULA = "gd_Balance_Inventory.Commerce.CurrencyCreditsValue"
PLAYER_CURRENCY = "d_attributes.Inventory.PlayerCurrencyOnHand"
INPUT_FIELDS = (
    "BaseValueConstant", "BaseValueAttribute", "InitializationDefinition",
    "BaseValueScaleConstant",
)
LEVEL_ONE_INPUT = {
    "BaseValueConstant": 1.0, "BaseValueAttribute": None,
    "InitializationDefinition": None, "BaseValueScaleConstant": 1.0,
}
# Actual definitions and level inputs from the user's BL1E snapshot.
FORMULA_INPUTS = (
    ("gd_Balance_Inventory.Commerce.WeaponItemValue", "Power", "d_attributes.Inventory.UnownedItemLevel"),
    (CURRENCY_FORMULA, "Power", "d_attributes.Inventory.CurrencyItemLevel"),
    ("gd_Balance.Missions.MissionCreditRewardFormula", "Power", "d_attributes.Balance.GameStage"),
    ("gd_globals.Skills.CostToResetSkillPoints", "Level", "d_attributes.ExperienceResourcePool.PlayerExperienceLevel"),
    ("gd_Balance_Inventory.Commerce.CostToResetSkillPoints", "Power", "d_attributes.ExperienceResourcePool.PlayerExperienceLevel"),
    ("gd_Balance_Inventory.Commerce.DeathPenaltyCap", "Power", "d_attributes.ExperienceResourcePool.PlayerExperienceLevel"),
)


@dataclass
class InputPatch:
    definition: Any
    input_name: str
    original: dict[str, Any]

    def write(self, active: bool) -> None:
        target = getattr(self.definition.ValueFormula, self.input_name)
        values = LEVEL_ONE_INPUT if active else self.original
        for name in INPUT_FIELDS:
            setattr(target, name, values[name])
        if not self.matches(active):
            raise RuntimeError(f"Cash formula write did not persist: {self.definition._path_name()}")

    def matches(self, active: bool) -> bool:
        target = getattr(self.definition.ValueFormula, self.input_name)
        values = LEVEL_ONE_INPUT if active else self.original
        return all(getattr(target, name) == values[name] for name in INPUT_FIELDS)


class Economy:
    def __init__(self, sdk: Any, reporter: Any) -> None:
        self.sdk = sdk
        self.reporter = reporter
        self.active = False
        self.patches: list[InputPatch] = []
        self.pinned: dict[int, tuple[Any, bool]] = {}
        self.reported: set[str] = set()
        self.problems: list[str] = []
        self.events: list[dict[str, Any]] = []
        self.busy = False

    def problem(self, key: str, exc: Exception) -> None:
        if key not in self.reported and len(self.reported) < 12:
            self.reported.add(key)
            message = f"{key}: {exc!r}"
            self.problems.append(message)
            self.reporter.error(f"[PT3 Economy] {message}")

    def pin(self, obj: Any) -> None:
        if obj is None:
            return
        address = obj._get_address()
        if address not in self.pinned:
            already_pinned = bool(obj.ObjectFlags & KEEP_ALIVE)
            obj.ObjectFlags |= KEEP_ALIVE
            self.pinned[address] = (obj, already_pinned)

    def prepare(self) -> bool:
        if self.patches:
            return True
        try:
            for package in ("gd_Balance_Inventory", "gd_Balance", "gd_globals", "gd_currency"):
                self.sdk.load_package(package)
            pending = []
            for path, input_name, expected_attribute in FORMULA_INPUTS:
                definition = self.sdk.find_object("AttributeInitializationDefinition", path)
                formula = definition.ValueFormula
                target = getattr(formula, input_name)
                attribute = target.BaseValueAttribute
                if (
                    not formula.bEnabled
                    or attribute is None
                    or attribute._path_name().lower() != expected_attribute.lower()
                    or target.InitializationDefinition is not None
                ):
                    raise ValueError(f"Unexpected formula input at {path}.{input_name}")
                original = {name: getattr(target, name) for name in INPUT_FIELDS}
                pending.append(InputPatch(definition, input_name, original))
            # Detaching original attributes would otherwise allow GC to free them.
            for patch in pending:
                self.pin(patch.definition)
                self.pin(patch.original["BaseValueAttribute"])
                self.pin(patch.original["InitializationDefinition"])
            self.patches = pending
            return True
        except Exception as exc:
            self.problem("Could not prepare cash formulas", exc)
            return False

    def set_mode(self, active: bool, *, refresh: bool = True, reason: str = "selection") -> bool:
        if self.busy:
            return False
        self.busy = True
        try:
            return self._set_mode(active, refresh=refresh, reason=reason)
        finally:
            self.busy = False

    def _set_mode(self, active: bool, *, refresh: bool, reason: str) -> bool:
        if active and not self.prepare():
            return False
        # Engine/menu callbacks can run before the selected playthrough is set.
        # Recheck actual inputs at cash operations rather than trusting a flag.
        if active != self.active or any(not patch.matches(active) for patch in self.patches):
            try:
                for patch in self.patches:
                    patch.write(active)
            except Exception as exc:
                # Do not leave a partially applied price policy on failure.
                for patch in self.patches:
                    try:
                        patch.write(False)
                    except Exception as restore_exc:
                        self.problem("Could not restore a cash formula", restore_exc)
                self.active = False
                self.problem("Could not apply cash formulas", exc)
                return False
            self.active = active
            self.events.append({"active": active, "reason": reason})
            self.events = self.events[-24:]
            self.reporter.info(
                "[PT3 Economy] " + ("Level-1 cash formulas active" if active else "Normal cash formulas restored")
                + f" ({reason})."
            )
        if refresh and self.patches:
            self.refresh_inventory()
        return True

    def is_currency(self, item: Any) -> bool:
        if str(item.Class.Name) != "WillowUsableItem":
            return False
        definition = item.DefinitionData.ItemDefinition
        for slot in definition.AttributeSlotEffects:
            attribute = slot.AttributeToModify
            if attribute is None or attribute._path_name().lower() != PLAYER_CURRENCY.lower():
                continue
            for value in (slot.BaseModifierValue, slot.PerGradeUpgrade):
                formula = value.InitializationDefinition
                if formula is not None and formula._path_name().lower() == CURRENCY_FORMULA.lower():
                    return True
        return False

    def refresh_item(self, item: Any) -> None:
        if item is None:
            return
        try:
            if "default__" in item._path_name().lower() or item.bDeleteMe or item.bPendingDelete:
                return
            if self.is_currency(item):
                item.InitializeAttributeSlots(bIncludeNameParts=True)
            value = int(item.ComputeCashValue())
            if value >= 0:
                item.CashValue = value
        except Exception as exc:
            self.problem("Could not refresh an item cash value", exc)

    def refresh_inventory(self) -> None:
        """One synchronous pass on load/mode change, never a per-frame scan."""
        try:
            for item in self.sdk.find_all("WillowInventory", exact=False):
                self.refresh_item(item)
        except Exception as exc:
            self.problem("Could not enumerate inventory", exc)

    def snapshot(self) -> dict[str, Any]:
        """Read-only, JSON-safe status included in the F10 diagnostic export."""
        formulas = []
        for path, input_name, _expected in FORMULA_INPUTS:
            record = {"path": path, "input": input_name}
            try:
                definition = self.sdk.find_object("AttributeInitializationDefinition", path)
                target = getattr(definition.ValueFormula, input_name)
                for name in INPUT_FIELDS:
                    value = getattr(target, name)
                    record[name] = value._path_name() if value is not None and hasattr(value, "_path_name") else value
            except Exception as exc:
                record["error"] = repr(exc)
            formulas.append(record)
        return {
            "active": self.active, "prepared_count": len(self.patches),
            "problems": list(self.problems), "events": list(self.events),
            "formula_inputs": formulas,
        }

    def release(self) -> None:
        if not self.set_mode(False):
            return  # Keep originals pinned if restoration failed.
        for obj, already_pinned in self.pinned.values():
            if not already_pinned:
                obj.ObjectFlags &= ~KEEP_ALIVE
        self.patches.clear()
        self.pinned.clear()
        self.reported.clear()
        self.problems.clear()


_economy = Economy(unrealsdk, logging)


def prepare() -> bool:
    return _economy.prepare()


def set_mode(active: bool, *, refresh: bool = True) -> bool:
    return _economy.set_mode(active, refresh=refresh)


def on_enable() -> None:
    logging.info("[PT3 Economy] Enabled; runtime cash hooks installed.")
    pc = get_pc()
    if pc is not None and pc.Pawn is not None:
        _economy.set_mode(pc.GetCurrentPlaythrough() == 2, reason="enable")


def on_disable() -> None:
    _economy.release()


@hook("WillowGame.WillowPlayerController:ClientSetProfileLoaded", Type.POST)
def profile_loaded(obj: Any, _args: Any, _ret: Any, _func: Any) -> None:
    pc = get_pc()
    if pc is not None and obj == pc:
        # Do not undo a PT3 menu selection if this early callback still reports
        # the previous playthrough. PT1/PT2 restore at their selection instead.
        if obj.GetCurrentPlaythrough() == 2:
            _economy.set_mode(True, reason="profile loaded")


def sync_runtime(reason: str) -> bool:
    """Confirm the live playthrough at the point cash is calculated/displayed."""
    if _economy.busy:
        return False
    try:
        pc = get_pc()
        if pc is None or pc.Pawn is None:
            return False
        # A loading controller can still report PT1 after PT3 was selected.
        # Only the menu selection/on-enable may restore another playthrough.
        if pc.GetCurrentPlaythrough() != 2:
            return False
        return _economy.set_mode(True, refresh=False, reason=reason)
    except Exception as exc:
        _economy.problem("Could not synchronize live playthrough", exc)
        return False


@hook("Engine.WillowInventory:ComputeCashValue")
@hook("WillowGame.MissionDefinition:GetCreditReward")
@hook("WillowGame.WillowVendingMachine:GetResetCost")
def cash_calculation(_obj: Any, _args: Any, _ret: Any, _func: Any) -> None:
    sync_runtime("cash calculation")


@hook("WillowGame.WillowVendingMachine:GetSellingPriceForInventory")
def vendor_price(_obj: Any, args: Any, _ret: Any, _func: Any) -> None:
    if sync_runtime("vendor price"):
        _economy.refresh_item(args.InventoryForSale)


@hook("WillowGame.VendingMachineGFxMovie:SetPrice")
@hook("WillowGame.WillowVendingMachine:PlayerBuyItem")
@hook("WillowGame.WillowVendingMachine:PlayerSellItem")
@hook("WillowGame.WillowVendingMachine:PlayerBuyBackItem")
def vendor_item(_obj: Any, args: Any, _ret: Any, _func: Any) -> None:
    if sync_runtime("vendor item"):
        _economy.refresh_item(getattr(args, "Thing", None) or getattr(args, "Item", None))


@hook("WillowGame.WillowPlayerController:OnExpLevelChange", Type.POST)
def level_changed(obj: Any, _args: Any, _ret: Any, _func: Any) -> None:
    if obj == get_pc() and sync_runtime("level change"):
        _economy.refresh_inventory()


HOOKS = [profile_loaded, cash_calculation, vendor_price, vendor_item, level_changed]
