"""Read a verified zero-proficiency expression without changing gameplay."""

import math

PROFICIENCY_ATTRIBUTES = frozenset(
    f"Proficiency_{kind}_LevelBonus"
    for kind in ("Pistol", "Shotgun", "Sniper", "SMG", "RocketLauncer", "Eridan", "CombatRifle")
)
SKILL_PREFIX = "gd_skills_common.SkillGrades.SkillGrade_WeapProficiency_"


def constant_value(data):
    if (data is None or data.BaseValueAttribute is not None
            or data.InitializationDefinition is not None):
        return None
    return float(data.BaseValueConstant) * float(data.BaseValueScaleConstant)


def zero_proficiency_bonus(definition):
    """Read only the captured formula: proficiency * scale + constant.

    EvaluateInitializationData(bonus, None) returns the definition fallback in
    the live game, even for a NoContextNeeded root resolver. That is NOT the
    zero-proficiency result. Instead substitute zero for the verified skill
    input and read the constant operand. Unknown expressions stay native.
    """
    bonus = definition.PlayerUseLevelBonus
    if bonus.InitializationDefinition is not None:
        return None
    attribute = bonus.BaseValueAttribute
    if attribute is None:
        return constant_value(bonus)
    contexts = list(attribute.ContextResolverChain)
    values = list(attribute.ValueResolverChain)
    if (str(attribute.Name) not in PROFICIENCY_ATTRIBUTES or attribute.AttributeContextClass is not None
            or not attribute.bIsSimpleAttribute or len(contexts) != 1
            or str(contexts[0].Class.Name) != "NoContextNeededAttributeContextResolver"
            or len(values) != 1):
        return None
    resolver = values[0]
    # Captured native enum values: attribute first argument (1), addition (0).
    if (str(resolver.Class.Name) != "SimpleMathValueResolver"
            or getattr(resolver, "Arg1Option", None) != 1
            or getattr(resolver, "Operand", None) != 0):
        return None
    first = resolver.Arg1Attribute
    skill = first.BaseValueAttribute
    # Any standard weapon proficiency is zero for this display calculation.
    # Do not derive the skill spelling from the root attribute's legacy typos.
    if (first.InitializationDefinition is not None or skill is None
            or not skill._path_name().startswith(SKILL_PREFIX)
            or float(first.BaseValueConstant) != 0
            or not math.isfinite(float(first.BaseValueScaleConstant))):
        return None
    constant = constant_value(resolver.Argument)
    if constant is None:
        return None
    return constant * float(bonus.BaseValueScaleConstant)


def level_details(weapon):
    result = {"ordinary_required_level": None, "resolved_bonus": None,
              "resolution": "unsupported"}
    if weapon is None or str(weapon.Class.Name) != "WillowWeapon":
        return result
    definition = weapon.GetInventoryDefinition()
    if definition is None:
        result["resolution"] = "uninitialized"
        return result
    if not definition.bUsesPlayerLevelRequirement:
        result["resolution"] = "no_level_requirement"
        return result
    value = zero_proficiency_bonus(definition)
    # Do not invent rounding rules or hide an incorrect level behind a cap.
    if value is None or not math.isfinite(value) or value < 0 or not value.is_integer():
        return result
    result.update(ordinary_required_level=max(1, int(weapon.ExpLevel) - int(value)),
                  resolved_bonus=int(value), resolution=("constant" if
                      definition.PlayerUseLevelBonus.BaseValueAttribute is None
                      else "zero_proficiency_expression"))
    return result


def ordinary_level(weapon):
    return level_details(weapon)["ordinary_required_level"]
