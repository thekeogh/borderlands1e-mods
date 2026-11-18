"""BL1 Enhanced diagnostics only; no engine/driver/input settings are changed."""

from pathlib import Path

from mods_base import SETTINGS_DIR, ButtonOption, Game, SpinnerOption, build_mod, keybind

from .runtime import Recorder

recorder = Recorder(Path(SETTINGS_DIR) / "SmoothFPS" / "diagnostics")
mode = SpinnerOption(
    "Capture detail", "Camera and timing", ["Camera and timing", "Timing only"],
    description="Camera mode includes processed input and cached camera rotation. Timing only reduces observer overhead.",
)


def toggle(_option=None):
    recorder.toggle(mode.value)


@keybind("Start/stop frame diagnostics", "F5")
def capture_key():
    toggle()


@keybind("Mark a perceived stutter", "F6")
def marker_key():
    recorder.mark()


def on_disable():
    recorder.stop("mod disabled")
    recorder.detach()


__version__: str
__version_info__: tuple[int, ...]

build_mod(
    supported_games=Game.BL1E,
    options=[mode, ButtonOption("Start/stop frame diagnostics", on_press=toggle)],
    keybinds=[capture_key, marker_key],
    hooks=[],
    settings_file=Path(SETTINGS_DIR) / "SmoothFPS.json",
    on_disable=on_disable,
)
