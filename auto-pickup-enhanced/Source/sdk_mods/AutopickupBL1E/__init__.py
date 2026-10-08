from __future__ import annotations

import math
from pathlib import Path

from mods_base import BoolOption, SETTINGS_DIR, build_mod, get_pc, hook
from unrealsdk import logging
from unrealsdk.hooks import Type
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct

# A BL1E (GOTY Enhanced) port of Miner Of Worlds and RedxYeti's original BL1
# "Auto-Pickup SDK" mod (https://github.com/MOW531/MOW531-BL1-SDK-Mods,
# GPL-3.0). See README.md for what changed and why this is a separate
# GPL-3.0 project rather than a patch to the original.
#
# keogh 2.0.0: use native PickupSomething rather than an incomplete direct
# GiveTo sequence. The previous port left empty pickups selected by the
# controller, allowing the use key to try that item instead of a container
# or station. Keep the original categories, range and event-driven retries.

pickup_ammo = BoolOption(
    "Pickup Ammo",
    True,
    description="Automatically collect ammo, from the ground or a container.",
)
pickup_currency = BoolOption(
    "Pickup Currency & Valuables",
    True,
    description="Automatically collect cash, Bobbleheads, and Skag Pearls.",
)
pickup_health = BoolOption(
    "Pickup Health Vials",
    True,
    description="Automatically collect health vials.",
)
pickup_mission_collectibles = BoolOption(
    "Pickup Quest Collectibles",
    True,
    description="Automatically collect mission tally pickups, e.g. Bottle of Booze.",
)

# Item names (short Name, not full object path - all that's available off a
# spawned pickup) mapped to the option that gates them. Verified directly
# against this install's own data (grepped
# WillowGame/CookedPC/Packages/GameData/Inventory/gd_ammodrops.upk and
# gd_currency.upk for every AmmoDrop_/Currency/Bobblehead/SkagPearl object)
# rather than assumed.
CURRENCY_NAMES = frozenset((
    "Currency",
    "Currency_big",
    "Currency_PrizeFighter",
    "Bobblehead",
    "SkagPearl",
))
HEALTH_VIAL_NAMES = frozenset((
    "HealthVial_1",
    "HealthVial_2",
    "HealthVial_3",
    "HealthVial_4",
    "HealthVial_5",
    # "Healing Kit" tiers (Minor/Light/Healing Kit/Greater/Super Healing Kit) -
    # a separate item family from the "Insta-Health Vial" tiers above, both
    # confirmed in gd_HealthDrops.INT. Missed entirely until a "Healing Kit"
    # pickup was reported not auto-collecting (still showing [F] PICK UP) -
    # this mod only ever tracked the Vial names, not the Pack names.
    "HealthPack_1",
    "HealthPack_2",
    "HealthPack_3",
    "HealthPack_4",
    "HealthPack_5",
))


def option_for(item_def, is_mission_item: bool, inventory_class_name: str) -> BoolOption | None:
    """Which toggle, if any, governs auto-collecting this pickup.

    Preserve the port's usable mission-item toggle. The native pickup operation
    decides whether its quest conditions permit collection. WillowMissionItem,
    weapons and equipment are outside this mod's automatic collection scope.
    """
    if is_mission_item:
        if inventory_class_name == "WillowUsableItem":
            return pickup_mission_collectibles
        return None

    name = str(item_def.Name)
    if name.startswith("AmmoDrop_"):
        return pickup_ammo
    if name in CURRENCY_NAMES:
        return pickup_currency
    if name in HEALTH_VIAL_NAMES:
        return pickup_health
    return None


# SawPickupable (added below) is the native aim/raycast "you're looking at
# this" event - unlike TouchedPickupable/SpawnPickupParticles/PickupAtRest,
# which each fire once per pickup, this can plausibly re-fire every tick for
# as long as the player keeps aiming at the same still-uncollectible item.
# Message-text-based throttling (same technique already used in
# AutoLootBL1E, chosen there for the same reason) dedupes identical repeat
# log lines without needing the pickup actor's Python-side identity to stay
# stable across separate hook calls, which nothing in this codebase relies
# on elsewhere.
_recent_log_messages: dict[str, float] = {}
LOG_REPEAT_COOLDOWN = 5.0
_collecting = False


def log_throttled(now: float, message: str) -> None:
    last = _recent_log_messages.get(message)
    if last is not None and now - last < LOG_REPEAT_COOLDOWN:
        return
    _recent_log_messages[message] = now
    logging.info(message)


