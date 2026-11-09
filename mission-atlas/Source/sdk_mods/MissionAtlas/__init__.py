"""Mission Atlas: additional accepted-mission markers on the current map."""

from pathlib import Path

from mods_base import ButtonOption, BoolOption, SliderOption, SETTINGS_DIR, build_mod, get_pc, hook, keybind
from unrealsdk.hooks import Type

from .runtime import Atlas

include_turn_ins = BoolOption('Show turn-in markers', True,
                             description='Include accepted missions ready to hand in on this map.')
opacity = SliderOption('Other mission opacity', 55, 15, 90, 5, False,
                       description='Opacity percent for the extra mission diamonds.')
atlas = Atlas(get_pc, lambda: include_turn_ins.value, lambda: opacity.value)


def export_diagnostics(_option=None):
    return atlas.export(Path(SETTINGS_DIR) / 'MissionAtlas' / 'diagnostics')


atlas.export_callback = export_diagnostics


@keybind('Export Mission Atlas diagnostics', 'F9')
def diagnostic_key():
    export_diagnostics()


@hook('Engine.GameViewportClient:PostRender', Type.POST)
def on_render(_obj, _args, _ret, _func):
    try:
        atlas.poll()
    except Exception as exc:
        atlas.problem('map discovery', exc)


@hook('WillowGame.WillowGameInfo:PreCommitMapChange', Type.PRE)
def map_change(_obj, _args, _ret, _func):
    # Only synchronous map calls hold native waypoint wrappers. Nothing persists
    # across travel; never reset or resolve the player's tracked mission.
    atlas.reset_rendering()
    atlas.cache_key = None


build_mod(
    options=[include_turn_ins, opacity,
             ButtonOption('Export Mission Atlas diagnostics', on_press=export_diagnostics,
                          description='Export map/waypoint interfaces and recent calls. Also available on F9.')],
    keybinds=[diagnostic_key],
    hooks=[on_render, map_change],
    settings_file=Path(SETTINGS_DIR) / 'MissionAtlas.json',
    on_enable=atlas.enable,
    on_disable=atlas.disable,
)
