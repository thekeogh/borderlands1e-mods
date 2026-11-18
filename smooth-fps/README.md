# Smooth FPS Diagnostics — BL1 Enhanced only

Version 0.1.1. First-stage diagnostics for small stutters during camera pans, even when the FPS counter stays near 240. **This version records evidence; it does not apply a fix.**

## Install

1. Install the [BL1 Python SDK / Mod Manager](https://bl-sdk.github.io/willow1-mod-db/).
2. Copy `dist/SmoothFPS.sdkmod` into the game's `sdk_mods` folder. Keep the `.sdkmod` compressed. Remove any older unpacked `SmoothFPS` folder to avoid duplicates.
3. Restart the game. Enable **Smooth FPS Diagnostics** in Mods. BL1 Classic is explicitly unsupported.

No extra Python packages, native DLLs, or administrator access required beyond the SDK installation.

## First recording

1. Load a character. Find an area where you notice the problem. Keep your current graphics, sync and FPS settings for this first test.
2. Stand still, close menus, then press **F5**. Hold the right stick steadily to pan for **30 seconds**. Avoid moving the character, opening menus, travelling, or alt-tabbing.
3. Recording stops and saves automatically. **F5 again** stops and saves early. **F6** optionally marks when you notice a stutter; it doesn't show a message during capture.
4. Send the new `smooth-fps-*.json` from:

   ```text
   <game>\sdk_mods\settings\SmoothFPS\diagnostics\
   ```

The SDK console/log prints the complete output path. A HUD message is attempted too. Keybinds can be reassigned through the mod manager if F5/F6 conflict with another mod. The Mods option **Start/stop frame diagnostics** is a fallback, but close the menu promptly after starting.

If practical, send a second recording of a steady **mouse** pan in the same area. Include which file used which input, your current FPS limit and VSync/G-SYNC settings, and whether both felt uneven. Input type and driver settings are not automatically detected.

## What the JSON contains

- High-resolution CPU timestamps for consecutive `GameViewportClient.PostRender` callbacks, plus raw engine delta/game/real clocks.
- Controller and optional cached camera yaw/pitch. Rotation wrapping is handled in motion summaries.
- Optional processed look-input values immediately before `UpdateRotation`; hook availability and missing fields are explicit. An installed hook with zero callbacks is not assumed to work.
- Interval percentiles, jitter, long intervals, slowest-1% callback rate, and raw rows for deeper analysis. A high average rate can coexist with alternating short/long intervals.
- Optional F6 markers and Python garbage collection events. These do not measure Unreal's native garbage collector.
- Loaded mod names/versions/enabled state, SDK/Python versions, map name, canvas size, selected live settings and allowlisted INI settings.
- Observer callback costs, bounded errors, missing fields and measurement limitations.

Rows are compact arrays with a matching `columns` list. Timing uses `perf_counter_ns`, not the game's lower-precision world clock. The first 500 ms and intervals crossing paused/pawnless samples are excluded from summaries; all captured rows remain available. Long unpaused gaps remain included.

Selected INI settings are read from the Enhanced configuration folder under Windows' Documents location, including redirected Documents. Repeated values are retained. Missing files/properties are reported, not treated as known settings. No player saves, account names, keybindings, chat or full INI contents are deliberately collected. Error messages can contain local file paths.

## Limits and troubleshooting

This measures **CPU callback cadence**, not GPU presentation, G-SYNC operation, display scanout, GPU utilisation or controller hardware polling. A clean report cannot rule out problems later in the rendering/display pipeline. Cached camera state may differ from the final rendered view. The export can narrow the cause; it cannot guarantee a diagnosis.

There is no per-frame file I/O or object scanning. Observers are attached only during recording and removed before analysis/export. Recording itself adds overhead. If it changes how the game feels, choose **Capture detail → Timing only** and repeat; this omits camera/input observation. The report flags high measured observer cost, but cannot account for all SDK dispatch overhead.

Saving the JSON can cause a short pause **after** recording. This pause is outside the measured window. A failed export retains the report in memory; press F5 to retry before starting another capture. Do not quit the game before retrying.

Hook registration is verified with the SDK's `has_hook` API; stale registrations belonging to Smooth FPS are replaced before recording. If capture startup fails, the mod saves a JSON failure report containing the startup error and available metadata. Send that report even if it contains no frame samples.

Map/controller changes, loss of the player pawn, disabling the mod, or a buffer limit save a partial report. Each stream is capped at 24,000 rows; events at 256 and errors at 32. The 30-second auto-stop is checked on PostRender callbacks: if the game stops delivering callbacks during a pause/loading screen, it saves when a callback resumes, or when you press F5. A hard process crash cannot save the in-memory recording.

No changes to FPS caps, VSync, smoothing, time dilation, camera/input settings, saves, INIs or GPU drivers. No telemetry or network requests.

## Development

```sh
python3 -m unittest discover -s smooth-fps/tests -v
python3 smooth-fps/package.py
```

Tests cover synthetic 240 Hz pacing, alternating intervals, hitches, rotation wrap, optional fields, capture lifecycle, partial capture, limits and export retry. They do not establish compatibility with every live BL1E/SDK build. Windows/in-game validation is still required.

SDK interfaces follow upstream [keybinds](https://github.com/bl-sdk/mods_base/blob/master/keybinds.py), [hook API](https://github.com/bl-sdk/mods_base/blob/master/hook.py), and [settings directory](https://github.com/bl-sdk/mods_base/blob/master/settings.py), alongside existing BL1E mods in this repository.
