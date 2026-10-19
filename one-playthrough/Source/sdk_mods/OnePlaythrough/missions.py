"""Mission offers follow the player; accepted missions retain their level."""

from .patches import Patches
from .scaling import character_key

INTRO = "z0_missions.missions.m_introstatesaver"


def states(pc):
    """Read only; never accept, reset, complete or rewrite a mission status."""
    if not pc.MissionPlaythroughData:
        return {}
    return {row.MissionDef._path_name().lower(): (row.MissionDef, int(row.Status))
            for row in pc.MissionPlaythroughData[0].MissionList if row.MissionDef is not None}


class Missions:
    def __init__(self, runtime, store):
        self.runtime = runtime
        self.store = store
        self.patches = Patches()
        self.volatile = {}
        self.token = None
        self.key = None
        self.levels = {}
        self.scopes = []
        self.pending = {}

    def select(self, pc, level, loading=False):
        profile = getattr(pc, "LastLoadedProfile", None)
        token = (pc._get_address(), profile._get_address() if profile is not None else None)
        key = character_key(pc)
        if token != self.token:
            self.volatile = {}
        if key is None:
            levels = self.volatile
        else:
            levels = self.store.levels(key)
            if token == self.token and self.key is None and self.volatile:
                levels.update(self.volatile)
                self.volatile = {}
                self.store.save()
        if loading and level == 1:
            progress = states(pc)
            # Reused save slots must not inherit a deleted character's locks.
            # Reopening an existing level-1 introduction is harmless: its lock is 1.
            if not progress or all(name == INTRO and status < 4 for name, (_, status) in progress.items()):
                levels.clear()
                if key is not None:
                    self.store.save()
        self.token, self.key, self.levels = token, key, levels

    def remember(self, name, level, replace=False):
        if replace or name not in self.levels:
            self.levels[name] = level
            if self.key is not None:
                self.store.save()

    def apply(self, mission, pc, progress=None):
        level = self.runtime.level(pc)
        if level is None or mission is None:
            return None
        self.select(pc, level)
        name = mission._path_name().lower()
        state = (states(pc) if progress is None else progress).get(name, (None, 0))[1]
        if state in (1, 2, 3):
            self.remember(name, level)
            level = self.levels[name]
        elif state == 4:
            level = self.levels.get(name, level)
        # An unaccepted offer ignores stale sidecar data after quit-without-save.
        self.patches.set(mission, ("GameStage",), level)
        self.patches.set(mission, ("ExpLevel",), level)
        self.patches.set(mission, ("MinimumLevel",), 0)
        return level

    def refresh(self, pc):
        progress = states(pc)
        for mission in self.runtime.sdk.find_all("MissionDefinition", exact=False):
            if "default__" not in mission._path_name().lower():
                self.apply(mission, pc, progress)

    def before_accept(self, pc, mission):
        level = self.runtime.level(pc)
        if level is None or mission is None:
            return
        self.select(pc, level)
        name = mission._path_name().lower()
        state = states(pc).get(name, (None, 0))[1]
        self.pending.setdefault((pc._get_address(), name), []).append((state, level))
        self.apply(mission, pc)

    def after_accept(self, pc, mission):
        if mission is None:
            return
        name = mission._path_name().lower()
        stack = self.pending.get((pc._get_address(), name), [])
        pending = stack.pop() if stack else None
        if not stack:
            self.pending.pop((pc._get_address(), name), None)
        level = self.runtime.level(pc)
        if level is None:
            return
        self.select(pc, level)
        state = states(pc).get(name, (None, 0))[1]
        if state in (1, 2, 3, 4) and pending is not None and pending[0] == 0:
            self.remember(name, pending[1], replace=True)
        self.apply(mission, pc)

    def enter_reward(self, mission, pc):
        level = self.apply(mission, pc)
        if level is None or mission.GameStageRegion is None:
            return None
        name = mission.GameStageRegion._path_name().lower()
        token = object()
        self.scopes.append((token, name, level))
        # Native C++ reward calls can bypass Python function hooks. Override the
        # mission's existing regional input for this synchronous call as well.
        try:
            self.runtime.regions.override(name, level)
        except Exception:
            self.exit_reward(token)
            raise
        return token

    def exit_reward(self, token):
        if token is None:
            return
        found = next((i for i, row in enumerate(self.scopes) if row[0] is token), None)
        if found is None:
            return
        _, name, _ = self.scopes.pop(found)
        level = next((row[2] for row in reversed(self.scopes) if row[1] == name), None)
        # Reapply the latest player level, not the old one: a reward can level up.
        self.runtime.regions.override(name, level)

    def restore(self):
        self.scopes.clear()
        self.pending.clear()
        return self.patches.restore()
