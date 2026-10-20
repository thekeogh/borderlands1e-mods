"""Synthetic Flash/native API models; no game assets are redistributed."""

import ast
from contextlib import nullcontext
import importlib
from pathlib import Path
import struct
import sys
from types import ModuleType, SimpleNamespace as NS
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
package = ModuleType("money_native_test")
package.__path__ = [str(ROOT)]
sys.modules[package.__name__] = package
swf = importlib.import_module(package.__name__ + ".swf_text")
native = importlib.import_module(package.__name__ + ".native_text")
icon = importlib.import_module(package.__name__ + ".currency_icon")


def fixture():
    # Captured LV style constants, with synthetic identifiers and a tiny movie.
    font = b"gfxfontlib.swf\0\x01\x00" + struct.pack("<HH", 1, 245) + b"$WillowHead\0"
    edit = (struct.pack("<H", 289) + swf.make_rect((-409, 625, -40, 351))
            + b"\xed\x33" + struct.pack("<HH", 245, 240) + b"\xff\xff\xff\xff"
            + b"\x00" + struct.pack("<HHHh", 0, 0, 0, 40) + b'\0<p align="left"></p>\0')
    filters = (b"\x01\x00\x00\x00\x00\xb2"
               + struct.pack("<iiiiH", 2 << 16, 2 << 16, 0, 0, 7 << 8) + b"\x21")
    placement = b"\x26\x01" + struct.pack("<HH", 208, 289) + b"\x00level\0" + filters
    sprite = struct.pack("<HH", 933, 1) + swf.tag(70, placement) + swf.tag(1, b"") + swf.tag(0, b"")
    body = (swf.make_rect((0, 25600, 0, 14400)) + struct.pack("<HH", 24 << 8, 1)
            + swf.tag(71, font) + swf.tag(37, edit) + swf.tag(39, sprite)
            + swf.tag(1, b"") + swf.tag(0, b""))
    return b"GFX\x09" + struct.pack("<I", 8 + len(body)) + body, filters


def inventory_fixture():
    # Synthetic tall gold contour plus wide decorative bars. No game artwork.
    writer = icon.Writer()
    writer.put(1, 4)
    writer.put(0, 4)
    for x, y, width, height in ((100, -20, 200, 400), (400, 0, 3000, 40)):
        writer.put(0, 1)
        writer.put(5, 5)
        count = writer.signed((x, y))
        writer.put(count, 5)
        writer.put(x, count)
        writer.put(y, count)
        writer.put(1, 1)
        for dx, dy in ((width, 0), (0, height), (-width, 0), (0, -height)):
            count = writer.signed((dx, dy), 2)
            writer.put(1, 1)
            writer.put(1, 1)
            writer.put(count - 2, 4)
            writer.put(1, 1)
            writer.put(dx, count)
            writer.put(dy, count)
    writer.put(0, 6)
    shape = (struct.pack("<H", 431) + swf.make_rect((100, 3400, -20, 400))
             + b"\x01\x00\xff\xcc\x00\x00" + writer.finish())
    body = (swf.make_rect((0, 25600, 0, 14400)) + struct.pack("<HH", 24 << 8, 1)
            + swf.tag(2, shape) + swf.tag(1, b"") + swf.tag(0, b""))
    return b"GFX\x09" + struct.pack("<I", 8 + len(body)) + body


