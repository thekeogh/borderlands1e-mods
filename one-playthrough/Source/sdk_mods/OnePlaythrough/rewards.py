"""Generate equipment at the accepted mission's native use requirement.

Custom rewards can inherit empty manufacturer tables from BaseDefinition.
Materialize those tables on the child only for the synchronous reward call;
never change the parent, saved balance identity, or global use-level formulas.
"""

from copy import deepcopy
import math

from .patches import Patches


def inherited(balance):
    chain, seen = [], set()
    while balance is not None:
        name = balance._path_name().lower()
        if name in seen or len(chain) >= 64:
            raise ValueError("Cyclic or excessive reward balance inheritance")
        seen.add(name)
        chain.append(balance)
        balance = getattr(balance, "BaseDefinition", None)
    return chain


def internal_level(definition, mission_level):
    """Convert the ordinary backpack requirement to the native internal level.

    Captured BL1E sniper data: internal 7, requirement 5, fallback use bonus 2.
    The captured repeater uses 1 instead; do not hardcode a universal +2.
    Equipped proficiency display differences remain native behavior.
    """
    bonus = getattr(definition, "PlayerUseLevelBonus", None)
    if bonus is None:
        return int(mission_level)
    if bonus.InitializationDefinition is not None:
        raise ValueError("Unsupported dynamic reward use-level bonus")
    attribute = bonus.BaseValueAttribute
    if attribute is not None:
        name = str(getattr(attribute, "Name", "")) or attribute._path_name().rsplit(".", 1)[-1]
        if not (name.startswith("Proficiency_") and name.endswith("_LevelBonus")):
            raise ValueError("Unsupported reward use-level attribute")
    offset = float(bonus.BaseValueConstant) * float(bonus.BaseValueScaleConstant)
    if not math.isfinite(offset) or not offset.is_integer():
        raise ValueError("Unsupported fractional reward use-level bonus")
    return max(1, int(mission_level) + int(offset))


class RewardPatches(Patches):
    def __init__(self):
        super().__init__()
        self.materialized = []
        self.reward_levels = {}

    def manufacturers(self, balance, source):
        # WrappedStruct.__deepcopy__ creates a Python-owned native struct copy,
        # including its grade array. Never edit wrappers into the parent's data.
        original = tuple(balance.Manufacturers)  # Empty by construction.
        copies = [deepcopy(row) for row in source.Manufacturers]
        self.pin(balance)
        self.materialized.append((balance, original))
        balance.Manufacturers = copies

    def restore(self):
        errors = super().restore()
        for balance, original in reversed(self.materialized):
            try:
                balance.Manufacturers = list(original)
            except Exception as exc:
                errors.append(repr(exc))
        self.materialized.clear()
        return errors


def prepare_items(mission, level):
    """Temporarily override reward item grades; return the owned rollback scope."""
    patches = RewardPatches()
    try:
        for balance in getattr(mission, "ItemRewards", ()):
            if balance is None:
                continue
            chain = inherited(balance)
            if any("storagedeckupgrade" in item._path_name().lower()
                   or "itemgrade_sdu_" in item._path_name().lower() for item in chain):
                continue
            source = next((item for item in chain if getattr(item, "Manufacturers", ())), None)
            if source is None:
                continue
            definition = next((item.InventoryDefinition for item in chain
                               if getattr(item, "InventoryDefinition", None) is not None), None)
            if getattr(definition, "bUsesPlayerLevelRequirement", True) is False:
                continue  # Consumables/progression items have no equipment level.
            if source != balance:
                patches.manufacturers(balance, source)
            patches.reward_levels[balance._path_name().lower()] = int(level)
            for i, manufacturer in enumerate(balance.Manufacturers):
                grades = manufacturer.Grades
                if not grades:
                    continue
                lows = [g.GameStageRequirement.MinGameStage for g in grades]
                highs = [g.GameStageRequirement.MaxGameStage for g in grades]
                for j, grade in enumerate(grades):
                    inventory = getattr(grade.GradeModifiers, "CustomInventoryDefinition", None) or definition
                    if getattr(inventory, "bUsesPlayerLevelRequirement", True) is False:
                        continue
                    path = ("Manufacturers", i, "Grades", j)
                    patches.set(balance, (*path, "GradeModifiers", "ExpLevel"), internal_level(inventory, level))
                    if lows[j] == min(lows) and level < lows[j]:
                        patches.set(balance, (*path, "GameStageRequirement", "MinGameStage"), int(level))
                    if highs[j] == max(highs) and level > highs[j]:
                        patches.set(balance, (*path, "GameStageRequirement", "MaxGameStage"), int(level))
        return patches
    except Exception:
        patches.restore()
        raise


def describe(mission, level):
    """Small inheritance/level summary for manual F10 exports only."""
    records = []
    for balance in list(getattr(mission, "ItemRewards", ()))[:8]:
        if balance is None:
            continue
        chain = inherited(balance)
        source = next((item for item in chain if getattr(item, "Manufacturers", ())), None)
        definition = next((item.InventoryDefinition for item in chain
                           if getattr(item, "InventoryDefinition", None) is not None), None)
        records.append({"balance": balance._path_name(),
                        "chain": [item._path_name() for item in chain],
                        "manufacturer_source": source._path_name() if source is not None else None,
                        "inventory_definition": definition._path_name() if definition is not None else None,
                        "mission_level": level,
                        "target_internal_level": internal_level(definition, level),
                        "manufacturer_grades": [{
                            "manufacturer_index": i, "grade_index": j,
                            "native_internal_level": grade.GradeModifiers.ExpLevel,
                            "min_stage": grade.GameStageRequirement.MinGameStage,
                            "max_stage": grade.GameStageRequirement.MaxGameStage,
                        } for i, row in enumerate(list(source.Manufacturers)[:12])
                            for j, grade in enumerate(list(row.Grades)[:32])] if source is not None else []})
    return records
