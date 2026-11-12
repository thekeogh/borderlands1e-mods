"""Economy Buster: money only, all levels and playthroughs."""

from __future__ import annotations

from functools import wraps
from pathlib import Path

import unrealsdk
from unrealsdk import logging
from unrealsdk.hooks import Type
from mods_base import SETTINGS_DIR, ButtonOption, Game, build_mod, get_ordered_mod_list, get_pc, hook

from .economy import Economy
from .diagnostics import collect, write_snapshot

runtime = Economy(unrealsdk)


def safe(callback):
    @wraps(callback)
    def wrapped(*args, **kwargs):
        try:
            return callback(*args, **kwargs)
        except Exception as exc:
            runtime.problem(callback.__name__, exc)
            return None
    return wrapped


def on_enable() -> None:
    if not runtime.enable():
        logging.error("[Economy Buster] Could not activate money formulas. Export diagnostics from the mod options.")


def on_disable() -> None:
    runtime.disable()


@hook("WillowGame.WillowPlayerController:ClientSetProfileLoaded", Type.POST)
@hook("WillowGame.WillowPlayerController:OnExpLevelChange", Type.POST)
@safe
def player_ready(obj, _args, _ret, _func):
    if obj == get_pc():
        runtime.ensure("player ready", refresh=True)


@hook("Engine.WorldInfo:PostBeginPlay", Type.POST)
@safe
def world_ready(obj, _args, _ret, _func):
    pc = get_pc()
    if pc is not None and pc.WorldInfo == obj:
        runtime.ensure("world ready", refresh=True)


@hook("Engine.WillowInventory:ComputeCashValue")
@hook("WillowGame.WillowItem:InitializeAttributeSlots")
@safe
def cash_calculation(_obj, _args, _ret, _func):
    runtime.ensure("cash calculation")


@hook("WillowGame.VendingMachineGFxMovie:SetPrice")
@safe
def vendor_display(_obj, args, _ret, _func):
    if runtime.ensure("vendor display"):
        runtime.refresh_item(args.Thing)


def price_hook(path, *, item_field=None):
    @hook(path, Type.PRE, hook_identifier=f"EconomyBuster.before:{path}")
    @safe
    def before(_obj, args, _ret, _func):
        if not runtime.enabled:
            return
        if runtime.ensure(path) and item_field is not None:
            runtime.refresh_item(getattr(args, item_field, None))

    return before


HOOKS = [player_ready, world_ready, cash_calculation, vendor_display]
for _path, _item in (
    ("WillowGame.MissionDefinition:GetCreditReward", None),
    ("WillowGame.WillowVendingMachine:GetResetCost", None),
    ("WillowGame.WillowVendingMachine:GetSellingPriceForInventory", "InventoryForSale"),
    ("WillowGame.WillowVendingMachine:PlayerBuyItem", "Item"),
    ("WillowGame.WillowVendingMachine:PlayerSellItem", "Item"),
    ("WillowGame.WillowVendingMachine:PlayerBuyBackItem", "Item"),
    ("WillowGame.WillowPlayerReplicationInfo:AddCurrencyOnHand", None),
):
    HOOKS.append(price_hook(_path, item_field=_item))


def export_diagnostics(_option=None):
    logging.info("[Economy Buster] Diagnostics export requested.")
    try:
        snapshot = collect(unrealsdk, get_pc(), runtime, version=__version__,
                           mods=list(get_ordered_mod_list()), hooks=HOOKS, game=str(Game.get_current()))
        path = write_snapshot(snapshot, Path(SETTINGS_DIR) / "EconomyBuster" / "diagnostics")
    except Exception as exc:
        runtime.problem("export diagnostics", exc)
        logging.error(f"[Economy Buster] Diagnostics export failed: {exc!r}")
        return None
    logging.info(f"[Economy Buster] Diagnostics saved to {path}")
    return path


__version__: str
__version_info__: tuple[int, ...]

build_mod(hooks=HOOKS,
          options=[ButtonOption("Export diagnostics", on_press=export_diagnostics)],
          keybinds=[], on_enable=on_enable, on_disable=on_disable,
          settings_file=Path(SETTINGS_DIR) / "EconomyBuster.json")
logging.info(f"Economy Buster Loaded: {__version__}")
