"""Read-only Unreal observers, installed only while a capture is active."""

from datetime import datetime, timezone
import gc
import json
import math
from pathlib import Path
from time import perf_counter_ns

import mods_base
import unrealsdk
from unrealsdk import logging
from unrealsdk.hooks import Type, add_hook, has_hook, remove_hook

from .capture import Capture, MAX_ROWS
from .environment import snapshot

POST_RENDER = "Engine.GameViewportClient:PostRender"
INPUT_CANDIDATES = ("WillowGame.WillowPlayerController.UpdateRotation", "Engine.PlayerController.UpdateRotation")


class Recorder:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.capture = None
        self.pending = None
        self.hooks = []
        self.unavailable = {}
        self.disabled_reads = set()
        self.last_path = None
        self.world_address = None
        self.controller_address = None

    def notify(self, message):
        logging.info("[Smooth FPS] " + message)
        try:
            pc = mods_base.get_pc()
            if pc is not None:
                pc.ClientMessage("Smooth FPS: " + message)
        except Exception:
            pass  # Console logging is the fallback if the HUD message is unavailable.

    def number(self, root, path, label):
        if label in self.disabled_reads:
            return None
        try:
            obj = root
            for part in path.split("."):
                if obj is None:
                    return None  # Transiently absent camera/input is not a missing field.
                obj = getattr(obj, part)
            value = float(obj)
            return value if math.isfinite(value) else None
        except Exception as exc:
            self.unavailable[label] = f"{type(exc).__name__}: {exc}"
            self.disabled_reads.add(label)  # Avoid repeated reflection exceptions at 240 Hz.
            return None

    def install(self, path, kind, callback):
        identifier = "SmoothFPS." + ("render" if path == POST_RENDER else "input")
        # Match mods_base.HookType.enable: replace only our own registration.
        # A falsy add result alone cannot establish whether a hook is present.
        remove_hook(path, kind, identifier)
        result = add_hook(path, kind, identifier, callback)
        self.hooks.append((path, kind, identifier))
        if not has_hook(path, kind, identifier):
            raise RuntimeError(f"Hook absent after registration: {path}; add_hook returned {result!r}")

    def detach(self):
        for path, kind, identifier in self.hooks:
            remove_hook(path, kind, identifier)
        self.hooks.clear()
        if self.gc_event in gc.callbacks:
            gc.callbacks.remove(self.gc_event)

    def toggle(self, mode):
        if self.capture is not None:
            return self.stop("F5/manual stop")
        if self.pending is not None:
            self.notify("Previous export failed. Retrying it before a new recording.")
            return self.save_pending()
        metadata = {"started_utc": datetime.now(timezone.utc).isoformat()}
        try:
            if mods_base.Game.get_current() != mods_base.Game.BL1E:
                self.notify("BL1 Enhanced only.")
                return
            pc = mods_base.get_pc()
            if pc is None or pc.Pawn is None:
                self.notify("Load a character, then press F5.")
                return
            metadata = snapshot(unrealsdk, mods_base, pc)
            self.unavailable = {}
            self.disabled_reads.clear()
            self.world_address = pc.WorldInfo._get_address()
            self.controller_address = pc._get_address()
            self.install(POST_RENDER, Type.POST_UNCONDITIONAL, self.frame)
            input_status = {"installed": False, "path": None, "attempts": []}
            if mode != "Timing only":
                for candidate in INPUT_CANDIDATES:
                    try:
                        function = unrealsdk.find_object("Function", candidate)
                        if function is None:
                            continue
                        path = function._path_name().replace(":", ".").rsplit(".", 1)
                        hook_path = ":".join(path)
                        self.install(hook_path, Type.PRE, self.rotation)
                        input_status.update(installed=True, path=hook_path)
                        break
                    except Exception as exc:
                        input_status["attempts"].append(f"{candidate}: {type(exc).__name__}: {exc}")
            metadata["input_hook"] = input_status
            metadata["post_render_hook"] = {"installed": True, "path": POST_RENDER}
            self.notify("Recording 30 seconds. Pan steadily. F5 stops early; F6 marks a stutter.")
            # Setup and notification are complete before the measurement clock starts.
            self.capture = Capture(perf_counter_ns(), metadata, mode)
            gc.callbacks.append(self.gc_event)
        except Exception as exc:
            self.capture = None
            self.detach()
            logging.error(f"[Smooth FPS] Cannot start capture: {type(exc).__name__}: {exc}")
            self.notify("Could not start. Saving a failure report; check SDK console/log.")
            failed = Capture(perf_counter_ns(), metadata, mode)
            failed.error("capture startup", exc)
            self.pending = failed.report("capture startup failed", perf_counter_ns())
            return self.save_pending()

    def frame(self, _obj, args, _ret, _func):
        capture = self.capture
        if capture is None:
            return
        start = perf_counter_ns()
        try:
            pc = mods_base.get_pc()
            if (pc is None or pc.WorldInfo is None or pc.Pawn is None or
                    pc.WorldInfo._get_address() != self.world_address or
                    pc._get_address() != self.controller_address):
                self.stop("world/controller changed or player pawn unavailable")
                return
            world = pc.WorldInfo
            dt = self.number(world, "DeltaSeconds", "world.DeltaSeconds")
            real = self.number(world, "RealTimeSeconds", "world.RealTimeSeconds")
            game = self.number(world, "TimeSeconds", "world.TimeSeconds")
            yaw = pitch = cam_yaw = cam_pitch = camera_stamp = None
            if capture.mode != "Timing only":
                rotation = getattr(pc, "Rotation", None)
                yaw = self.number(rotation, "Yaw", "controller.yaw")
                pitch = self.number(rotation, "Pitch", "controller.pitch")
                camera = getattr(pc, "PlayerCamera", None)
                cam_yaw = self.number(camera, "CameraCache.POV.Rotation.Yaw", "camera.yaw")
                cam_pitch = self.number(camera, "CameraCache.POV.Rotation.Pitch", "camera.pitch")
                camera_stamp = self.number(camera, "CameraCache.TimeStamp", "camera.timestamp")
            paused = getattr(world, "Pauser", None) is not None
            row = [capture.elapsed_ms(start), None if dt is None else dt * 1000,
                   real, game, yaw, pitch, cam_yaw, cam_pitch, camera_stamp,
                   paused, True, 0.0]
            capture.frames.append(row)
            if "canvas_size" not in capture.metadata:
                canvas = getattr(args, "Canvas", None)
                capture.metadata["canvas_size"] = {
                    "width": self.number(canvas, "SizeX", "canvas.width"),
                    "height": self.number(canvas, "SizeY", "canvas.height")}
            row[-1] = (perf_counter_ns() - start) / 1000
            if capture.elapsed_ms(start) >= 30000:
                self.stop("30-second limit")
            elif len(capture.frames) >= MAX_ROWS:
                self.stop("frame buffer limit")
        except Exception as exc:
            capture.error("PostRender", exc)
            self.stop("frame observer error")

    def rotation(self, pc, args, _ret, _func):
        capture = self.capture
        if capture is None:
            return
        start = perf_counter_ns()
        try:
            if pc._get_address() != self.controller_address:
                return
            if len(capture.inputs) >= MAX_ROWS:
                capture.event(start, "input_buffer_limit")
                self.stop("input buffer limit")
                return
            player_input = getattr(pc, "PlayerInput", None)
            dt = self.number(args, "DeltaTime", "rotation.DeltaTime")
            values = [self.number(player_input, field, "input." + field)
                      for field in ("aTurn", "aLookUp", "aMouseX", "aMouseY")]
            row = [capture.elapsed_ms(start), None if dt is None else dt * 1000, *values, 0.0]
            capture.inputs.append(row)
            row[-1] = (perf_counter_ns() - start) / 1000
        except Exception as exc:
            capture.error("UpdateRotation", exc)

    def gc_event(self, phase, info):
        capture = self.capture
        if capture is not None:
            capture.event(perf_counter_ns(), "python_gc_" + phase,
                          generation=info.get("generation"), collected=info.get("collected"))

    def mark(self):
        if self.capture is not None:
            # No HUD/log output during sampling; the marker itself stays lightweight.
            self.capture.event(perf_counter_ns(), "user_noticed_stutter")

    def stop(self, reason):
        capture = self.capture
        if capture is None:
            return
        end = perf_counter_ns()
        self.capture = None  # Stop observing before analysis, file I/O or notification.
        self.detach()
        capture.metadata["unavailable_fields"] = dict(self.unavailable)
        self.pending = capture.report(reason, end)
        return self.save_pending()

    def save_pending(self):
        if self.pending is None:
            return
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
            path = self.directory / f"smooth-fps-{stamp}.json"
            # Publish a complete file only. On failure the report remains in memory for F5 retry.
            temporary = path.with_suffix(".json.tmp")
            temporary.write_text(json.dumps(self.pending, separators=(",", ":"), allow_nan=False) + "\n", encoding="utf-8")
            temporary.replace(path)
            self.pending = None
            self.last_path = path
            self.notify(f"Saved {path}")
            return path
        except Exception as exc:
            logging.error(f"[Smooth FPS] Export failed: {type(exc).__name__}: {exc}")
            self.notify("Export failed; report retained in memory. Press F5 to retry. Check SDK log.")
