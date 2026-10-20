"""Native Scaleform text, independently added to the installed HUD movie."""

from html import escape
from itertools import count
import math

from .swf_text import FIELD_NAME, add_money_field
from .currency_icon import ICON_NAME, INVENTORY_ASSET

HUD_ASSET = "GfxHUD.FlashMovie.HUD"
FIELD = "_root." + FIELD_NAME
ICON = "_root." + ICON_NAME
KEEP_ALIVE = 0x4000
ICON_SIZE = 105
ICON_SPACING = 7
AMOUNT_SIZE = 100
HUD_NAMES = count()


class NativeText:
    def __init__(self, sdk):
        self.sdk = sdk
        self.asset = None
        self.original = None
        self.patched = None
        self.geometry = None
        self.was_pinned = False
        self.movie_asset = None
        self.bind_count = 0

    def prepare(self, asset=None):
        if asset is None:
            try:
                asset = self.sdk.find_object("GFxMovieInfo", HUD_ASSET)
            except ValueError:
                return False  # Not loaded yet; the native HUD Start hook retries.
        if asset is None or asset._path_name().lower() != HUD_ASSET.lower():
            return False
        if self.asset is not None:
            return True
        original = bytes(asset.RawData)
        try:
            inventory = self.sdk.find_object("GFxMovieInfo", INVENTORY_ASSET)
        except ValueError:
            self.sdk.load_package(INVENTORY_ASSET.split(".")[0])
            inventory = self.sdk.find_object("GFxMovieInfo", INVENTORY_ASSET)
        patched, geometry = add_money_field(original, bytes(inventory.RawData))
        # A changed RawData array does not replace an already compiled GFx
        # movie. Give the prepared HUD a distinct resource identity and bind it
        # before native SetMovieInfo/Start, instead of relying on cache timing.
        movie_asset = self.sdk.construct_object(
            asset.Class, asset.Outer,
            name=f"FullMoneyIndicatorWhiteHUD_{next(HUD_NAMES)}", template_obj=asset)
        movie_asset.RawData = bytearray(patched)
        movie_asset.ObjectFlags |= KEEP_ALIVE
        was_pinned = bool(asset.ObjectFlags & KEEP_ALIVE)
        asset.ObjectFlags |= KEEP_ALIVE
        try:
            asset.RawData = bytearray(patched)
        except Exception:
            try:
                asset.RawData = bytearray(original)
            finally:
                if not was_pinned:
                    asset.ObjectFlags &= ~KEEP_ALIVE
                movie_asset.ObjectFlags &= ~KEEP_ALIVE
            raise
        self.asset, self.original, self.patched = asset, original, patched
        self.geometry, self.was_pinned = geometry, was_pinned
        self.movie_asset = movie_asset
        return True

    def movie_info_for(self, info):
        """Return our private resource only for the game's HUD movie."""
        if info is None:
            return None
        if self.movie_asset is not None and info == self.movie_asset:
            return None
        if info._path_name().lower() != HUD_ASSET.lower():
            return None
        if not self.prepare(info):
            return None
        return self.movie_asset

    def before_start(self, movie):
        replacement = self.movie_info_for(getattr(movie, "MovieInfo", None))
        if replacement is not None:
            # Called only in PRE Start, never against an already running HUD.
            movie.SetMovieInfo(replacement)
            self.bind_count += 1

    @staticmethod
    def movie(pc):
        hud = getattr(pc, "myHUD", None)
        return hud, getattr(hud, "HUDMovie", None)

    def draw(self, pc, text, size_x, size_y, offset, bottom_margin):
        hud, movie = self.movie(pc)
        if movie is None or not movie.bReady[0]:
            return
        if movie.GetVariableString(FIELD + "._name") != FIELD_NAME:
            raise RuntimeError("Native money field is not loaded. Fully restart the game after installing this version.")
        if movie.GetVariableString(ICON + "._name") != ICON_NAME:
            raise RuntimeError("Native dollar icon is not loaded. Fully restart the game after installing this version.")
        visible = bool(hud.bShowHUD and not movie.bRenderingDisabled)
        movie.SetVariableBool(FIELD + "._visible", False)
        movie.SetVariableBool(ICON + "._visible", False)
        if not visible:
            return
        if self.geometry is None:
            raise RuntimeError("Native HUD text was not prepared before HUD startup")
        g = self.geometry
        screen_scale = min(size_x / 1920.0, size_y / 1080.0)
        native_scale = min(size_x / g["width"], size_y / g["height"])
        amount_scale = AMOUNT_SIZE / 100
        font_size = g["font_size"]
        y = g["height"] - g["text_height"] * amount_scale - (bottom_margin - offset) * screen_scale / native_scale
        movie.SetVariableNumber(FIELD + "._y", y)
        # Scale the text itself: changing HTML font size alone was ineffective
        # with this imported font on the user's HUD.
        movie.SetVariableNumber(FIELD + "._xscale", AMOUNT_SIZE)
        movie.SetVariableNumber(FIELD + "._yscale", AMOUNT_SIZE)
        # Match the explicit font formatting used by the live native LV label.
        movie.SetVariableBool(FIELD + ".embedFonts", True)
        html = (f'<p align="center"><font face="{g["font"]}" '
                f'size="{font_size:g}" color="#FFFFFF">'
                f'{escape(text.removeprefix("$"))}</font></p>')
        movie.SetVariableString(FIELD + ".htmlText", html)
        width = movie.GetVariableNumber(FIELD + ".textWidth")
        text_height = movie.GetVariableNumber(FIELD + ".textHeight")
        if not math.isfinite(width) or width < 0:
            raise RuntimeError("Native amount text measurement failed")
        if not math.isfinite(text_height) or text_height <= 0:
            text_height = font_size
        width *= amount_scale
        text_height *= amount_scale
        icon_height = 18 * ICON_SIZE / 100
        icon_scale = icon_height / g["icon_height"]
        icon_width = g["icon_width"] * icon_scale * g["icon_x_ratio"]
        gap = ICON_SPACING * screen_scale / native_scale
        # Center the whole icon + gap + amount group, not just the digits.
        movie.SetVariableNumber(FIELD + "._x", g["width"] * (1 - amount_scale) / 2 + (icon_width + gap) / 2)
        movie.SetVariableNumber(ICON + "._xscale", icon_scale * g["icon_x_ratio"] * 100)
        movie.SetVariableNumber(ICON + "._yscale", icon_scale * 100)
        movie.SetVariableNumber(ICON + "._x", (g["width"] - width - gap - icon_width) / 2)
        movie.SetVariableNumber(ICON + "._y", y + 2 * amount_scale + (text_height - icon_height) / 2)
        # Reveal only after both elements have their final scale and position.
        for path in (FIELD, ICON):
            movie.SetVariableNumber(path + "._alpha", 100)
            movie.SetVariableBool(path + "._visible", True)

    def inspect(self, pc):
        """Read native timeline/field state only when diagnostics are requested."""
        result = {"prepared": self.asset is not None, "geometry": self.geometry,
                  "movie_asset": self.movie_asset._path_name() if self.movie_asset is not None else None,
                  "bind_count": self.bind_count,
                  "defaults": {"icon_size": ICON_SIZE, "icon_spacing": ICON_SPACING, "amount_size": AMOUNT_SIZE}}
        hud, movie = self.movie(pc)
        result["movie_present"] = movie is not None
        info = getattr(movie, "MovieInfo", None) if movie is not None else None
        result["live_movie_info"] = info._path_name() if info is not None else None
        if movie is None:
            return result
        result["variables"] = values = {}
        for prefix in ("_root", FIELD, ICON, "_root.p1", "_root.p1.level"):
            for suffix, getter in (
                ("_name", movie.GetVariableString),
                ("_currentframe", movie.GetVariableNumber),
                ("_visible", movie.GetVariableBool),
                ("_alpha", movie.GetVariableNumber),
                ("_x", movie.GetVariableNumber),
                ("_y", movie.GetVariableNumber),
                ("_width", movie.GetVariableNumber),
                ("_height", movie.GetVariableNumber),
                ("_xscale", movie.GetVariableNumber),
                ("_yscale", movie.GetVariableNumber),
                ("textWidth", movie.GetVariableNumber),
                ("textHeight", movie.GetVariableNumber),
                ("text", movie.GetVariableString),
                ("htmlText", movie.GetVariableString),
                ("embedFonts", movie.GetVariableBool),
            ):
                path = prefix + "." + suffix
                try:
                    value = getter(path)
                    # Undefined native numbers can be NaN; keep JSON valid.
                    if isinstance(value, float) and not math.isfinite(value):
                        value = str(value)
                    values[path] = value
                except Exception as exc:
                    values[path] = {"error": str(exc)}
        return result

    def restore(self, pc):
        errors = []
        try:
            _, movie = self.movie(pc)
            if movie is not None:
                movie.SetVariableBool(FIELD + "._visible", False)
                movie.SetVariableBool(ICON + "._visible", False)
        except Exception as exc:
            errors.append(exc)
        if self.asset is not None:
            try:
                # Preserve any subsequent changes made by a different HUD mod.
                if bytes(self.asset.RawData) == self.patched:
                    self.asset.RawData = bytearray(self.original)
            except Exception as exc:
                errors.append(exc)
            finally:
                try:
                    if not self.was_pinned:
                        self.asset.ObjectFlags &= ~KEEP_ALIVE
                except Exception as exc:
                    errors.append(exc)
                self.asset = self.original = self.patched = self.geometry = None
        if self.movie_asset is not None:
            try:
                # A live movie's MovieInfo reference keeps its resource alive.
                # Do not switch/restart that live HUD while disabling the mod.
                self.movie_asset.ObjectFlags &= ~KEEP_ALIVE
            except Exception as exc:
                errors.append(exc)
            self.movie_asset = None
        return errors
