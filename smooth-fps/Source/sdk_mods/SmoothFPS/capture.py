"""SDK-independent, bounded capture and analysis. All rows contain primitives."""

import math
from statistics import mean, median, pstdev

FRAME_COLUMNS = (
    "t_ms", "world_delta_ms", "world_real_s", "world_game_s",
    "controller_yaw_units", "controller_pitch_units",
    "camera_yaw_units", "camera_pitch_units", "camera_timestamp_s",
    "paused", "has_pawn", "observer_us",
)
INPUT_COLUMNS = ("t_ms", "delta_ms", "turn", "look_up", "mouse_x", "mouse_y", "observer_us")
MAX_ROWS = 24000
WARMUP_MS = 500.0


def percentile(ordered, fraction):
    if not ordered:
        return None
    index = (len(ordered) - 1) * fraction
    lo = math.floor(index)
    hi = math.ceil(index)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (index - lo)


def distribution(values):
    ordered = sorted(v for v in values if v is not None and math.isfinite(v))
    if not ordered:
        return None
    return {"count": len(ordered), "min": ordered[0], "mean": mean(ordered),
            "p50": median(ordered), "p95": percentile(ordered, .95),
            "p99": percentile(ordered, .99), "max": ordered[-1],
            "stddev": pstdev(ordered)}


def angle_delta(previous, current):
    """UE3 rotator units: 65536 per revolution; handle signed/unsigned wrap."""
    if previous is None or current is None:
        return None
    return ((current - previous + 32768) % 65536 - 32768) * 360.0 / 65536.0


class Capture:
    def __init__(self, start_ns, metadata, mode="Camera and timing"):
        self.start_ns = start_ns
        self.metadata = metadata
        self.mode = mode
        self.frames = []
        self.inputs = []
        self.events = []
        self.errors = []

    def elapsed_ms(self, now_ns):
        return (now_ns - self.start_ns) / 1_000_000.0

    def error(self, context, exc):
        entry = {"context": context, "error": f"{type(exc).__name__}: {exc}"}
        if entry not in self.errors and len(self.errors) < 32:
            self.errors.append(entry)

    def event(self, now_ns, kind, **details):
        if len(self.events) < 256:
            self.events.append({"t_ms": self.elapsed_ms(now_ns), "event": kind, **details})

    def report(self, reason, now_ns):
        # Exclude setup/notification warmup and intervals crossing paused frames.
        intervals = []
        pairs = []
        for i in range(1, len(self.frames)):
            previous, current = self.frames[i - 1], self.frames[i]
            dt = current[0] - previous[0]
            if (previous[0] >= WARMUP_MS and dt > 0 and
                    not previous[9] and not current[9] and previous[10] and current[10]):
                intervals.append((i, dt))
                pairs.append((previous, current, dt))
        times = [dt for _, dt in intervals]
        cadence = distribution(times)
        summary = {"raw_frames": len(self.frames), "input_callbacks": len(self.inputs),
                   "analysed_intervals": len(times), "analysed_seconds": sum(times) / 1000,
                   "excluded_intervals": max(0, len(self.frames) - 1 - len(times)),
                   "warmup_ms": WARMUP_MS, "callback_interval_ms": cadence,
                   "frame_observer_us": distribution(row[11] for row in self.frames),
                   "input_observer_us": distribution(row[6] for row in self.inputs),
                   "world_delta_ms": distribution(current[1] for _, current, _ in pairs)}
        if times:
            typical = median(times)
            slowest = sorted(times, reverse=True)[:max(1, math.ceil(len(times) * .01))]
            summary.update(
                observed_callback_hz=1000.0 / mean(times),
                one_percent_low_callback_hz=1000.0 / mean(slowest),
                over_1_5x_median=sum(dt > typical * 1.5 for dt in times),
                over_2x_median=sum(dt > typical * 2 for dt in times),
                over_8_33ms=sum(dt > 1000 / 120 for dt in times),
                over_16_67ms=sum(dt > 1000 / 60 for dt in times),
                worst_intervals=[{"frame_index": i, "t_ms": self.frames[i][0], "dt_ms": dt}
                                 for i, dt in sorted(intervals, key=lambda item: item[1], reverse=True)[:32]],
            )
        motion = {}
        for label, column in (("controller", 4), ("camera", 6)):
            deltas = [(angle_delta(a[column], b[column]), dt) for a, b, dt in pairs]
            valid = [(d, dt) for d, dt in deltas if d is not None]
            motion[label] = {
                "valid_yaw_intervals": len(valid),
                "yaw_step_degrees": distribution(abs(d) for d, _ in valid),
                "absolute_yaw_speed_deg_s": distribution(abs(d) * 1000 / dt for d, dt in valid),
                "unchanged_yaw_intervals": sum(d == 0 for d, _ in valid),
            }
        comparable = [(angle_delta(a[4], b[4]), angle_delta(a[6], b[6])) for a, b, _ in pairs]
        motion["camera_unchanged_while_controller_turns"] = sum(
            controller is not None and camera == 0 and abs(controller) > .02
            for controller, camera in comparable)
        warnings = []
        if not self.frames:
            warnings.append("No PostRender samples. Check hook status and load a character.")
        if summary["analysed_seconds"] < 5:
            warnings.append("Less than five seconds of usable samples; repeat a longer capture.")
        if not self.inputs and self.mode != "Timing only":
            warnings.append("No UpdateRotation input samples; see input hook status. Timing remains usable.")
        if self.mode != "Timing only" and not motion["camera"]["valid_yaw_intervals"]:
            warnings.append("No usable cached camera rotation; controller rotation may still be available.")
        if cadence and summary["frame_observer_us"]:
            if summary["frame_observer_us"]["p95"] / 1000 > cadence["p50"] * .05:
                warnings.append("Frame observer p95 exceeds 5% of median interval; compare Timing only mode.")
        return {
            "schema_version": 1, "mod_version": "0.1.1", "game": "BL1E",
            "stop_reason": reason, "duration_ms": self.elapsed_ms(now_ns), "mode": self.mode,
            "metadata": self.metadata, "summary": summary, "motion": motion,
            "quality_warnings": warnings, "errors": list(self.errors), "events": list(self.events),
            "frames": {"columns": FRAME_COLUMNS, "rows": self.frames},
            "rotation_inputs": {"columns": INPUT_COLUMNS, "rows": self.inputs},
            "measurement_limits": [
                "PostRender callback spacing is CPU-side cadence, not GPU Present or display scanout timing.",
                "No measurement of G-SYNC, driver VSync, GPU utilisation, actual refresh rate or input polling rate.",
                "CameraCache is an optional cached camera state, not proof of the final rendered view.",
                "UpdateRotation inputs are processed engine values, not raw controller device samples.",
                "World clocks may lose float precision in long sessions; perf_counter_ns is the timing reference.",
                "Python observer costs omit SDK hook dispatch and some callback bookkeeping.",
                "Capture setup and JSON writing occur outside the analysed window. Warmup rows remain in raw data.",
                "Python GC events describe Python only; native Unreal GC is not measured.",
                "Motion summaries depend on the test movement; no automatic root-cause diagnosis is made.",
            ],
        }
