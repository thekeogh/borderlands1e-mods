"""SDK/native models verify isolation and captured regressions, not Windows rendering."""

from contextlib import contextmanager, ExitStack
import importlib
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace as NS
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'Source/sdk_mods/ConsistentWeaponLevels'
FIXTURE = json.loads((ROOT / 'tests/fixtures/bl1e_levels.json').read_text())
MISMATCH = json.loads((ROOT / 'tests/fixtures/bl1e_level_mismatch.json').read_text())
NULL_CONTEXT = json.loads((ROOT / 'tests/fixtures/bl1e_null_context_failure.json').read_text())


class Hook:
    def __init__(self, path, kind, identifier, fn):
        self.path, self.kind, self.hook_identifier, self.fn = path, kind, identifier, fn

    def __call__(self, *args):
        return self.fn(*args)

    def get_active_count(self):
        return 1


class Object(NS):
    def _path_name(self):
        return self.path


def initialization_data(fields):
    attribute = fields['BaseValueAttribute']
    if attribute is not None:
        path = attribute['ref']
        attribute = Object(path=path, Name=path.rsplit('.', 1)[-1])
    return NS(BaseValueConstant=fields['BaseValueConstant'], BaseValueAttribute=attribute,
              InitializationDefinition=fields['InitializationDefinition'],
              BaseValueScaleConstant=fields['BaseValueScaleConstant'])


class Weapon(Object):
    def __init__(self, path='World.Weapon', exp=42, base=1, proficiency=0, kind='Pistol'):
        # Use captured reflected resolver fields, not a guessed native result.
        captured = FIXTURE['proficiency_resolvers'][
            f'gd_Balance.LevelLimits.Proficiency_{kind}_LevelBonus:SimpleMathValueResolver_0']
        resolver = Object(path='Native.Math', Class=NS(Name='SimpleMathValueResolver'),
                          Arg1Option=captured['Arg1Option'], Operand=captured['Operand'],
                          Arg1Attribute=initialization_data(captured['Arg1Attribute']['fields']),
                          Argument=initialization_data(captured['Argument']['fields']))
        attribute = Object(path='gd_Balance.LevelLimits.Proficiency_' + kind + '_LevelBonus',
            Name='Proficiency_' + kind + '_LevelBonus', AttributeContextClass=None,
            bIsSimpleAttribute=True,
            ContextResolverChain=[Object(Class=NS(Name='NoContextNeededAttributeContextResolver'))],
            ValueResolverChain=[resolver])
        bonus = NS(BaseValueConstant=base, BaseValueScaleConstant=1,
                   BaseValueAttribute=attribute, InitializationDefinition=None)
        definition = Object(path='Native.WeaponType.' + kind, bUsesPlayerLevelRequirement=True,
                            PlayerUseLevelBonus=bonus)
        super().__init__(path=path, Class=NS(Name='WillowWeapon'), ExpLevel=exp,
            attribute=attribute, bonus=bonus, definition=definition, proficiency=proficiency, resolver=resolver,
            Owner=None, Inventory=None, query_calls=[])

    def GetInventoryDefinition(self):
        return self.definition

    def GetControllerPlayerExpLevelRequiredToUse(self, controller):
        self.query_calls.append(controller)
        return max(1, self.ExpLevel - int(self.proficiency * .25 + 2))

    def GetShortHumanReadableName(self):
        return 'Lady Finger'

    def CanBeUsedBy(self, pawn):
        return self.ExpLevel - int(self.proficiency * .25 + 2) <= pawn.GetExpLevel()

    def IsLevelRequirementMet(self, pc):
        level = self.GetControllerPlayerExpLevelRequiredToUse(pc)
        return level <= pc.Pawn.GetExpLevel(), level


class Movie(Object):
    def __init__(self, item, kind='StatusMenuExGFxMovie', path='World.Menu'):
        super().__init__(Class=NS(Name=kind), path=path, selected=item, comparing=False,
                         strings={}, writes=[])
        self.ActiveTextList = NS(GetHighlightedObject=lambda: self.selected)
        self.bOnItemOfTheDay = False
        self.ItemOfTheDayData = NS(Item=item)

    def GetCurrentHighlightedObject(self):
        return self.selected

    def IsComparing(self):
        return self.comparing

    def field(self, card, text='LV 40'):
        prefix = card + '.requirement.requirement'
        self.strings[prefix + '._name'] = 'requirement'
        self.strings[prefix + '.text'] = text

    def GetVariableString(self, path):
        return self.strings.get(path, '')

    def SetVariableString(self, path, value):
        self.writes.append((path, value))
        self.strings[path] = value


