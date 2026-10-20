"""Manual, read-only HUD/font inspection. Never runs from the render hook."""

from collections import deque
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

MAX_OBJECTS = 500
MAX_ERRORS = 100
MAX_ASSETS = 16
MAX_ASSET_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
MAX_VALUES = 30_000
ASSET_CLASSES = {"SwfMovie", "FlashMovie", "GFxMovieInfo", "GFxRawData"}
SCHEMAS = ("WillowHUDGFxMovie", "WillowHUDGFxMovieDefinition", "WillowHUD",
           "GFxObject", "GFxMoviePlayer", "GFxMovie", "GearboxGFxMovie", "WillowGFxMovie",
           "Font", "MultiFont", "Canvas")
ROOTS = ("WillowHUDGFxMovie", "WillowHUDGFxMovieDefinition", "WillowHUD",
         "WillowGFxUIManager", "Font", "Canvas", "SwfMovie", "FlashMovie", "GFxMovieInfo")
SKIP = {"Class", "Outer", "Name", "ObjectFlags", "InternalIndex"}
FONT_FIELDS = ("font", "texture", "resolution", "height", "size", "scale", "import",
               "distance", "antialias", "kerning", "baseline", "ascent", "descent")


def export(sdk, pc, directory, version, runtime=None):
    stamp = datetime.now(timezone.utc).strftime("hud-%Y%m%d-%H%M%S-%f")
    folder = Path(directory) / stamp
    folder.mkdir(parents=True, exist_ok=False)
    report_path = folder / "report.json"
    report = {"version": version, "created_utc": datetime.now(timezone.utc).isoformat(),
              "complete": False, "runtime": runtime, "objects": [], "classes": {}, "assets": [],
              "errors": [], "limits": [], "player_present": pc is not None}

    def save():
        temporary = folder / "report.tmp"
        temporary.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        temporary.replace(report_path)

    save()  # Leave a basic report even if optional Unreal reflection fails.
    pending = deque()
    seen = set()
    asset_bytes = 0
    values_read = 0

    def error(context, exc):
        if len(report["errors"]) < MAX_ERRORS:
            report["errors"].append({"context": context, "error": repr(exc)[:500]})

    def read(context, getter, fallback=None):
        try:
            return getter()
        except Exception as exc:
            error(context, exc)
            return fallback

    def limit(name):
        if name not in report["limits"]:
            report["limits"].append(name)

    def class_name(obj):
        return str(obj.Class.Name)

    def queue(obj):
        name = obj._path_name()
        if name in seen or "default__" in name.lower():
            return
        cls = class_name(obj)
        if not (cls in ASSET_CLASSES or any(term in cls.lower() for term in
                ("hud", "gfx", "font", "movie", "canvas")) or cls == "Texture2D"):
            return
        if len(seen) >= MAX_OBJECTS:
            limit("object count")
            return
        seen.add(name)
        pending.append(obj)

    def value(data, depth=0):
        nonlocal values_read
        values_read += 1
        if values_read > MAX_VALUES:
            limit("serialized values")
            return "value limit"
        if data is None or isinstance(data, (str, int, bool)):
            return data
        if isinstance(data, float):
            return data if math.isfinite(data) else str(data)
        if hasattr(data, "_path_name"):
            queue(data)
            return {"ref": data._path_name(), "class": class_name(data)}
        if depth >= 4:
            return "depth limit"
        if isinstance(data, (bytes, bytearray)):
            return {"bytes": len(data)}
        if isinstance(data, (list, tuple)) or type(data).__name__ == "WrappedArray":
            items = [value(data[i], depth + 1) for i in range(min(len(data), 40))]
            return {"length": len(data), "items": items} if len(data) > 40 else items
        if hasattr(data, "_type") and hasattr(data._type, "_properties"):
            return {str(p.Name): read(str(p.Name), lambda p=p: value(getattr(data, str(p.Name)), depth + 1))
                    for p in data._type._properties()}
        return str(data)[:300]

    # Capture actual method/parameter names. No guessed GFx/ActionScript calls.
    for name in SCHEMAS:
        cls = read(f"class {name}", lambda name=name: sdk.find_class(name))
        if cls is None:
            continue
        record = {"path": cls._path_name(), "properties": [], "functions": {}}
        report["classes"][name] = record
        for prop in read(f"{name} properties", lambda: list(cls._properties()), [])[:256]:
            record["properties"].append({"name": str(prop.Name), "type": class_name(prop)})
        for field in read(f"{name} fields", lambda: list(cls._fields()), [])[:512]:
            if class_name(field) != "Function":
                continue
            record["functions"][str(field.Name)] = read(field._path_name(), lambda field=field: [
                {"name": str(p.Name), "type": class_name(p), "flags": int(p.PropertyFlags),
                 "struct": value(p.Struct) if hasattr(p, "Struct") else None}
                for p in list(field._properties())[:64]], [])

    for cls in ROOTS:
        # Only loaded objects: do not load packages, execute UI methods or alter
        # the HUD, native text, wallet, object flags, or actor state.
        objects = read(f"find {cls}", lambda cls=cls: sdk.find_all(cls, exact=False), [])
        for obj in objects:
            path = read(f"{cls} path", obj._path_name, "")
            if cls in ASSET_CLASSES and not any(word in path.lower() for word in ("hud", "font", "experience", "xpbar")):
                continue
            read(path, lambda obj=obj: queue(obj))
    if pc is not None:
        for name in ("myHUD", "GFxUIManager"):
            read(f"player.{name}", lambda name=name: value(getattr(pc, name, None)))

    while pending:
        obj = pending.popleft()
        path = obj._path_name()
        cls = class_name(obj)
        fields = {}
        record = {"path": path, "class": cls, "fields": fields}
        report["objects"].append(record)
        props = read(f"{path} properties", lambda: list(obj.Class._properties()), [])
        is_font = "font" in cls.lower()
        if len(props) > 256:
            limit("object fields")
        for prop in props[:256]:
            name = str(prop.Name)
            if name in SKIP:
                continue
            if is_font and not any(term in name.lower() for term in FONT_FIELDS):
                continue
            if cls == "Texture2D" and name not in ("SizeX", "SizeY", "Format", "LODGroup"):
                continue
            if name.lower() in ("rawdata", "rawbytes", "data") and cls in ASSET_CLASSES:
                raw = read(f"{path}.{name}", lambda name=name: getattr(obj, name))
                length = read(f"{path}.{name} length", lambda: len(raw), 0)
                fields[name] = {"length": length}
                if not length:
                    continue
                if len(report["assets"]) >= MAX_ASSETS or length > MAX_ASSET_BYTES or asset_bytes + length > MAX_TOTAL_BYTES:
                    limit("Flash asset size/count")
                    continue
                data = read(f"{path}.{name} bytes", lambda: bytes(raw))
                if data is None:
                    continue
                # Preserve only recognizable Flash/Scaleform files, not arbitrary
                # game buffers. These remain private diagnostic assets.
                signature = data[:3]
                if signature not in (b"FWS", b"CWS", b"ZWS", b"GFX", b"CFX"):
                    fields[name]["signature_hex"] = data[:8].hex()
                    continue
                extension = ".gfx" if signature in (b"GFX", b"CFX") else ".swf"
                filename = f"asset-{len(report['assets']):02d}" + extension
                (folder / filename).write_bytes(data)
                report["assets"].append({"object": path, "field": name, "file": filename,
                                         "size": len(data), "sha256": hashlib.sha256(data).hexdigest()})
                asset_bytes += len(data)
                continue
            fields[name] = read(f"{path}.{name}", lambda name=name: value(getattr(obj, name)))

    report["complete"] = True
    save()
    bundle = folder.with_suffix(".zip")
    with ZipFile(bundle, "w", ZIP_DEFLATED) as archive:
        for path in sorted(folder.iterdir()):
            if path.is_file():
                archive.write(path, path.name)
    return bundle
