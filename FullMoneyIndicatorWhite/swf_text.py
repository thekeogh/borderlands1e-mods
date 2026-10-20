"""Add native money text and an optional inventory currency sprite.

No HUD artwork or fonts are shipped. Every original tag is kept byte-for-byte;
additional tags are generated from the installed game's own UI data.
"""

import struct
import zlib

FIELD_NAME = "fullMoneyIndicatorWhite"
FONT_NAME = "$WillowHead"

# PlaceObject3 CXFORMWITHALPHA: RGB multiplier 1, alpha multiplier 0.
# Born transparent, before Python or a ready player/HUD can position the field.
_alpha_bits = "01" + "1010" + f"{256:010b}" * 3 + "0" * 10
TRANSPARENT = int(_alpha_bits + "0" * (-len(_alpha_bits) % 8), 2).to_bytes(6, "big")


class Bits:
    def __init__(self, data, position=0):
        self.data = data
        self.bit = position * 8

    def read(self, count, signed=False):
        result = 0
        for _ in range(count):
            result = (result << 1) | ((self.data[self.bit // 8] >> (7 - self.bit % 8)) & 1)
            self.bit += 1
        return result - (1 << count) if signed and count and result & (1 << (count - 1)) else result

    @property
    def position(self):
        return (self.bit + 7) // 8


def rect(data, start=0):
    reader = Bits(data, start)
    count = reader.read(5)
    return tuple(reader.read(count, signed=True) for _ in range(4)), reader.position


def make_rect(values):
    count = max(max(1, (v if v >= 0 else ~v).bit_length() + 1) for v in values)
    if count > 31:
        raise ValueError("HUD text bounds exceed SWF rectangle range")
    bits = f"{count:05b}" + "".join(f"{v & ((1 << count) - 1):0{count}b}" for v in values)
    bits += "0" * (-len(bits) % 8)
    return int(bits, 2).to_bytes(len(bits) // 8, "big")


def skip_matrix(data, start):
    reader = Bits(data, start)
    for _ in range(2):  # Optional scale and rotation pairs.
        if reader.read(1):
            count = reader.read(5)
            reader.read(count * 2)
    reader.read(reader.read(5) * 2)
    return reader.position


def tag(code, payload):
    size = len(payload)
    return (struct.pack("<H", (code << 6) | min(size, 63))
            + (struct.pack("<I", size) if size >= 63 else b"") + payload)


def tags(data, start=0):
    position = start
    while position < len(data):
        beginning = position
        header, = struct.unpack_from("<H", data, position)
        position += 2
        code, length = header >> 6, header & 63
        if length == 63:
            length, = struct.unpack_from("<I", data, position)
            position += 4
        end = position + length
        if end > len(data):
            raise ValueError("Truncated HUD Flash tag")
        yield code, data[position:end], data[beginning:end]
        position = end
        if code == 0:
            return


def c_string(data, start):
    end = data.index(0, start)
    return data[start:end].decode("utf-8"), end + 1


def placement(payload):
    # The captured single-player LV field is a PlaceObject3 with precisely
    # Character/Matrix/Name/Filters, plus our optional initial transparency.
    # Reject unfamiliar layouts instead of guessing.
    if payload[:2] not in (b"\x26\x01", b"\x2e\x01"):
        return None
    character, = struct.unpack_from("<H", payload, 4)
    position = skip_matrix(payload, 6)
    if payload[0] & 8:
        reader = Bits(payload, position)
        additions, multipliers, count = reader.read(1), reader.read(1), reader.read(4)
        reader.read((additions + multipliers) * count * 4)
        position = reader.position
    name, position = c_string(payload, position)
    return character, name, payload[position:]


def edit_text(payload):
    bounds, position = rect(payload, 2)
    flags, flags2 = payload[position:position + 2]
    position += 2
    if not flags & 1 or flags2 & 128:
        return None  # Require the native imported font ID, not a guessed font class.
    font, height = struct.unpack_from("<HH", payload, position)
    position += 4
    if flags & 4:
        position += 4  # RGBA.
    if flags & 2:
        position += 2  # MaxLength.
    layout = position if flags2 & 32 else None
    if layout is not None:
        position += 9
    _, position = c_string(payload, position)  # VariableName.
    return bounds, font, height, layout, position, flags, flags2


def add_money_field(raw, inventory_raw=None):
    """Return patched bytes and native geometry, or reject unsupported HUD data."""
    if raw[:3] not in (b"GFX", b"FWS", b"CFX", b"CWS"):
        raise ValueError("Unsupported HUD Flash signature")
    compressed = raw[:3] in (b"CFX", b"CWS")
    body = zlib.decompress(raw[8:]) if compressed else raw[8:]
    bounds, position = rect(body)
    width, height = (bounds[1] - bounds[0]) / 20, (bounds[3] - bounds[2]) / 20
    entries = list(tags(body, position + 4))  # Frame rate and count follow RECT.
    if any(FIELD_NAME.encode() + b"\0" in p for _, p, _ in entries):
        raise ValueError("HUD already contains the money field")
    font_id = None
    font_import = None
    texts = {}
    placements = []
    used_ids = set()
    for code, payload, _ in entries:
        if len(payload) >= 2:
            used_ids.add(struct.unpack_from("<H", payload)[0])
        if code in (57, 71):  # ImportAssets / ImportAssets2.
            _, p = c_string(payload, 0)
            p += 2 if code == 71 else 0
            count, = struct.unpack_from("<H", payload, p)
            p += 2
            import_prefix = payload[:p - 2]
            for _ in range(count):
                identifier, = struct.unpack_from("<H", payload, p)
                name, p = c_string(payload, p + 2)
                used_ids.add(identifier)
                if name == FONT_NAME:
                    font_id = identifier
                    font_import = (code, import_prefix)
        elif code == 37:
            info = edit_text(payload)
            if info is not None:
                texts[struct.unpack_from("<H", payload)[0]] = (payload, info)
        elif code == 39:
            for sub_code, sub_payload, _ in tags(payload, 4):
                if sub_code == 70:
                    item = placement(sub_payload)
                    if item is not None and item[1] == "level":
                        placements.append(item)
    candidates = [(texts[c][1][2], texts[c], filters) for c, _, filters in placements
                  if c in texts and texts[c][1][1] == font_id]
    if not candidates:
        raise ValueError("Native LV text/font/filter could not be identified")
    # Solo LV is the largest native player-level label. Split-screen variants
    # are smaller; the enemy label uses WillowBody and was excluded above.
    _, (template, info), filters = max(candidates, key=lambda item: item[0])
    old_bounds, _, font_height, layout, text_start, flags, flags2 = info
    available = (i for i in range(60000, 65535) if i not in used_ids)
    identifier, own_font = next(available), next(available)
    icon_tags = []
    icon_geometry = {}
    if inventory_raw is not None:
        from .currency_icon import ICON_NAME, extract_icon
        shape, icon_geometry = extract_icon(inventory_raw)
        shape_id, sprite_id = next(available), next(available)
        sprite = (struct.pack("<HH", sprite_id, 1)
                  + tag(26, b"\x06" + struct.pack("<HH", 1, shape_id) + b"\0")
                  + tag(1, b"") + tag(0, b""))
        place = (b"\x2e\x01" + struct.pack("<HH", 60001, sprite_id) + b"\0" + TRANSPARENT
                 + ICON_NAME.encode() + b"\0" + filters)
        icon_tags = [tag(2, struct.pack("<H", shape_id) + shape), tag(39, sprite), tag(70, place)]
    _, bounds_end = rect(template, 2)
    tail = bytearray(template[bounds_end:text_start])
    struct.pack_into("<H", tail, 2, own_font)
    tail[0] &= ~(64 | 32)  # Single line; never wrap a long wallet amount.
    if layout is None:
        raise ValueError("Native LV text has no layout information")
    tail[layout - bounds_end] = 2  # Center alignment, same native font/spacing.
    new_bounds = (0, int(width * 20), old_bounds[2], old_bounds[3])
    new_text = (struct.pack("<H", identifier) + make_rect(new_bounds) + bytes(tail)
                + b'<p align="center"></p>\0')
    # Identity MATRIX at the root. Position is updated through the native GFx
    # API; the copied LV filter remains on this independent text field.
    new_place = (b"\x2e\x01" + struct.pack("<HH", 60000, identifier) + b"\x00" + TRANSPARENT
                 + FIELD_NAME.encode() + b"\0" + filters)
    # Keep placement in frame 1, which survives the HUD's layout jumps. Import
    # the font under our own ID first, without moving or replacing native tags.
    import_code, import_prefix = font_import
    own_import = (import_prefix + struct.pack("<HH", 1, own_font)
                  + FONT_NAME.encode() + b"\0")
    output = []
    inserted = False
    for code, payload, original in entries:
        if code == 1 and not inserted:
            output.extend([tag(import_code, own_import), tag(37, new_text), tag(70, new_place)] + icon_tags)
            inserted = True
        output.append(original)
    if not inserted:
        raise ValueError("HUD movie has no first frame")
    patched_body = body[:position + 4] + b"".join(output)
    header = raw[:4] + struct.pack("<I", 8 + len(patched_body))
    patched = header + (zlib.compress(patched_body) if compressed else patched_body)
    return patched, {"width": width, "height": height,
                     "text_height": (new_bounds[3] - new_bounds[2]) / 20,
                     "font": FONT_NAME, "font_size": font_height / 20, **icon_geometry}
