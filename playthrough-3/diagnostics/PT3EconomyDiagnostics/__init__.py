"""Temporary read-only exporter for diagnosing PT3 economy on Enhanced."""

import sys

from mods_base import SETTINGS_DIR, ButtonOption, Game, build_mod, get_pc, get_ordered_mod_list, keybind
from unrealsdk import logging
import unrealsdk

from .exporter import collect, write_snapshot


def export_economy(_option=None) -> None:
    pc = get_pc()
    if pc is None or pc.Pawn is None:
        logging.error("[PT3 Economy Diagnostics] Load your PT3 character first.")
        return
    try:
        snapshot = collect(unrealsdk, pc)
        snapshot["game"] = str(Game.get_current())
        snapshot["sdk_version"] = getattr(unrealsdk, "__version__", "unknown")
        snapshot["loaded_mods"] = [
            {"name": mod.name, "version": mod.version, "author": mod.author, "enabled": mod.is_enabled}
            for mod in get_ordered_mod_list()
        ]
        module = sys.modules.get("Playthrough 3.economy")
        if module is not None and hasattr(module, "_economy"):
            status = getattr(module._economy, "snapshot", None)
            snapshot["pt3_economy"] = (
                status() if callable(status) else {"status_export_supported": False}
            )
        path = write_snapshot(snapshot, SETTINGS_DIR / "PT3EconomyDiagnostics")
        logging.info(f"[PT3 Economy Diagnostics] Exported to {path}")
    except Exception as exc:
        logging.error(f"[PT3 Economy Diagnostics] Export failed: {exc!r}")


@keybind("Export economy diagnostics", "F10")
def export_key() -> None:
    export_economy()


build_mod(
    options=[ButtonOption("Export economy diagnostics", on_press=export_economy)],
    keybinds=[export_key],
    hooks=[],
)
