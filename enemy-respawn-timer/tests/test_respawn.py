"""Event/cooldown regression model; cannot reproduce UE3 native faults."""

import json
from itertools import product
from pathlib import Path
import sys
import tempfile
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
            return Object(path.rsplit(".", 1)[0] + ":" + path.rsplit(".", 1)[1])
        raise ValueError("Object not found: " + path)
    sdk.find_object = find_object
    sdk.find_all = lambda cls: [] if cls in ("Function", "PopulationOpportunityDen") else (_ for _ in ()).throw(AssertionError("No pawn scans"))
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
            fn.hook_identifier = path
            fn.get_active_count = lambda: 1
            return fn
        return decorate
    base.hook = hook
    def keybind(name, key):
        def decorate(fn):
            fn.identifier, fn.key = name, key
            return fn
        return decorate
    base.keybind = keybind
    build = []
    base.build_mod = lambda **kw: build.append(kw)
    package = ModuleType("respawn_test")
    package.__package__ = package.__name__
    package.__path__ = [str(SOURCE)]
    policy = ModuleType("respawn_test.policy")
    named = ModuleType("respawn_test.named_enemies")
    modules = {"mods_base": base, "unrealsdk": sdk, "unrealsdk.hooks": hooks,
               "unrealsdk.unreal": unreal, package.__name__: package, policy.__name__: policy, named.__name__: named}
    with patch.dict(sys.modules, modules):
        exec(compile((SOURCE / "named_enemies.py").read_text(), "named_enemies.py", "exec"), named.__dict__)
        exec(compile((SOURCE / "policy.py").read_text(), "policy.py", "exec"), policy.__dict__)
        exec(compile((SOURCE / "__init__.py").read_text(), "__init__.py", "exec"), package.__dict__)
        package.on_enable()
    package.testing = NS(sdk=sdk, hooks=hooks, base=base, world=world, pc=pc,
                         messages=messages, additions=additions, removals=removals,
                         registrations=registrations, build=build, policy=policy, named=named)
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
        den.IsEnabled = True
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

    def test_exact_five_choices_default_and_settings(self):
        self.assertEqual(self.mod.respawn_delay.value, "30 minutes")
        self.assertEqual(self.mod.respawn_delay.choices,
                         ["1 minute", "30 minutes", "1 hour", "3 hours", "Forever (until reload)"])
        self.assertEqual(self.mod.testing.build[0]["settings_file"].name, "EnemyRespawnTimer.json")

    def test_default_starts_after_last_enemy_not_first_kill(self):
        first, second = self.spawn()
        self.die(first, 110)
        self.assertEqual(self.den.SpawnData.NextSpawnTime, 120)
        self.die(second, 130)
        self.assertEqual(self.den.SpawnData.NextSpawnTime, 1930)
        self.world.TimeSeconds = 1929
        self.assertIs(self.attempt(), self.mod.Block)
        self.world.TimeSeconds = 1930
        self.assertIsNone(self.attempt())

    def test_every_finite_choice_deadline_and_exact_expiry(self):
        for choice, seconds in [("1 minute", 60), ("30 minutes", 1800), ("1 hour", 3600), ("3 hours", 10800)]:
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
        self.world.TimeSeconds = 1930
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
        self.mod.change_delay(None, "1 minute")
        self.mod.respawn_delay.value = "1 minute"
        self.assertEqual(self.den.SpawnData.NextSpawnTime, 190)
        self.world.TimeSeconds = 200
        self.assertIsNone(self.attempt())

    def test_change_forever_to_finite_keeps_clear_time(self):
        self.mod.respawn_delay.value = "Forever (until reload)"
        pawn, = self.spawn(count=1)
        self.die(pawn, 150)
        self.mod.change_delay(None, "1 minute")
        self.mod.respawn_delay.value = "1 minute"
        self.world.TimeSeconds = 210
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
        self.assertEqual(self.den.SpawnData.NextSpawnTime, 1930)
        self.assertEqual(self.mod._counts["cleared_groups"], 1)

    def test_blocked_death_with_alive_flag_does_not_start_timer(self):
        pawn, = self.spawn(count=1)
        self.mod.record_death(pawn, None, None, None)
        self.assertEqual(self.den.SpawnData.NextSpawnTime, 120)

    def test_respawn_generation_gets_fresh_native_restore_baseline(self):
        first, = self.spawn(count=1)
        self.die(first, 130)
        self.world.TimeSeconds = 1930
        second, = self.spawn(count=1)
        self.den.SpawnData.NextSpawnTime = 2000  # Native second-generation schedule.
        self.die(second, 1940)
        self.mod.on_disable()
        self.assertEqual(self.den.SpawnData.NextSpawnTime, 2000)

    def test_untracked_deaths_and_spawns_outside_den_do_not_change_behavior(self):
        pawn = Object(); pawn.Allegiance = Object("gd_allegiance.HumanEnemy.Bandit"); pawn.bIsDead = True
        self.mod.record_spawn(NS(), None, pawn, None)
        self.mod.record_death(pawn, None, None, None)
        self.assertEqual(self.mod._actors, {})
        self.assertEqual(self.den.SpawnData.NextSpawnTime, 120)

    def test_missing_native_hook_keeps_polling_available_and_reports_error(self):
        self.mod.on_disable()
        self.mod.testing.sdk.find_object = lambda *args: None
        self.mod.on_enable()
        self.assertTrue(self.mod._ready)
        self.assertTrue(self.mod._errors)
        self.assertIsNotNone(self.mod.host_clock())

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

    def test_windows_sdk_function_path_installs_canonical_hook(self):
        # The mock originally used dot-only paths, hiding the Windows bug.
        self.assertEqual(self.mod._spawn_path,
                         "GearboxFramework.PopulationOpportunityDen:DoSpawning")
        self.assertEqual([args[0] for args in self.mod.testing.additions],
                         [self.mod._spawn_path, self.mod._spawn_path])
        for sdk_path in ("WillowGame.PopulationOpportunityDen:DoSpawning",
                         "WillowGame:PopulationOpportunityDen.DoSpawning",
                         "WillowGame.PopulationOpportunityDen.DoSpawning"):
            with self.subTest(sdk_path=sdk_path):
                self.mod.on_disable()
                self.mod.testing.sdk.find_object = lambda *args: Object(sdk_path)
                self.mod.on_enable()
                self.assertEqual(self.mod._spawn_path, "WillowGame.PopulationOpportunityDen:DoSpawning")
                self.assertEqual(self.mod.testing.additions[-1][0], self.mod._spawn_path)

    def test_function_inventory_accepts_windows_sdk_colon_path(self):
        self.mod.on_disable()
        self.mod.testing.sdk.find_object = lambda *args: None
        self.mod.testing.sdk.find_all = lambda cls: [Object("WillowGame.PopulationOpportunityDen:DoSpawning")]
        self.mod.on_enable()
        self.assertEqual(self.mod._spawn_path, "WillowGame.PopulationOpportunityDen:DoSpawning")
        self.assertTrue(self.mod._ready)

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
        self.assertTrue(self.mod._ready)
        self.assertTrue(self.mod._errors)
        self.assertEqual(len(self.mod.testing.removals), 4)

    def test_diagnostics_is_read_only_and_json_serialisable(self):
        pawn, = self.spawn(count=1)
        self.die(pawn, 130)
        before = dict(vars(self.den.SpawnData)), dict(self.mod._counts)
        result = self.mod.snapshot()
        json.dumps(result, allow_nan=False)
        self.assertEqual(result["counts"]["tracked_spawns"], 1)
        self.assertEqual(result["dens"][0]["deadline"], 1930)
        self.assertEqual((dict(vars(self.den.SpawnData)), dict(self.mod._counts)), before)

    def test_one_minute_diagnostics_explain_full_lifecycle(self):
        self.mod.respawn_delay.value = "1 minute"
        pawn, = self.spawn(count=1)
        self.die(pawn, 130)
        self.world.TimeSeconds = 189
        self.assertIs(self.attempt(), self.mod.Block)
        report = self.mod.snapshot()
        self.assertEqual(report["counts"]["den_spawn_calls"], 2)
        self.assertEqual(report["counts"]["factory_callbacks"], 1)
        self.assertEqual(report["counts"]["death_callbacks"], 1)
        self.assertEqual(report["dens"][0]["deadline"], 190)
        self.assertEqual([e["event"] for e in report["recent_events"]],
                         ["session_reset", "spawn_tracked", "death_tracked", "group_cleared", "spawn_blocked"])

    def test_skipped_allegiance_and_den_are_explained(self):
        self.spawn(count=1, allegiance="Custom.Unknown")
        self.den.Aspect = Object()
        self.attempt()
        report = self.mod.snapshot()
        self.assertEqual(report["skip_counts"]["scripted_aspect"], 1)
        self.assertEqual(report["skip_counts"]["unknown_or_non_enemy_allegiance"], 1)
        self.assertEqual(report["dens"][0]["ignore_reason"], "unknown_or_non_enemy_allegiance")

    def test_scripted_skag_aspect_export_is_read_only_and_explains_exclusion(self):
        aspect = Object("Arid_Firestone.TheWorld:PersistentLevel.PopulationOpportunityDen_25.MissionPopulationAspect_0")
        aspect.MissionReactions = NS(MissionDefinition="gd_Missions.TestMission",
                                     MissionStatusOpportunityReaction=(1, 1, 1, 0))
        aspect.MissionItems = NS(MissionDefinition=None, MissionItemPool="gd_Items.QuestPool")
        aspect.MissionObjective = NS(MissionDefinition=None, ObjectiveIndex=-1)
        cls = Object("WillowGame.MissionPopulationAspect")
        cls._properties = lambda: (_ for _ in ()).throw(AssertionError("No raw schema dumps"))
        aspect.Class = cls
        self.den.Aspect = aspect
        self.den.SpawnData.PopulationDefName = "SkagDen_Regular"
        self.den.SpawnData.NumActiveActors = 0
        self.den.SpawnData.NumTotalActors = 5
        self.mod.testing.sdk.find_all = lambda name: [self.den] if name == "PopulationOpportunityDen" else []
        before = dict(vars(self.den.SpawnData)), dict(vars(aspect))
        report = self.mod.snapshot()
        row, = report["native_dens"]
        self.assertEqual(row["skip_reason"], "scripted_aspect")
        self.assertEqual(set(row["aspect"]["fields"]),
                         {"MissionReactions", "MissionItems", "MissionObjective"})
        self.assertIn("gd_Missions.TestMission", row["aspect"]["fields"]["MissionReactions"])
        self.assertNotIn("read_error", row["aspect"])
        self.assertNotIn("schemas", report)
        self.assertEqual((dict(vars(self.den.SpawnData)), dict(vars(aspect))), before)
        self.assertIsNone(self.mod.aspect_snapshot(None))

    def test_native_inventory_available_without_tracking(self):
        self.mod.testing.sdk.find_all = lambda cls: [self.den] if cls == "PopulationOpportunityDen" else []
        before = dict(vars(self.den.SpawnData))
        report = self.mod.snapshot()
        self.assertEqual(report["native_dens"][0]["spawn_data"]["NextSpawnTime"], 120)
        self.assertFalse(report["native_dens"][0]["tracked"])
        self.assertEqual(dict(vars(self.den.SpawnData)), before)

    def test_diagnostics_export_key_and_button_write_even_when_not_ready(self):
        self.mod._ready = False
        key, = self.mod.testing.build[0]["keybinds"]
        self.assertEqual(key.key, "F8")
        with tempfile.TemporaryDirectory() as folder:
            self.mod.SETTINGS_DIR = Path(folder)
            key()
            button = self.mod.testing.build[0]["options"][1]
            button.on_press(button)
            files = list((Path(folder) / "EnemyRespawnTimer").glob("respawn-*.json"))
            self.assertEqual(len(files), 2)
            for file in files:
                report = json.loads(file.read_text())
                self.assertFalse(report["ready"])
                self.assertEqual(report["version"], "1.3.0")
                self.assertNotIn("schemas", report)

    def test_event_buffer_is_bounded_and_reports_dead_weak_references(self):
        pawn, = self.spawn(count=1)
        self.mod._actors[pawn._get_address()] = (lambda: None, self.den._get_address())
        for i in range(250):
            self.mod.trace("test", index=i)
        report = self.mod.snapshot()
        self.assertEqual(len(report["recent_events"]), 200)
        self.assertFalse(report["dens"][0]["actors"][0]["valid"])

    def test_removed_saved_choice_falls_back_to_thirty_minutes(self):
        self.mod.on_disable()
        self.mod.respawn_delay.value = "15 minutes"
        self.mod.on_enable()
        self.assertEqual(self.mod.respawn_delay.value, "30 minutes")

    def prepare_native_den(self, count=2, allegiance="gd_allegiance.HumanoidEnemy.BanditAllegiance"):
        self.den.SpawnData.NumActiveActors = count
        self.den.SpawnData.NumTotalActors = count
        self.den.MaxTotalActors = count
        self.den.SpawnedDenMembers = []
        for i in range(count):
            pawn = Object("TheWorld.NativePawn" + str(i))
            pawn.bIsDead = False
            pawn.Allegiance = Object(allegiance)
            self.den.SpawnedDenMembers.append(pawn)
            self.pawns.append(pawn)
        self.mod.testing.sdk.find_all = lambda cls: [self.den] if cls == "PopulationOpportunityDen" else []
        self.mod.respawn_delay.value = "1 minute"
        self.mod.poll_tick(None, None, None, None)
        return list(self.den.SpawnedDenMembers)

    def native_kill(self, pawn, now, callback=True):
        self.world.TimeSeconds = now
        pawn.bIsDead = True
        self.den.SpawnedDenMembers.remove(pawn)
        self.den.SpawnData.NumActiveActors -= 1
        if callback:
            self.mod.record_death(pawn, None, None, None)
        self.mod.poll_tick(None, None, None, None)

    def test_recorded_kroms_bridge_bandits_track_clear_and_rearm(self):
        # 1.2.0 exports: 11.893s alive; 36.630s both dead; 130.911s still empty.
        # Previously all 301 polls rejected this exact captured allegiance.
        self.den.path = "Scrap_Canyon_P.TheWorld:PersistentLevel.PopulationOpportunityDen_31"
        self.world.TimeSeconds = 11.893261909484863
        first, second = self.prepare_native_den(
            allegiance="gd_allegiance.humanoidenemy.banditallegiance")
        entry = self.mod._dens[self.den._get_address()]
        self.assertFalse(entry["ignored"])
        self.assertEqual(len(entry["group"].members), 2)
        self.native_kill(first, 30)
        self.native_kill(second, 36.62998962402344)
        self.assertEqual(entry["group"].cleared_at, 36.62998962402344)
        self.assertAlmostEqual(self.den.SpawnData.NextSpawnTime, 96.62998962402344)
        self.world.TimeSeconds = 96.12998962402344
        self.mod.poll_tick(None, None, None, None)
        self.assertEqual(self.den.SpawnData.NumTotalActors, 2)
        self.world.TimeSeconds = 130.9114532470703
        self.mod.poll_tick(None, None, None, None)
        self.assertTrue(entry["released"])
        self.assertEqual(self.den.SpawnData.NumTotalActors, 0)
        self.assertEqual(self.mod._counts["tracked_spawns"], 2)
        self.assertEqual(self.mod._counts["cleared_groups"], 1)
        self.assertEqual(self.mod._counts["rearmed_groups"], 1)

    def test_humanoid_enemy_paths_keep_friendly_neutral_and_unknown_exclusions(self):
        for path, expected in (
            ("gd_allegiance.HumanoidEnemy:BanditAllegiance", True),
            ("gd_allegiance.HumanoidEnemy.BanditAllegiance", True),
            ("gd_allegiance.HumanoidEnemy.FriendlyNPC", False),
            ("gd_allegiance.HumanoidEnemy.NeutralNPC", False),
            ("gd_allegiance.HumanoidEnemy.Player", False),
            ("gd_allegiance.NotHumanoidEnemy.BanditAllegiance", False),
            ("gd_allegiance.Friendly.NPC", False),
        ):
            with self.subTest(path=path):
                self.setUp()
                self.prepare_native_den(1, allegiance=path)
                entry = self.mod._dens[self.den._get_address()]
                self.assertEqual(not entry["ignored"], expected)
                self.assertEqual(len(entry["group"].members), int(expected))

    def make_fyrestone_aspect(self):
        aspect = Object("Arid_Firestone.TheWorld:PersistentLevel.PopulationOpportunityDen_25.MissionPopulationAspect_0")
        aspect.Class = Object("WillowGame.MissionPopulationAspect")
        aspect.MissionReactions = NS(
            MissionDefinition=Object("Z0_Missions.Missions.M_RepairClapTrap_02"),
            MissionStatusOpportunityReaction=(1, 1, 1, 0))
        aspect.MissionItems = NS(MissionDefinition=None, MissionItemPool=None)
        aspect.MissionObjective = NS(MissionDefinition=None, ObjectiveIndex=-1)
        return aspect

    def test_captured_enabled_fyrestone_skag_gate_can_clear_and_rearm(self):
        self.den.Aspect = self.make_fyrestone_aspect()
        self.den.IsEnabled = True
        pawn, = self.prepare_native_den(1, allegiance="gd_allegiance.creatureenemy.skagallegiance")
        before = self.den.Aspect.MissionReactions.MissionStatusOpportunityReaction
        self.native_kill(pawn, 110)
        self.assertEqual(self.mod._counts["cleared_groups"], 1)
        self.world.TimeSeconds = 170
        self.mod.poll_tick(None, None, None, None)
        self.assertEqual(self.mod._counts["rearmed_groups"], 1)
        self.assertEqual(self.den.SpawnData.NumTotalActors, 0)
        self.assertEqual(self.den.Aspect.MissionReactions.MissionStatusOpportunityReaction, before)
        self.assertTrue(self.den.IsEnabled)

    def test_mission_gate_rejects_objectives_items_and_unknown_layouts(self):
        for change in ("disabled", "no_respawn", "objective", "objective_index", "item_mission",
                       "item_pool", "invalid_pattern", "unknown_class", "missing_layout"):
            with self.subTest(change=change):
                self.setUp()
                self.den.IsEnabled = True
                aspect = self.make_fyrestone_aspect()
                self.den.Aspect = aspect
                if change == "disabled": self.den.IsEnabled = False
                elif change == "no_respawn": self.den.bNoRespawning = True
                elif change == "objective": aspect.MissionObjective.MissionDefinition = Object()
                elif change == "objective_index": aspect.MissionObjective.ObjectiveIndex = 0
                elif change == "item_mission": aspect.MissionItems.MissionDefinition = Object()
                elif change == "item_pool": aspect.MissionItems.MissionItemPool = Object()
                elif change == "invalid_pattern": aspect.MissionReactions.MissionStatusOpportunityReaction = (1, 0, 4, 0)
                elif change == "unknown_class": aspect.Class = Object("WillowGame.OtherAspect")
                elif change == "missing_layout": del aspect.MissionObjective
                self.prepare_native_den(1, allegiance="gd_allegiance.creatureenemy.skagallegiance")
                self.assertNotIn(self.den._get_address(), self.mod._dens)
                self.assertEqual(self.den.SpawnData.NumTotalActors, 1)

    def test_enabled_unconditional_mission_gate_without_payload_is_allowed(self):
        self.den.IsEnabled = True
        self.den.Aspect = self.make_fyrestone_aspect()
        self.den.Aspect.MissionReactions.MissionDefinition = None
        self.den.Aspect.MissionReactions.MissionStatusOpportunityReaction = (0, 0, 0, 0)
        self.assertIsNone(self.mod.den_skip_reason(self.den, self.world))
        # Captured den 1 carries a quest item pool and must still be skipped.
        self.den.Aspect.MissionItems.MissionItemPool = Object("gd_COEMissions.ItemPools.IP_SkagYoung")
        self.assertEqual(self.mod.den_skip_reason(self.den, self.world), "scripted_aspect")

    def test_captured_aqueduct_turret_gate_tracks_two_kills_and_rearms(self):
        # 1.2.3 captures: den 7, AutoTurret_Gatling, two alive -> zero alive.
        self.den.path = "Trash_Aquaduct.TheWorld:PersistentLevel.PopulationOpportunityDen_7"
        self.den.SpawnData.PopulationDefName = "AutoTurret_Gatling"
        self.den.IsEnabled = True
        self.den.Aspect = self.make_fyrestone_aspect()
        reactions = self.den.Aspect.MissionReactions
        reactions.MissionDefinition = Object("Z1_Missions.Missions.M_JaynisCleaningUp")
        reactions.MissionStatusOpportunityReaction = (1, 0, 0, 0)
        first, second = self.prepare_native_den()
        self.assertEqual(self.mod._counts["tracked_spawns"], 2)
        self.native_kill(first, 110)
        self.assertEqual(self.mod._counts["cleared_groups"], 0)
        self.native_kill(second, 120)
        self.assertEqual(self.den.SpawnData.NextSpawnTime, 180)
        self.world.TimeSeconds = 179
        self.mod.poll_tick(None, None, None, None)
        self.assertEqual(self.den.SpawnData.NumTotalActors, 2)
        self.world.TimeSeconds = 180
        self.mod.poll_tick(None, None, None, None)
        self.assertEqual(self.mod._counts["rearmed_groups"], 1)
        self.assertEqual(self.den.SpawnData.NumTotalActors, 0)
        self.assertEqual(reactions.MissionStatusOpportunityReaction, (1, 0, 0, 0))
        self.assertTrue(self.den.IsEnabled)

    def test_all_256_known_gate_combinations_track_clear_and_rearm(self):
        for states in product(range(4), repeat=4):
            for linked_mission in (False, True):
                with self.subTest(states=states, linked_mission=linked_mission):
                    self.setUp()
                    self.den.IsEnabled = True
                    self.den.Aspect = self.make_fyrestone_aspect()
                    reactions = self.den.Aspect.MissionReactions
                    reactions.MissionStatusOpportunityReaction = states
                    if not linked_mission:
                        reactions.MissionDefinition = None
                    pawn, = self.prepare_native_den(1)
                    self.assertEqual(self.mod._counts["tracked_spawns"], 1)
                    self.native_kill(pawn, 110)
                    self.world.TimeSeconds = 170
                    self.mod.poll_tick(None, None, None, None)
                    self.assertEqual(self.mod._counts["rearmed_groups"], 1)
                    self.assertEqual(reactions.MissionStatusOpportunityReaction, states)
                    self.assertTrue(self.den.IsEnabled)

    def test_all_256_known_gate_combinations_preserve_other_exclusions(self):
        for states in product(range(4), repeat=4):
            for exclusion in ("disabled", "no_respawn", "objective", "items"):
                with self.subTest(states=states, exclusion=exclusion):
                    self.setUp()
                    self.den.IsEnabled = True
                    self.den.Aspect = self.make_fyrestone_aspect()
                    self.den.Aspect.MissionReactions.MissionStatusOpportunityReaction = states
                    if exclusion == "disabled": self.den.IsEnabled = False
                    elif exclusion == "no_respawn": self.den.bNoRespawning = True
                    elif exclusion == "objective": self.den.Aspect.MissionObjective.MissionDefinition = Object()
                    elif exclusion == "items": self.den.Aspect.MissionItems.MissionItemPool = Object()
                    self.assertIsNotNone(self.mod.den_skip_reason(self.den, self.world))

    def test_captured_skag_gully_respawn_reactions_are_tracked_and_guarded_on_forever(self):
        fixture = json.loads((ROOT / "tests/fixtures/skag-gully-reaction-values.json").read_text())
        self.assertEqual(len(fixture["records"]), 3)
        for record in fixture["records"]:
            with self.subTest(den=record["den"], states=record["states"]):
                self.setUp()
                self.den.path = record["den"]
                self.den.Location = record["location"]
                self.den.SpawnData.PopulationDefName = record["definition"]
                self.den.IsEnabled = True
                self.den.Aspect = self.make_fyrestone_aspect()
                reactions = self.den.Aspect.MissionReactions
                reactions.MissionDefinition = Object(record["mission"])
                reactions.MissionStatusOpportunityReaction = tuple(record["states"])
                first, second = self.prepare_native_den(2, allegiance="gd_allegiance.CreatureEnemy.SkagAllegiance")
                self.mod.respawn_delay.value = "Forever (until reload)"
                self.native_kill(first, 110)
                self.native_kill(second, 120)
                entry = self.mod._dens[self.den._get_address()]
                self.assertEqual(self.mod._counts["cleared_groups"], 1)
                self.assertTrue(self.den.bNoRespawning)
                self.assertFalse(entry["ignored"])
                self.world.TimeSeconds = 2000
                self.mod.poll_tick(None, None, None, None)
                self.assertTrue(self.den.bNoRespawning)
                self.assertEqual(self.mod._counts["rearmed_groups"], 0)
                self.assertEqual(entry["group"].cleared_at, 120)
                self.assertEqual(tuple(reactions.MissionStatusOpportunityReaction), tuple(record["states"]))

    def test_invalid_gate_table_shapes_and_values_are_excluded(self):
        self.den.IsEnabled = True
        self.den.Aspect = self.make_fyrestone_aspect()
        for states in ((), (1, 0, 0), (1, 0, 0, 0, 0), (1, 4, 0, 0), (-1, 0, 0, 0), None):
            with self.subTest(states=states):
                self.den.Aspect.MissionReactions.MissionStatusOpportunityReaction = states
                self.assertFalse(self.mod.passive_mission_gate(self.den, self.den.Aspect))

    def test_native_membership_without_any_den_hook_rearms_exactly_once(self):
        first, second = self.prepare_native_den()
        self.assertEqual(self.mod._counts["den_spawn_calls"], 0)
        self.assertEqual(self.mod._counts["tracked_spawns"], 2)
        self.native_kill(first, 110)
        self.assertEqual(self.mod._counts["cleared_groups"], 0)
        self.native_kill(second, 130)
        self.assertEqual(self.den.SpawnData.NextSpawnTime, 190)
        self.world.TimeSeconds = 189.5
        self.mod.poll_tick(None, None, None, None)
        self.assertEqual(self.den.SpawnData.NumTotalActors, 2)
        self.world.TimeSeconds = 190
        self.mod.poll_tick(None, None, None, None)
        self.assertEqual(self.den.SpawnData.NumTotalActors, 0)
        self.assertEqual(self.den.SpawnData.NextSpawnTime, 0)
        self.assertEqual(self.mod._counts["rearmed_groups"], 1)
        self.world.TimeSeconds = 200
        self.mod.poll_tick(None, None, None, None)
        self.assertEqual(self.mod._counts["rearmed_groups"], 1)
        self.assertEqual(self.mod.snapshot()["tracking_mode"], "native_den_members")

    def test_native_second_generation_can_clear_and_rearm_again(self):
        pawn, = self.prepare_native_den(1)
        self.native_kill(pawn, 110)
        self.world.TimeSeconds = 170
        self.mod.poll_tick(None, None, None, None)
        other = Object("TheWorld.NewGeneration")
        other.bIsDead = False
        other.Allegiance = Object("gd_allegiance.HumanEnemy:Bandit")
        self.den.SpawnedDenMembers = [other]
        self.den.SpawnData.NumTotalActors = self.den.SpawnData.NumActiveActors = 1
        self.world.TimeSeconds = 171
        self.mod.poll_tick(None, None, None, None)
        self.native_kill(other, 180)
        self.assertEqual(self.den.SpawnData.NextSpawnTime, 240)
        self.world.TimeSeconds = 240
        self.mod.poll_tick(None, None, None, None)
        self.assertEqual(self.mod._counts["rearmed_groups"], 2)

    def test_poll_recovers_missed_death_callback_but_never_guesses_disappearance(self):
        first, second = self.prepare_native_den()
        self.native_kill(first, 110, callback=False)
        self.assertEqual(self.mod._counts["cleared_groups"], 0)
        self.native_kill(second, 120, callback=False)
        self.assertEqual(self.mod._counts["cleared_groups"], 1)
        self.mod.reset_session()
        pawn, = self.prepare_native_den(1)
        self.mod._actors[pawn._get_address()] = (lambda: None, self.den._get_address())
        self.den.SpawnedDenMembers = []
        self.den.SpawnData.NumActiveActors = 0
        self.world.TimeSeconds = 140
        self.mod.poll_tick(None, None, None, None)
        entry = self.mod._dens[self.den._get_address()]
        self.assertFalse(entry["ignored"])
        self.assertTrue(entry["suspended"])
        self.assertIsNone(entry["group"].cleared_at)

    def test_disappeared_member_is_replaced_without_permanently_excluding_den(self):
        old, = self.prepare_native_den(1)
        self.mod._actors[old._get_address()] = (lambda: None, self.den._get_address())
        replacement = Object("TheWorld.ReplacementPawn")
        replacement.bIsDead = False
        replacement.Allegiance = old.Allegiance
        self.den.SpawnedDenMembers = [replacement]
        self.world.TimeSeconds = 110
        self.mod.poll_tick(None, None, None, None)
        entry = self.mod._dens[self.den._get_address()]
        self.assertFalse(entry["ignored"])
        self.assertFalse(entry["suspended"])
        self.assertEqual(entry["group"].members, {replacement._get_address()})
        self.assertNotIn(old._get_address(), self.mod._actors)
        self.assertEqual(self.mod._counts["cleared_groups"], 0)
        self.native_kill(replacement, 120)
        self.world.TimeSeconds = 180
        self.mod.poll_tick(None, None, None, None)
        self.assertEqual(self.mod._counts["cleared_groups"], 1)
        self.assertEqual(self.mod._counts["rearmed_groups"], 1)

    def test_captured_rust_commons_dens_recover_after_native_actor_replacement(self):
        fixture = json.loads((ROOT / "tests/fixtures/rust-commons-west-disappearances.json").read_text())
        self.assertEqual(len(fixture["records"]), 6)
        for record in fixture["records"]:
            with self.subTest(den=record["den"], definition=record["definition"]):
                self.setUp()
                self.den.path = record["den"]
                self.den.Location = record["location"]
                self.den.SpawnData.PopulationDefName = record["definition"]
                old, = self.prepare_native_den(1)
                self.mod._actors[old._get_address()] = (lambda: None, self.den._get_address())
                self.den.SpawnedDenMembers = []
                self.den.SpawnData.NumActiveActors = 0
                self.world.TimeSeconds = 110
                self.mod.poll_tick(None, None, None, None)
                entry = self.mod._dens[self.den._get_address()]
                self.assertTrue(entry["suspended"])
                replacement = Object("Loader.TheWorld:PersistentLevel.ReplacementPawn")
                replacement.bIsDead = False
                replacement.Allegiance = old.Allegiance
                self.den.SpawnedDenMembers = [replacement]
                self.den.SpawnData.NumActiveActors = 1
                self.world.TimeSeconds = 120
                self.mod.poll_tick(None, None, None, None)
                self.assertFalse(entry["suspended"])
                self.native_kill(replacement, 130)
                self.world.TimeSeconds = 190
                self.mod.poll_tick(None, None, None, None)
                self.assertEqual(self.mod._counts["rearmed_groups"], 1)
                recovery = [e for e in self.mod._events if e["event"] == "tracking_recovered"][-1]
                self.assertEqual(recovery["definition"], record["definition"])
                self.assertEqual(recovery["location"], record["location"])

    def test_empty_uncertain_den_waits_then_recovers_when_native_members_return(self):
        old, = self.prepare_native_den(1)
        self.mod._actors[old._get_address()] = (lambda: None, self.den._get_address())
        self.den.SpawnedDenMembers = []
        self.den.SpawnData.NumActiveActors = 0
        self.world.TimeSeconds = 110
        self.mod.poll_tick(None, None, None, None)
        entry = self.mod._dens[self.den._get_address()]
        self.assertTrue(entry["suspended"])
        self.world.TimeSeconds = 300
        self.mod.poll_tick(None, None, None, None)
        self.assertEqual(self.mod._counts["cleared_groups"], 0)
        self.assertEqual(self.den.SpawnData.NumTotalActors, 1)
        self.den.SpawnedDenMembers = [old]
        self.den.SpawnData.NumActiveActors = 1
        self.world.TimeSeconds = 301
        self.mod.poll_tick(None, None, None, None)
        self.assertFalse(entry["suspended"])
        self.native_kill(old, 310)
        self.assertEqual(entry["group"].deadline("1 minute"), 370)

    def test_still_valid_actor_removed_from_native_den_is_reconciled(self):
        old, = self.prepare_native_den(1)
        self.den.SpawnedDenMembers = []
        self.den.SpawnData.NumActiveActors = 0
        self.world.TimeSeconds = 110
        self.mod.poll_tick(None, None, None, None)
        entry = self.mod._dens[self.den._get_address()]
        self.assertTrue(entry["suspended"])
        self.assertNotIn(old._get_address(), self.mod._actors)
        self.assertIsNone(entry["group"].cleared_at)

    def test_incomplete_native_list_cannot_resume_or_start_cooldown(self):
        old, survivor = self.prepare_native_den(2)
        self.mod._actors[old._get_address()] = (lambda: None, self.den._get_address())
        self.den.SpawnedDenMembers = [survivor]
        # Native count still reports two: one known pawn is insufficient.
        self.world.TimeSeconds = 110
        self.mod.poll_tick(None, None, None, None)
        entry = self.mod._dens[self.den._get_address()]
        self.assertTrue(entry["suspended"])
        self.native_kill(survivor, 120)
        self.assertEqual(self.mod._counts["cleared_groups"], 0)
        self.assertIsNone(entry["group"].cleared_at)

    def test_forever_cooldown_survives_native_member_absence(self):
        pawn, = self.prepare_native_den(1)
        self.mod.respawn_delay.value = "Forever (until reload)"
        self.native_kill(pawn, 110)
        self.world.TimeSeconds = 10000
        self.mod.poll_tick(None, None, None, None)
        entry = self.mod._dens[self.den._get_address()]
        self.assertFalse(entry["suspended"])
        self.assertTrue(entry["group"].blocked(10000, self.mod.respawn_delay.value))
        self.assertEqual(self.den.SpawnData.NumTotalActors, 1)

    def remove_without_dead_flag(self, pawn, when, returned=None, remove=True):
        self.world.TimeSeconds = when
        self.mod.record_death(pawn, None, returned, None)
        if remove:
            self.den.SpawnedDenMembers.remove(pawn)
            self.den.SpawnData.NumActiveActors -= 1
        self.mod.poll_tick(None, None, None, None)

    def test_turret_death_callback_plus_native_removal_starts_cooldown(self):
        self.den.SpawnData.PopulationDefName = "AutoTurret_Gatling"
        first, second = self.prepare_native_den()
        self.remove_without_dead_flag(first, 110)
        self.assertEqual(self.mod._counts["cleared_groups"], 0)
        self.remove_without_dead_flag(second, 120)
        self.assertEqual(self.mod._counts["cleared_groups"], 1)
        self.assertEqual(self.mod._counts["deaths_confirmed_by_native_removal"], 2)
        self.assertEqual(self.den.SpawnData.NextSpawnTime, 180)
        self.assertFalse(first.bIsDead)
        self.assertFalse(second.bIsDead)
        self.world.TimeSeconds = 180
        self.mod.poll_tick(None, None, None, None)
        self.assertEqual(self.mod._counts["rearmed_groups"], 1)

    def test_death_evidence_survives_pawn_expiring_before_poll(self):
        pawn, = self.prepare_native_den(1)
        self.world.TimeSeconds = 110
        self.mod.record_death(pawn, None, True, None)
        self.mod._actors[pawn._get_address()] = (lambda: None, self.den._get_address())
        self.den.SpawnedDenMembers = []
        self.den.SpawnData.NumActiveActors = 0
        self.world.TimeSeconds = 110.5
        self.mod.poll_tick(None, None, None, None)
        self.assertEqual(self.den.SpawnData.NextSpawnTime, 170)
        self.assertEqual(self.mod._counts["cleared_groups"], 1)

    def test_rejected_death_return_cannot_turn_disappearance_into_clear(self):
        pawn, = self.prepare_native_den(1)
        self.remove_without_dead_flag(pawn, 110, returned=False)
        entry = self.mod._dens[self.den._get_address()]
        self.assertTrue(entry["suspended"])
        self.assertEqual(self.mod._counts["cleared_groups"], 0)

    def test_death_callback_with_still_living_native_member_is_not_a_kill(self):
        pawn, = self.prepare_native_den(1)
        self.remove_without_dead_flag(pawn, 110, remove=False)
        self.world.TimeSeconds = 113
        self.mod.poll_tick(None, None, None, None)
        entry = self.mod._dens[self.den._get_address()]
        self.assertEqual(entry["death_evidence"], {})
        self.den.SpawnedDenMembers = []
        self.den.SpawnData.NumActiveActors = 0
        self.world.TimeSeconds = 114
        self.mod.poll_tick(None, None, None, None)
        self.assertEqual(self.mod._counts["cleared_groups"], 0)
        self.assertTrue(entry["suspended"])

    def test_native_count_mismatch_does_not_confirm_candidate_death(self):
        pawn, = self.prepare_native_den(1)
        self.world.TimeSeconds = 110
        self.mod.record_death(pawn, None, True, None)
        self.den.SpawnedDenMembers = []
        # Active count remains 1: no corroborating removal.
        self.mod.poll_tick(None, None, None, None)
        self.assertEqual(self.mod._counts["cleared_groups"], 0)

    def test_late_confirmation_uses_last_kill_time_not_earlier_callback(self):
        first, second = self.prepare_native_den()
        self.world.TimeSeconds = 110
        self.mod.record_death(first, None, None, None)
        self.den.SpawnedDenMembers.remove(first)
        self.den.SpawnData.NumActiveActors -= 1
        self.world.TimeSeconds = 111
        second.bIsDead = True
        self.den.SpawnedDenMembers.remove(second)
        self.den.SpawnData.NumActiveActors -= 1
        self.mod.record_death(second, None, None, None)
        self.mod.poll_tick(None, None, None, None)
        self.assertEqual(self.den.SpawnData.NextSpawnTime, 171)

    def test_captured_forever_clear_retains_native_guard_through_late_timestamp_reset(self):
        fixture = json.loads((ROOT / "tests/fixtures/forever-native-bypass.json").read_text())
        cleared = next(e for e in fixture["events"] if e["event"] == "group_cleared")
        deaths = [e["death_time"] for e in fixture["events"] if e["event"] == "death_confirmed_by_native_removal"]
        new_spawn = next(e for e in fixture["events"]
                         if e["event"] == "spawn_tracked" and e["game_time"] > cleared["game_time"])
        self.den.path = fixture["den"]
        self.den.SpawnData.PopulationDefName = "AutoTurret_Gatling"
        first, second = self.prepare_native_den()
        self.mod.respawn_delay.value = "Forever (until reload)"
        self.remove_without_dead_flag(first, deaths[0], returned=True)
        self.remove_without_dead_flag(second, deaths[1], returned=True)
        entry = self.mod._dens[self.den._get_address()]
        self.assertTrue(self.den.bNoRespawning)
        self.assertIsNone(self.mod.den_skip_reason(self.den, self.world))
        self.assertAlmostEqual(entry["group"].cleared_at, deaths[-1])
        # Reproduce the native schedule being reset long after the clear.
        self.den.SpawnData.NextSpawnTime = 0
        self.den.SpawnData.NumTotalActors = 0
        self.world.TimeSeconds = new_spawn["game_time"]
        self.mod.poll_tick(None, None, None, None)
        self.assertTrue(self.den.bNoRespawning)
        self.assertGreater(self.den.SpawnData.NextSpawnTime, self.world.TimeSeconds)
        self.assertEqual(self.mod._counts["rearmed_groups"], 0)
        self.assertEqual(entry["group"].cleared_at, deaths[-1])
        report = self.mod.snapshot()
        self.assertTrue(report["dens"][0]["owns_no_respawn_guard"])
        self.assertTrue(report["dens"][0]["native_no_respawn"])

    def test_recorded_rakk_den_is_disabled_after_clear_and_stays_disabled_through_reset(self):
        fixture = json.loads((ROOT / "tests/fixtures/rakk-guard-bypass.json").read_text())
        self.den.path = fixture["den"]
        self.den.SpawnData.PopulationDefName = "RakkSquad_Regular"
        pawns = self.prepare_native_den(6, allegiance="gd_allegiance.CreatureEnemy.RakkAllegiance")
        self.mod.respawn_delay.value = "Forever (until reload)"
        deaths = fixture["deaths"]
        self.assertEqual(len(deaths), 6)
        self.assertTrue(self.den.IsEnabled)
        for pawn, death in zip(pawns, deaths):
            self.native_kill(pawn, death["game_time"])
        entry = self.mod._dens[self.den._get_address()]
        self.assertFalse(self.den.IsEnabled)
        self.assertTrue(self.den.bNoRespawning)
        self.assertTrue(entry["original_enabled"])
        bypass = next(e for e in fixture["events"] if e["event"] == "spawn_during_cooldown")
        self.world.TimeSeconds = bypass["game_time"]
        # Original capture changed quota/active limit despite the no-respawn flag.
        self.den.SpawnData.NumTotalActors = 0
        self.den.SpawnData.MaxActiveActors = 5
        self.mod.poll_tick(None, None, None, None)
        self.assertFalse(self.den.IsEnabled)
        self.assertEqual(self.mod._counts["rearmed_groups"], 0)
        self.assertEqual(entry["group"].cleared_at, deaths[-1]["game_time"])
        report = self.mod.snapshot()
        self.assertTrue(report["dens"][0]["owns_activation_guard"])
        self.assertFalse(report["dens"][0]["native_enabled"])

    def test_guard_reapplies_activation_if_native_state_is_reset(self):
        pawn, = self.prepare_native_den(1)
        self.mod.respawn_delay.value = "Forever (until reload)"
        self.native_kill(pawn, 110)
        self.den.IsEnabled = True
        self.den.bNoRespawning = False
        self.world.TimeSeconds = 1100
        self.mod.poll_tick(None, None, None, None)
        self.assertFalse(self.den.IsEnabled)
        self.assertTrue(self.den.bNoRespawning)
        self.assertEqual(self.mod._counts["rearmed_groups"], 0)

    def test_preexisting_disabled_activation_is_preserved_on_cleanup(self):
        pawn, = self.prepare_native_den(1)
        self.den.IsEnabled = False  # A native/script change before the clear.
        self.native_kill(pawn, 110)
        entry = self.mod._dens[self.den._get_address()]
        self.assertIsNone(entry["original_enabled"])
        self.mod.on_disable()
        self.assertFalse(self.den.IsEnabled)

    def test_staged_mission_aspect_activation_is_not_overridden(self):
        self.den.IsEnabled = True
        self.den.Aspect = self.make_fyrestone_aspect()
        self.den.Aspect.MissionReactions.MissionStatusOpportunityReaction = (1, 0, 1, 0)
        pawn, = self.prepare_native_den(1)
        self.mod.respawn_delay.value = "Forever (until reload)"
        self.native_kill(pawn, 110)
        entry = self.mod._dens[self.den._get_address()]
        self.assertTrue(self.den.IsEnabled)
        self.assertTrue(self.den.bNoRespawning)
        self.assertIsNone(entry["original_enabled"])
        self.world.TimeSeconds = 1100
        self.mod.poll_tick(None, None, None, None)
        self.assertFalse(entry["ignored"])
        self.assertTrue(self.den.IsEnabled)
        self.mod.on_disable()
        self.assertTrue(self.den.IsEnabled)
        self.assertFalse(self.den.bNoRespawning)

    def test_recorded_fyrestone_skag_gate_holds_activation_through_late_reset(self):
        fixture = json.loads((ROOT / "tests/fixtures/fyrestone-mission-guard-bypass.json").read_text())
        self.den.path = fixture["den"]
        self.den.Aspect = self.make_fyrestone_aspect()
        self.den.SpawnData.PopulationDefName = "SkagDen_Regular"
        pawns = self.prepare_native_den(5, allegiance="gd_allegiance.CreatureEnemy.SkagAllegiance")
        self.mod.respawn_delay.value = "Forever (until reload)"
        deaths = fixture["deaths"]
        self.assertEqual(len(deaths), 5)
        for pawn, death in zip(pawns, deaths):
            self.native_kill(pawn, death["game_time"])
        entry = self.mod._dens[self.den._get_address()]
        self.assertTrue(entry["original_enabled"])
        self.assertFalse(self.den.IsEnabled)
        self.assertIsNone(self.mod.den_skip_reason(self.den, self.world))
        bypass = next(e for e in fixture["events"] if e["event"] == "spawn_during_cooldown")
        self.world.TimeSeconds = bypass["game_time"]
        self.den.SpawnData.NumTotalActors = 0
        self.mod.poll_tick(None, None, None, None)
        self.assertFalse(self.den.IsEnabled)
        self.assertTrue(self.den.bNoRespawning)
        self.assertFalse(entry["ignored"])
        self.assertEqual(entry["group"].cleared_at, deaths[-1]["game_time"])
        self.assertEqual(self.mod._counts["rearmed_groups"], 0)

    def test_persistent_gate_activation_is_restored_on_expiry_disable_and_map_reload(self):
        for states in ((0, 0, 0, 0), (1, 0, 0, 0), (1, 1, 0, 0), (1, 1, 1, 0)):
            for action in ("expiry", "disable", "map"):
                with self.subTest(states=states, action=action):
                    self.setUp()
                    self.den.Aspect = self.make_fyrestone_aspect()
                    self.den.Aspect.MissionReactions.MissionStatusOpportunityReaction = states
                    pawn, = self.prepare_native_den(1)
                    self.native_kill(pawn, 110)
                    self.assertFalse(self.den.IsEnabled)
                    self.world.TimeSeconds = 120
                    self.mod.poll_tick(None, None, None, None)
                    entry = self.mod._dens[self.den._get_address()]
                    self.assertFalse(entry["ignored"])
                    if action == "expiry":
                        self.world.TimeSeconds = 170
                        self.mod.poll_tick(None, None, None, None)
                    elif action == "disable":
                        self.mod.on_disable()
                    else:
                        self.mod.map_change(None, None, None, None)
                    self.assertTrue(self.den.IsEnabled)
                    self.assertFalse(self.den.bNoRespawning)
                    self.assertEqual(tuple(self.den.Aspect.MissionReactions.MissionStatusOpportunityReaction), states)

    def test_staged_disable_or_respawn_gate_does_not_acquire_activation(self):
        for states in ((1, 0, 1, 0), (0, 0, 2, 0), (0, 0, 3, 0), (0, 0, 0, 3)):
            with self.subTest(states=states):
                self.setUp()
                self.den.Aspect = self.make_fyrestone_aspect()
                self.den.Aspect.MissionReactions.MissionStatusOpportunityReaction = states
                pawn, = self.prepare_native_den(1)
                self.native_kill(pawn, 110)
                entry = self.mod._dens[self.den._get_address()]
                self.assertTrue(self.den.IsEnabled)
                self.assertIsNone(entry["original_enabled"])
                self.assertTrue(self.den.bNoRespawning)

    def bonehead_den(self):
        self.den.SpawnData.PopulationDefName = "Bandit_Bonehead"
        self.den.bNoRespawning = True
        self.den.Aspect = self.make_fyrestone_aspect()
        self.den.Aspect.MissionObjective.MissionDefinition = Object("Z0_Missions.Missions.M_FixVSS")
        self.den.Aspect.MissionObjective.ObjectiveIndex = 0
        self.den.Aspect.MissionReactions.MissionStatusOpportunityReaction = (1, 0, 1, 0)
        return self.prepare_native_den(1)

    def test_bonehead_first_spawn_and_mission_kill_are_allowed_then_guarded(self):
        pawn, = self.bonehead_den()
        entry = self.mod._dens[self.den._get_address()]
        self.assertEqual(entry["named_enemy"], "Bone Head")
        self.assertTrue(self.den.IsEnabled)
        self.assertEqual(self.mod._counts["tracked_spawns"], 1)
        objective = self.den.Aspect.MissionObjective.MissionDefinition
        self.mod.respawn_delay.value = "Forever (until reload)"
        self.native_kill(pawn, 110)
        self.assertTrue(entry["named_killed"])
        self.assertTrue(entry["original_no_respawn"])
        self.assertFalse(self.den.IsEnabled)
        self.assertEqual(entry["group"].cleared_at, 110)
        self.assertIs(self.den.Aspect.MissionObjective.MissionDefinition, objective)
        self.world.TimeSeconds = 1200
        self.mod.poll_tick(None, None, None, None)
        self.assertFalse(entry["ignored"])
        self.assertFalse(self.den.IsEnabled)
        self.assertEqual(self.mod._counts["rearmed_groups"], 0)
        self.mod.map_change(None, None, None, None)
        self.assertTrue(self.den.IsEnabled)
        self.assertTrue(self.den.bNoRespawning)  # Original native flag restored.
        self.assertEqual(self.mod._dens, {})

    def test_bonehead_finite_expiry_restores_native_flags_without_forcing_spawns(self):
        pawn, = self.bonehead_den()
        self.native_kill(pawn, 110)
        self.world.TimeSeconds = 170
        self.mod.poll_tick(None, None, None, None)
        self.assertTrue(self.den.IsEnabled)
        self.assertTrue(self.den.bNoRespawning)
        self.assertEqual(self.mod._counts["rearmed_groups"], 1)

    def test_exact_catalogue_id_recognizes_dlc_named_enemy_without_population_alias(self):
        self.den.SpawnData.PopulationDefName = "UnaliasedDlcPopulation"
        self.den.bNoRespawning = True
        self.den.Aspect = self.make_fyrestone_aspect()
        self.den.Aspect.MissionObjective.MissionDefinition = Object()
        self.prepare_native_den(0)
        pawn = Object("TheWorld.Knoxx")
        pawn.bIsDead = False
        pawn.Allegiance = Object("gd_allegiance.HumanoidEnemy.Lance")
        pawn.ObjectArchetype = Object("dlc3_gd_clmecha.knoxx.character.pawn_knoxx")
        self.den.SpawnedDenMembers = [pawn]
        self.den.SpawnData.NumActiveActors = self.den.SpawnData.NumTotalActors = 1
        self.world.TimeSeconds = 110
        self.mod.poll_tick(None, None, None, None)
        entry = self.mod._dens[self.den._get_address()]
        self.assertEqual(entry["named_enemy"], "General Knoxx")
        self.native_kill(pawn, 120)
        self.assertFalse(self.den.IsEnabled)
        self.assertTrue(entry["named_killed"])

    def test_factory_balance_identifies_named_actor_when_archetype_is_unavailable(self):
        pawn, = self.prepare_native_den(1)
        self.mod.reset_session()
        self.den.SpawnData.PopulationDefName = "UnaliasedPopulation"
        self.den.bNoRespawning = True
        factory = Object("TheWorld.NamedFactory")
        factory.PawnBalanceDefinition = Object("gd_Balance_Enemies_Humans.Bandits.Named.Pawn_Balance_Bonehead")
        self.mod.record_spawn(factory, None, pawn, None)
        self.mod.poll_tick(None, None, None, None)
        self.assertEqual(self.mod._dens[self.den._get_address()]["named_enemy"], "Bone Head")

    def test_named_kill_starts_cooldown_without_waiting_for_grunts_in_same_den(self):
        boss, grunt = self.prepare_native_den(2)
        boss.ObjectArchetype = Object("gd_banditcaptain1.pawnarchetype.pawn_banditcaptain1")
        entry = self.mod._dens[self.den._get_address()]
        # Late native identity metadata is reconciled on the following poll.
        self.world.TimeSeconds = 105
        self.mod.poll_tick(None, None, None, None)
        self.assertIn(boss._get_address(), entry["named_members"])
        self.assertEqual(entry["named_enemy"], "Bone Head")
        self.mod.respawn_delay.value = "Forever (until reload)"
        self.native_kill(boss, 110)
        self.assertEqual(entry["group"].cleared_at, 110)
        self.assertFalse(self.den.IsEnabled)
        self.assertEqual(len(entry["group"].members), 1)
        self.native_kill(grunt, 120)
        self.assertEqual(entry["group"].cleared_at, 110)
        self.assertEqual(self.mod._counts["cleared_groups"], 1)

    def test_named_catalogue_uses_exact_ids_and_excludes_friendly_variants(self):
        for path, label in self.mod.testing.named.BALANCE_NAMES.items():
            self.assertEqual(self.mod.named_enemy(Object(path), None), label)
            self.assertIsNone(self.mod.named_enemy(Object(path + "_unknown"), None))
        for path, label in self.mod.testing.named.ARCHETYPE_NAMES.items():
            self.assertEqual(self.mod.named_enemy(None, Object(path)), label)
        self.den.SpawnData.PopulationDefName = "Bandit_Bonehead"
        self.spawn(count=1, allegiance="gd_allegiance.Friendly.NPC")
        self.assertTrue(self.mod._dens[self.den._get_address()]["ignored"])

    def test_named_disappearance_without_death_still_does_not_count_as_a_kill(self):
        pawn, = self.bonehead_den()
        self.mod._actors[pawn._get_address()] = (lambda: None, self.den._get_address())
        self.den.SpawnedDenMembers = []
        self.den.SpawnData.NumActiveActors = 0
        self.world.TimeSeconds = 110
        self.mod.poll_tick(None, None, None, None)
        entry = self.mod._dens[self.den._get_address()]
        self.assertFalse(entry["named_killed"])
        self.assertIsNone(entry["group"].cleared_at)
        self.assertTrue(self.den.IsEnabled)

    def test_finite_native_guard_is_released_at_expiry_and_disable_or_map_reload(self):
        for action in ("expiry", "disable", "map"):
            with self.subTest(action=action):
                self.setUp()
                pawn, = self.prepare_native_den(1)
                self.native_kill(pawn, 110)
                self.assertTrue(self.den.bNoRespawning)
                self.assertFalse(self.den.IsEnabled)
                if action == "expiry":
                    self.world.TimeSeconds = 170
                    self.mod.poll_tick(None, None, None, None)
                    self.assertEqual(self.mod._counts["rearmed_groups"], 1)
                elif action == "disable":
                    self.mod.on_disable()
                else:
                    self.mod.map_change(None, None, None, None)
                self.assertFalse(self.den.bNoRespawning)
                self.assertTrue(self.den.IsEnabled)

    def test_preexisting_no_respawn_flag_is_never_acquired_or_restored(self):
        self.den.bNoRespawning = True
        self.mod.testing.sdk.find_all = lambda cls: [self.den] if cls == "PopulationOpportunityDen" else []
        self.mod.poll_tick(None, None, None, None)
        self.assertNotIn(self.den._get_address(), self.mod._dens)
        self.mod.on_disable()
        self.assertTrue(self.den.bNoRespawning)

    def test_unexpected_spawn_cannot_silently_erase_forever_cooldown(self):
        pawn, = self.prepare_native_den(1)
        self.mod.respawn_delay.value = "Forever (until reload)"
        self.native_kill(pawn, 110)
        entry = self.mod._dens[self.den._get_address()]
        original_clear = entry["group"].cleared_at
        unexpected = Object("TheWorld.BypassPawn")
        unexpected.bIsDead = False
        unexpected.Allegiance = Object("gd_allegiance.HumanoidEnemy.BanditAllegiance")
        self.den.SpawnedDenMembers = [unexpected]
        self.den.SpawnData.NumActiveActors = 1
        self.den.bNoRespawning = False  # External/script bypass of owned guard.
        self.world.TimeSeconds = 1100
        self.mod.poll_tick(None, None, None, None)
        self.assertEqual(entry["group"].cleared_at, original_clear)
        self.assertEqual(self.mod._counts["cooldown_bypasses"], 1)
        self.assertTrue(self.den.bNoRespawning)
        self.assertEqual(self.mod._events[-1]["event"], "spawn_during_cooldown")
        self.world.TimeSeconds = 1101
        self.mod.poll_tick(None, None, None, None)
        self.assertEqual(self.mod._counts["cooldown_bypasses"], 1)

    def test_changing_forever_to_finite_releases_guard_after_original_clear_delay(self):
        pawn, = self.prepare_native_den(1)
        self.mod.respawn_delay.value = "Forever (until reload)"
        self.native_kill(pawn, 110)
        self.world.TimeSeconds = 200
        self.mod.respawn_delay.value = "1 minute"
        self.mod.change_delay(None, "1 minute")
        self.mod.poll_tick(None, None, None, None)
        self.assertFalse(self.den.bNoRespawning)
        self.assertEqual(self.mod._counts["rearmed_groups"], 1)

    def test_null_den_world_skips_without_losing_forever_timer_or_native_guard(self):
        pawn, = self.prepare_native_den(1)
        self.mod.respawn_delay.value = "Forever (until reload)"
        self.native_kill(pawn, 110)
        entry = self.mod._dens[self.den._get_address()]
        self.den.WorldInfo = None
        self.world.TimeSeconds = 200
        self.mod.poll_tick(None, None, None, None)
        self.assertEqual(self.mod._errors, [])
        self.assertFalse(entry["ignored"])
        self.assertEqual(entry["group"].cleared_at, 110)
        self.assertTrue(self.den.bNoRespawning)
        self.assertEqual(self.mod._skips["missing_den_world"], 1)
        self.den.WorldInfo = self.world
        self.world.TimeSeconds = 201
        self.mod.poll_tick(None, None, None, None)
        self.assertFalse(entry["ignored"])
        self.assertTrue(self.den.bNoRespawning)
        self.assertEqual(self.mod._errors, [])

    def test_null_player_world_skips_without_resetting_existing_session(self):
        pawn, = self.prepare_native_den(1)
        self.native_kill(pawn, 110)
        before = self.mod._dens[self.den._get_address()]
        self.mod.testing.pc.WorldInfo = None
        self.mod.poll_tick(None, None, None, None)
        self.mod.record_death(pawn, None, None, None)
        self.assertEqual(self.mod._errors, [])
        self.assertIs(self.mod._dens[self.den._get_address()], before)
        self.assertTrue(self.den.bNoRespawning)
        self.mod.testing.pc.WorldInfo = self.world
        self.world.TimeSeconds = 170
        self.mod.poll_tick(None, None, None, None)
        self.assertEqual(self.mod._counts["rearmed_groups"], 1)

    def test_null_native_member_does_not_invent_a_kill_or_suspend_tracking(self):
        pawn, = self.prepare_native_den(1)
        self.den.SpawnedDenMembers = [None]
        self.world.TimeSeconds = 110
        self.mod.poll_tick(None, None, None, None)
        entry = self.mod._dens[self.den._get_address()]
        self.assertEqual(entry["group"].members, {pawn._get_address()})
        self.assertFalse(entry["suspended"])
        self.assertEqual(self.mod._counts["cleared_groups"], 0)
        self.assertEqual(self.mod._errors, [])
        self.den.SpawnedDenMembers = [pawn]
        self.native_kill(pawn, 120)
        self.assertEqual(entry["group"].cleared_at, 120)

    def test_null_den_inventory_and_callback_targets_skip_cleanly(self):
        self.mod.testing.sdk.find_all = lambda name: [None] if name == "PopulationOpportunityDen" else []
        self.mod.poll_tick(None, None, None, None)
        self.mod.record_death(None, None, None, None)
        self.mod.before_spawning(None, None, None, None)
        self.mod.after_spawning(None, None, None, None)
        self.assertEqual(self.mod._stack, [])
        self.assertEqual(self.mod._errors, [])
        self.assertEqual(self.mod.snapshot()["native_dens"], [])
        self.assertEqual(self.mod.den_skip_reason(None, self.world), "missing_den")
        self.assertEqual(self.mod.den_skip_reason(self.den, None), "missing_player_world")

    def test_error_report_includes_original_source_function(self):
        try:
            raise RuntimeError("diagnostic source test")
        except RuntimeError as exc:
            self.mod.error(exc)
        self.assertIn("test_error_report_includes_original_source_function", self.mod._errors[0])
        self.assertIn("test_respawn.py:", self.mod._errors[0])

    def test_forever_never_releases_native_quota(self):
        pawn, = self.prepare_native_den(1)
        self.mod.respawn_delay.value = "Forever (until reload)"
        self.native_kill(pawn, 110)
        self.world.TimeSeconds = 1_000_000_000
        self.mod.poll_tick(None, None, None, None)
        self.assertEqual(self.den.SpawnData.NumTotalActors, 1)
        self.assertEqual(self.mod._counts["rearmed_groups"], 0)

    def test_disable_restores_unconsumed_quota_but_preserves_new_native_spawns(self):
        for spawned in (False, True):
            with self.subTest(spawned=spawned):
                self.setUp()
                pawn, = self.prepare_native_den(1)
                self.native_kill(pawn, 110)
                self.world.TimeSeconds = 170
                self.mod.poll_tick(None, None, None, None)
                self.assertEqual(self.den.SpawnData.NumTotalActors, 0)
                if spawned:
                    self.den.SpawnData.NumTotalActors = 3
                self.mod.on_disable()
                self.assertEqual(self.den.SpawnData.NumTotalActors, 3 if spawned else 1)

    def test_poll_is_throttled_by_game_time_and_rejects_clients(self):
        self.prepare_native_den()
        polls = self.mod._counts["den_polls"]
        for i in range(10):
            self.mod.poll_tick(None, None, None, None)
        self.assertEqual(self.mod._counts["den_polls"], polls)
        self.world.TimeSeconds += 1
        self.world.NetMode = 3
        self.mod.poll_tick(None, None, None, None)
        self.assertEqual(self.mod._counts["den_polls"], polls)

    def test_all_factory_and_death_observers_are_unconditional_post_hooks(self):
        for path, kind in self.mod.testing.registrations:
            if path.endswith(":PreCommitMapChange"):
                self.assertEqual(kind, "pre")
            else:
                self.assertEqual(kind, "post-always")
        self.assertEqual(len(self.mod.testing.registrations), 7)


if __name__ == "__main__":
    unittest.main()