class IconTests(unittest.TestCase):
    def test_only_tall_gold_contour_is_extracted_and_normalized(self):
        shape, geometry = icon.extract_icon(inventory_fixture())
        self.assertEqual(geometry, {"icon_width": 10, "icon_height": 20, "icon_x_ratio": 1.0})
        self.assertEqual(swf.rect(shape)[0], (-20, 220, -20, 420))
        _, p = swf.rect(shape)
        self.assertEqual(shape[p:p + 11], b"\x01\x00\xff\xcc\x00\x01\x28\x00\x00\x00\x00")
        colors, paths = icon.contours(b"\x01\x00" + shape)
        self.assertEqual(colors, [(255, 204, 0)])
        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0]["start"], (0, 0))
        self.assertEqual(paths[0]["edges"], [(200, 0), (0, 400), (-200, 0), (0, -400)])

    def test_inventory_nonuniform_symbol_aspect_is_preserved(self):
        raw = inventory_fixture()
        _, p = swf.rect(raw, 8)
        entries = list(swf.tags(raw, p + 4))
        matrix = icon.Writer()
        matrix.put(1, 1)
        matrix.put(18, 5)
        matrix.put(32768, 18)
        matrix.put(65536, 18)
        matrix.put(0, 1)
        matrix.put(0, 5)
        placed = b"\x06" + struct.pack("<HH", 2, 432) + matrix.finish()
        sprite = (struct.pack("<HH", 433, 1) + swf.tag(26, placed)
                  + swf.tag(1, b"") + swf.tag(0, b""))
        body = raw[8:p + 4] + entries[0][2] + swf.tag(39, sprite) + b"".join(t[2] for t in entries[1:])
        raw = raw[:4] + struct.pack("<I", len(body) + 8) + body
        _, geometry = icon.extract_icon(raw)
        self.assertEqual(geometry["icon_x_ratio"], 0.5)

    def test_symbol_and_amount_are_transparent_in_the_movie_before_python_runs(self):
        raw, _ = fixture()
        patched, _ = swf.add_money_field(raw, inventory_fixture())
        _, p = swf.rect(patched, 8)
        placements = [data for code, data, _ in swf.tags(patched, p + 4)
                      if code == 70 and b"fullMoneyIndicator" in data]
        self.assertEqual(len(placements), 2)
        for data in placements:
            self.assertTrue(data[0] & 8)
            reader = swf.Bits(data, swf.skip_matrix(data, 6))
            self.assertEqual((reader.read(1), reader.read(1)), (0, 1))
            count = reader.read(4)
            self.assertEqual([reader.read(count, True) for _ in range(4)], [256, 256, 256, 0])

    def test_bad_or_missing_art_is_rejected(self):
        with self.assertRaises(ValueError): icon.extract_icon(b"bad")
        with self.assertRaises(ValueError): icon.extract_icon(fixture()[0])

    def test_icon_sprite_is_inserted_in_first_frame_and_original_tags_preserved(self):
        raw, _ = fixture()
        patched, geometry = swf.add_money_field(raw, inventory_fixture())
        _, p = swf.rect(raw, 8)
        old, new = list(swf.tags(raw, p + 4)), list(swf.tags(patched, p + 4))
        self.assertEqual([t[0] for t in new[3:9]], [71, 37, 70, 2, 39, 70])
        self.assertEqual(new[:3] + new[9:], old)
        self.assertEqual(swf.placement(new[8][1])[1], icon.ICON_NAME)
        self.assertEqual(geometry["icon_height"], 20)


class FlashTests(unittest.TestCase):
    def test_only_three_tags_added_and_all_original_tags_are_unchanged(self):
        raw, filters = fixture()
        patched, geometry = swf.add_money_field(raw)
        _, p = swf.rect(raw, 8)
        old, new = list(swf.tags(raw, p + 4)), list(swf.tags(patched, p + 4))
        self.assertEqual(len(new), len(old) + 3)
        additions = new[3:6]
        self.assertEqual([t[0] for t in additions], [71, 37, 70])
        self.assertEqual(new[:3] + new[6:], old)
        self.assertEqual(swf.placement(additions[2][1])[1:], (swf.FIELD_NAME, filters))
        self.assertEqual(geometry, {"width": 1280, "height": 720, "text_height": 19.55,
                                    "font": "$WillowHead", "font_size": 12})
        self.assertEqual(struct.unpack_from("<I", patched, 4)[0], len(patched))

    def test_early_field_gets_own_font_before_first_frame_despite_late_native_import(self):
        raw, _ = fixture()
        _, p = swf.rect(raw, 8)
        entries = list(swf.tags(raw, p + 4))
        # Real Enhanced HUD: nine loading frames precede the font imports.
        body = raw[8:p + 4] + swf.tag(1, b"") * 9 + b"".join(t[2] for t in entries)
        raw = raw[:4] + struct.pack("<I", 8 + len(body)) + body
        patched, _ = swf.add_money_field(raw)
        _, p = swf.rect(patched, 8)
        entries = list(swf.tags(patched, p + 4))
        font_index = next(i for i, t in enumerate(entries) if t[0] == 71)
        lv_index = next(i for i, t in enumerate(entries)
                        if t[0] == 37 and int.from_bytes(t[1][:2], "little") == 289)
        added_index = next(i for i, t in enumerate(entries)
                           if t[0] == 37 and int.from_bytes(t[1][:2], "little") >= 60000)
        self.assertLess(font_index, lv_index)
        self.assertEqual(added_index, font_index + 1)
        self.assertLess(added_index, lv_index)
        self.assertEqual(sum(t[0] == 1 for t in entries[:added_index]), 0)

    def test_font_color_size_and_layout_preserved_except_centering_and_wrapping(self):
        raw, _ = fixture()
        patched, _ = swf.add_money_field(raw)
        _, p = swf.rect(patched, 8)
        text = next(data for code, data, _ in swf.tags(patched, p + 4)
                    if code == 37 and struct.unpack_from("<H", data)[0] >= 60000)
        bounds, font, height, layout, _, flags, flags2 = swf.edit_text(text)
        self.assertEqual((font, height), (60001, 240))
        self.assertEqual(bounds, (0, 25600, -40, 351))
        self.assertEqual(text[layout], 2)
        self.assertFalse(flags & (32 | 64))
        self.assertTrue(flags2 & 1)  # UseOutlines: native font glyphs.

    def test_compressed_movies_keep_their_signature_and_correct_logical_length(self):
        raw, _ = fixture()
        compressed = b"CFX" + raw[3:8] + zlib.compress(raw[8:])
        patched, g = swf.add_money_field(compressed)
        self.assertEqual(patched[:3], b"CFX")
        self.assertEqual(struct.unpack_from("<I", patched, 4)[0], 8 + len(zlib.decompress(patched[8:])))
        self.assertEqual(g["font"], "$WillowHead")

    def test_duplicate_and_missing_native_font_are_rejected(self):
        raw, _ = fixture()
        patched, _ = swf.add_money_field(raw)
        with self.assertRaises(ValueError): swf.add_money_field(patched)
        with self.assertRaises(ValueError): swf.add_money_field(raw.replace(b"$WillowHead", b"$WillowBody"))

    def test_rectangle_negative_and_large_values_round_trip(self):
        for values in ((-409, 625, -40, 351), (0, 25600, 0, 14400), (-1, 1, -1, 1)):
            self.assertEqual(swf.rect(swf.make_rect(values))[0], values)


