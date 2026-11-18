"""Read selected settings once, outside the measured window. No configuration writes."""

from datetime import datetime, timezone
import math
import os
from pathlib import Path
import platform
import sys
import time

INI_KEYS = {
    "bsmoothframerate", "minsmoothedframerate", "maxsmoothedframerate", "maxdeltatime",
    "busefixedframerate", "fixedframerate", "usevsync", "busevsync", "resx", "resy",
    "fullscreen", "bfullscreen", "buseborderlesswindow", "onethreadframelag",
    "ballowd3d9msaa", "busesmoothedframerate", "bhasvoiceenabled", "ballowmousesmoothing",
    "bmousesmoothing", "benablemousesmoothing", "mousesensitivity", "mousesmoothingspeed", "doubleclicktime",
    "lookrightsensitivity", "lookupsensitivity", "controllerlookspeed", "deadzonethreshold",
    "poolsize", "busenvidiaapex", "benablemouseacceleration",
}


def primitive(value):
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    # Object/struct wrappers must never be retained in a report.
    raise TypeError("Not a primitive setting")


def selected_ini(path):
    """Only allowlisted scalar settings, including duplicate sections/keys."""
    if path.stat().st_size > 2_000_000:
        raise ValueError("Config larger than 2 MB")
    content = path.read_bytes()
    text = content.decode("utf-16") if content.startswith((b"\xff\xfe", b"\xfe\xff")) else content.decode("utf-8-sig", errors="replace")
    result = {}
    section = ""
    # Parse line by line so Unreal's repeated sections/array keys don't erase evidence.
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith((";", "#")):
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
        elif "=" in stripped:
            key, value = stripped.split("=", 1)
            if key.strip().lower() in INI_KEYS:
                result.setdefault(section, {}).setdefault(key.strip(), []).append(value.strip()[:200])
    return result


def documents_dir():
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        # CSIDL_PERSONAL follows redirected Documents (including OneDrive).
        get_folder = ctypes.windll.shell32.SHGetFolderPathW
        get_folder.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR]
        get_folder.restype = ctypes.c_long
        buffer = ctypes.create_unicode_buffer(32768)
        if get_folder(None, 5, None, 0, buffer) == 0:
            return Path(buffer.value)
    return Path.home() / "Documents"


def snapshot(sdk, mods, pc):
    result = {
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version, "windows_version": platform.platform(),
        "executable": Path(sys.executable).name,
        "sdk_version": str(getattr(sdk, "__version__", "unknown")),
        "mods_base_version": str(getattr(mods, "__version__", "unknown")),
        "clock": {"implementation": time.get_clock_info("perf_counter").implementation,
                  "resolution_s": time.get_clock_info("perf_counter").resolution},
        "loaded_mods": [], "live_settings": {}, "ini_settings": {}, "read_errors": [],
        "test_context": "User described RTX 4080 SUPER, Windows 11, 4K 240 Hz OLED; not detected by this mod.",
    }

    def attempt(label, getter):
        try:
            return getter()
        except Exception as exc:
            if len(result["read_errors"]) < 64:
                result["read_errors"].append({"context": label, "error": f"{type(exc).__name__}: {exc}"})
            return None

    for mod in (attempt("mod list", mods.get_ordered_mod_list) or [])[:100]:
        item = attempt("mod metadata", lambda: {
            "name": str(mod.name), "version": str(mod.version), "enabled": bool(mod.is_enabled)})
        if item:
            result["loaded_mods"].append(item)
    for label, obj, fields in (
        ("engine", mods.ENGINE, ("bSmoothFrameRate", "MinSmoothedFrameRate", "MaxSmoothedFrameRate",
                               "MaxDeltaTime", "bUseFixedFrameRate", "FixedFrameRate")),
        ("world", pc.WorldInfo, ("TimeDilation", "NetMode", "TimeSeconds", "RealTimeSeconds", "DeltaSeconds")),
        ("controller", pc, ("bUsingGamepad", "bCinematicMode", "bBehindView")),
        ("input", getattr(pc, "PlayerInput", None), ("bEnableMouseSmoothing", "bUsingGamepad", "MouseSensitivity")),
    ):
        result["live_settings"][label] = {
            name: attempt(label + "." + name, lambda name=name: primitive(getattr(obj, name)))
            for name in fields}
    result["map"] = attempt("map", lambda: pc.WorldInfo.GetMapName())
    config = attempt("Documents folder", documents_dir)
    if config is not None:
        config = config / "My Games/Borderlands Game of the Year/WillowGame/Config"
        for filename in ("WillowEngine.ini", "WillowInput.ini", "WillowGame.ini"):
            path = config / filename
            result["ini_settings"][filename] = attempt(filename, lambda path=path: selected_ini(path))
    return result
