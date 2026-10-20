from __future__ import annotations

import time
from pathlib import Path

import unrealsdk  # type: ignore
from unrealsdk import logging  # type: ignore
from unrealsdk.hooks import Block, Type, prevent_hooking_direct_calls  # type: ignore
from unrealsdk.unreal import BoundFunction, UObject, WrappedStruct  # type: ignore

from mods_base import SETTINGS_DIR, ButtonOption, Game, SliderOption, build_mod, get_pc, hook, keybind

from .native_text import NativeText

LABEL = "Full Money Indicator White"
renderer = NativeText(unrealsdk)
last_warning = None

y_offset = SliderOption(
    "Y offset",
    0,
    -200,
    200,
    1,
    True,
    description="Move the money display vertically. Positive moves down; negative moves up. "
                "0 keeps the original bottom spacing. Pixels are scaled from 1920x1080.",
)

# How far the amount sits above the bottom of the screen, in pixels at 1920x1080.
# Enhanced puts its level and XP bar lower, so the amount goes under that bar there.
# Older copies of the SDK do not know Enhanced by name, so it is asked for carefully.
ON_ENHANCED = getattr(Game, "BL1E", None) is not None and Game.get_current() is Game.BL1E
BOTTOM_MARGIN = 18 if ON_ENHANCED else 60

# How often the amount is read again, in seconds.
READ_SECONDS = 0.25

# The most money the game can hold. One more dollar and the game's own count wraps
# round to a large negative number, so a negative count is put back to this top.
MOST_MONEY = 2147483647

# The original wallet reader and its polling interval are unchanged.
money = None
text = ""
read_at = 0.0


def read_money() -> int | None:
    pc = get_pc()
    try:
        pri = pc.PlayerReplicationInfo
        amount = int(pri.CurrencyOnHand)
        if amount < 0:
            pri.CurrencyOnHand = MOST_MONEY
            amount = MOST_MONEY
            logging.info(f"[{LABEL}] money had gone past the top and turned negative, put back to ${MOST_MONEY:,}")
        return amount
    except Exception:
        return None


def warn_once(exc):
    global last_warning
    message = str(exc)
    if message != last_warning:
        logging.dev_warning(f"[{LABEL}] {message}")
        last_warning = message


def on_enable():
    try:
        renderer.prepare()
    except Exception as exc:
        warn_once(exc)


def on_disable():
    for exc in renderer.restore(get_pc()):
        warn_once(exc)


@hook("WillowGame.WillowHUDGFxMovie:Start")
@hook("GFxUI.GFxMovie:Start")
def on_hud_start(obj, _args, _ret, _func):
    try:
        with prevent_hooking_direct_calls():
            renderer.before_start(obj)
    except Exception as exc:
        warn_once(exc)


@hook("GFxUI.GFxMovie:SetMovieInfo")
def on_movie_info(obj, args, _ret, func):
    invoked = False
    try:
        replacement = renderer.movie_info_for(args.Data)
        if replacement is not None:
            with prevent_hooking_direct_calls():
                invoked = True
                func(replacement)
            renderer.bind_count += 1
            return Block
    except Exception as exc:
        warn_once(exc)
        if invoked:
            return Block


@hook(hook_func="Engine.GameViewportClient:PostRender", hook_type=Type.POST)
def on_render(
    obj: UObject,
    __args: WrappedStruct,
    __ret: any,
    __func: BoundFunction,
) -> None:
    global money, text, read_at
    pc = get_pc()
    if pc is None or pc.Pawn is None or __args.Canvas is None:
        return
    now = time.monotonic()
    if now - read_at < READ_SECONDS:
        return
    read_at = now
    try:
        amount = read_money()
        if amount is not None:
            money = amount
            text = f"${amount:,}"
        if text:
            canvas = __args.Canvas
            renderer.draw(pc, text, float(canvas.SizeX), float(canvas.SizeY),
                          float(y_offset.value), BOTTOM_MARGIN)
    except Exception as exc:
        warn_once(exc)


# Gets populated from `build_mod` below
__version__: str
__version_info__: tuple[int, ...]


def export_hud_info(_option=None):
    # Loaded and executed only on manual request, never during normal drawing.
    logging.info(f"[{LABEL}] HUD text export requested.")
    try:
        from .hud_info import export
        path = export(unrealsdk, get_pc(), Path(SETTINGS_DIR) / "FullMoneyIndicatorWhite" / "diagnostics", __version__,
                      runtime={"renderer": renderer.inspect(get_pc()), "last_warning": last_warning,
                               "text": text, "y_offset": y_offset.value})
    except Exception as exc:
        logging.error(f"[{LABEL}] HUD text export failed: {exc!r}")
        return None
    logging.info(f"[{LABEL}] HUD text export saved to {path}")
    return path


@keybind("Export HUD text information", "F11")
def export_hud_key():
    export_hud_info()


build_mod(
    options=[y_offset, ButtonOption("Export HUD text information", on_press=export_hud_info)],
    keybinds=[export_hud_key],
    hooks=[on_render, on_hud_start, on_movie_info],
    on_enable=on_enable,
    on_disable=on_disable,
    commands=[],
    settings_file=Path(f"{SETTINGS_DIR}/FullMoneyIndicatorWhite.json"),
)

logging.info(f"Full Money Indicator White Loaded: {__version__}, {__version_info__}")