class Asset:
    def __init__(self):
        self.RawData = fixture()[0]; self.ObjectFlags = 8
        self.Class = "GFxMovieInfo"; self.Outer = "FlashMovie"
    def _path_name(self): return native.HUD_ASSET


class Movie:
    def __init__(self):
        self.bReady = [True]
        self.bRenderingDisabled = False
        self.values = {}
        self.calls = []
        self.present = True
    def GetVariableString(self, path):
        if not self.present: return ""
        return icon.ICON_NAME if path.startswith(native.ICON) else swf.FIELD_NAME
    def GetVariableNumber(self, path):
        if path.endswith(".textWidth"): return 60.0
        if path.endswith(".textHeight"): return 14.0
        return self.values.get(path, 0.0)
    def GetVariableBool(self, path): return self.values.get(path, False)
    def SetVariableString(self, path, value): self.values[path] = value; self.calls.append((path, value))
    def SetVariableNumber(self, path, value): self.values[path] = value; self.calls.append((path, value))
    def SetVariableBool(self, path, value): self.values[path] = value; self.calls.append((path, value))


class NativeTests(unittest.TestCase):
    def setUp(self):
        self.asset = Asset()
        self.inventory = NS(RawData=inventory_fixture())
        self.sdk = NS(find_object=lambda cls, path: self.inventory if path == icon.INVENTORY_ASSET else self.asset)
        self.created = []
        def construct(cls, outer, name, template_obj):
            result = Asset()
            result._path_name = lambda: "GfxHUD.FlashMovie." + name
            self.created.append(result)
            return result
        self.sdk.construct_object = construct
        self.renderer = native.NativeText(self.sdk)
        self.movie = Movie()
        self.hud = NS(HUDMovie=self.movie, bShowHUD=True)
        self.pc = NS(myHUD=self.hud)

    def test_prepare_is_idempotent_and_restore_reverts_bytes_and_owned_pin(self):
        raw = bytes(self.asset.RawData)
        self.renderer.prepare()
        first = bytes(self.asset.RawData)
        self.assertTrue(self.asset.ObjectFlags & native.KEEP_ALIVE)
        self.renderer.prepare()
        self.assertEqual(bytes(self.asset.RawData), first)
        self.assertEqual(self.renderer.restore(self.pc), [])
        self.assertEqual(bytes(self.asset.RawData), raw)
        self.assertEqual(self.asset.ObjectFlags, 8)
        self.assertFalse(self.movie.values[native.FIELD + "._visible"])

    def test_private_resource_replaces_cached_original_before_start_only(self):
        self.renderer.prepare()
        private = self.renderer.movie_asset
        self.assertNotEqual(private._path_name(), self.asset._path_name())
        self.assertEqual(bytes(private.RawData), self.renderer.patched)
        self.assertTrue(private.ObjectFlags & native.KEEP_ALIVE)
        self.movie.MovieInfo = self.asset
        calls = []
        # Original path was compiled before the mod patched RawData. It still
        # resolves to a movie with no fields, despite those bytes now changing.
        compiled = {self.asset._path_name(): False}
        self.movie.present = False
        def set_info(data):
            calls.append(data)
            self.movie.MovieInfo = data
            self.movie.present = compiled.setdefault(data._path_name(), b"fullMoneyIndicator" in data.RawData)
        self.movie.SetMovieInfo = set_info
        self.renderer.before_start(self.movie)
        self.renderer.before_start(self.movie)
        self.assertEqual(calls, [private])
        self.assertTrue(self.movie.present)
        self.assertFalse(compiled[self.asset._path_name()])
        self.assertEqual(self.renderer.bind_count, 1)
        self.assertEqual(len(self.created), 1)
        self.assertIs(self.renderer.movie_info_for(self.asset), private)
        self.assertIsNone(self.renderer.movie_info_for(private))
        unrelated = NS(_path_name=lambda: "ui_inventory.Inventory")
        self.assertIsNone(self.renderer.movie_info_for(unrelated))
        self.renderer.restore(self.pc)
        self.assertFalse(private.ObjectFlags & native.KEEP_ALIVE)
        self.assertIs(self.movie.MovieInfo, private)  # No live HUD reload.
        self.renderer.prepare()
        self.assertIsNot(self.renderer.movie_asset, private)

    def test_registered_lifecycle_callbacks_redirect_once_and_skip_other_movies(self):
        tree = ast.parse((ROOT / "__init__.py").read_text())
        callbacks = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                     and node.name in ("on_movie_info", "on_hud_start")]
        for node in callbacks:
            node.decorator_list = []
        block, warnings = object(), []
        namespace = {"renderer": self.renderer, "Block": block,
                     "prevent_hooking_direct_calls": nullcontext, "warn_once": warnings.append}
        exec(compile(ast.Module(body=callbacks, type_ignores=[]), "callbacks", "exec"), namespace)
        calls = []
        result = namespace["on_movie_info"](self.movie, NS(Data=self.asset), None, calls.append)
        self.assertIs(result, block)
        self.assertEqual(calls, [self.renderer.movie_asset])
        other = NS(_path_name=lambda: "ui_lobby.Lobby2")
        self.assertIsNone(namespace["on_movie_info"](self.movie, NS(Data=other), None, calls.append))
        self.assertEqual(len(calls), 1)
        self.movie.MovieInfo = self.asset
        self.movie.SetMovieInfo = lambda data: setattr(self.movie, "MovieInfo", data)
        namespace["on_hud_start"](self.movie, None, None, None)
        self.assertIs(self.movie.MovieInfo, self.renderer.movie_asset)
        self.assertEqual(warnings, [])

    def test_failed_private_resource_creation_leaves_original_untouched(self):
        original = bytes(self.asset.RawData)
        def fail(*args, **kwargs): raise ValueError("construction failed")
        self.sdk.construct_object = fail
        with self.assertRaisesRegex(ValueError, "construction failed"):
            self.renderer.prepare()
        self.assertEqual(bytes(self.asset.RawData), original)
        self.assertEqual(self.asset.ObjectFlags, 8)
        self.assertIsNone(self.renderer.asset)
        self.assertIsNone(self.renderer.movie_asset)

    def test_already_pinned_asset_stays_pinned_and_external_edit_is_preserved(self):
        self.asset.ObjectFlags |= native.KEEP_ALIVE
        self.renderer.prepare()
        self.asset.RawData = b"another mod's edit"
        self.renderer.restore(self.pc)
        self.assertEqual(self.asset.RawData, b"another mod's edit")
        self.assertTrue(self.asset.ObjectFlags & native.KEEP_ALIVE)

    def test_native_text_and_positive_negative_offsets_scale_at_1080p_and_4k(self):
        self.renderer.prepare()
        for width, height in ((1920, 1080), (3840, 2160)):
            self.renderer.draw(self.pc, "$2,147,483,647", width, height, 0, 18)
            y = self.movie.values[native.FIELD + "._y"]
            html = self.movie.values[native.FIELD + ".htmlText"]
            self.assertIn('2,147,483,647</font>', html)
            self.assertIn('face="$WillowHead" size="12"', html)
            self.assertTrue(self.movie.values[native.FIELD + ".embedFonts"])
            self.assertNotIn("$2,147", html)
            for offset in (-10, 5):
                self.renderer.draw(self.pc, "$123", width, height, offset, 18)
                self.assertAlmostEqual(self.movie.values[native.FIELD + "._y"] - y, offset / 1.5)

    def test_fixed_preferences_preserve_font_and_center_whole_group(self):
        self.renderer.prepare()
        for width, height in ((1920, 1080), (3840, 2160)):
            self.renderer.draw(self.pc, "$123", width, height, 0, 18)
            values = self.movie.values
            self.assertIn('size="12"', values[native.FIELD + ".htmlText"])
            self.assertAlmostEqual(values[native.FIELD + "._xscale"], 100)
            self.assertAlmostEqual(values[native.FIELD + "._yscale"], 100)
            icon_width = 18.9 * 0.5  # Synthetic icon aspect ratio.
            gap = 7 / 1.5
            amount_center = 640 + values[native.FIELD + "._x"]
            icon_left = values[native.ICON + "._x"]
            amount_left = amount_center - 60 / 2
            self.assertAlmostEqual(amount_left - (icon_left + icon_width), gap)
            self.assertAlmostEqual((icon_left + amount_center + 60 / 2) / 2, 640)
            self.assertAlmostEqual(values[native.ICON + "._xscale"], 94.5)
            self.assertAlmostEqual(values[native.ICON + "._yscale"], 94.5)
        self.renderer.restore(self.pc)
        self.assertFalse(values[native.ICON + "._visible"])

    def test_show_follows_layout_and_failed_layout_keeps_both_elements_hidden(self):
        self.renderer.prepare()
        self.renderer.draw(self.pc, "$123", 1920, 1080, 0, 18)
        calls = self.movie.calls
        layout_end = max(i for i, (path, _) in enumerate(calls) if path == native.ICON + "._y")
        for path in (native.FIELD, native.ICON):
            show = next(i for i, call in enumerate(calls) if call == (path + "._visible", True))
            self.assertGreater(show, layout_end)
            self.assertEqual(self.movie.values[path + "._alpha"], 100)
        self.movie.GetVariableNumber = lambda path: float("nan")
        with self.assertRaisesRegex(RuntimeError, "measurement"):
            self.renderer.draw(self.pc, "$123", 1920, 1080, 0, 18)
        self.assertFalse(self.movie.values[native.FIELD + "._visible"])
        self.assertFalse(self.movie.values[native.ICON + "._visible"])

    def test_manual_inspection_captures_missing_field_without_writes(self):
        self.movie.GetVariableNumber = lambda path: float("nan")
        self.movie.GetVariableBool = lambda path: False
        self.movie.present = False
        result = self.renderer.inspect(self.pc)
        self.assertEqual(result["variables"][native.FIELD + "._name"], "")
        self.assertEqual(result["variables"]["_root._currentframe"], "nan")
        self.assertFalse(result["prepared"])
        self.assertEqual(self.movie.values, {})

    def test_native_hud_visibility_is_respected(self):
        self.renderer.prepare()
        self.hud.bShowHUD = False
        self.renderer.draw(self.pc, "$123", 3840, 2160, 0, 18)
        self.assertEqual(self.movie.values, {native.FIELD + "._visible": False, native.ICON + "._visible": False})

    def test_old_already_loaded_hud_requires_restart_without_bitmap_fallback(self):
        self.renderer.prepare()
        self.movie.present = False
        with self.assertRaisesRegex(RuntimeError, "restart"):
            self.renderer.draw(self.pc, "$123", 3840, 2160, 0, 18)
        self.assertEqual(self.movie.values, {})

    def test_unloaded_asset_waits_for_native_start_and_invalid_data_does_not_mutate(self):
        def missing(*args): raise ValueError("not loaded")
        self.renderer.sdk.find_object = missing
        self.assertFalse(self.renderer.prepare())
        self.sdk.find_object = lambda cls, path: self.inventory if path == icon.INVENTORY_ASSET else self.asset
        self.asset.RawData = b"not a HUD"
        with self.assertRaises(ValueError): self.renderer.prepare(self.asset)
        self.assertEqual(self.asset.RawData, b"not a HUD")
        self.assertEqual(self.asset.ObjectFlags, 8)


if __name__ == "__main__": unittest.main()
