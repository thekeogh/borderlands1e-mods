"""Select captured PT2 combat inputs without changing campaign progression."""

import math

from .patches import Patches

ROOT = "gd_Balance_HealthAndDamage."
BRANCHES = {
    "HealthMultipliers.Enemy_Health_ByPlaythrough": (1.0, 2.0),
    "DamageMultipliers.Enemy_Damage_ByPlaythrough": (0.75, 1.15),
    "HealthMultipliers.Guardian_Shield_ByPlaythrough": (1.0, 2.0),
    "HealthMultipliers.Enemy_Health_Exponent_ByPlaythrough_VAULTBOSS": (1.95, 1.5),
}


def branch_inputs(definition):
    conditional = definition.ConditionalInitialization
    if not conditional.bEnabled:
        raise ValueError("Playthrough conditions are disabled")
    branches = {}
    for index, branch in enumerate(conditional.ConditionalExpressionList):
        if len(branch.Expressions) != 1:
            raise ValueError("Unexpected playthrough expression")
        condition = branch.Expressions[0]
        attribute = condition.AttributeOperand1
        if (attribute is None or attribute._path_name().lower() != "d_attributes.balance.playthroughcount"
                or int(condition.ComparisonOperator) != 0 or int(condition.Operand2Usage) != 0
                or condition.AttributeOperand2 is not None):
            raise ValueError("Unexpected playthrough comparison")
        number = condition.ConstantOperand2
        value = branch.BaseValueIfTrue
        if (number not in (1, 2) or number in branches or value.BaseValueAttribute is not None
                or value.InitializationDefinition is not None or value.BaseValueScaleConstant != 1):
            raise ValueError("Unexpected playthrough branch")
        branches[number] = index, float(value.BaseValueConstant)
    if branches.keys() != {1, 2}:
        raise ValueError("Missing native combat branch")
    return branches


class Combat:
    def __init__(self, runtime):
        self.runtime = runtime
        self.patches = Patches()
        self.applied = {}
        self.package_loaded = False

    def update(self):
        if len(self.applied) == len(BRANCHES):
            return
        if not self.package_loaded:
            try:
                self.runtime.sdk.load_package("gd_Balance_HealthAndDamage")
                self.package_loaded = True
            except Exception as exc:
                self.runtime.problem("combat package", exc)
        for name, expected in BRANCHES.items():
            if name in self.applied:
                continue
            try:
                definition = self.runtime.sdk.find_object("AttributeInitializationDefinition", ROOT + name)
                if definition is None:
                    raise ValueError("Definition not loaded")
                branches = branch_inputs(definition)
                index, pt1 = branches[1]
                _, pt2 = branches[2]
                if not all(math.isclose(value, target, abs_tol=1e-6)
                           for value, target in zip((pt1, pt2), expected)):
                    raise ValueError("Unexpected native combat values")
                self.patches.set(definition, ("ConditionalInitialization", "ConditionalExpressionList",
                                              index, "BaseValueIfTrue", "BaseValueConstant"), pt2)
                self.applied[name] = pt2
            except Exception as exc:
                self.runtime.problem("combat " + name, exc)

    def restore(self):
        self.applied.clear()
        return self.patches.restore()

    def snapshot(self):
        return {"pt2_branches_applied": dict(self.applied),
                "missing": [name for name in BRANCHES if name not in self.applied]}
