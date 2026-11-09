"""Read-only mission selection; no mission activation or progress changes."""


def map_name(value):
    value = str(value).split('?', 1)[0].replace('\\', '/').rsplit('/', 1)[-1]
    if value.lower().endswith(('.umap', '.upk')):
        value = value.rsplit('.', 1)[0]
    return value.rsplit('.', 1)[-1].lower()


def waypoint_for(row, current_map, tracked, include_turn_ins=True):
    mission = row.MissionDef
    if mission is None or mission._path_name().lower() in tracked:
        return None
    status = int(row.Status)
    if status == 1:
        if getattr(mission, 'bDoNotResolveWaypoint', False):
            return None
        waypoint = getattr(mission, 'TargetWaypointDefinition', None)
    elif status == 2 and include_turn_ins:
        waypoint = getattr(mission, 'TurnInWaypointDefinition', None)
    else:
        # Never show offers, completed/redeemed missions, or unknown states.
        return None
    if waypoint is None or map_name(waypoint.PersistentLevelName) != map_name(current_map):
        return None
    return waypoint


def unfinished_number(row):
    """Numbered waypoints are one-based; zero denotes a mission-wide marker.

    Use native required/current counts, including objectives requiring several
    kills/items. Missing requirements are unknown, not assumed to be one.
    """
    required = list(getattr(row.MissionDef, 'Objectives', []))
    progress = list(getattr(row, 'Objectives', []))
    if not required or len(progress) != len(required):
        return None
    for index,(definition,status) in enumerate(zip(required,progress)):
        count = getattr(definition,'ObjectiveCount',None)
        amount = getattr(status,'CurrentAmount',None)
        if count is None or amount is None or int(count) <= 0:
            return None
        if int(amount) < int(count):
            return index+1
    return None


def select_waypoint(row, actors):
    """Choose at most one real actor per mission, without switching missions."""
    if not actors:
        return None,'unloaded'
    ordered = sorted(actors,key=lambda a:(int(getattr(a,'WaypointNumber',0)),a._path_name()))
    generic = [a for a in ordered if int(getattr(a,'WaypointNumber',0)) == 0]
    if generic:
        return generic[0],'mission-wide'
    number = unfinished_number(row) if int(row.Status) == 1 else None
    if number is not None:
        match = next((a for a in ordered if int(getattr(a,'WaypointNumber',0)) == number),None)
        return match,'first-unfinished' if match is not None else 'current-waypoint-unloaded'
    # Some definitions expose an overview/numbered location without a matching
    # objective counter. Keep a deterministic representative, never all of them.
    return ordered[0],'lowest-number-fallback'
