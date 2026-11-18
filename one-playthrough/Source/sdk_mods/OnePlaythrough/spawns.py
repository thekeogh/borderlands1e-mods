"""Native initialization with regional floors and rare ordinary-enemy upgrades."""

from itertools import count
from random import randrange
import re

from .named_enemies import named_enemy
from .patches import Patches

EXACT_STAGE = "gd_Balance.EnemyLevel.EnemyLevel_GameStage_exact"
NAMES = count()


DIFFICULTIES = {
    "Easy": (0, 40, 60),
    "Medium": (0, 0, 60, 40),
    "Hard": (0, 0, 0, 80, 20),
    "Very Hard": (0, 0, 0, 20, 75, 5),
}


FIXED_NAMED_OFFSETS = {"Easy": 2, "Medium": 2, "Hard": 3, "Very Hard": 4}

# Percentages at bracket midpoints. Integer tenths retain every interpolated
# probability exactly: ten levels between anchors, 1,000 equally likely tickets.
ADAPTIVE_ANCHORS = (
    (5,  (0, 20, 80, 0, 0, 0)),
    (15, (0, 0, 80, 20, 0, 0)),
    (25, (0, 0, 40, 60, 0, 0)),
    (35, (0, 0, 20, 70, 10, 0)),
    (45, (0, 0, 0, 70, 30, 0)),
    (55, (0, 0, 0, 45, 52, 3)),
    (65, (0, 0, 0, 20, 75, 5)),
)


def adaptive_weights(player):
    """Return 1,000-ticket weights, blending by player level, never area level."""
    if player <= ADAPTIVE_ANCHORS[0][0]:
        return tuple(weight * 10 for weight in ADAPTIVE_ANCHORS[0][1])
    for (lower, left), (upper, right) in zip(ADAPTIVE_ANCHORS, ADAPTIVE_ANCHORS[1:]):
        if player <= upper:
            return tuple(a * (upper - player) + b * (player - lower)
                         for a, b in zip(left, right))
    return tuple(weight * 10 for weight in ADAPTIVE_ANCHORS[-1][1])


def adaptive_bonus(ticket, player):
    if not 0 <= ticket < 1000:
        raise ValueError("Adaptive enemy ticket must be between 0 and 999")
    for extra, weight in enumerate(adaptive_weights(player)):
        if ticket < weight:
            return extra
        ticket -= weight
    raise ValueError("Invalid Adaptive enemy weights")


def named_offset(difficulty, player):
    if difficulty == "Adaptive":
        return 2 if player < 23 else 3 if player < 53 else 4
    return FIXED_NAMED_OFFSETS.get(difficulty)