def live_pickup(pickupable) -> bool:
    """A pickup which can still be selected; never retain it between callbacks."""
    if pickupable is None:
        return False
    try:
        return (
            not pickupable.bDeleteMe
            and not pickupable.bPendingDelete
            and bool(pickupable.bPickupable)
            and pickupable.Inventory is not None
        )
    except Exception:
        # An actor freed by the native pickup operation is not safe to restore.
        return False


def clear_stale_targets(controller) -> None:
    """Clear empty/deleting targets only; keep legitimate manual loot targets."""
    if controller is None:
        return
    for field in ("CurrentSeenPickupable", "CurrentTouchedPickupable"):
        target = getattr(controller, field)
        if target is not None and not live_pickup(target):
            setattr(controller, field, None)


def restore_target(controller, field: str, original, pickupable) -> None:
    # If native code selected a different item during collection, keep it.
    current = getattr(controller, field)
    if current is not None and current != pickupable and live_pickup(current):
        return
    target = original if live_pickup(original) else None
    setattr(controller, field, target)


def dist(a, b) -> float:
    return math.sqrt((b.X - a.X) ** 2 + (b.Y - a.Y) ** 2 + (b.Z - a.Z) ** 2)


def within_reach(controller, pickupable) -> bool:
    """Whether this pickup is within the game's own normal pickup reach.

    SpawnPickupParticles/PickupAtRest fire for every pickup that exists
    anywhere in the loaded level, with no proximity of their own at all -
    unlike TouchedPickupable/SawPickupable, which the engine itself only
    fires once a pawn is actually close to or aiming at the pickup. Without
    this check, any pickup that spawns far from the player (e.g. mission
    tally items placed around a level, or handed out by a scripted event at
    a distance) got collected instantly the moment it existed, regardless of
    how far away the player actually was - confirmed in play as objective
    items appearing to "teleport" to the player from across the map.

    PlayerInteractionDistance is the same field AutoLootBL1E's own pickup
    range check already uses, and is what governs the native [F] PICK UP
    prompt/TouchedPickupable-SawPickupable range in the first place - so a
    pickup this lets through was always going to become reachable within a
    few steps anyway, this just stops it happening from across the map.
    """
    try:
        max_dist = controller.GetWillowGlobals().GetGlobalsDefinition().PlayerInteractionDistance
        return dist(controller.Pawn.Location, pickupable.Location) <= max_dist
    except Exception as ex:  # noqa: BLE001
        logging.warning(f"[AutoPickup Enhanced] could not check pickup range: {ex!r}")
        return False


def collect_pickup(controller, pickupable) -> tuple[bool, str]:
    """Collect precisely this item through the game's normal use-key operation."""
    if not live_pickup(pickupable):
        return False, "pickup not ready"
    if controller.WorldInfo.Game is None:
        return False, "not the host (WorldInfo.Game is None on remote clients)"
    controller.UpdateAmmoCounts(True)
    item_def = pickupable.Inventory.DefinitionData.ItemDefinition
    if item_def.bPlayerUseItemOnPickup and not pickupable.Inventory.CanBeUsedBy(controller.Pawn):
        return False, "item cannot currently be used"
    if not controller.HasRoomInInventoryFor(pickupable):
        return False, "HasRoomInInventoryFor=False"

    seen = controller.CurrentSeenPickupable
    touched = controller.CurrentTouchedPickupable
    try:
        # GetCurrentPickupable prioritizes the seen target. Select this exact
        # pickup for one synchronous native call, so a nearby ammo spawn cannot
        # accidentally collect the weapon the player is looking at instead.
        controller.CurrentSeenPickupable = pickupable
        controller.CurrentTouchedPickupable = pickupable
        controller.PickupSomething(False)
        success = not live_pickup(pickupable)
        return success, "native pickup" if success else "native pickup refused"
    finally:
        # Native collection handles pickup/coop lifecycle. Drop its dead target
        # immediately, restore other live targets, and do the same on failure.
        try:
            restore_target(controller, "CurrentSeenPickupable", seen, pickupable)
        finally:
            restore_target(controller, "CurrentTouchedPickupable", touched, pickupable)


