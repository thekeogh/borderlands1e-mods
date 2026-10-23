"""Native initialization with regional floors and rare ordinary-enemy upgrades."""

from itertools import count
from random import randrange
import re

from .named_enemies import named_enemy
from .patches import Patches

EXACT_STAGE = "gd_Balance.EnemyLevel.EnemyLevel_GameStage_exact"
NAMES = count()


DIFFICULTIES = {
    "Easy": (70, 20, 9, 1),
    "Normal": (50, 20, 25, 5),
    "Hard": (20, 5, 55, 20),
}


def bonus(ticket, difficulty="Normal"):
    """Map one of 100 equally likely tickets to the selected ordinary bonus."""
    for extra, weight in enumerate(DIFFICULTIES.get(difficulty, DIFFICULTIES["Normal"])):
        if ticket < weight:
            return extra
        ticket -= weight
    raise ValueError("Enemy difficulty ticket must be between 0 and 99")


def native_level(data, stage):
    """Evaluate only captured native constant/exact/offset level inputs."""
    if data.InitializationDefinition is not None:
        return None
    attribute = data.BaseValueAttribute
    base = float(data.BaseValueConstant)
    if attribute is not None:
        path = attribute._path_name().lower()
        match = re.fullmatch(r"gd_balance\.enemylevel\.enemylevel_gamestage_(exact|plus(\d+)|minus(\d+))", path)
        if match is None:
            return None
        offset = int(match[2]) if match[2] else -int(match[3]) if match[3] else 0
        base = stage + offset
    return int(base * float(data.BaseValueScaleConstant))


def grade_level(default, modifier):
    """Positive grade levels are explicit overrides; zero uses the default."""
    return int(modifier) if modifier > 0 else default + int(modifier)


def hostile(factory, definition, archetype):
    """Inspect data only: never call actor methods on an archetype."""
    if archetype is None:
        return False
    allegiance = getattr(factory, "SpawnAllegiance", None) or getattr(archetype, "Allegiance", None)
    path = allegiance._path_name().lower() if allegiance is not None else ""
    if any(word in path for word in ("friendly", "player", "neutral")):
        return False
    return any(word in path for word in (".creatureenemy.", ".humanoidenemy.", ".humanenemy.", ".enemy.", ".enemies.")) or (
        bool(path) and definition is not None and "_enemies" in definition._path_name().lower())


class Spawns:
    def __init__(self, runtime):
        self.runtime = runtime
        self.roll = lambda: randrange(100)
        self.difficulty = lambda: "Normal"
        self.clones = {}
        self.pins = Patches()
        self.active = False

    def exact_definition(self, definition, base, target, preserve_stage=False):
        """Private persistent data; later spawns never change an existing pawn.

        Keep the original grade-selection bands and combat modifiers. Only the
        experience input changes, retaining any naturally higher grade level.
        The clone stays referenced by the native pawn after factory restoration.
        """
        native = native_level(definition.DefaultExpLevel, base)
        if native is None:
            raise ValueError(f"Unsupported native enemy level formula: {definition._path_name()}")
        # Positive ExpLevel is a fixed level, not an additive bonus. A retained
        # higher fixed value must remain absolute, never become a small +offset
        # that the engine would interpret as a low-level override.
        levels = tuple(max(target, grade_level(native, g.GradeModifiers.ExpLevel))
                       for g in definition.Grades)
        overrides = tuple(level if preserve_stage or level > target else 0 for level in levels)
        # A native floor must keep the original area GameStage for grade/type
        # selection. Use absolute level inputs, not a reduced factory stage.
        default = max(target, native) if preserve_stage or not definition.Grades else None
        key = (definition._get_address(), overrides, default)
        if key in self.clones:
            return self.clones[key]
        sdk = self.runtime.sdk
        exact = sdk.find_object("AttributeDefinition", EXACT_STAGE)
        if exact is None:
            raise ValueError(f"Missing native level attribute: {EXACT_STAGE}")
        clone = sdk.construct_object(definition.Class, definition.Outer,
                                     name=f"OnePlaythrough_Level_{next(NAMES)}",
                                     template_obj=definition)
        # The cache uses the source address. Keep that source alive too, so a
        # map unload cannot recycle its address for a different enemy definition.
        self.pins.pin(definition)
        self.pins.pin(clone)
        self.pins.pin(exact)
        data = clone.DefaultExpLevel
        data.BaseValueConstant = float(default) if default is not None else 0.0
        data.BaseValueAttribute = None if default is not None else exact
        data.InitializationDefinition = None
        data.BaseValueScaleConstant = 1.0
        for grade, fixed in zip(clone.Grades, overrides):
            grade.GradeModifiers.ExpLevel = fixed
        self.clones[key] = clone
        return clone

    def plan(self, factory, player, incoming, vehicle=False):
        base = max(player, int(incoming))
        definition = getattr(factory, "VehicleBalanceDefinition" if vehicle else "PawnBalanceDefinition", None)
        archetype = (getattr(factory, "VehicleArchetype", None) if vehicle else
                     getattr(definition, "AIPawnArchetype", None))
        if definition is not None and hasattr(definition, "Grades"):
            self.runtime.grades.prepare(definition)
        name = named_enemy(definition, archetype)
        # Conservative exclusion for custom named/boss definitions outside the
        # exact-ID list. Unknown identities never receive the ordinary bonus.
        paths = " ".join(obj._path_name().lower() for obj in (definition, archetype) if obj is not None)
        named = name is not None or ".named." in paths or "boss" in paths
        if vehicle or not hostile(factory, definition, archetype):
            return base, None
        natural = native_level(definition.DefaultExpLevel, base)
        if named:
            eligible = [g for g in definition.Grades
                        if g.GameStageRequirement.MinGameStage <= base <= g.GameStageRequirement.MaxGameStage]
            if natural is not None and (natural < player or any(
                    grade_level(natural, g.GradeModifiers.ExpLevel) < player for g in eligible)):
                return base, self.exact_definition(definition, base, player, preserve_stage=True)
            return base, None
        extra = bonus(self.roll(), self.selected_difficulty())
        if natural is None:
            self.runtime.problem("enemy level", ValueError(f"Native formula retained: {paths}"))
            return base, None
        minimum = player + 1
        if not extra:
            eligible = [g for g in definition.Grades
                        if g.GameStageRequirement.MinGameStage <= base <= g.GameStageRequirement.MaxGameStage]
            if natural < minimum or any(grade_level(natural, g.GradeModifiers.ExpLevel) < minimum for g in eligible):
                return base, self.exact_definition(definition, base, minimum, preserve_stage=True)
            return base, None
        # Use the higher of the natural level and bonus target; never add them.
        return base + extra, self.exact_definition(definition, base, base + extra)

    def restore(self):
        self.clones.clear()
        # Do not undo clone data: live pawns can still reference their clone.
        # Native references keep those objects alive after our keep-alive ends.
        return self.pins.restore()

    def selected_difficulty(self):
        value = self.difficulty()
        return value if value in DIFFICULTIES else "Normal"

    def snapshot(self):
        difficulty = self.selected_difficulty()
        return {"difficulty": difficulty,
                "ordinary_tickets": dict(zip(("native", "+1", "+2", "+3"), DIFFICULTIES[difficulty])),
                "native_floor": "max(player level + 1, native spawn level)",
                "named_bonus": False, "private_definitions": len(self.clones)}
