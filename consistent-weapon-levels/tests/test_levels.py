"""SDK stubs check hook boundaries/restoration; these do not run native BL1E."""

from contextlib import contextmanager
from pathlib import Path
from types import ModuleType, SimpleNamespace as NS
from unittest.mock import patch
import json
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Source/sdk_mods/ConsistentWeaponLevels/__init__.py"
FIXTURE = json.loads((ROOT / "tests/fixtures/bl1e_levels.json").read_text())


class Hook:
    def __init__(self, path, kind, identifier, fn):
        self.path, self.kind, self.hook_identifier, self.fn = path, kind, identifier, fn

    def __call__(self, *args):
        return self.fn(*args)

    def get_active_count(self):
        return 1


def load_mod():
    module = ModuleType("ConsistentWeaponLevels")
    module.__version__ = "1.0.0"
    module.__version_info__ = (1, 0, 0)
    base = ModuleType("mods_base")
    base.SETTINGS_DIR = ROOT / "test-settings"
    base.get_pc = lambda: None
    base.ButtonOption = lambda title, **kw: NS(title=title, **kw)
    base.build_mod = lambda **kw: setattr(module, "registration", kw)
    base.hook = lambda path, kind="PRE", **kw: lambda fn: Hook(
        path, kind, kw.get("hook_identifier", fn.__name__), fn)
    sdk = ModuleType("unrealsdk")
    sdk.find_all = lambda cls: []
    sdk.logging = NS(info=lambda s: None, warning=lambda s: None)
    hooks = ModuleType("unrealsdk.hooks")
    hooks.Type = NS(PRE="PRE", POST_UNCONDITIONAL="POST_UNCONDITIONAL")
    hooks.Block = object()
    calls = NS(depth=0)

    @contextmanager
    def prevent():
        calls.depth += 1
        try:
            yield
        finally:
            calls.depth -= 1

    hooks.prevent_hooking_direct_calls = prevent
    with patch.dict(sys.modules, {"mods_base": base, "unrealsdk": sdk,
                                "unrealsdk.hooks": hooks}):
        exec(compile(SOURCE.read_text(), str(SOURCE), "exec"), module.__dict__)
    module.direct_calls = calls
    module.on_enable()
    return module


class Weapon:
    def __init__(self, *, exp=71, base=2, kind="Sniper", proficiency=50):
        self.Class = NS(Name="WillowWeapon")
        self.ExpLevel = exp
        self.proficiency = proficiency
        self.attribute = NS(Name=f"Proficiency_{kind}_LevelBonus")
        self.bonus = NS(BaseValueAttribute=self.attribute, BaseValueConstant=base,
                        InitializationDefinition=None, BaseValueScaleConstant=1)
        self.definition = NS(PlayerUseLevelBonus=self.bonus)
        self.Owner = object()
        self.calls = []
        self.GetControllerPlayerExpLevelRequiredToUse = self.native

    def _path_name(self):
        return "TheWorld.Weapon"

    def GetInventoryDefinition(self):
        return self.definition

    def native(self, argument):
        self.calls.append(argument)
        # A model of the observed proficiency expression and a delegated clamp.
        # The mod itself does not implement this expression or these limits.
        value = (self.proficiency * .25 + 2 if self.bonus.BaseValueAttribute
                 else self.bonus.BaseValueConstant)
        return max(1, min(69, self.ExpLevel - int(value * self.bonus.BaseValueScaleConstant)))


