"""Model the SDK's main-menu settings lifecycle; no native engine execution.

SDK Mod.enable()/disable() call on_enable/on_disable before saving. The SDK's
default_save_mod_settings() opens settings_file directly, without mkdir().
Sources: https://github.com/bl-sdk/mods_base/blob/master/mod.py
         https://github.com/bl-sdk/mods_base/blob/master/settings.py
"""

import json
from pathlib import Path
import re
import tempfile
import unittest

from test_one_playthrough import Harness, SOURCE


class SDKSettingsMod:
    """The relevant SDK state/load/write behavior, with actual mod callbacks."""
    def __init__(self, *, settings_file, on_enable, on_disable, keybinds, options, **_kwargs):
        self.settings_file = settings_file
        self.on_enable, self.on_disable = on_enable, on_disable
        self.keybinds = keybinds
        self.options = options
        self.is_enabled = False
        metadata = (SOURCE / "pyproject.toml").read_text()
        self.auto_enable = re.search(r"^auto_enable = (true|false)$", metadata, re.M).group(1) == "true"
        self.load_settings()

    def save_settings(self):
        data = {"keybinds": {bind.identifier: bind.key for bind in self.keybinds}}
        data["options"] = {o.identifier: o.value for o in self.options if hasattr(o, "value")}
        if self.auto_enable:
            data["enabled"] = self.is_enabled
        # Deliberately match the SDK: parent creation is the mod's responsibility.
        with self.settings_file.open("w") as stream:
            json.dump(data, stream)

    def load_settings(self):
        try:
            data = json.loads(self.settings_file.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return
        for option in self.options:
            if option.identifier in data.get("options", {}):
                option.value = data["options"][option.identifier]
        for bind in self.keybinds:
            if bind.identifier in data.get("keybinds", {}):
                bind.key = data["keybinds"][bind.identifier]
        if self.auto_enable and data.get("enabled", False):
            self.enable()

    def enable(self):
        if self.is_enabled:
            return
        self.is_enabled = True
        self.on_enable()
        if self.auto_enable:
            self.save_settings()

    def disable(self):
        if not self.is_enabled:
            return
        self.is_enabled = False
        self.on_disable()
        if self.auto_enable:
            self.save_settings()


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.settings = Path(self.tmp.name) / "OnePlaythrough/mod.json"

    def boot(self):
        return Harness(self.tmp.name, registration_factory=SDKSettingsMod, in_menu=True)

    def test_first_menu_enable_persists_and_next_boot_restores_enabled_state(self):
        first = self.boot()
        self.assertFalse(first.registered_mod.is_enabled)
        first.registered_mod.enable()
        self.assertTrue(json.loads(self.settings.read_text())["enabled"])
        self.assertFalse((self.settings.parent / "mission-levels.json").exists())
        second = self.boot()
        self.assertTrue(second.registered_mod.is_enabled)
        self.assertTrue(second.runtime.enabled)

    def test_manual_disable_remains_disabled_on_next_boot(self):
        first = self.boot()
        first.registered_mod.enable()
        first.registered_mod.disable()
        self.assertFalse(json.loads(self.settings.read_text())["enabled"])
        second = self.boot()
        self.assertFalse(second.registered_mod.is_enabled)
        self.assertFalse(second.runtime.enabled)

    def test_saved_difficulty_survives_menu_restart_and_upgrade_defaults_to_normal(self):
        self.settings.parent.mkdir(parents=True)
        self.settings.write_text(json.dumps({"enabled": True}))
        first = self.boot()
        self.assertEqual(first.mod.enemy_difficulty.value, "Normal")
        self.assertEqual(first.mod.enemy_difficulty.choices, ["Easy", "Normal", "Hard"])
        first.mod.enemy_difficulty.value = "Hard"
        first.registered_mod.save_settings()
        second = self.boot()
        self.assertEqual(second.mod.enemy_difficulty.value, "Hard")
        self.assertEqual(second.runtime.spawns.snapshot()["difficulty"], "Hard")
        self.assertTrue(second.registered_mod.is_enabled)

    def test_saved_keybind_and_mission_levels_survive_enable_and_restart(self):
        self.settings.parent.mkdir(parents=True)
        self.settings.write_text(json.dumps({"enabled": False, "keybinds": {
            "Export One Playthrough diagnostics": "F9"}}))
        missions = self.settings.parent / "mission-levels.json"
        original = '{"format_version":1,"characters":{"slot:1:soldier":{"mission":7}}}'
        missions.write_text(original)
        first = self.boot()
        self.assertEqual(first.registration["keybinds"][0].key, "F9")
        first.registered_mod.enable()
        second = self.boot()
        self.assertEqual(second.registration["keybinds"][0].key, "F9")
        self.assertEqual(missions.read_text(), original)


if __name__ == "__main__":
    unittest.main()
