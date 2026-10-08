"""Use context-free weapon levels while native item cards are being rendered."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from threading import get_ident

from mods_base import ButtonOption, SETTINGS_DIR, build_mod, get_pc, hook
from unrealsdk import find_all, logging
from unrealsdk.hooks import Block, Type, prevent_hooking_direct_calls

PROFICIENCY_ATTRIBUTES = frozenset(
    f"Proficiency_{kind}_LevelBonus"
    for kind in (
        "Pistol", "Shotgun", "Sniper", "SMG", "RocketLauncer", "Eridan", "CombatRifle"
    )
)

# Card-rendering entry points used by BL1/BL1E UI mods. Do not include equipment
# changes or use/equip checks: those are gameplay, not card rendering.
CARD_FUNCTIONS = (
    "WillowGame.StatusMenuExGFxMovie:UpdateCardPanel",
    "WillowGame.StatusMenuExGFxMovie:UpdateCardPanelWithCurrentCell",
    "WillowGame.StatusMenuExGFxMovie:UpdateCardPanelWithCurrentActiveListEntry",
    "WillowGame.StatusMenuExGFxMovie:extSetMouseOverCell",
    "WillowGame.StatusMenuExGFxMovie:extCard2Visible",
    "WillowGame.VendingMachineGFxMovie:UpdateCardPanel",
    "WillowGame.VendingMachineGFxMovie:UpdateCardPanelWithItemOfTheDay",
    "WillowGame.VendingMachineGFxMovie:UpdateCardPanelWithCurrentActiveListEntry",
    "WillowGame.VendingMachineGFxMovie:extSetMouseOverCell",
    "WillowGame.VendingMachineGFxMovie:extCard2Visible",
    "WillowGame.BankGFxMovie:UpdateCardPanelWithCurrentActiveListEntry",
    "WillowGame.BankGFxMovie:extCard2Visible",
    "WillowGame.BankGFxMovie:StartComparing",
    "WillowGame.ItemPickupGFxMovie:UpdateCompareAgainstThing",
    "WillowGame.WillowHUDGFxMovie:extEquippedCardOpened",
    "WillowGame.QuestAcceptGFxMovie:extSetUpRewardsPage",
)

_depth: dict[int, int] = {}
_calculating: set[int] = set()
_enabled = False
_stats = {"card_calls": 0, "level_queries": 0, "corrected_queries": 0}
_errors: list[str] = []


def report_error(exc: Exception) -> None:
    message = f"{type(exc).__name__}: {exc}"
    if message not in _errors and len(_errors) < 10:
        _errors.append(message)
        logging.warning(f"[Consistent Weapon Levels] {message}")


def card_enter(_obj, _args, _ret, _func) -> None:
    if _enabled:
        thread = get_ident()
        _depth[thread] = _depth.get(thread, 0) + 1
        _stats["card_calls"] += 1


def card_exit(_obj, _args, _ret, _func) -> None:
    thread = get_ident()
    depth = _depth.get(thread, 0)
    if depth > 1:
        _depth[thread] = depth - 1
    else:
        _depth.pop(thread, None)


def context_free_level(weapon, native_function, argument):
    """Re-run one native query with its definition's ordinary fallback bonus.

    BL1E exports show PlayerUseLevelBonus.BaseValueAttribute selecting the
    proficiency resolver, with BaseValueConstant providing the backpack fallback.
    Different weapon definitions have different constants; do not hardcode 2 or
    display raw ExpLevel. The native function retains its own rounding and caps.

    Only the one attribute reference is temporarily changed, synchronously, and
    restored even if the query fails. No definition is retained between hooks.
    """
    definition = weapon.GetInventoryDefinition()
    bonus = definition.PlayerUseLevelBonus
    attribute = bonus.BaseValueAttribute
    if (attribute is None
            or str(attribute.Name) not in PROFICIENCY_ATTRIBUTES
            or bonus.InitializationDefinition is not None):
        return None

    thread = get_ident()
    _calculating.add(thread)
    try:
        bonus.BaseValueAttribute = None
        with prevent_hooking_direct_calls():
            return native_function(argument)
    finally:
        try:
            # WrappedStruct fields write through to native memory.
            bonus.BaseValueAttribute = attribute
        finally:
            _calculating.discard(thread)


def displayed_level(obj, argument, func):
    thread = get_ident()
    if not _enabled or not _depth.get(thread, 0) or thread in _calculating:
        return None
    try:
        if str(obj.Class.Name) != "WillowWeapon":
            return None
        _stats["level_queries"] += 1
        level = context_free_level(obj, func, argument)
        if level is not None:
            _stats["corrected_queries"] += 1
            return Block, level
    except Exception as exc:
        report_error(exc)
    return None


@hook("Engine.WillowInventory:GetControllerPlayerExpLevelRequiredToUse")
def controller_level(obj, args, _ret, func):
    return displayed_level(obj, args.OtherController, func)


@hook("Engine.WillowInventory:GetPlayerExpLevelRequiredToUse")
def pawn_level(obj, args, _ret, func):
    # Hook both wrappers: native code may call the controller implementation
    # directly, without dispatching its own hookable Unreal function call.
    return displayed_level(obj, args.Other, func)


_card_hooks = []
for _path in CARD_FUNCTIONS:
    _card_hooks.append(hook(
        _path, Type.PRE, hook_identifier=f"ConsistentWeaponLevels.enter:{_path}"
    )(card_enter))
    _card_hooks.append(hook(
        _path, Type.POST_UNCONDITIONAL,
        hook_identifier=f"ConsistentWeaponLevels.exit:{_path}"
    )(card_exit))


def on_enable() -> None:
    global _enabled
    _depth.clear()
    _calculating.clear()
    _errors.clear()
    for key in _stats:
        _stats[key] = 0
    _enabled = True
    logging.info("[Consistent Weapon Levels] Item-card display fix enabled.")


def on_disable() -> None:
    global _enabled
    _enabled = False
    _depth.clear()
    _calculating.clear()


def export_diagnostics(_option=None) -> None:
    """Optional, bounded export to verify native UI coverage on Windows."""
    try:
        pc = get_pc()
        if pc is None or pc.Pawn is None:
            logging.warning("[Consistent Weapon Levels] Load a character before exporting.")
            return
        report = {
            "version": __version__,
            "enabled": _enabled,
            "captured_utc": datetime.now(timezone.utc).isoformat(),
            "stats": dict(_stats),
            "errors": list(_errors),
            "active_card_depth": _depth.get(get_ident(), 0),
            "hooks": {h.hook_identifier: h.get_active_count()
                      for h in [controller_level, pawn_level, *_card_hooks]},
            "weapons": [],
        }
        for weapon in find_all("WillowWeapon"):
            if weapon.Owner != pc.Pawn:
                continue
            if len(report["weapons"]) >= 100:
                break
            try:
                with prevent_hooking_direct_calls():
                    original = weapon.GetControllerPlayerExpLevelRequiredToUse(pc)
                corrected = context_free_level(
                    weapon, weapon.GetControllerPlayerExpLevelRequiredToUse, pc
                )
                report["weapons"].append({
                    "object": weapon._path_name(),
                    "internal_level": weapon.ExpLevel,
                    "native_level_with_controller": original,
                    "card_level_without_proficiency": corrected,
                })
            except Exception as exc:
                report["weapons"].append({"error": f"{type(exc).__name__}: {exc}"})
        directory = Path(SETTINGS_DIR) / "ConsistentWeaponLevels"
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
        path = directory / f"weapon-levels-{stamp}.json"
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        logging.info(f"[Consistent Weapon Levels] Exported to {path}")
    except Exception as exc:
        report_error(exc)


__version__: str
__version_info__: tuple[int, ...]

build_mod(
    hooks=[controller_level, pawn_level, *_card_hooks],
    options=[ButtonOption("Export level diagnostics", on_press=export_diagnostics)],
    on_enable=on_enable,
    on_disable=on_disable,
)
