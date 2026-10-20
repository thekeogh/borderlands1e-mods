"""Extract the gold currency contour from the installed inventory's vector art.

No game artwork is bundled. The inventory's surrounding bars/background are
excluded; a solid black vector stroke keeps the symbol readable.
"""

import struct
import zlib

from .swf_text import Bits, make_rect, rect, tags

INVENTORY_ASSET = "menus_ingame_redux.FlashMovies.status_menu"
ICON_NAME = "fullMoneyIndicatorDollar"
OUTLINE_TWIPS = 40  # Two source pixels, scaled with the native symbol.


class Writer:
    def __init__(self):
        self.bits = []

    def put(self, value, count):
        self.bits.append(f"{value & ((1 << count) - 1):0{count}b}")

    @staticmethod
    def signed(values, minimum=1):
        return max(minimum, *(max(1, (v if v >= 0 else ~v).bit_length() + 1) for v in values))

    def finish(self):
        bits = "".join(self.bits)
        bits += "0" * (-len(bits) % 8)
        return int(bits, 2).to_bytes(len(bits) // 8, "big")


def contours(payload):
    """Read simple solid-colour DefineShape contours, retaining native curves."""
    _, position = rect(payload, 2)
    count = payload[position]
    position += 1
    if count == 255:
        raise ValueError("Unsupported inventory fill table")
    colors = []
    for _ in range(count):
        if payload[position] != 0:
            raise ValueError("Currency shape requires solid vector fills")
        colors.append(tuple(payload[position + 1:position + 4]))
        position += 4
    line_count = payload[position]
    if line_count == 255:
        raise ValueError("Unsupported currency vector line table")
    # DefineShape uses width (UI16) + RGB for each simple line style.
    reader = Bits(payload, position + 1 + line_count * 5)
    fills, lines = reader.read(4), reader.read(4)
    x = y = fill0 = fill1 = 0
    paths = []
    current = None
    while True:
        if not reader.read(1):
            flags = reader.read(5)
            if flags == 0:
                break
            if flags & 16:
                raise ValueError("Unexpected inline currency vector styles")
            if flags & 1:
                count = reader.read(5)
                x, y = reader.read(count, True), reader.read(count, True)
            if flags & 2:
                fill0 = reader.read(fills)
            if flags & 4:
                fill1 = reader.read(fills)
            if flags & 8:
                reader.read(lines)
            current = {"start": (x, y), "fill0": fill0, "fill1": fill1, "edges": []}
            paths.append(current)
            continue
        straight = reader.read(1)
        count = reader.read(4) + 2
        if straight:
            if reader.read(1):
                dx, dy = reader.read(count, True), reader.read(count, True)
            elif reader.read(1):
                dx, dy = 0, reader.read(count, True)
            else:
                dx, dy = reader.read(count, True), 0
            edge = (dx, dy)
            x, y = x + dx, y + dy
        else:
            edge = tuple(reader.read(count, True) for _ in range(4))
            x, y = x + edge[0] + edge[2], y + edge[1] + edge[3]
        if current is None:
            raise ValueError("Currency contour has no starting point")
        current["edges"].append(edge)
    return colors, paths


def extract_icon(raw):
    """Return a normalized solid-gold shape payload (without its character ID)."""
    if raw[:3] not in (b"GFX", b"FWS", b"CFX", b"CWS"):
        raise ValueError("Unsupported inventory Flash signature")
    body = zlib.decompress(raw[8:]) if raw[:3] in (b"CFX", b"CWS") else raw[8:]
    _, position = rect(body)
    # This is the inventory credits graphic, not an approximation of its glyph.
    entries = list(tags(body, position + 4))
    payload = next((p for c, p, _ in entries
                    if c == 2 and struct.unpack_from("<H", p)[0] == 431), None)
    if payload is None:
        raise ValueError("Inventory currency vector was not found")
    colors, paths = contours(payload)
    candidates = []
    for path in paths:
        selected = [colors[i - 1] for i in (path["fill0"], path["fill1"]) if i]
        if (255, 204, 0) not in selected:
            continue
        x, y = path["start"]
        points = [(x, y)]
        for edge in path["edges"]:
            if len(edge) == 2:
                x, y = x + edge[0], y + edge[1]
            else:
                points.append((x + edge[0], y + edge[1]))
                x, y = x + edge[0] + edge[2], y + edge[1] + edge[3]
            points.append((x, y))
        left, right = min(p[0] for p in points), max(p[0] for p in points)
        top, bottom = min(p[1] for p in points), max(p[1] for p in points)
        # Exclude the long, short decorative bars and the dark outer contour.
        if bottom - top > right - left > 0 and (x, y) == path["start"]:
            candidates.append((path, left, right, top, bottom))
    if len(candidates) != 1:
        raise ValueError("Could not isolate the native inventory dollar sign")
    path, left, right, top, bottom = candidates[0]
    writer = Writer()
    writer.put(1, 4)  # One gold fill.
    writer.put(1, 4)  # One solid black line style.
    writer.put(0, 1)
    writer.put(13, 5)  # MoveTo + FillStyle1 + LineStyle.
    start = (path["start"][0] - left, path["start"][1] - top)
    count = writer.signed(start)
    writer.put(count, 5)
    for v in start:
        writer.put(v, count)
    writer.put(1, 1)
    writer.put(1, 1)  # Apply black outline to the complete closed contour.
    for edge in path["edges"]:
        count = writer.signed(edge, 2)
        writer.put(1, 1)
        writer.put(len(edge) == 2, 1)
        writer.put(count - 2, 4)
        if len(edge) == 2:
            writer.put(1, 1)  # General line: explicit X and Y.
        for v in edge:
            writer.put(v, count)
    writer.put(0, 6)  # EndShape.
    width, height = right - left, bottom - top
    half_stroke = OUTLINE_TWIPS // 2
    shape = (make_rect((-half_stroke, width + half_stroke, -half_stroke, height + half_stroke))
             + b"\x01\x00\xff\xcc\x00\x01"
             + struct.pack("<H", OUTLINE_TWIPS) + b"\x00\x00\x00" + writer.finish())
    # The inventory narrows the symbol with a non-uniform placement scale.
    # Preserve that native aspect ratio independently of the configured symbol size.
    x_ratio = 1.0
    for code, sprite, _ in entries:
        if code != 39 or struct.unpack_from("<H", sprite)[0] != 433:
            continue
        for sub_code, placed, _ in tags(sprite, 4):
            if (sub_code == 26 and placed[0] & 6 == 6
                    and struct.unpack_from("<H", placed, 3)[0] == 432):
                reader = Bits(placed, 5)
                if reader.read(1):
                    count = reader.read(5)
                    scale_x, scale_y = reader.read(count, True), reader.read(count, True)
                    if scale_x <= 0 or scale_y <= 0:
                        raise ValueError("Invalid native currency symbol scale")
                    x_ratio = scale_x / scale_y
    return shape, {"icon_width": width / 20, "icon_height": height / 20,
                   "icon_x_ratio": x_ratio}
