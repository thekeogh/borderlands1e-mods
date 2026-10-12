"""Event/cooldown regression model; cannot reproduce UE3 native faults."""

import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace as NS
import unittest
from unittest.mock import patch
import weakref

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Source/sdk_mods/EnemyRespawnTimer"


class Object:
    def __init__(self, path="TheWorld.Object"):
        self.path = path
        self.Name = path.rsplit(".", 1)[-1]

    def _get_address(self): return id(self)
    def _path_name(self): return self.path

    def IsEnemy(self, *args): raise AssertionError("Do not call native predicates")
    def IsBoss(self, *args): raise AssertionError("Do not call native predicates")
    def DoSpawning(self, *args): raise AssertionError("Never force native spawning")
    def SetExpLevel(self, *args): raise AssertionError("Do not change enemy levels")


def load():
    sdk = ModuleType("unrealsdk")
    messages, additions, removals, registrations = [], [], [], []
    sdk.logging = NS(info=messages.append, error=messages.append)
    def find_object(cls, path):
        if path.startswith("GearboxFramework."):
            return Object(path)
        raise ValueError("Object not found: " + path)
    sdk.find_object = find_object
    sdk.find_all = lambda cls: [] if cls == "Function" else (_ for _ in ()).throw(AssertionError("No pawn scans"))
    sdk.find_class = lambda name: None
    hooks = ModuleType("unrealsdk.hooks")
    hooks.Block = object()
    hooks.Type = NS(PRE="pre", POST="post", POST_UNCONDITIONAL="post-always")
    hooks.add_hook = lambda *args: additions.append(args) or True
    hooks.remove_hook = lambda *args: removals.append(args)
    unreal = ModuleType("unrealsdk.unreal")
    unreal.WeakPointer = weakref.ref
    base = ModuleType("mods_base")
    world = Object("TheWorld.WorldInfo")
    world.TimeSeconds, world.NetMode = 100.0, 0
    pc = NS(Pawn=Object(), WorldInfo=world)
    base.get_pc = lambda: pc
    base.SETTINGS_DIR = ROOT / "unused-settings"
    base.SpinnerOption = lambda name, value, choices, **kw: NS(identifier=name, value=value, choices=choices, **kw)
    base.ButtonOption = lambda name, **kw: NS(identifier=name, **kw)
    def hook(path, kind):
        def decorate(fn):
            registrations.append((path, kind))
            return fn
        return decorate
    base.hook = hook
    build = []
    base.build_mod = lambda **kw: build.append(kw)
    package = ModuleType("respawn_test")
    package.__package__ = package.__name__
    package.__path__ = [str(SOURCE)]
    policy = ModuleType("respawn_test.policy")
    modules = {"mods_base": base, "unrealsdk": sdk, "unrealsdk.hooks": hooks,
               "unrealsdk.unreal": unreal, package.__name__: package, policy.__name__: policy}
    with patch.dict(sys.modules, modules):
        exec(compile((SOURCE / "policy.py").read_text(), "policy.py", "exec"), policy.__dict__)
        exec(compile((SOURCE / "__init__.py").read_text(), "__init__.py", "exec"), package.__dict__)
        package.on_enable()
    package.testing = NS(sdk=sdk, hooks=hooks, base=base, world=world, pc=pc,
                         messages=messages, additions=additions, removals=removals,
                         registrations=registrations, build=build, policy=policy)
    return package


