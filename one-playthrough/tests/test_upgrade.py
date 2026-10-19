"""Preserve accepted mission levels when upgrading the renamed mod."""

import json
from pathlib import Path
import tempfile
import unittest

from test_one_playthrough import Harness


class UpgradeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.h = Harness(self.tmp.name)
        self.legacy = Path(self.tmp.name) / "Playthrough3/mission-levels.json"
        self.current = Path(self.tmp.name) / "OnePlaythrough/mission-levels.json"

    def payload(self, level):
        return {"format_version": 1, "characters": {
            "slot:1:gd_playerclassid.soldier": {self.h.mission.path.lower(): level},
            "slot:2:gd_playerclassid.soldier": {self.h.mission.path.lower(): 20},
        }}

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def test_upgrade_copies_all_character_locks_and_preserves_legacy_bytes(self):
        self.write(self.legacy, self.payload(7))
        before = self.legacy.read_bytes()
        self.h.state()
        self.h.enable(8)
        self.assertEqual(self.h.mission.ExpLevel, 7)
        self.assertEqual(json.loads(self.current.read_text()), self.payload(7))
        self.assertEqual(self.legacy.read_bytes(), before)
        self.assertEqual(self.h.runtime.store.path, self.current)

    def test_existing_new_settings_take_priority_over_legacy(self):
        self.write(self.legacy, self.payload(7))
        self.write(self.current, self.payload(6))
        self.h.state()
        self.h.enable(8)
        self.assertEqual(self.h.mission.ExpLevel, 6)
        self.assertEqual(json.loads(self.legacy.read_text()), self.payload(7))

    def test_migration_is_not_repeated_on_later_loads(self):
        self.write(self.legacy, self.payload(7))
        self.h.enable(8)
        self.write(self.legacy, self.payload(5))
        reloaded = Harness(self.tmp.name)
        reloaded.state()
        reloaded.enable(9)
        self.assertEqual(reloaded.mission.ExpLevel, 7)

    def test_corrupt_legacy_is_preserved_without_creating_empty_new_file(self):
        self.legacy.parent.mkdir(parents=True)
        self.legacy.write_text("corrupt settings")
        self.h.enable(8)
        self.assertIsNotNone(self.h.runtime.store.error)
        self.assertFalse(self.current.exists())
        self.assertEqual(self.legacy.read_text(), "corrupt settings")

    def test_invalid_legacy_levels_are_not_copied(self):
        self.write(self.legacy, self.payload(0))
        self.h.enable(8)
        self.assertIsNotNone(self.h.runtime.store.error)
        self.assertFalse(self.current.exists())

    def test_corrupt_new_settings_do_not_fall_back_to_stale_legacy(self):
        self.write(self.legacy, self.payload(7))
        self.current.parent.mkdir(parents=True, exist_ok=True)
        self.current.write_text("corrupt new settings")
        self.h.enable(8)
        self.assertIsNotNone(self.h.runtime.store.error)
        self.assertEqual(self.current.read_text(), "corrupt new settings")

    def test_new_install_does_not_create_or_depend_on_old_settings_directory(self):
        self.h.enable(8)
        self.h.accept()
        self.assertTrue(self.current.exists())
        self.assertFalse(self.legacy.parent.exists())


if __name__ == "__main__":
    unittest.main()