@contextmanager
def loaded_mod():
    base, sdk, hooks = (ModuleType(n) for n in ('mods_base', 'unrealsdk', 'unrealsdk.hooks'))
    state = NS(pc=None, objects={}, evaluations=[], registration=None)
    base.SETTINGS_DIR = ROOT / 'test-settings'
    base.get_pc = lambda: state.pc
    base.get_ordered_mod_list = lambda: [NS(name='Consistent Weapon Levels', version='2.0.1', is_enabled=True)]
    base.ButtonOption = lambda title, **kw: NS(title=title, **kw)
    base.build_mod = lambda **kw: setattr(state, 'registration', kw)
    base.hook = lambda path, kind='PRE', **kw: lambda fn: Hook(
        path, kind, kw.get('hook_identifier', fn.__name__), fn)
    sdk.find_object = lambda cls, path: state.objects.get(path)
    sdk.find_all = lambda cls: [obj for obj in state.objects.values() if obj.Class.Name == cls]
    sdk.logging = NS(info=lambda s: None, warning=lambda s: None)

    def evaluate(bonus, context):
        # Captured live behavior: null context returns the fallback, NOT the
        # expression's constant operand. Version 2.0.0 failed with this behavior.
        state.evaluations.append((bonus, context))
        return bonus.BaseValueConstant * bonus.BaseValueScaleConstant

    sdk.find_class = lambda name: NS(ClassDefaultObject=NS(EvaluateInitializationData=evaluate))
    hooks.Type = NS(PRE='PRE', POST='POST')
    old = {k: v for k, v in sys.modules.items() if k.startswith('ConsistentWeaponLevels')}
    for key in old:
        del sys.modules[key]
    with patch.dict(sys.modules, {'mods_base': base, 'unrealsdk': sdk, 'unrealsdk.hooks': hooks}):
        spec = importlib.util.spec_from_file_location('ConsistentWeaponLevels', PACKAGE/'__init__.py')
        mod = importlib.util.module_from_spec(spec)
        mod.__version__ = '2.0.1'
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        mod.on_enable()
        try:
            yield mod, state
        finally:
            for key in list(sys.modules):
                if key.startswith('ConsistentWeaponLevels'):
                    del sys.modules[key]
            sys.modules.update(old)


