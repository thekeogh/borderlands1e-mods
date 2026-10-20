"""Scope equipment reward grades to the mission's locked acceptance level.

InventoryManufacturerBalanceData.Grades[].GradeModifiers.ExpLevel supports an
explicit level (also used by the BL1 SDU Guaranteed mod). Setting GameStage
alone leaves these fixed levels/offsets in control of the generated item.
Never clone a reward balance: its original identity must survive item saving.
"""

from .patches import Patches


def prepare_items(mission, level):
    """Temporarily override native item levels; return an owned rollback scope."""
    patches = Patches()
    try:
        for balance in getattr(mission, "ItemRewards", ()):
            if balance is None:
                continue
            name = balance._path_name().lower()
            # SDUs are progression upgrades, not levelled equipment. Preserve
            # their native level/grade behavior and other mods' SDU guarantees.
            if "storagedeckupgrade" in name or "itemgrade_sdu_" in name:
                continue
            for i, manufacturer in enumerate(getattr(balance, "Manufacturers", ())):
                grades = manufacturer.Grades
                if not grades:
                    continue
                lows = [g.GameStageRequirement.MinGameStage for g in grades]
                highs = [g.GameStageRequirement.MaxGameStage for g in grades]
                for j in range(len(grades)):
                    path = ("Manufacturers", i, "Grades", j)
                    patches.set(balance, (*path, "GradeModifiers", "ExpLevel"), int(level))
                    # Keep native tier selection/weights; extend only end bands
                    # when the accepted mission level is outside their range.
                    if lows[j] == min(lows) and level < lows[j]:
                        patches.set(balance, (*path, "GameStageRequirement", "MinGameStage"), int(level))
                    if highs[j] == max(highs) and level > highs[j]:
                        patches.set(balance, (*path, "GameStageRequirement", "MaxGameStage"), int(level))
        return patches
    except Exception:
        patches.restore()
        raise