def try_auto_collect(obj: UObject, trigger: str, controller=None) -> None:
    """Retry eligible nearby loot at spawn/rest/touch/seen events, without scans."""
    global _collecting
    if _collecting or not live_pickup(obj):
        return
    inventory = obj.Inventory
    if inventory is None or inventory.DefinitionData is None or inventory.Class is None:
        return
    # Only WillowUsableItem's DefinitionData struct (ItemDefinitionData) has
    # an ItemDefinition field at all - WillowWeapon's is WeaponDefinitionData,
    # which does not, and every category this mod ever acts on (ammo,
    # currency, health vials, mission tally pickups) is WillowUsableItem
    # anyway. Confirmed crashing in play: AttributeError 'WeaponDefinitionData'
    # object has no attribute 'ItemDefinition', thrown every time a weapon
    # pickup (e.g. one dropped by another mod) spawned its particles, because
    # this used to read .DefinitionData.ItemDefinition unconditionally before
    # checking the class at all.
    class_name = str(inventory.Class.Name)
    if class_name != "WillowUsableItem":
        return
    item_def = inventory.DefinitionData.ItemDefinition
    if item_def is None:
        return

    item_name = str(item_def.Name)
    is_mission_item = bool(item_def.bMissionItem)
    option = option_for(item_def, is_mission_item, class_name)
    now = obj.WorldInfo.TimeSeconds

    # No option matched, the matching option is off, no pawn yet, or out of
    # reach are all routine, expected outcomes - most pickups in a level are
    # untracked or simply far away, and SawPickupable re-enters this every
    # tick while merely aiming at one. None of that is worth a log line any
    # more (it was, briefly, while this hook was being rewritten from
    # scratch and every gate needed to be checkable from a report - see git
    # history). Only an actual collection attempt is logged now.
    if option is None or not option.value:
        return

    controller = get_pc() if controller is None else controller
    if controller is None or controller.Pawn is None:
        return

    if not within_reach(controller, obj):
        return

    _collecting = True
    try:
        success, reason = collect_pickup(controller, obj)
    except Exception as ex:  # noqa: BLE001
        logging.warning(f"[AutoPickup Enhanced] could not auto-collect {item_name} ({trigger}): {ex!r}")
        return
    finally:
        _collecting = False

    if success:
        # A real, one-time event per item - never repeats for the same
        # pickup, so no throttling needed.
        logging.info(f"[AutoPickup Enhanced] picked up {item_name} ({trigger})")
    else:
        # Can repeat every tick while aiming at something persistently
        # refused (e.g. backpack full) - throttled like everything else
        # SawPickupable can retrigger continuously.
        log_throttled(now, f"[AutoPickup Enhanced] could not pick up {item_name} ({trigger}): {reason}")


@hook("WillowGame.WillowPickup:SpawnPickupParticles", Type.POST)
def SpawnPickupParticles(obj: UObject, __args: WrappedStruct, __ret: any, __func: BoundFunction) -> None:
    try_auto_collect(obj, "spawn")


@hook("WillowGame.WillowPickup:PickupAtRest", Type.POST)
def PickupAtRest(obj: UObject, __args: WrappedStruct, __ret: any, __func: BoundFunction) -> None:
    # A successful native collection is no longer a live pickup, so repeated
    # lifecycle events cannot award the same item twice.
    try_auto_collect(obj, "rest")


def player_pickup_event(controller, args, trigger: str) -> None:
    # A hook can run for other players; only use the local controller's event.
    if _collecting or controller != get_pc():
        return
    clear_stale_targets(controller)
    pickupable = getattr(args, "Pickup", None)
    if pickupable is not None:
        try_auto_collect(pickupable, trigger, controller)


@hook("WillowGame.WillowPlayerController:TouchedPickupable", Type.POST)
def TouchedPickupable(obj: UObject, args: WrappedStruct, _ret: any, _func: BoundFunction) -> None:
    player_pickup_event(obj, args, "touch")


@hook("WillowGame.WillowPlayerController:SawPickupable", Type.POST)
def SawPickupable(obj: UObject, args: WrappedStruct, _ret: any, _func: BoundFunction) -> None:
    player_pickup_event(obj, args, "seen")


def on_enable() -> None:
    clear_stale_targets(get_pc())
    logging.info("[AutoPickup Enhanced] Enabled; native pickup handling active.")


def on_disable() -> None:
    global _collecting
    _collecting = False
    clear_stale_targets(get_pc())
    _recent_log_messages.clear()


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]

build_mod(
    options=[pickup_ammo, pickup_currency, pickup_health, pickup_mission_collectibles],
    hooks=[SpawnPickupParticles, PickupAtRest, TouchedPickupable, SawPickupable],
    settings_file=Path(f"{SETTINGS_DIR}/AutoPickupSDK.json"),
    on_enable=on_enable,
    on_disable=on_disable,
)

logging.info(f"AutoPickup Enhanced Loaded: {__version__}, {__version_info__}")
