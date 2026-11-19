"""Use native enemy levels during the first campaign."""


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
        self.active = False

    def plan(self, factory, player, incoming, vehicle=False):
        definition = getattr(factory, "VehicleBalanceDefinition" if vehicle else "PawnBalanceDefinition", None)
        archetype = (getattr(factory, "VehicleArchetype", None) if vehicle else
                     getattr(definition, "AIPawnArchetype", None))
        if not hostile(factory, definition, archetype):
            return incoming
        try:
            if definition is not None and hasattr(definition, "Grades"):
                self.runtime.grades.prepare(definition)
        except Exception as exc:
            self.runtime.problem("native enemy grades", exc)
        return max(player, int(incoming))

    def snapshot(self):
        return {"levels": "native enemy rules at max(player level, native area stage)"}
