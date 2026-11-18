# Changelog

## 0.1.1

- Verify hook presence directly instead of treating the add-hook return value as registration state.
- Replace stale Smooth FPS hook registrations before starting; leave other mods' hooks alone.
- Export a failure JSON when capture startup aborts.

## 0.1.0

- Enhanced-only diagnostics, F5 start/stop and automatic save after 30 seconds.
- F6 perceived-stutter markers; CPU cadence, camera and optional processed-input capture.
- Raw JSON, timing/motion summaries, selected settings, mod list, observer costs and limits.
- Timing-only comparison mode; bounded capture and export retry.
- No performance/gameplay fixes or settings changes yet.
