"""Synthetic timing and SDK contracts. These do not substitute for a BL1E run."""

import gc
import importlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace as NS
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "Source/sdk_mods/SmoothFPS"
package = ModuleType("smooth_fps_test")
package.__path__ = [str(SOURCE)]
sys.modules[package.__name__] = package
analysis = importlib.import_module(package.__name__ + ".capture")
environment = importlib.import_module(package.__name__ + ".environment")


def frame(t, yaw=0, camera=None, paused=False, pawn=True):
    return [t, 1000 / 240, t / 1000, t / 1000, yaw, 0,
            yaw if camera is None else camera, 0, t / 1000, paused, pawn, 10]


class AnalysisTests(unittest.TestCase):
    def test_stable_240hz_and_rotation_wrap(self):
        capture = analysis.Capture(0, {})
        capture.frames = [frame(i * 1000 / 240, (65000 + i * 100) % 65536) for i in range(1441)]
        report = capture.report("test", 6_000_000_000)
        self.assertAlmostEqual(report["summary"]["observed_callback_hz"], 240)
        self.assertEqual(report["summary"]["over_1_5x_median"], 0)
        self.assertAlmostEqual(report["motion"]["camera"]["yaw_step_degrees"]["max"], 100 * 360 / 65536)
        json.dumps(report, allow_nan=False)

    def test_short_long_alternation_is_visible_at_240_average(self):
        capture = analysis.Capture(0, {})
        t = 500
        for i in range(1441):
            capture.frames.append(frame(t))
            t += 2 if i % 2 == 0 else 1000 / 120 - 2
        summary = capture.report("test", int(t * 1e6))["summary"]
        self.assertAlmostEqual(summary["observed_callback_hz"], 240)
        self.assertGreater(summary["callback_interval_ms"]["stddev"], 2)
        self.assertLess(summary["one_percent_low_callback_hz"], 160)

    def test_warmup_pause_and_intervals_across_pause_excluded(self):
        capture = analysis.Capture(0, {})
        capture.frames = [frame(0), frame(499), frame(500), frame(504),
                          frame(1500, paused=True), frame(2500), frame(2504)]
        report = capture.report("test", 3_000_000_000)
        self.assertEqual(report["summary"]["analysed_intervals"], 2)
        self.assertEqual(report["summary"]["callback_interval_ms"]["max"], 4)
        self.assertEqual(len(report["frames"]["rows"]), 7)

    def test_hitch_kept_and_index_points_to_raw_row(self):
        capture = analysis.Capture(0, {})
        capture.frames = [frame(500), frame(504), frame(554), frame(558)]
        summary = capture.report("test", 600_000_000)["summary"]
        self.assertEqual(summary["over_2x_median"], 1)
        self.assertEqual(summary["worst_intervals"][0], {"frame_index": 2, "t_ms": 554, "dt_ms": 50})

    def test_camera_hold_while_controller_rotates(self):
        capture = analysis.Capture(0, {})
        capture.frames = [frame(500, 100, 100), frame(504, 200, 100), frame(508, 300, 300)]
        motion = capture.report("test", 600_000_000)["motion"]
        self.assertEqual(motion["camera_unchanged_while_controller_turns"], 1)

    def test_empty_capture_and_missing_camera_are_explicit(self):
        capture = analysis.Capture(0, {})
        report = capture.report("test", 0)
        self.assertIsNone(report["summary"]["callback_interval_ms"])
        self.assertTrue(any("No PostRender" in text for text in report["quality_warnings"]))
        json.dumps(report, allow_nan=False)

    def test_events_and_errors_bounded(self):
        capture = analysis.Capture(0, {})
        for i in range(500):
            capture.event(i, "marker")
            capture.error(str(i), ValueError("failure"))
        self.assertEqual(len(capture.events), 256)
        self.assertEqual(len(capture.errors), 32)