class LevelTests(unittest.TestCase):
    def setUp(self):
        self.mod = load_mod()
        self.weapon = Weapon()
        self.controller = object()

    def enter(self):
        self.mod.card_enter(None, None, None, None)

    def exit(self):
        self.mod.card_exit(None, None, None, None)

    def query(self, weapon=None, function=None):
        weapon = weapon or self.weapon
        return self.mod.controller_level(weapon, NS(OtherController=self.controller),
                                         None, function or weapon.native)

    def test_equipped_57_becomes_backpack_69(self):
        self.assertEqual(self.weapon.native(self.controller), 57)
        self.enter()
        self.assertEqual(self.query(), (self.mod.Block, 69))
        self.exit()
        self.assertEqual(self.weapon.native(self.controller), 57)

    def test_outside_cards_does_not_recall_or_change_native_query(self):
        self.assertIsNone(self.query())
        self.assertEqual(self.weapon.calls, [])
        self.assertIs(self.weapon.bonus.BaseValueAttribute, self.weapon.attribute)

    def test_pawn_wrapper_is_also_corrected(self):
        pawn = object()
        self.enter()
        result = self.mod.pawn_level(self.weapon, NS(Other=pawn), None, self.weapon.native)
        self.assertEqual(result[1], 69)
        self.assertIs(self.weapon.calls[-1], pawn)

    def test_native_receives_original_controller(self):
        self.enter()
        self.query()
        self.assertIs(self.weapon.calls[-1], self.controller)

    def test_nested_cards_keep_scope_until_outer_exit(self):
        self.enter()
        self.enter()
        self.exit()
        self.assertIsNotNone(self.query())
        self.exit()
        self.assertIsNone(self.query())
        self.assertEqual(self.mod._depth, {})

    def test_all_card_entries_have_unconditional_exit(self):
        hooks = self.mod.registration["hooks"]
        for path in self.mod.CARD_FUNCTIONS:
            matches = [h for h in hooks if h.path == path]
            self.assertEqual({h.kind for h in matches}, {"PRE", "POST_UNCONDITIONAL"})
            self.assertEqual(len(matches), 2)

    def test_blocked_card_unconditional_exit_cleans_scope(self):
        for h in self.mod._card_hooks[:2]:
            h(None, None, None, None)
        self.assertIsNone(self.query())

    def test_no_gameplay_or_equipping_entry_points(self):
        paths = [h.path for h in self.mod.registration["hooks"]]
        self.assertFalse(any(p.endswith((":WeaponChanged", ":SetCurrentWeapon",
                                         ":IsLevelRequirementMet", ":CanBeUsedBy")) for p in paths))

    def test_display_scope_is_thread_specific(self):
        self.enter()
        results = []
        thread = threading.Thread(target=lambda: results.append(self.query()))
        thread.start()
        thread.join()
        self.assertEqual(results, [None])
        self.assertIsNotNone(self.query())

    def test_disable_inside_scope_clears_state(self):
        self.enter()
        self.mod.on_disable()
        self.assertIsNone(self.query())
        self.exit()
        self.assertEqual(self.mod._depth, {})
        self.mod.on_enable()
        self.assertIsNone(self.query())

    def test_disabled_cards_do_not_enter_scope(self):
        self.mod.on_disable()
        self.enter()
        self.assertEqual(self.mod._depth, {})

    def test_native_exception_restores_definition_and_falls_through(self):
        def fail(arg):
            self.assertIsNone(self.weapon.bonus.BaseValueAttribute)
            raise RuntimeError("simulated native error")
        self.enter()
        self.assertIsNone(self.query(function=fail))
        self.assertIs(self.weapon.bonus.BaseValueAttribute, self.weapon.attribute)
        self.assertEqual(self.mod._calculating, set())
        self.assertEqual(self.mod.direct_calls.depth, 0)
        self.assertEqual(len(self.mod._errors), 1)
        self.assertEqual(self.query()[1], 69)

    def test_recursion_guard_for_nested_native_wrappers(self):
        self.enter()
        def nested(arg):
            self.assertEqual(self.mod.direct_calls.depth, 1)
            self.assertIsNone(self.query())
            return self.weapon.native(arg)
        self.assertEqual(self.query(function=nested)[1], 69)

    def test_non_weapon_equipment_is_unchanged(self):
        self.weapon.Class.Name = "WillowEquipAbleItem"
        self.enter()
        self.assertIsNone(self.query())
        self.assertIs(self.weapon.bonus.BaseValueAttribute, self.weapon.attribute)

    def test_custom_attributes_and_initializers_are_unchanged(self):
        self.enter()
        self.weapon.attribute.Name = "CustomLevelBonus"
        self.assertIsNone(self.query())
        self.weapon.attribute.Name = "Proficiency_Sniper_LevelBonus"
        self.weapon.bonus.InitializationDefinition = object()
        self.assertIsNone(self.query())

    def test_already_context_free_definition_is_unchanged(self):
        self.weapon.bonus.BaseValueAttribute = None
        self.enter()
        self.assertIsNone(self.query())
        self.assertEqual(self.weapon.calls, [])

    def test_each_exported_weapon_uses_its_own_fallback(self):
        self.enter()
        for path, fields in FIXTURE["weapon_level_bonuses"].items():
            with self.subTest(path=path):
                base = fields["BaseValueConstant"]
                if fields["BaseValueAttribute"] is None:
                    w = Weapon()
                    w.bonus.BaseValueAttribute = None
                    self.assertIsNone(self.query(w))
                    continue
                attr = fields["BaseValueAttribute"]["ref"].split(".")[-1]
                w = Weapon(exp=40)
                w.attribute.Name = attr
                w.bonus.BaseValueConstant = base
                self.assertEqual(self.query(w)[1], 40 - int(base))
                self.assertIs(w.bonus.BaseValueAttribute, w.attribute)

    def test_game_clamp_is_delegated(self):
        self.enter()
        self.assertEqual(self.query(Weapon(exp=1))[1], 1)
        self.assertEqual(self.query(Weapon(exp=1000))[1], 69)

    def test_scale_constant_is_preserved(self):
        self.weapon.bonus.BaseValueScaleConstant = 3
        self.enter()
        self.assertEqual(self.query()[1], 65)
        self.assertEqual(self.weapon.bonus.BaseValueScaleConstant, 3)

    def test_source_export_confirms_signatures_and_proficiency_expression(self):
        for fn, arg in [("GetControllerPlayerExpLevelRequiredToUse", "OtherController"),
                        ("GetPlayerExpLevelRequiredToUse", "Other")]:
            fields = FIXTURE["functions"]["Engine.WillowInventory:" + fn]["fields"]
            self.assertEqual([f["name"] for f in fields if f["PropertyFlags"] == 128], [arg])
        for resolver in FIXTURE["proficiency_resolvers"].values():
            self.assertEqual(resolver["Arg1Attribute"]["fields"]["BaseValueScaleConstant"], .25)
            self.assertEqual(resolver["Argument"]["fields"]["BaseValueConstant"], 2)

    def test_diagnostic_export_restores_definitions(self):
        pc = NS(Pawn=object())
        self.weapon.Owner = pc.Pawn
        other = Weapon()
        self.mod.get_pc = lambda: pc
        self.mod.find_all = lambda cls: [other, self.weapon]
        with tempfile.TemporaryDirectory() as temp:
            self.mod.SETTINGS_DIR = Path(temp)
            self.mod.export_diagnostics()
            p = next(Path(temp).rglob("*.json"))
            d = json.loads(p.read_text())
        self.assertEqual(len(d["weapons"]), 1)
        w = d["weapons"][0]
        self.assertEqual(w["native_level_with_controller"], 57)
        self.assertEqual(w["card_level_without_proficiency"], 69)
        self.assertIs(self.weapon.bonus.BaseValueAttribute, self.weapon.attribute)
        self.assertEqual(self.mod._depth, {})


if __name__ == "__main__":
    unittest.main()
