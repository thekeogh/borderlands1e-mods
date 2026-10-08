"""Regression model for pickup selection and the subsequent use-key interaction.

Native BL1E PickupSomething still needs Windows verification. This model checks
the controller references and calls made by the mod, including the old bug.
"""

import __future__
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Source/sdk_mods/AutopickupBL1E/__init__.py"


def load_mod(path, name):
    """Execute source in memory so reference files never get bytecode writes."""
    module = ModuleType(name)
    module.__file__ = str(path)
    module.__version__ = "2.0.0"
    module.__version_info__ = (2, 0, 0)
    options = []

    def bool_option(title, value, **kwargs):
        option = SimpleNamespace(title=title, value=value, **kwargs)
        options.append(option)
        return option

    base = ModuleType("mods_base")
    base.BoolOption = bool_option
    base.SETTINGS_DIR = Path("unused-settings")
    base.build_mod = lambda **kwargs: setattr(module, "registration", kwargs)
    base.get_pc = lambda: None
    base.hook = lambda *args, **kwargs: lambda fn: fn
    sdk = ModuleType("unrealsdk")
    sdk.logging = SimpleNamespace(info=lambda message: None, warning=lambda message: None)
    hooks = ModuleType("unrealsdk.hooks")
    hooks.Type = SimpleNamespace(POST="POST")
    unreal = ModuleType("unrealsdk.unreal")
    unreal.UObject = object
    unreal.WrappedStruct = object
    unreal.BoundFunction = object
    replacements = {"mods_base": base, "unrealsdk": sdk,
                    "unrealsdk.hooks": hooks, "unrealsdk.unreal": unreal}
    with patch.dict(sys.modules, replacements):
        exec(compile(path.read_text(), str(path), "exec", flags=__future__.annotations.compiler_flag), module.__dict__)
    module.test_options = options
    return module


def vector(x=0):
    return SimpleNamespace(X=x, Y=0, Z=0)


class Pickup:
    def __init__(self, name="Currency", *, usable=True, instant=True,
                 mission=False, inventory_class="WillowUsableItem", x=0):
        definition = SimpleNamespace(Name=name, bMissionItem=mission,
                                     bPlayerUseItemOnPickup=instant)
        data = SimpleNamespace(ItemDefinition=definition)
        if inventory_class == "WillowWeapon":
            data = SimpleNamespace(WeaponTypeDefinition=object())
        self.Inventory = SimpleNamespace(
            Class=SimpleNamespace(Name=inventory_class), DefinitionData=data,
            CanBeUsedBy=lambda pawn: self.usable,
        )
        self.usable = usable
        self.bDeleteMe = False
        self.bPendingDelete = False
        self.bPickupable = True
        self.Location = vector(x)
        self.WorldInfo = SimpleNamespace(TimeSeconds=10.0)
        self.awards = 0

    def GiveTo(self, pawn, swap):
        # Old direct sequence: the item is gone but the controller still points
        # to its empty pickup actor. Native selection cleanup was bypassed.
        self.awards += 1
        self.Inventory = None


class Controller:
    def __init__(self):
        self.Pawn = SimpleNamespace(Location=vector())
        self.CurrentSeenPickupable = None
        self.CurrentTouchedPickupable = None
        self.WorldInfo = SimpleNamespace(Game=SimpleNamespace(
            PickupQuery=lambda pawn, pickup: pickup.Inventory is not None and pickup.usable))
        self.room = True
        self.native_calls = []
        self.ammo_updates = 0
        self.native_refuses = False
        self.native_error = None
        self.during_native = None
        self.direct_calls = []

    def GetWillowGlobals(self):
        return SimpleNamespace(GetGlobalsDefinition=lambda: SimpleNamespace(PlayerInteractionDistance=100.0))

    def GetCurrentPickupable(self):
        return self.CurrentSeenPickupable or self.CurrentTouchedPickupable

    def HasRoomInInventoryFor(self, pickup):
        return self.room and pickup.Inventory is not None

    def UpdateAmmoCounts(self, force):
        assert force is True
        self.ammo_updates += 1

    def PickupSomething(self, swap):
        assert swap is False
        pickup = self.GetCurrentPickupable()
        self.native_calls.append(pickup)
        if self.during_native:
            self.during_native(pickup)
        if self.native_error:
            raise self.native_error
        if self.native_refuses:
            return
        pickup.GiveTo(self.Pawn, swap)
        pickup.bPickupable = False
        self.CurrentSeenPickupable = None
        self.CurrentTouchedPickupable = None

    def ShouldUseCoopRange(self, pickup):
        self.direct_calls.append("coop query")
        return False

    def ClientSpawnPickupableMesh(self, pickup):
        self.direct_calls.append("mesh")

    def use_interactive(self, kind):
        pickup = self.GetCurrentPickupable()
        if pickup is not None:
            return "Full" if pickup.Inventory is None else "pickup selected"
        return "used " + kind


class PickupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod(SOURCE, "test_autopickup")

    def setUp(self):
        self.pc = Controller()
        self.mod.get_pc = lambda: self.pc
        self.mod._collecting = False
        self.mod._recent_log_messages.clear()
        for option in self.mod.test_options:
            option.value = True

    def test_original_reproduces_full_after_direct_give(self):
        original = load_mod(ROOT.parent / "reference/AutopickupBL1E/__init__.py", "test_original")
        pickup = Pickup()
        self.pc.CurrentSeenPickupable = pickup
        self.pc.CurrentTouchedPickupable = pickup
        self.assertTrue(original.collect_pickup(self.pc, pickup)[0])
        self.assertEqual(self.pc.use_interactive("red chest"), "Full")
        self.assertEqual(self.pc.use_interactive("New-U"), "Full")

    def test_collected_cash_does_not_block_containers_or_new_u(self):
        for kind in ("container", "red chest", "New-U"):
            pickup = Pickup()
            self.pc.CurrentSeenPickupable = pickup
            self.pc.CurrentTouchedPickupable = pickup
            self.mod.try_auto_collect(pickup, "seen")
            self.assertEqual(pickup.awards, 1)
            self.assertEqual(self.pc.use_interactive(kind), "used " + kind)
        self.assertEqual(self.pc.direct_calls, [])

    def test_only_event_pickup_is_collected_when_different_item_is_seen(self):
        seen = Pickup("Weapon", inventory_class="WillowWeapon")
        touched = Pickup("AmmoDrop_Repeater_Pistol_Clip")
        self.pc.CurrentSeenPickupable = seen
        self.pc.CurrentTouchedPickupable = touched
        self.mod.TouchedPickupable(self.pc, SimpleNamespace(Pickup=touched), None, None)
        self.assertEqual(touched.awards, 1)
        self.assertEqual(seen.awards, 0)
        self.assertIs(self.pc.CurrentSeenPickupable, seen)
        self.assertIsNone(self.pc.CurrentTouchedPickupable)

    def test_spawn_rest_seen_touch_cannot_award_twice(self):
        pickup = Pickup()
        self.mod.SpawnPickupParticles(pickup, None, None, None)
        self.mod.PickupAtRest(pickup, None, None, None)
        args = SimpleNamespace(Pickup=pickup)
        self.mod.SawPickupable(self.pc, args, None, None)
        self.mod.TouchedPickupable(self.pc, args, None, None)
        self.assertEqual(pickup.awards, 1)
        self.assertEqual(len(self.pc.native_calls), 1)

    def test_full_ammo_is_left_alone_and_retried_after_space_available(self):
        pickup = Pickup("AmmoDrop_Repeater_Pistol_Clip", usable=False)
        self.mod.try_auto_collect(pickup, "spawn")
        self.assertEqual(self.pc.native_calls, [])
        self.assertEqual(self.pc.use_interactive("red chest"), "used red chest")
        pickup.usable = True
        self.mod.TouchedPickupable(self.pc, SimpleNamespace(Pickup=pickup), None, None)
        self.assertEqual(pickup.awards, 1)

    def test_full_health_vial_is_left_alone(self):
        pickup = Pickup("HealthVial_5", usable=False)
        self.mod.try_auto_collect(pickup, "rest")
        self.assertEqual(pickup.awards, 0)
        self.assertEqual(self.pc.native_calls, [])

    def test_healing_kit_can_be_carried_when_full_health(self):
        pickup = Pickup("HealthPack_5", instant=False, usable=False)
        self.mod.try_auto_collect(pickup, "rest")
        self.assertEqual(pickup.awards, 1)

    def test_full_backpack_does_not_attempt_native_pickup(self):
        self.pc.room = False
        pickup = Pickup("HealthPack_1", instant=False)
        self.mod.try_auto_collect(pickup, "rest")
        self.assertEqual(self.pc.native_calls, [])
        self.assertEqual(pickup.awards, 0)

    def test_native_refusal_restores_previous_targets(self):
        self.pc.native_refuses = True
        previous = Pickup("Weapon", inventory_class="WillowWeapon")
        self.pc.CurrentSeenPickupable = previous
        pickup = Pickup()
        self.mod.try_auto_collect(pickup, "spawn")
        self.assertIs(self.pc.CurrentSeenPickupable, previous)
        self.assertIsNone(self.pc.CurrentTouchedPickupable)
        self.assertEqual(pickup.awards, 0)

    def test_exception_restores_targets_and_releases_reentry_guard(self):
        previous = Pickup("Weapon", inventory_class="WillowWeapon")
        self.pc.CurrentSeenPickupable = previous
        self.pc.native_error = RuntimeError("native failure")
        pickup = Pickup()
        self.mod.try_auto_collect(pickup, "spawn")
        self.assertIs(self.pc.CurrentSeenPickupable, previous)
        self.assertIsNone(self.pc.CurrentTouchedPickupable)
        self.assertFalse(self.mod._collecting)
        self.pc.native_error = None
        self.mod.try_auto_collect(pickup, "rest")
        self.assertEqual(pickup.awards, 1)

    def test_recursive_pickup_event_does_not_collect_another_item(self):
        other = Pickup("Currency_big")
        self.pc.during_native = lambda pickup: self.mod.SawPickupable(
            self.pc, SimpleNamespace(Pickup=other), None, None)
        pickup = Pickup()
        self.mod.try_auto_collect(pickup, "spawn")
        self.assertEqual(pickup.awards, 1)
        self.assertEqual(other.awards, 0)
        self.assertEqual(len(self.pc.native_calls), 1)

    def test_previous_target_destroyed_during_native_call_is_not_restored(self):
        previous = Pickup("Weapon", inventory_class="WillowWeapon")
        self.pc.CurrentSeenPickupable = previous
        self.pc.during_native = lambda pickup: setattr(previous, "bPendingDelete", True)
        self.mod.try_auto_collect(Pickup(), "spawn")
        self.assertIsNone(self.pc.CurrentSeenPickupable)

    def test_new_native_selection_is_preserved(self):
        replacement = Pickup("Weapon", inventory_class="WillowWeapon")
        self.pc.native_refuses = True
        self.pc.during_native = lambda pickup: setattr(self.pc, "CurrentSeenPickupable", replacement)
        self.mod.try_auto_collect(Pickup(), "spawn")
        self.assertIs(self.pc.CurrentSeenPickupable, replacement)

    def test_out_of_reach_item_is_not_collected(self):
        pickup = Pickup(x=101)
        self.mod.try_auto_collect(pickup, "spawn")
        self.assertEqual(pickup.awards, 0)
        self.assertEqual(self.pc.native_calls, [])

    def test_no_pawn_does_not_collect(self):
        self.pc.Pawn = None
        pickup = Pickup()
        self.mod.try_auto_collect(pickup, "spawn")
        self.assertEqual(pickup.awards, 0)

    def test_remote_client_is_not_given_items_locally(self):
        self.pc.WorldInfo.Game = None
        self.mod.try_auto_collect(Pickup(), "spawn")
        self.assertEqual(self.pc.native_calls, [])

    def test_other_player_event_does_not_use_local_controller(self):
        pickup = Pickup()
        self.mod.SawPickupable(Controller(), SimpleNamespace(Pickup=pickup), None, None)
        self.assertEqual(pickup.awards, 0)
        self.assertEqual(self.pc.native_calls, [])

    def test_disabled_categories_do_not_collect(self):
        cases = [("pickup_ammo", "AmmoDrop_Repeater_Pistol_Clip", False),
                 ("pickup_currency", "Bobblehead", False),
                 ("pickup_health", "HealthVial_1", False),
                 ("pickup_mission_collectibles", "BottleOfBooze", True)]
        for option, name, mission in cases:
            getattr(self.mod, option).value = False
            pickup = Pickup(name, mission=mission)
            self.mod.try_auto_collect(pickup, "spawn")
            self.assertEqual(pickup.awards, 0, name)

    def test_quest_tally_uses_native_operation(self):
        pickup = Pickup("BottleOfBooze", mission=True)
        self.mod.try_auto_collect(pickup, "spawn")
        self.assertEqual(pickup.awards, 1)

    def test_carried_quest_items_weapons_and_gear_stay_manual(self):
        for cls in ("WillowWeapon", "WillowEquipAbleItem", "WillowMissionItem"):
            pickup = Pickup("MissionKey", mission=True, inventory_class=cls)
            self.mod.try_auto_collect(pickup, "spawn")
            self.assertEqual(pickup.awards, 0, cls)
        self.assertEqual(self.pc.native_calls, [])

    def test_unready_and_deleted_pickups_are_skipped(self):
        for field in ("bDeleteMe", "bPendingDelete", "bPickupable"):
            pickup = Pickup()
            setattr(pickup, field, field != "bPickupable")
            self.mod.try_auto_collect(pickup, "spawn")
            self.assertEqual(pickup.awards, 0, field)

    def test_disable_repairs_stale_targets_and_keeps_live_manual_loot(self):
        stale = Pickup()
        stale.Inventory = None
        live = Pickup("Weapon", inventory_class="WillowWeapon")
        self.pc.CurrentSeenPickupable = stale
        self.pc.CurrentTouchedPickupable = live
        self.mod.on_disable()
        self.assertIsNone(self.pc.CurrentSeenPickupable)
        self.assertIs(self.pc.CurrentTouchedPickupable, live)

    def test_enable_repairs_empty_targets_from_previous_version(self):
        stale = Pickup()
        stale.Inventory = None
        self.pc.CurrentSeenPickupable = stale
        self.pc.CurrentTouchedPickupable = stale
        self.mod.on_enable()
        self.assertEqual(self.pc.use_interactive("New-U"), "used New-U")

    def test_missing_event_argument_does_not_fall_back_to_unrelated_selection(self):
        pickup = Pickup()
        self.pc.CurrentSeenPickupable = pickup
        self.mod.SawPickupable(self.pc, SimpleNamespace(), None, None)
        self.assertEqual(pickup.awards, 0)

    def test_new_u_object_is_never_treated_as_pickup(self):
        self.mod.try_auto_collect(SimpleNamespace(), "spawn")
        self.assertEqual(self.pc.native_calls, [])


if __name__ == "__main__":
    unittest.main()
