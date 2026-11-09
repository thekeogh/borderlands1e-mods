# Native tooltip contract, 0.1.8

Evidence: user-supplied `logs/menus_ingame_redux.upk`.
SHA-256: `419f573d53ee9014e02d3493fbf2071d35ce74503a60ea9aad35be65f64d1fab`.

The uncompressed UE3 package has status_menu as export 2 (serial offset 30647).
Its embedded GFX 9 stream starts at byte 30679, length 847045.
GFX SHA-256: `1c059d4999bd63eca1ae288e9be09945a18297bd36a81042e5ae0512d3a968a9`.
Decompiled locally with JPEXS 26.4.0; relevant root script is frame 11.
No package/assets/decompiled code/tools are part of the mod release.

Verified API:

- `AddLandmark(clip, x, y, rotation, frame, title, body)` duplicates the source
  using `frame + getNextHighestDepth()` as the new instance name, selects the
  frame, binds rollover/out/drag-out and appends the full path/title/body to
  `mapItems`, `tooltipTitles`, `tooltipBodies`. Returns the full path string.
- Its waypoint-only mouse-up action is restricted to the literal `waypoint`
  frame argument. A private token selects the safe non-waypoint handler branch;
  set the actual objective frame afterward using the owned clip's gotoAndStop.
- `ShowTooltipMouse` looks up the hovered clip in `mapItems` for its title/body.
- `CheckCrosshair` scans the same arrays using the native crosshair hit-test.
- `UpdateLandmark` calls CheckCrosshair only when `bMouseTooltipActive` is false.
- `UpdatePlayerWaypointTooltipText(clip, body)` updates the matching registered
  body. Despite the function name it matches any registered clip path.

Validation: extracted five relevant functions verbatim into an ignored local JS
sandbox with Flash object/hit-test stubs. The old bare-copy failure reproduces;
registration, mouse/controller enter/leave, label changes and cleanup pass. This
executes the asset's registration/lookup code, not Windows rendering/hit geometry.
Ignored local `verify_native_flash.js` holds the runnable sandbox.