class LevelTests(unittest.TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        self.mod, self.state = stack.enter_context(loaded_mod())
        self.weapon = Weapon()
        self.movie = Movie(self.weapon)
        self.movie.field('topLevel_mc.card1', 'LV 41')

    def render(self, movie=None):
        self.assertIsNone(self.mod.after_card(movie or self.movie, None, None, None))

    def test_captured_41_card_at_player_40_becomes_40(self):
        for phase in ('before_equipping', 'after_equipping'):
            row = MISMATCH[phase]
            self.assertEqual(row['native_level_with_controller'], 40)
            self.assertEqual(row['card_level_without_proficiency'], 41)
            self.weapon.ExpLevel = row['internal_level']
            self.movie.field('topLevel_mc.card1', 'LV 41')
            self.render()
            self.assertEqual(self.movie.writes[-1][1], 'LV 40')
        self.assertEqual(self.weapon.bonus.BaseValueConstant, 1)
        self.assertIs(self.weapon.bonus.BaseValueAttribute, self.weapon.attribute)
        self.assertEqual(self.state.evaluations, [])
        self.assertEqual(self.weapon.query_calls, [])

    def test_replay_live_2_0_0_null_context_failure_equipped_and_backpack(self):
        definition = NULL_CONTEXT['definition']
        captured_resolver = definition['resolvers'][0]

        def data(captured):
            return initialization_data({
                'BaseValueConstant': captured['constant'],
                'BaseValueScaleConstant': captured['scale'],
                'BaseValueAttribute': ({'ref': captured['attribute']}
                                       if captured['attribute'] is not None else None),
                'InitializationDefinition': captured['initialization'],
            })

        for case in NULL_CONTEXT['cases']:
            with self.subTest(source=case['source']):
                row, card = case['weapon'], case['card']
                self.weapon.ExpLevel = row['internal_level']
                self.weapon.bonus.BaseValueConstant = definition['constant']
                self.weapon.bonus.BaseValueScaleConstant = definition['scale']
                self.weapon.resolver.Arg1Attribute = data(captured_resolver['Arg1Attribute'])
                self.weapon.resolver.Argument = data(captured_resolver['Argument'])
                # Reproduce the previous version using actual null-context
                # fallback behavior; its old model incorrectly returned 2 here.
                evaluator = sys.modules['unrealsdk'].find_class('AttributeInitializationDefinition').ClassDefaultObject
                old_bonus = evaluator.EvaluateInitializationData(self.weapon.bonus, None)
                self.assertEqual(row['internal_level'] - old_bonus, row['ordinary_required_level'])
                self.assertEqual(old_bonus, 1)
                self.state.evaluations.clear()
                self.movie.field('topLevel_mc.card1', card['before'])
                self.movie.writes.clear()
                self.render()
                self.assertEqual(self.movie.writes, [])
                self.assertEqual(self.mod._recent_cards[-1]['after'], 'LEVEL REQUIREMENT: 40')
                self.movie.field('topLevel_mc.card1', card['after'])
                self.render()
                self.assertEqual(self.movie.writes[-1][1], 'LEVEL REQUIREMENT: 40')
                self.assertEqual(self.state.evaluations, [])
                self.assertEqual(self.mod._recent_cards[-1]['resolved_bonus'], 2)

    def test_captured_repeater_41_displays_native_39_not_40(self):
        self.weapon.ExpLevel = 41
        self.movie.field('topLevel_mc.card1', 'LEVEL REQUIREMENT: 39')
        self.render()
        self.assertEqual(self.movie.writes, [])
        self.assertEqual(self.mod._recent_cards[-1]['ordinary_required_level'], 39)

    def test_formula_operand_and_outer_scales_applied_once(self):
        self.weapon.resolver.Argument.BaseValueConstant = 4
        self.weapon.resolver.Argument.BaseValueScaleConstant = 2
        self.weapon.bonus.BaseValueScaleConstant = 3
        self.assertEqual(self.mod.ordinary_level(self.weapon), 18)
        self.assertEqual(self.state.evaluations, [])

    def test_unknown_math_and_dynamic_operands_stay_native(self):
        changes = (
            (self.weapon.resolver, 'Arg1Option', 0),
            (self.weapon.resolver, 'Operand', 1),
            (self.weapon.resolver.Argument, 'InitializationDefinition', object()),
            (self.weapon.resolver.Argument, 'BaseValueAttribute', object()),
            (self.weapon.resolver.Arg1Attribute, 'InitializationDefinition', object()),
            (self.weapon.resolver.Arg1Attribute, 'BaseValueConstant', 1),
            (self.weapon.resolver.Arg1Attribute, 'BaseValueScaleConstant', float('nan')),
            (self.weapon.resolver.Arg1Attribute, 'BaseValueAttribute', Object(path='Custom.Skill')),
        )
        for obj, field, value in changes:
            with self.subTest(field=field), patch.object(obj, field, value):
                self.assertIsNone(self.mod.ordinary_level(self.weapon))
        self.assertEqual(self.state.evaluations, [])

    def test_uninitialized_weapon_is_normal_skip(self):
        self.weapon.GetInventoryDefinition = lambda: None
        self.render()
        self.assertEqual(self.movie.writes, [])
        self.assertEqual(self.mod._stats['errors'], 0)
        self.assertEqual(self.mod._recent_cards[-1]['resolution'], 'uninitialized')

    def test_inactive_menu_prototypes_are_normal_skips(self):
        vendor = Movie(None, kind='VendingMachineGFxMovie')
        vendor.GetCurrentHighlightedObject = None
        vendor.ActiveTextList = None
        pickup = Movie(None, kind='ItemPickupGFxMovie')
        pickup.MyHUDOwner = None
        reward = Movie(None, kind='QuestAcceptGFxMovie')
        reward.CardContents = None
        for movie in (vendor, pickup, reward):
            self.render(movie)
            self.assertEqual(movie.writes, [])
        self.assertEqual(self.mod._stats['errors'], 0)

    def test_equipped_57_becomes_ordinary_69(self):
        self.weapon.ExpLevel = 71
        self.weapon.proficiency = 50
        self.assertEqual(self.weapon.GetControllerPlayerExpLevelRequiredToUse(object()), 57)
        self.movie.field('topLevel_mc.card1', 'LV 57')
        self.render()
        self.assertEqual(self.movie.writes[-1][1], 'LV 69')

    def test_lady_finger_fix_uses_resolver_instead_of_cap(self):
        self.weapon.ExpLevel = 71
        self.assertEqual(self.mod.ordinary_level(self.weapon), 69)
        self.weapon.ExpLevel = 80
        self.assertEqual(self.mod.ordinary_level(self.weapon), 78)

    def test_every_normal_level_and_native_minimum(self):
        for level in range(1, 70):
            self.weapon.ExpLevel = level + 2
            self.assertEqual(self.mod.ordinary_level(self.weapon), level)
        self.weapon.ExpLevel = 1
        self.assertEqual(self.mod.ordinary_level(self.weapon), 1)

    def test_definition_and_weapon_fields_never_written(self):
        class ReadOnly:
            def __init__(self, source):
                self.__dict__.update(vars(source))
            def __setattr__(self, name, value):
                raise AssertionError('Unexpected native field write: ' + name)
            def _path_name(self):
                return self.path
        self.weapon.bonus = ReadOnly(self.weapon.bonus)
        self.weapon.definition.PlayerUseLevelBonus = self.weapon.bonus
        self.weapon.definition = ReadOnly(self.weapon.definition)
        self.weapon = ReadOnly(self.weapon)
        # Bind the model method after wrapping without permitting any assignment.
        self.weapon.__dict__['GetInventoryDefinition'] = lambda: self.weapon.definition
        self.movie.selected = self.weapon
        self.render()
        self.assertEqual(self.movie.writes[-1][1], 'LV 40')

    def test_registered_hooks_only_observe_ui_and_never_block(self):
        hooks = self.state.registration['hooks']
        self.assertTrue(all('GFxMovie:' in h.path for h in hooks))
        self.assertTrue(all(h.kind == 'POST' for h in self.mod._card_hooks))
        for callback in self.mod._card_hooks:
            self.assertIsNone(callback(self.movie, None, None, None))
        self.assertEqual(self.weapon.query_calls, [])

    def test_no_requirement_and_nonweapons_unchanged(self):
        self.weapon.definition.bUsesPlayerLevelRequirement = False
        self.render()
        self.weapon.Class.Name = 'WillowEquipAbleItem'
        self.render()
        self.assertEqual(self.movie.writes, [])

    def test_unknown_contexts_and_initializers_never_evaluated(self):
        for field, value in (
            ('Name', 'CustomLevelBonus'), ('AttributeContextClass', object()),
            ('bIsSimpleAttribute', False), ('ContextResolverChain', []),
            ('ContextResolverChain', [NS(Class=NS(Name='PawnAttributeContextResolver'))]),
            ('ValueResolverChain', [NS(Class=NS(Name='CustomDynamicResolver'))]),
        ):
            with self.subTest(field=field), patch.object(self.weapon.attribute, field, value):
                self.assertIsNone(self.mod.ordinary_level(self.weapon))
        self.weapon.bonus.InitializationDefinition = object()
        self.assertIsNone(self.mod.ordinary_level(self.weapon))
        self.assertEqual(self.state.evaluations, [])

    def test_constant_definitions_and_scale_once(self):
        self.weapon.bonus.BaseValueScaleConstant = 3
        self.assertEqual(self.mod.ordinary_level(self.weapon), 36)
        self.weapon.bonus.BaseValueAttribute = None
        self.assertEqual(self.mod.ordinary_level(self.weapon), 39)
        self.assertEqual(self.state.evaluations, [])

    def test_invalid_expression_results_stay_native(self):
        for value in (float('nan'), float('inf'), -1, 1.5):
            self.weapon.resolver.Argument.BaseValueConstant = value
            self.assertIsNone(self.mod.ordinary_level(self.weapon))
        self.render()
        self.assertEqual(self.movie.writes, [])

    def test_read_failure_keeps_ui_and_definition_unchanged(self):
        self.weapon.resolver.Argument.BaseValueConstant = None
        self.render()
        self.assertEqual(self.movie.writes, [])
        self.assertIs(self.weapon.bonus.BaseValueAttribute, self.weapon.attribute)
        self.assertEqual(len(self.mod._errors), 1)
        self.weapon.resolver.Argument.BaseValueConstant = 2
        self.render()
        self.assertEqual(self.movie.writes[-1][1], 'LV 40')

    def test_localized_label_and_other_fields_preserved(self):
        self.movie.field('topLevel_mc.card1', 'NIVEAU REQUIS : 41')
        self.movie.strings['topLevel_mc.card1.classreq.requirement.text'] = 'Soldier'
        self.movie.strings['topLevel_mc.card1.requirement._currentframe'] = 'on'
        before = dict(self.movie.strings)
        self.render()
        changed = [k for k in before if before[k] != self.movie.strings[k]]
        self.assertEqual(changed, ['topLevel_mc.card1.requirement.requirement.text'])
        self.assertEqual(self.movie.writes[-1][1], 'NIVEAU REQUIS : 40')

    def test_missing_ambiguous_and_unknown_fields_never_created(self):
        for text in ('', 'undefined', 'LV 40 / 41'):
            self.movie.field('topLevel_mc.card1', text)
            self.render()
        self.movie.field('topLevel_mc.card1', 'LV 41')
        del self.movie.strings['topLevel_mc.card1.requirement.requirement._name']
        self.render()
        self.assertEqual(self.movie.writes, [])
        self.assertEqual(self.mod._stats['missing_text'], 4)

    def test_no_redundant_writes_and_readback_failure_recorded(self):
        self.movie.field('topLevel_mc.card1', 'LV 40')
        self.render()
        self.assertEqual(self.movie.writes, [])
        self.movie.field('topLevel_mc.card1', 'LV 41')
        self.movie.SetVariableString = lambda path, value: None
        self.render()
        self.assertEqual(self.mod._stats['write_mismatch'], 1)

    def test_comparison_uses_each_weapons_own_level(self):
        other = Weapon(path='World.Other', exp=60)
        self.state.objects[self.weapon.path] = self.weapon
        self.mod.remember_comparison(self.movie, None, None, None)
        self.movie.comparing = True
        self.movie.selected = other
        self.movie.field('topLevel_mc.card2', 'LV 55')
        self.render()
        self.assertEqual(dict(self.movie.writes), {
            'topLevel_mc.card1.requirement.requirement.text': 'LV 40',
            'topLevel_mc.card2.requirement.requirement.text': 'LV 58'})
        self.assertTrue(all(isinstance(x, str) for x in next(iter(self.mod._comparisons.values()))))

    def test_stale_comparison_source_does_not_touch_first_card(self):
        self.mod.remember_comparison(self.movie, None, None, None)
        self.movie.comparing = True
        self.movie.field('topLevel_mc.card2', 'LV 41')
        self.render()
        self.assertEqual(len(self.movie.writes), 1)
        self.assertIn('card2', self.movie.writes[0][0])

    def test_vendor_daily_and_bank_compare_exit(self):
        vendor = Movie(None, kind='VendingMachineGFxMovie')
        vendor.GetCurrentHighlightedObject = None
        vendor.bOnItemOfTheDay = True
        vendor.ItemOfTheDayData.Item = self.weapon
        vendor.field('topLevel_mc.card1', 'LV 41')
        self.render(vendor)
        self.assertEqual(vendor.writes[-1][1], 'LV 40')
        bank = Movie(self.weapon, kind='BankGFxMovie')
        bank.field('currentPage.card1', 'LV 41')
        self.mod.remember_comparison(bank, None, None, None)
        self.mod.leave_bank_compare(bank, None, None, None)
        self.assertEqual(bank.writes[-1][1], 'LV 40')

    def test_pickup_hud_and_reward_card_item_routing(self):
        self.state.pc = NS(Pawn=NS(Weapon=self.weapon))
        for kind, path in (
            ('ItemPickupGFxMovie', 'inventory.card1'),
            ('WillowHUDGFxMovie', 'p1.outerequip.equipcard'),
            ('QuestAcceptGFxMovie', 'reward.card1'),
        ):
            movie = Movie(None, kind=kind)
            movie.MyHUDOwner = NS(ItemComparison=[self.weapon])
            movie.CardContents = NS(Inv=self.weapon)
            movie.field(path, 'LV 41')
            self.render(movie)
            self.assertEqual(movie.writes[-1], (path + '.requirement.requirement.text', 'LV 40'))

    def test_hud_shield_comparison_never_uses_current_gun_level(self):
        shield = NS(Class=NS(Name='WillowEquipAbleItem'))
        self.state.pc = NS(Pawn=NS(Weapon=self.weapon), myHUD=NS(ItemComparison=[shield, shield]))
        hud = Movie(None, kind='WillowHUDGFxMovie')
        hud.field('p1.outerequip.equipcard', 'LV 41')
        self.render(hud)
        self.assertEqual(hud.writes, [])

    def test_disable_and_reenable(self):
        self.mod.remember_comparison(self.movie, None, None, None)
        self.mod.on_disable()
        self.render()
        self.assertEqual(self.movie.writes, [])
        self.assertEqual(self.mod._comparisons, {})
        self.mod.on_enable()
        self.render()
        self.assertEqual(self.movie.writes[-1][1], 'LV 40')

    def test_recent_history_bounded_and_contains_no_native_objects(self):
        for _ in range(60):
            self.render()
        self.assertEqual(len(self.mod._recent_cards), 40)
        json.dumps(list(self.mod._recent_cards), allow_nan=False)

    def test_exported_original_resolvers_explain_pistol_mismatch(self):
        pistol = FIXTURE['weapon_level_bonuses']['gd_weap_repeater_pistol.A_Weapon.WeaponType_repeater_pistol']
        self.assertEqual(pistol['BaseValueConstant'], 1)
        for resolver in FIXTURE['proficiency_resolvers'].values():
            self.assertEqual(resolver['Argument']['fields']['BaseValueConstant'], 2)

    def test_diagnostics_record_native_checks_equipped_identity_and_ui_history(self):
        pawn = NS(GetExpLevel=lambda: 40, Weapon=self.weapon,
                  InvManager=NS(InventoryChain=self.weapon))
        self.state.pc = NS(Pawn=pawn)
        self.weapon.Owner = pawn
        self.state.objects = {self.weapon.path: self.weapon, self.movie.path: self.movie}
        self.render()
        before = dict(self.movie.strings)
        stats = dict(self.mod._stats)
        with tempfile.TemporaryDirectory() as tmp, patch.object(self.mod, 'SETTINGS_DIR', Path(tmp)):
            self.mod.export_diagnostics()
            report = json.loads(next(Path(tmp).rglob('*.json')).read_text())
        row = report['weapons'][0]
        self.assertEqual(report['version'], '2.0.1')
        self.assertEqual(report['player']['level'], 40)
        self.assertEqual(report['loaded_mods'][0]['version'], '2.0.1')
        self.assertTrue(row['equipped'])
        self.assertTrue(row['can_be_used_by_player'])
        self.assertEqual(row['native_level_requirement_check'], [True, 40])
        self.assertEqual((row['internal_level'], row['native_level_with_controller'], row['ordinary_required_level']), (42, 40, 40))
        self.assertEqual(row['resolved_bonus'], 2)
        self.assertEqual(row['resolution'], 'zero_proficiency_expression')
        resolver = report['definitions'][row['definition']]['resolvers'][0]
        self.assertEqual((resolver['Arg1Option'], resolver['Operand']), (1, 0))
        self.assertEqual(report['recent_cards'][-1]['after'], 'LV 40')
        self.assertEqual(report['export_errors'], [])
        self.assertEqual(self.movie.strings, before)
        self.assertEqual(self.mod._stats, stats)
        self.assertIs(self.weapon.bonus.BaseValueAttribute, self.weapon.attribute)

    def test_export_without_character_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(self.mod, 'SETTINGS_DIR', Path(tmp)):
            self.mod.export_diagnostics()
            self.assertEqual(list(Path(tmp).rglob('*.json')), [])


if __name__ == '__main__':
    unittest.main()