class IniTests(unittest.TestCase):
    def test_only_selected_settings_and_duplicate_values_retained(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "WillowEngine.ini"
            path.write_text("[Engine.GameEngine]\nbSmoothFrameRate=True\nPlayerName=private\n"
                            "[Engine.GameEngine]\nbSmoothFrameRate=False\nBindings=private\n")
            selected = environment.selected_ini(path)
            self.assertEqual(selected, {"Engine.GameEngine": {"bSmoothFrameRate": ["True", "False"]}})

    def test_utf16_config_supported(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "WillowInput.ini"
            path.write_text("[Engine.PlayerInput]\nbEnableMouseAcceleration=False\n", encoding="utf-16")
            self.assertEqual(environment.selected_ini(path)["Engine.PlayerInput"],
                             {"bEnableMouseAcceleration": ["False"]})


class Object(NS):
    def _get_address(self):
        return id(self)


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.messages, self.additions, self.removals = [], [], []
        self.clock = 0
        self.world = Object(DeltaSeconds=1 / 240, RealTimeSeconds=10, TimeSeconds=10, Pauser=None)
        self.pc = Object(Pawn=Object(), WorldInfo=self.world, Rotation=NS(Yaw=65500, Pitch=0),
                         PlayerCamera=NS(CameraCache=NS(POV=NS(Rotation=NS(Yaw=65500, Pitch=0)), TimeStamp=10)),
                         PlayerInput=NS(aTurn=1, aLookUp=0, aMouseX=0, aMouseY=0),
                         ClientMessage=self.messages.append)
        base = ModuleType("mods_base")
        base.get_pc = lambda: self.pc
        base.Game = NS(BL1E="BL1E", get_current=lambda: "BL1E")
        base.SETTINGS_DIR = Path(self.temp.name)
        base.SpinnerOption = lambda name, value, choices, **kw: NS(value=value, choices=choices)
        base.ButtonOption = lambda *a, **kw: NS(**kw)
        base.keybind = lambda *a, **kw: lambda fn: fn
        self.build = []
        base.build_mod = lambda **kw: self.build.append(kw)
        sdk = ModuleType("unrealsdk")
        sdk.logging = NS(info=self.messages.append, error=self.messages.append)
        sdk.find_object = lambda cls, path: NS(_path_name=lambda: path)
        hooks = ModuleType("unrealsdk.hooks")
        hooks.Type = NS(PRE="pre", POST_UNCONDITIONAL="post")
        self.registered = {}
        def add_hook(path, kind, identifier, callback):
            self.additions.append((path, kind, identifier, callback))
            key = (path, kind, identifier)
            if key in self.registered:
                return False
            self.registered[key] = callback
            return True
        def remove_hook(*key):
            self.removals.append(key)
            return self.registered.pop(key, None) is not None
        hooks.add_hook = add_hook
        hooks.remove_hook = remove_hook
        hooks.has_hook = lambda *key: key in self.registered
        self.base, self.sdk, self.hooks = base, sdk, hooks
        self.modules = patch.dict(sys.modules, {"mods_base": base, "unrealsdk": sdk, "unrealsdk.hooks": hooks})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        name = package.__name__ + ".runtime"
        sys.modules.pop(name, None)
        self.runtime = importlib.import_module(name)
        self.patches = [patch.object(self.runtime, "snapshot", return_value={}),
                        patch.object(self.runtime, "perf_counter_ns", side_effect=lambda: self.clock)]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)
        self.recorder = self.runtime.Recorder(Path(self.temp.name) / "reports")
        self.addCleanup(self.recorder.detach)

    def tick(self, milliseconds):
        self.clock = int(milliseconds * 1e6)
        self.recorder.frame(None, NS(Canvas=NS(SizeX=3840, SizeY=2160)), None, None)

    def report(self):
        return json.loads(self.recorder.last_path.read_text())

    def test_auto_stop_cleans_hooks_gc_and_exports_valid_json(self):
        self.recorder.toggle("Camera and timing")
        self.assertIn(self.recorder.gc_event, gc.callbacks)
        self.tick(500)
        self.recorder.rotation(self.pc, NS(DeltaTime=1 / 240), None, None)
        self.tick(504)
        self.tick(30001)
        self.assertIsNone(self.recorder.capture)
        self.assertEqual(len(self.removals), 4)  # Two replacements, then two detachments.
        self.assertEqual(self.registered, {})
        self.assertNotIn(self.recorder.gc_event, gc.callbacks)
        report = self.report()
        self.assertEqual(report["stop_reason"], "30-second limit")
        self.assertEqual(report["metadata"]["canvas_size"], {"width": 3840, "height": 2160})
        self.assertEqual(report["summary"]["input_callbacks"], 1)
        self.assertEqual(len(report["frames"]["columns"]), len(report["frames"]["rows"][0]))

    def test_colon_function_path_normalised_and_missing_override_falls_back(self):
        def find(cls, path):
            if "WillowGame" in path:
                raise ValueError("missing")
            return NS(_path_name=lambda: "Engine.PlayerController:UpdateRotation")
        self.sdk.find_object = find
        self.recorder.toggle("Camera and timing")
        self.assertEqual(self.additions[1][0], "Engine.PlayerController:UpdateRotation")

    def test_manual_stop_then_new_capture_has_fresh_buffer(self):
        self.recorder.toggle("Camera and timing")
        self.tick(1000)
        self.recorder.toggle("Camera and timing")
        self.assertEqual(self.report()["stop_reason"], "F5/manual stop")
        self.recorder.toggle("Camera and timing")
        self.assertEqual(self.recorder.capture.frames, [])

    def test_missing_optional_fields_do_not_stop_timing(self):
        self.pc.PlayerCamera = NS()
        del self.pc.PlayerInput.aMouseX
        self.recorder.toggle("Camera and timing")
        self.tick(500)
        self.recorder.rotation(self.pc, NS(DeltaTime=.004), None, None)
        self.tick(504)
        self.recorder.stop("test")
        report = self.report()
        self.assertEqual(len(report["frames"]["rows"]), 2)
        self.assertIn("camera.yaw", report["metadata"]["unavailable_fields"])
        self.assertIn("input.aMouseX", report["metadata"]["unavailable_fields"])
        self.assertIsNone(report["frames"]["rows"][0][6])

    def test_timing_only_never_installs_input_or_reads_rotation(self):
        del self.pc.Rotation
        del self.pc.PlayerCamera
        del self.pc.PlayerInput
        self.recorder.toggle("Timing only")
        self.tick(1000)
        self.recorder.stop("test")
        self.assertEqual(len(self.additions), 1)
        self.assertEqual(self.report()["errors"], [])

    def test_map_change_ends_capture_without_bridging_world_clocks(self):
        self.recorder.toggle("Camera and timing")
        self.tick(500)
        self.pc.WorldInfo = Object()
        self.tick(504)
        self.assertIsNone(self.recorder.capture)
        self.assertEqual(len(self.report()["frames"]["rows"]), 1)
        self.assertIn("world/controller changed", self.report()["stop_reason"])

    def test_hook_install_failure_rolls_back_and_keeps_game_usable(self):
        # No registration is made; direct presence verification must fail.
        with patch.object(self.runtime, "add_hook", return_value=False):
            self.recorder.toggle("Camera and timing")
        self.assertIsNone(self.recorder.capture)
        self.assertNotIn(self.recorder.gc_event, gc.callbacks)
        self.assertEqual(self.registered, {})
        report = self.report()
        self.assertEqual(report["stop_reason"], "capture startup failed")
        self.assertEqual(report["errors"][0]["context"], "capture startup")
        self.assertIn("add_hook returned False", report["errors"][0]["error"])

    def test_none_add_result_with_registered_hook_records_and_saves(self):
        def add_with_no_return(*args):
            self.hooks.add_hook(*args)
        with patch.object(self.runtime, "add_hook", side_effect=add_with_no_return):
            self.recorder.toggle("Camera and timing")
        self.assertIsNotNone(self.recorder.capture)
        self.tick(500)
        self.tick(504)
        self.recorder.stop("test")
        self.assertEqual(len(self.report()["frames"]["rows"]), 2)
        self.assertEqual(self.registered, {})

    def test_stale_own_hook_replaced_without_removing_other_mods(self):
        own_key = (self.runtime.POST_RENDER, "post", "SmoothFPS.render")
        other_key = (self.runtime.POST_RENDER, "post", "AnotherMod.render")
        old_callback = lambda *args: None
        self.registered.update({own_key: old_callback, other_key: old_callback})
        self.recorder.toggle("Timing only")
        self.assertEqual(self.registered[own_key], self.recorder.frame)
        self.recorder.stop("test")
        self.assertEqual(self.registered, {other_key: old_callback})

    def test_hook_registration_exception_still_exports_failure_json(self):
        with patch.object(self.runtime, "add_hook", side_effect=RuntimeError("SDK registration error")):
            self.recorder.toggle("Timing only")
        self.assertIsNone(self.recorder.capture)
        self.assertIn("SDK registration error", self.report()["errors"][0]["error"])

    def test_true_add_result_without_registered_hook_is_rejected(self):
        with patch.object(self.runtime, "add_hook", return_value=True):
            self.recorder.toggle("Timing only")
        self.assertIsNone(self.recorder.capture)
        self.assertEqual(self.report()["stop_reason"], "capture startup failed")

    def test_no_input_hook_still_saves_frame_data(self):
        self.sdk.find_object = lambda *a: None
        self.recorder.toggle("Camera and timing")
        self.tick(600)
        self.recorder.stop("test")
        self.assertFalse(self.report()["metadata"]["input_hook"]["installed"])

    def test_export_failure_retains_report_for_retry(self):
        self.recorder.toggle("Timing only")
        self.tick(500)
        with patch.object(Path, "write_text", side_effect=OSError("disk full")):
            self.recorder.stop("test")
        self.assertIsNotNone(self.recorder.pending)
        self.assertIsNone(self.recorder.capture)
        self.recorder.toggle("Timing only")
        self.assertIsNone(self.recorder.pending)
        self.assertEqual(self.report()["stop_reason"], "test")

    def test_enhanced_only_guard_and_load_character_requirement(self):
        self.base.Game.get_current = lambda: "BL1"
        self.recorder.toggle("Timing only")
        self.assertEqual(self.additions, [])
        self.base.Game.get_current = lambda: "BL1E"
        self.pc.Pawn = None
        self.recorder.toggle("Timing only")
        self.assertEqual(self.additions, [])

    def test_user_marker_and_python_gc_events_exported(self):
        self.recorder.toggle("Timing only")
        self.recorder.mark()
        self.recorder.gc_event("start", {"generation": 1})
        self.recorder.gc_event("stop", {"generation": 1, "collected": 5})
        self.recorder.stop("test")
        kinds = [event["event"] for event in self.report()["events"]]
        self.assertIn("user_noticed_stutter", kinds)
        self.assertIn("python_gc_start", kinds)
        self.assertIn("python_gc_stop", kinds)

    def test_real_snapshot_handles_missing_settings_and_reads_only_allowlisted_ini(self):
        self.base.ENGINE = NS(bSmoothFrameRate=False, MaxSmoothedFrameRate=240)
        self.base.get_ordered_mod_list = lambda: [NS(name="Example", version="1.0", is_enabled=True)]
        config = Path(self.temp.name) / "My Games/Borderlands Game of the Year/WillowGame/Config"
        config.mkdir(parents=True)
        (config / "WillowInput.ini").write_text(
            "[Engine.PlayerInput]\nbEnableMouseSmoothing=True\nAccountName=private\n")
        with patch.object(environment, "documents_dir", return_value=Path(self.temp.name)):
            result = environment.snapshot(self.sdk, self.base, self.pc)
        self.assertEqual(result["live_settings"]["engine"]["MaxSmoothedFrameRate"], 240)
        self.assertEqual(result["loaded_mods"][0]["name"], "Example")
        self.assertIn("bEnableMouseSmoothing", result["ini_settings"]["WillowInput.ini"]["Engine.PlayerInput"])
        self.assertNotIn("private", json.dumps(result))
        self.assertTrue(result["read_errors"])
        json.dumps(result, allow_nan=False)

    def test_row_limit_stops_instead_of_silently_overwriting(self):
        self.recorder.toggle("Timing only")
        with patch.object(self.runtime, "MAX_ROWS", 2):
            self.tick(500)
            self.tick(504)
        self.assertEqual(self.report()["stop_reason"], "frame buffer limit")

    def test_package_registration_exposes_bindings_and_enhanced_only(self):
        name = "smooth_fps_registration_test"
        spec = importlib.util.spec_from_file_location(name, SOURCE / "__init__.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        # Reuse the tested runtime module under the entrypoint's relative import.
        with patch.dict(sys.modules, {name + ".runtime": self.runtime}):
            spec.loader.exec_module(module)
        settings = self.build[0]
        self.assertEqual(settings["supported_games"], "BL1E")
        self.assertEqual(len(settings["keybinds"]), 2)
        self.assertEqual(settings["hooks"], [])


if __name__ == "__main__":
    unittest.main()
