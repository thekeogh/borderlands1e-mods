"""Acceptance levels alongside SDK settings; never edits a .sav file."""

from __future__ import annotations

import json
from pathlib import Path


class MissionLevels:
    def __init__(self, path: Path, legacy_path: Path = None):
        self.path = path
        self.legacy_path = legacy_path
        self.characters = {}
        self.error = None
        self.loaded = False

    def load(self):
        if self.loaded:
            return
        self.loaded = True
        try:
            source = self.path
            if not source.exists():
                if self.legacy_path is None or not self.legacy_path.exists():
                    return
                source = self.legacy_path
            data = json.loads(source.read_text(encoding="utf-8"))
            if data.get("format_version") != 1 or not isinstance(data.get("characters"), dict):
                raise ValueError("Unknown mission-level settings format")
            for key, missions in data["characters"].items():
                if not isinstance(key, str) or not isinstance(missions, dict):
                    raise ValueError("Invalid character record")
                if any(not isinstance(name, str) or type(level) is not int or not 1 <= level <= 69
                       for name, level in missions.items()):
                    raise ValueError("Invalid acceptance level")
            self.characters = data["characters"]
            # Copy valid acceptance levels once when upgrading the renamed mod.
            # Existing new settings always win; never edit the legacy file.
            if source != self.path:
                self.save()
        except Exception as exc:
            # Keep the unreadable file intact; do not replace it with empty data.
            self.error = repr(exc)

    def levels(self, character):
        self.load()
        return self.characters.setdefault(character, {})

    def save(self):
        self.load()
        if self.error is not None:
            return False
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps({"format_version": 1, "characters": self.characters},
                                            indent=2, sort_keys=True) + "\n", encoding="utf-8")
            temporary.replace(self.path)
            return True
        except Exception as exc:
            self.error = repr(exc)
            return False
