"""Coordinate data-only scaling with native initialization and save lifecycle."""

from .missions import Missions
from .scaling import Grades, Regions, player_level
from .spawns import Spawns


class Runtime:
    def __init__(self, sdk, store):
        self.sdk = sdk
        self.store = store
        self.enabled = False
        self.regions = Regions(sdk)
        self.grades = Grades()
        self.missions = Missions(self, store)
        self.spawns = Spawns(self)
        self.problems = []
        self.syncing = False

    def problem(self, context, exc):
        message = f"{context}: {exc!r}"
        if message not in self.problems and len(self.problems) < 16:
            self.problems.append(message)

    def level(self, pc, profile=None):
        if not self.enabled:
            return None
        try:
            return player_level(pc, profile)
        except Exception as exc:
            self.problem("player context", exc)
            return None

    def sync(self, pc, profile=None, loading=False):
        if self.syncing:
            return
        self.syncing = True
        try:
            level = self.level(pc, profile)
            if level is None:
                self.restore()
                return
            self.regions.update(level)
            self.missions.select(pc, level, loading=loading)
            # A profile PRE hook prepares regions only; mission data still belongs
            # to the old profile until the native profile application completes.
            if profile is None:
                self.missions.refresh(pc)
        except Exception as exc:
            self.problem("synchronize", exc)
        finally:
            self.syncing = False

    def ensure(self, pc):
        level = self.level(pc)
        if level is None:
            self.restore()
        elif self.regions.level != level:
            self.sync(pc)
        return level

    def restore(self):
        for error in self.missions.restore() + self.grades.restore() + self.spawns.restore():
            self.problem("restore", error)
        self.regions.restore()

    def disable(self):
        self.enabled = False
        self.restore()

    def snapshot(self):
        return {"enabled": self.enabled, "world_base_level": self.regions.level,
                "enemy_policy": self.spawns.snapshot(),
                "regions": self.regions.snapshot(), "character": self.missions.key,
                "mission_levels": dict(self.missions.levels),
                "reward_scopes": len(self.missions.scopes), "settings_error": self.store.error,
                "problems": list(self.problems)}