def bonus(ticket, difficulty="Medium"):
    """Map one of 100 equally likely tickets to the selected ordinary bonus."""
    for extra, weight in enumerate(DIFFICULTIES.get(difficulty, DIFFICULTIES["Medium"])):
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
        self.adaptive_roll = lambda: randrange(1000)
        self.difficulty = lambda: "Medium"
        self.clones = {}
        self.pins = Patches()
        self.active = False

    def exact_definition(self, definition, base, target, preserve_stage=False, force_exact=False):
        """Private persistent data; later spawns never change an existing pawn.

        Keep the original grade-selection bands and combat modifiers. Only the
        experience input changes, retaining any naturally higher grade level.
        Debug and fixed named/boss policies replace higher native levels.
        The clone stays referenced by the native pawn after factory restoration.
        """
        native = None if force_exact else native_level(definition.DefaultExpLevel, base)
        if native is None and not force_exact:
            raise ValueError(f"Unsupported native enemy level formula: {definition._path_name()}")
        # Positive ExpLevel is a fixed level, not an additive bonus. A retained
        # higher fixed value must remain absolute, never become a small +offset
        # that the engine would interpret as a low-level override.
        levels = tuple(target if force_exact else max(target, grade_level(native, g.GradeModifiers.ExpLevel))
                       for g in definition.Grades)
        overrides = tuple(level if force_exact or preserve_stage or level > target else 0 for level in levels)
        # A native floor must keep the original area GameStage for grade/type
        # selection. Use absolute level inputs, not a reduced factory stage.
        default = target if force_exact else (max(target, native) if preserve_stage or not definition.Grades else None)
        key = (definition._get_address(), overrides, default)
        if key in self.clones:
            return self.clones[key]
        sdk = self.runtime.sdk
        exact = None if force_exact else sdk.find_object("AttributeDefinition", EXACT_STAGE)
        if exact is None and not force_exact:
            raise ValueError(f"Missing native level attribute: {EXACT_STAGE}")
        clone = sdk.construct_object(definition.Class, definition.Outer,
                                     name=f"OnePlaythrough_Level_{next(NAMES)}",
                                     template_obj=definition)
        # The cache uses the source address. Keep that source alive too, so a
        # map unload cannot recycle its address for a different enemy definition.
        self.pins.pin(definition)
        self.pins.pin(clone)
        if exact is not None:
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
        if not hostile(factory, definition, archetype):
            return base, None
        if self.selected_difficulty() == 'Debug':
            if definition is None or not hasattr(definition,'DefaultExpLevel') or not hasattr(definition,'Grades'):
                self.runtime.problem('debug enemy level',ValueError(f'Unsupported balance layout: {paths}'))
                return base,None
            # Preserve grade-selection stage and identity, but bypass level
            # floors/offsets for testing. No random roll, even for bosses.
            return base,self.exact_definition(definition,base,max(1,player-30),force_exact=True)
        if named:
            if definition is None or not hasattr(definition,'DefaultExpLevel') or not hasattr(definition,'Grades'):
                self.runtime.problem('named enemy level',ValueError(f'Unsupported named balance layout: {paths}'))
                return base,None
            fixed = named_offset(self.selected_difficulty(), player)
            if fixed is not None:
                return base,self.exact_definition(definition,base,player+fixed,force_exact=True)
            natural = native_level(definition.DefaultExpLevel,base)
            if natural is None:
                self.runtime.problem('named enemy level',ValueError(f'Native formula retained: {paths}'))
                return base,None
            minimum = player+3
            eligible = [g for g in definition.Grades
                        if g.GameStageRequirement.MinGameStage <= base <= g.GameStageRequirement.MaxGameStage]
            if natural < minimum or any(grade_level(natural,g.GradeModifiers.ExpLevel) < minimum for g in eligible):
                return base,self.exact_definition(definition,base,minimum,preserve_stage=True)
            return base,None
        if vehicle:
            return base,None
        natural = native_level(definition.DefaultExpLevel, base)
        extra = (adaptive_bonus(self.adaptive_roll(), player) if self.selected_difficulty() == 'Adaptive'
                 else bonus(self.roll(), self.selected_difficulty()))
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
        if value == "Normal":
            value = "Medium"
        return value if value in DIFFICULTIES or value in ('Debug', 'Adaptive') else "Medium"

    def snapshot(self):
        difficulty = self.selected_difficulty()
        debug_rule = 'exactly max(1, player level - 30)'
        report = {"difficulty": difficulty,
                "ordinary_tickets": {"native" if extra == 0 else f"+{extra}": weight
                                     for extra, weight in enumerate(DIFFICULTIES.get(difficulty,()))},
                "native_floor": debug_rule if difficulty == 'Debug' else "max(player level + 1, native spawn level)",
                "named_bonus": False, "named_level": (debug_rule if difficulty == 'Debug' else
                    f"exactly player level + {FIXED_NAMED_OFFSETS[difficulty]}"
                    if difficulty in FIXED_NAMED_OFFSETS else "max(player level + 3, native spawn level)"),
                "private_definitions": len(self.clones)}
        if difficulty == 'Adaptive':
            player = self.runtime.regions.level
            report['ordinary_tickets'] = ({"native" if extra == 0 else f"+{extra}": weight / 10
                                          for extra, weight in enumerate(adaptive_weights(player))}
                                         if player is not None else {})
            report['named_level'] = (f"exactly player level + {named_offset(difficulty, player)}"
                                     if player is not None else "player +2 through 22; +3 through 52; +4 from 53")
            report['adaptive'] = {
                'player_level': player, 'ticket_count': 1000, 'weight_unit': 'percent',
                'blend': 'linear between player levels 5, 15, 25, 35, 45, 55, 65; endpoints clamped',
                'anchors': [{'player_level': level, 'percentages': list(weights)}
                            for level, weights in ADAPTIVE_ANCHORS],
                'named_thresholds': {'1-22': 2, '23-52': 3, '53+': 4},
            }
        return report
