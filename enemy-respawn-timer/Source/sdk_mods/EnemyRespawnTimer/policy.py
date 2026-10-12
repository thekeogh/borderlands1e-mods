"""Session-only respawn deadlines. No game objects or native calls here."""

from dataclasses import dataclass, field

DELAYS = {
    "5 minutes": 300,
    "15 minutes": 900,
    "30 minutes": 1800,
    "1 hour": 3600,
    "3 hours": 10800,
    "Forever (until reload)": None,
}
FOREVER_SECONDS = 99_999_999.0


@dataclass
class Group:
    members: set = field(default_factory=set)
    cleared_at: float = None

    def spawned(self, address):
        self.members.add(address)
        self.cleared_at = None

    def died(self, address, now):
        if address not in self.members:
            return False
        self.members.remove(address)
        if not self.members:
            self.cleared_at = now
            return True
        return False

    def deadline(self, choice):
        if self.cleared_at is None:
            return None
        seconds = DELAYS[choice]
        return self.cleared_at + (FOREVER_SECONDS if seconds is None else seconds)

    def blocked(self, now, choice):
        if self.cleared_at is None:
            return False
        seconds = DELAYS[choice]
        return seconds is None or now < self.cleared_at + seconds
