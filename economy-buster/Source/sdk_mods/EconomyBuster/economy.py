"""Level-1 money inputs, independent of item, mission and player levels.

Adapted from keogh's Playthrough 3 economy module. Definitions verified against
the supplied BL1E Borderlens extraction, 2026-11-10. No PT3 gameplay is imported.
"""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
from typing import Any

KEEP_ALIVE = 0x4000
CURRENCY_FORMULA = "gd_Balance_Inventory.Commerce.CurrencyCreditsValue"
PLAYER_CURRENCY = "d_attributes.Inventory.PlayerCurrencyOnHand"
PACKAGES = ("gd_Balance_Inventory", "gd_Balance", "gd_globals", "gd_currency")
INPUT_FIELDS = ("BaseValueConstant", "BaseValueAttribute", "InitializationDefinition", "BaseValueScaleConstant")
LEVEL_ONE = dict(BaseValueConstant=1.0, BaseValueAttribute=None,
                 InitializationDefinition=None, BaseValueScaleConstant=1.0)
FORMULA_INPUTS = (
    ("gd_Balance_Inventory.Commerce.WeaponItemValue", "Power", "d_attributes.Inventory.UnownedItemLevel"),
    (CURRENCY_FORMULA, "Power", "d_attributes.Inventory.CurrencyItemLevel"),
    ("gd_Balance.Missions.MissionCreditRewardFormula", "Power", "d_attributes.Balance.GameStage"),
    ("gd_globals.Skills.CostToResetSkillPoints", "Level", "d_attributes.ExperienceResourcePool.PlayerExperienceLevel"),
    ("gd_Balance_Inventory.Commerce.CostToResetSkillPoints", "Power", "d_attributes.ExperienceResourcePool.PlayerExperienceLevel"),
    ("gd_Balance_Inventory.Commerce.DeathPenaltyCap", "Power", "d_attributes.ExperienceResourcePool.PlayerExperienceLevel"),
)


def read_input(target: Any) -> dict[str, Any]:
    return {name: getattr(target, name) for name in INPUT_FIELDS}


def primitive(value: Any) -> Any:
    return value._path_name() if value is not None and hasattr(value, "_path_name") else value


@dataclass
class InputPatch:
    definition: Any
    input_name: str
    original: dict[str, Any]
    recovery_required: bool = False

    def current(self) -> dict[str, Any]:
        return read_input(getattr(self.definition.ValueFormula, self.input_name))

    def write(self, values: dict[str, Any]) -> None:
        target = getattr(self.definition.ValueFormula, self.input_name)
        for name, value in values.items():
            setattr(target, name, value)
        if self.current() != values:
            raise RuntimeError(f"Money input write did not persist: {self.definition._path_name()}.{self.input_name}")


