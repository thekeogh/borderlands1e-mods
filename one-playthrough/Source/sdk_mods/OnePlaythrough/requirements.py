"""Resolve ordinary equipment use requirements without player-proficiency context.

BL1E's context-free math/constant proficiency attributes can override a different
fallback constant. Lady Finger captured internal 5 / requirement 3 even though its
pistol fallback is 1. Evaluate supported static data natively; never touch a
partially initialized actor, edit a shared attribute or guess a universal offset.
"""

import math
import unrealsdk


def _name(obj):
    return str(getattr(obj, "Name", "")) or obj._path_name().rsplit(".", 1)[-1]


def _type(obj):
    return str(obj.Class.Name)


def use_bonus(definition):
    bonus = getattr(definition, "PlayerUseLevelBonus", None)
    if bonus is None:
        return 0
    if bonus.InitializationDefinition is not None:
        raise ValueError("Unsupported dynamic equipment use-level bonus")
    attribute = bonus.BaseValueAttribute
    if attribute is None:
        offset = float(bonus.BaseValueConstant) * float(bonus.BaseValueScaleConstant)
    else:
        name = _name(attribute)
        if not (name.startswith("Proficiency_") and name.endswith("_LevelBonus")):
            raise ValueError("Unsupported equipment use-level attribute")
        contexts = list(getattr(attribute, "ContextResolverChain", ()))
        values = list(getattr(attribute, "ValueResolverChain", ()))
        if (getattr(attribute, "AttributeContextClass", None) is not None
                or not getattr(attribute, "bIsSimpleAttribute", False)
                or len(contexts) != 1 or _type(contexts[0]) != "NoContextNeededAttributeContextResolver"
                or len(values) != 1 or _type(values[0]) not in
                    ("SimpleMathValueResolver", "ConstantAttributeValueResolver")):
            raise ValueError("Unsupported context-dependent equipment use-level bonus")
        # This native static evaluator is used by existing BL1 SDK mods. Passing
        # None is deliberate: the verified resolver explicitly needs no context.
        evaluator = unrealsdk.find_class("AttributeInitializationDefinition").ClassDefaultObject
        offset = float(evaluator.EvaluateInitializationData(bonus, None))
    if not math.isfinite(offset) or offset < 0 or not offset.is_integer():
        raise ValueError("Unsupported fractional/negative equipment use-level bonus")
    return int(offset)


def internal_level(definition, required_level):
    return max(1, int(required_level) + use_bonus(definition))


def describe(definition):
    """Small independent F10 summary, unaffected by the broad definition limit."""
    bonus = getattr(definition, "PlayerUseLevelBonus", None)
    if bonus is None:
        return {"resolved_bonus": 0, "resolution": "no bonus"}
    attribute = bonus.BaseValueAttribute
    report = {"fallback_constant": bonus.BaseValueConstant, "scale": bonus.BaseValueScaleConstant,
              "attribute": attribute._path_name() if attribute is not None else None,
              "initialization": bonus.InitializationDefinition._path_name() if bonus.InitializationDefinition is not None else None}
    if attribute is not None:
        report["contexts"] = [_type(row) for row in list(getattr(attribute, "ContextResolverChain", ()))[:8]]
        report["values"] = [_type(row) for row in list(getattr(attribute, "ValueResolverChain", ()))[:8]]
    try:
        report["resolved_bonus"] = use_bonus(definition)
        report["resolution"] = "native context-free attribute" if attribute is not None else "constant"
    except Exception as exc:
        report["error"] = repr(exc)
    return report