class RespawnTests(unittest.TestCase):
    def setUp(self):
        self.mod = load()
        self.world = self.mod.testing.world
        self.den = self.make_den("A")
        self.pawns = []

    def make_den(self, name):
        den = Object("TheWorld.Den" + name)
        den.WorldInfo = self.world
        den.bDeleteMe = den.bPendingDelete = den.bNoRespawning = False
        den.Aspect = None
        den.SpawnData = NS(PopulationDefName="gd_Bandits.Population", MaxActiveActors=3,
                           NextSpawnTime=120.0, NumTotalActors=7, CustomField="preserved")
        return den

    def spawn(self, den=None, count=2, allegiance="gd_allegiance.HumanEnemy.Bandit"):
        den = den or self.den
        self.assertIsNone(self.mod.before_spawning(den, None, None, None))
        result = []
        for i in range(count):
            pawn = Object("TheWorld.Pawn" + str(len(self.pawns)))
            pawn.bIsDead = False
            pawn.Allegiance = Object(allegiance) if allegiance else None
            result.append(pawn)
            self.pawns.append(pawn)
            self.mod.record_spawn(NS(), None, pawn, None)
        self.mod.after_spawning(den, None, None, None)
        return result

    def die(self, pawn, now):
        self.world.TimeSeconds = now
        pawn.bIsDead = True
        self.mod.record_death(pawn, None, None, None)

    def attempt(self, den=None):
        den = den or self.den
        result = self.mod.before_spawning(den, None, None, None)
        self.mod.after_spawning(den, None, None, None)
        return result

    def test_exact_six_choices_default_and_settings(self):
        self.assertEqual(self.mod.respawn_delay.value, "15 minutes")
        self.assertEqual(self.mod.respawn_delay.choices,
                         ["5 minutes", "15 minutes", "30 minutes", "1 hour", "3 hours", "Forever (until reload)"])
        self.assertEqual(self.mod.testing.build[0]["settings_file"].name, "EnemyRespawnTimer.json")

    def test_default_starts_after_last_enemy_not_first_kill(self):
        first, second = self.spawn()
        self.die(first, 110)
        self.assertEqual(self.den.SpawnData.NextSpawnTime, 120)
        self.die(second, 130)
        self.assertEqual(self.den.SpawnData.NextSpawnTime, 1030)
        self.world.TimeSeconds = 1029
        self.assertIs(self.attempt(), self.mod.Block)
        self.world.TimeSeconds = 1030
        self.assertIsNone(self.attempt())

    def test_every_finite_choice_deadline_and_exact_expiry(self):
        for choice, seconds in [("5 minutes", 300), ("15 minutes", 900), ("30 minutes", 1800), ("1 hour", 3600), ("3 hours", 10800)]:
            self.mod.reset_session()
            self.world.TimeSeconds = 100
            self.mod.respawn_delay.value = choice
            pawn, = self.spawn(count=1)
            self.die(pawn, 140)
            self.assertEqual(self.den.SpawnData.NextSpawnTime, 140 + seconds)
            self.world.TimeSeconds = 140 + seconds - 0.1
            self.assertIs(self.attempt(), self.mod.Block)
            self.world.TimeSeconds = 140 + seconds
            self.assertIsNone(self.attempt())

    def test_forever_is_session_guard_even_beyond_timestamp(self):
        self.mod.respawn_delay.value = "Forever (until reload)"
        pawn, = self.spawn(count=1)
        self.die(pawn, 120)
        self.world.TimeSeconds = 1_000_000_000
        self.assertIs(self.attempt(), self.mod.Block)
        self.mod.map_change(None, None, None, None)
        self.assertIsNone(self.attempt())
        self.assertEqual(self.den.SpawnData.NextSpawnTime, 120)

    def test_each_group_has_independent_clear_time_and_first_spawns_allowed(self):
        other = self.make_den("B")
        a, = self.spawn(count=1)
        b, = self.spawn(other, count=1)
        self.die(a, 130)
        self.die(b, 200)
        self.world.TimeSeconds = 1030
        self.assertIsNone(self.attempt())
        self.assertIs(self.attempt(other), self.mod.Block)
        self.assertIsNone(self.attempt(self.make_den("Untouched")))

    def test_changing_choice_updates_from_original_clear_time(self):
        pawn, = self.spawn(count=1)
        self.die(pawn, 130)
        self.world.TimeSeconds = 200
        self.mod.change_delay(None, "3 hours")
        self.assertEqual(self.den.SpawnData.NextSpawnTime, 10930)
        self.mod.respawn_delay.value = "3 hours"
        self.mod.change_delay(None, "5 minutes")
        self.mod.respawn_delay.value = "5 minutes"
        self.assertEqual(self.den.SpawnData.NextSpawnTime, 430)
        self.world.TimeSeconds = 431
        self.assertIsNone(self.attempt())

    def test_change_forever_to_finite_keeps_clear_time(self):
        self.mod.respawn_delay.value = "Forever (until reload)"
        pawn, = self.spawn(count=1)
        self.die(pawn, 150)
        self.mod.change_delay(None, "5 minutes")
        self.mod.respawn_delay.value = "5 minutes"
        self.world.TimeSeconds = 450
        self.assertIsNone(self.attempt())

    def test_disable_restores_only_timestamp_and_drops_weak_tracking(self):
        pawn, = self.spawn(count=1)
        self.die(pawn, 140)
        self.mod.on_disable()
        self.assertEqual(vars(self.den.SpawnData), {"PopulationDefName": "gd_Bandits.Population", "MaxActiveActors": 3,
                         "NextSpawnTime": 120.0, "NumTotalActors": 7, "CustomField": "preserved"})
        self.assertFalse(self.den.bNoRespawning)
        self.assertEqual(self.mod._dens, {})
        self.assertEqual(self.mod._actors, {})
        self.assertEqual(len(self.mod.testing.removals), 2)

    def test_disable_preserves_other_mods_timestamp(self):
        pawn, = self.spawn(count=1)
        self.die(pawn, 140)
        self.den.SpawnData.NextSpawnTime = 9000
        self.mod.on_disable()
        self.assertEqual(self.den.SpawnData.NextSpawnTime, 9000)

    def test_new_world_or_rewind_clears_timers(self):
        for kind in ("world", "time"):
            self.world.TimeSeconds = 100
            pawn, = self.spawn(count=1)
            self.die(pawn, 140)
            if kind == "world":
                world = Object("NewWorld")
                world.TimeSeconds, world.NetMode = 1, 0
                self.mod.testing.pc.WorldInfo = world
            else:
                self.world.TimeSeconds = 1
            self.mod.host_clock()
            self.assertEqual(self.mod._dens, {})
            self.assertEqual(self.den.SpawnData.NextSpawnTime, 120)
            self.mod.testing.pc.WorldInfo = self.world

    def test_clients_and_menus_do_not_track_or_block(self):
        for flag in ("client", "menu"):
            if flag == "client": self.world.NetMode = 3
            else:
                self.world.NetMode = 0
                self.mod.testing.pc.Pawn = None
            self.spawn()
            self.assertEqual(self.mod._actors, {})

    def test_scripted_aspects_no_respawn_defaults_and_invalid_dens_stay_native(self):
        for attr, value in [("Aspect", Object()), ("bNoRespawning", True), ("bDeleteMe", True),
                            ("bPendingDelete", True), ("Name", "Default__PopulationOpportunityDen")]:
            den = self.make_den("Skip")
            setattr(den, attr, value)
            self.spawn(den)
            self.assertNotIn(den._get_address(), self.mod._dens)
        for field, value in [("PopulationDefName", "None"), ("MaxActiveActors", 0)]:
            den = self.make_den("Invalid")
            setattr(den.SpawnData, field, value)
            self.spawn(den)
            self.assertNotIn(den._get_address(), self.mod._dens)

    def test_friendly_neutral_player_and_unknown_groups_stay_native(self):
        for allegiance in ("gd_allegiance.Friendly.NPC", "gd_allegiance.Player.Team", "gd_allegiance.Neutral.NPC", "Custom.Unknown", None):
            den = self.make_den("Unknown")
            pawn, = self.spawn(den, count=1, allegiance=allegiance)
            self.die(pawn, self.world.TimeSeconds + 10)
            self.assertEqual(den.SpawnData.NextSpawnTime, 120)
            self.assertIsNone(self.attempt(den))

    def test_mixed_group_never_blocks_npcs(self):
        self.mod.before_spawning(self.den, None, None, None)
        enemy = Object(); enemy.Allegiance = Object("gd_allegiance.HumanEnemy.Bandit"); enemy.bIsDead = False
        npc = Object(); npc.Allegiance = Object("gd_allegiance.Friendly.NPC")
        self.mod.record_spawn(NS(), None, enemy, None)
        self.mod.record_spawn(NS(), None, npc, None)
        self.mod.after_spawning(self.den, None, None, None)
        self.die(enemy, 150)
        self.assertIsNone(self.attempt())
        self.assertEqual(self.den.SpawnData.NextSpawnTime, 120)

    def test_spawn_allegiance_override_excludes_otherwise_hostile_pawn(self):
        self.mod.before_spawning(self.den, None, None, None)
        pawn = Object(); pawn.Allegiance = Object("gd_allegiance.HumanEnemy.Bandit")
        self.mod.record_spawn(NS(SpawnAllegiance=Object("gd_allegiance.Friendly.NPC")), None, pawn, None)
        self.mod.after_spawning(self.den, None, None, None)
        self.assertTrue(self.mod._dens[self.den._get_address()]["ignored"])

    def test_nested_spawn_contexts_unwind_without_cross_assigning_dens(self):
        other = self.make_den("Nested")
        self.mod.before_spawning(self.den, None, None, None)
        child, = self.spawn(other, count=1)
        parent = Object(); parent.Allegiance = Object("gd_allegiance.HumanEnemy.Bandit"); parent.bIsDead = False
        self.mod.record_spawn(NS(), None, parent, None)
        self.mod.after_spawning(self.den, None, None, None)
        self.assertEqual(self.mod._actors[child._get_address()][1], other._get_address())
        self.assertEqual(self.mod._actors[parent._get_address()][1], self.den._get_address())
        self.assertEqual(self.mod._stack, [])

    def test_population_definition_change_clears_old_timer_without_blocking_new_encounter(self):
        pawn, = self.spawn(count=1)
        self.die(pawn, 130)
        self.den.SpawnData.PopulationDefName = "gd_NewMission.Population"
        self.assertIsNone(self.attempt())
        self.assertEqual(self.den.SpawnData.NextSpawnTime, 120)

    def test_duplicate_death_does_not_restart_timer(self):
        pawn, = self.spawn(count=1)
        self.die(pawn, 130)
        self.die(pawn, 200)
        self.assertEqual(self.den.SpawnData.NextSpawnTime, 1030)
        self.assertEqual(self.mod._counts["cleared_groups"], 1)

    def test_blocked_death_with_alive_flag_does_not_start_timer(self):
        pawn, = self.spawn(count=1)
        self.mod.record_death(pawn, None, None, None)
        self.assertEqual(self.den.SpawnData.NextSpawnTime, 120)

    def test_respawn_generation_gets_fresh_native_restore_baseline(self):
        first, = self.spawn(count=1)
        self.die(first, 130)
        self.world.TimeSeconds = 1030
        second, = self.spawn(count=1)
        self.den.SpawnData.NextSpawnTime = 2000  # Native second-generation schedule.
        self.die(second, 1040)
        self.mod.on_disable()
        self.assertEqual(self.den.SpawnData.NextSpawnTime, 2000)

    def test_untracked_deaths_and_spawns_outside_den_do_not_change_behavior(self):
        pawn = Object(); pawn.Allegiance = Object("gd_allegiance.HumanEnemy.Bandit"); pawn.bIsDead = True
        self.mod.record_spawn(NS(), None, pawn, None)
        self.mod.record_death(pawn, None, None, None)
        self.assertEqual(self.mod._actors, {})
        self.assertEqual(self.den.SpawnData.NextSpawnTime, 120)

    def test_missing_native_hook_disables_mutations_and_reports_error(self):
        self.mod.on_disable()
        self.mod.testing.sdk.find_object = lambda *args: None
        self.mod.on_enable()
        self.assertFalse(self.mod._ready)
        self.assertTrue(self.mod._errors)
        self.spawn()
        self.assertEqual(self.mod._actors, {})

    def test_native_sdk_lookup_exception_tries_next_declaring_class(self):
        self.mod.on_disable()
        def lookup(cls, path):
            if path.startswith("GearboxFramework."):
                raise ValueError("Object not found")
            return Object(path)
        self.mod.testing.sdk.find_object = lookup
        self.mod.on_enable()
        self.assertTrue(self.mod._ready)
        self.assertEqual(self.mod._spawn_path, "WillowGame.PopulationOpportunityDen:DoSpawning")

    def test_native_sdk_lookup_exception_falls_back_to_function_inventory(self):
        self.mod.on_disable()
        def missing(*args):
            raise ValueError("Object not found")
        self.mod.testing.sdk.find_object = missing
        self.mod.testing.sdk.find_all = lambda cls: [Object("OtherFramework.PopulationOpportunityDen.DoSpawning")]
        self.mod.on_enable()
        self.assertTrue(self.mod._ready)
        self.assertEqual(self.mod._spawn_path, "OtherFramework.PopulationOpportunityDen:DoSpawning")

    def test_missing_layout_delegates_and_cleans_context(self):
        del self.den.SpawnData.MaxActiveActors
        self.assertIsNone(self.attempt())
        self.assertEqual(self.mod._stack, [])
        self.assertTrue(self.mod._errors)

    def test_partial_hook_install_failure_rolls_back_both_hooks(self):
        self.mod.on_disable()
        self.mod.testing.hooks.add_hook = lambda path, kind, identifier, callback: kind == "pre"
        # Module imports a direct alias; replace it too.
        self.mod.add_hook = self.mod.testing.hooks.add_hook
        self.mod.on_enable()
        self.assertFalse(self.mod._ready)
        self.assertTrue(self.mod._errors)
        self.assertEqual(len(self.mod.testing.removals), 4)

    def test_diagnostics_is_read_only_and_json_serialisable(self):
        pawn, = self.spawn(count=1)
        self.die(pawn, 130)
        before = dict(vars(self.den.SpawnData)), dict(self.mod._counts)
        result = self.mod.snapshot()
        json.dumps(result, allow_nan=False)
        self.assertEqual(result["counts"]["tracked_spawns"], 1)
        self.assertEqual(result["dens"][0]["deadline"], 1030)
        self.assertEqual((dict(vars(self.den.SpawnData)), dict(self.mod._counts)), before)

    def test_all_factory_and_death_observers_are_unconditional_post_hooks(self):
        for path, kind in self.mod.testing.registrations:
            if path.endswith(":PreCommitMapChange"):
                self.assertEqual(kind, "pre")
            else:
                self.assertEqual(kind, "post-always")
        self.assertEqual(len(self.mod.testing.registrations), 6)


if __name__ == "__main__":
    unittest.main()