class Economy:
    def __init__(self, sdk: Any) -> None:
        self.sdk = sdk
        self.enabled = False
        self.active = False
        self.busy = False
        self.patches: list[InputPatch] = []
        # Only static definitions/attributes are retained and pinned. Never actors.
        self.pinned: dict[int, tuple[Any, bool]] = {}
        self.problems: list[str] = []
        self.events: deque[dict[str, Any]] = deque(maxlen=24)
        self.counts: Counter[str] = Counter()

    def problem(self, context: str, exc: Exception) -> None:
        message = f"{context}: {type(exc).__name__}: {exc}"
        if message not in self.problems and len(self.problems) < 24:
            self.problems.append(message)

    def pin(self, obj: Any) -> None:
        if obj is None:
            return
        address = obj._get_address()
        if address not in self.pinned:
            previous = bool(obj.ObjectFlags & KEEP_ALIVE)
            obj.ObjectFlags |= KEEP_ALIVE
            self.pinned[address] = (obj, previous)

    def unpin(self) -> None:
        for address, (obj, previous) in list(self.pinned.items()):
            try:
                if not previous:
                    obj.ObjectFlags &= ~KEEP_ALIVE
                del self.pinned[address]
            except Exception as exc:
                self.problem("release static definition", exc)

    def prepare(self) -> bool:
        if self.patches:
            return True
        try:
            for package in PACKAGES:
                self.sdk.load_package(package)
            pending = []
            for path, name, expected in FORMULA_INPUTS:
                definition = self.sdk.find_object("AttributeInitializationDefinition", path)
                formula = definition.ValueFormula
                current = read_input(getattr(formula, name))
                attribute = current["BaseValueAttribute"]
                if (not formula.bEnabled or current["InitializationDefinition"] is not None
                        or attribute is None or attribute._path_name().lower() != expected.lower()):
                    raise ValueError(f"Unsupported or modified money input: {path}.{name}")
                pending.append(InputPatch(definition, name, current))
            # Validate the entire policy before editing any formula.
            for patch in pending:
                self.pin(patch.definition)
                self.pin(patch.original["BaseValueAttribute"])
            self.patches = pending
            return True
        except Exception as exc:
            self.problem("prepare money formulas", exc)
            self.unpin()
            return False

    def enable(self) -> bool:
        self.enabled = True
        return self.ensure("enable", refresh=True)

    def ensure(self, reason: str, *, refresh: bool = False) -> bool:
        """Recheck at cash boundaries. No playthrough selection or per-frame scan."""
        if not self.enabled or self.busy:
            return False
        self.busy = True
        try:
            if not self.prepare():
                return False
            before = [(patch, patch.current()) for patch in self.patches]
            # A known original can be restored by loading callbacks. A different
            # economy mod's unknown input must not be overwritten silently.
            for patch, current in before:
                if current != LEVEL_ONE and current != patch.original:
                    self.active = False
                    raise ValueError(f"Conflicting money input: {patch.definition._path_name()}.{patch.input_name}")
            changed = []
            try:
                for patch, current in before:
                    if current != LEVEL_ONE:
                        changed.append((patch, current))
                        patch.write(LEVEL_ONE)
            except Exception:
                for patch, current in reversed(changed):
                    try:
                        patch.write(current)
                    except Exception as exc:
                        patch.recovery_required = True
                        self.problem("roll back money formula", exc)
                self.active = False
                raise
            if changed or not self.active:
                self.events.append({"active": True, "reason": reason, "inputs_written": len(changed)})
                self.counts["formula_writes"] += len(changed)
            self.active = True
            if refresh:
                self._refresh_inventory()
            return True
        except Exception as exc:
            self.active = False
            self.problem("apply money formulas", exc)
            return False
        finally:
            self.busy = False

    def is_currency(self, item: Any) -> bool:
        if str(item.Class.Name) != "WillowUsableItem":
            return False
        definition = item.DefinitionData.ItemDefinition
        if definition is None:
            return False
        for slot in definition.AttributeSlotEffects:
            attribute = slot.AttributeToModify
            if attribute is None or attribute._path_name().lower() != PLAYER_CURRENCY.lower():
                continue
            for value in (slot.BaseModifierValue, slot.PerGradeUpgrade):
                formula = value.InitializationDefinition
                if formula is not None and formula._path_name().lower() == CURRENCY_FORMULA.lower():
                    return True
        return False

    @staticmethod
    def live(item: Any) -> bool:
        return (item is not None and "default__" not in item._path_name().lower()
                and not item.bDeleteMe and not item.bPendingDelete)

    def _refresh_item(self, item: Any) -> None:
        try:
            if not self.live(item):
                return
            # Currency pays from cached attribute slots, not just CashValue.
            # Never rebuild slots on equipment, health, ammo or SDUs.
            if self.is_currency(item):
                item.InitializeAttributeSlots(bIncludeNameParts=True)
                self.counts["currency_slot_refreshes"] += 1
            value = int(item.ComputeCashValue())
            if value >= 0:
                item.CashValue = value
                self.counts["cash_cache_refreshes"] += 1
        except Exception as exc:
            self.problem("refresh item cash", exc)

    def refresh_item(self, item: Any) -> None:
        if self.busy:
            return
        self.busy = True
        try:
            self._refresh_item(item)
        finally:
            self.busy = False

    def _refresh_inventory(self) -> None:
        try:
            self.counts["inventory_passes"] += 1
            for item in self.sdk.find_all("WillowInventory", exact=False):
                self._refresh_item(item)
        except Exception as exc:
            self.problem("enumerate inventory", exc)

    def disable(self) -> None:
        self.enabled = False
        if self.busy:
            self.problem("disable", RuntimeError("money operation still in progress"))
            return
        self.busy = True
        try:
            restored = True
            for patch in self.patches:
                try:
                    current = patch.current()
                    if current == LEVEL_ONE or patch.recovery_required:
                        patch.write(patch.original)
                        patch.recovery_required = False
                    elif current != patch.original:
                        # Preserve edits made by another mod since our last write.
                        self.problem("restore money input", ValueError(
                            f"External change retained: {patch.definition._path_name()}.{patch.input_name}"))
                except Exception as exc:
                    restored = False
                    self.problem("restore money input", exc)
            self.active = False
            if self.patches:
                self._refresh_inventory()
            self.events.append({"active": False, "reason": "disable", "restored": restored})
            if restored:
                self.patches.clear()
                self.unpin()
            # On a failed restoration retain original static references for retry.
        finally:
            self.busy = False

    def snapshot(self) -> dict[str, Any]:
        formulas = []
        originals = {(p.definition._path_name(), p.input_name): p.original for p in self.patches}
        for path, name, expected in FORMULA_INPUTS:
            record = {"path": path, "input": name, "native_level_attribute": expected}
            try:
                definition = self.sdk.find_object("AttributeInitializationDefinition", path)
                current = read_input(getattr(definition.ValueFormula, name))
                record["current"] = {k: primitive(v) for k, v in current.items()}
                record["level_one"] = current == LEVEL_ONE
                original = originals.get((path, name))
                record["before_enable"] = None if original is None else {k: primitive(v) for k, v in original.items()}
                record["recovery_required"] = any(p.recovery_required for p in self.patches
                    if p.definition._path_name() == path and p.input_name == name)
            except Exception as exc:
                record["error"] = repr(exc)
            formulas.append(record)
        return {"enabled": self.enabled, "active": self.active, "prepared_inputs": len(self.patches),
                "counts": dict(self.counts), "events": list(self.events),
                "problems": list(self.problems), "formula_inputs": formulas}
