# Mission Atlas

**0.1.9 · keogh · Borderlands GOTY Enhanced**

Show one faded diamond per other accepted mission on your current map. Your tracked
mission keeps its normal marker. Ready-to-turn-in missions use their hand-in
location; offers and paid missions are excluded. Hover an extra diamond with the
mouse or controller focus to show its mission name; labels are hidden otherwise.

## Install and test

1. **Close the game completely.** Replace `sdk_mods/MissionAtlas.sdkmod` with the
   archive from `dist/MissionAtlas.sdkmod`, then launch and enable Mission Atlas.
2. Load a character with multiple accepted missions on the same map. Track one
   whose objective is on that map, open the map, and wait briefly without touching
   the controls. Extra diamonds should appear automatically.
3. Pan, zoom, change the tracked mission, and try a ready-to-turn-in mission.
   Hover/focus an extra diamond: its mission name should appear only while hovered.
   Move away and check the label disappears; native icon tooltips should stay unchanged.
4. While on the map press **F9**, or use **Export Mission Atlas diagnostics** in
   Mods. Send the JSON from `sdk_mods/settings/MissionAtlas/diagnostics/`.

Options: **Show turn-in markers** and **Other mission opacity**. Runs separately
from One Playthrough; mission progress, rewards and save files are unchanged.

## What changed

0.1.9 removes temporary native/Flash tracing and automatic geometry/registry
sampling now that tooltips work. Manual F9/Mods export remains available, with
bounded counters, recent errors and an on-demand interaction snapshot. Export
saves one file immediately; it no longer arms a later capture. Normal native
hover queries, marker checks and cleanup remain unchanged.

0.1.8 registers extra diamonds through the actual Flash `AddLandmark` function
found in the supplied status-menu package. This binds mouse rollover/rollout and
adds each icon, heading and mission name to the parallel Flash arrays used by
controller crosshair hit-testing. Earlier versions copied visuals and added
Unreal metadata without this Flash registration.

Instances retain private Mission Atlas names; the native objective frame is
selected explicitly. Existing position calibration and opacity remain in use.
Label changes update the Flash registry, and removal cleans only owned entries
from all three arrays while preserving native/other-mod entry order. Failed
splices are rolled back using array-length readback. Controller queries preserve
active mouse hover labels. Diagnostics include actual Flash registry membership.

The copied native icon does not gain waypoint placement/removal or mission
selection actions. Original markers and native MapObjects entries keep their
values/order. Extra Unreal tooltip metadata remains owned and is cleaned up with
its clip. The user confirmed this registration fix works in game.



0.1.3 selects one location per mission instead of drawing every authored waypoint.
A mission-wide waypoint (number zero) takes priority. Otherwise, native objective
requirements and current amounts select the first unfinished numbered objective.
If counters are unavailable, use one stable numbered location as a fallback.
Mission keys stay stable as the selected objective changes.

Opening the map can precede its native icon creation. A focused post-ApplyFlash
hook and a bounded viewport retry now render as soon as those icons are ready,
without waiting for input. Positions remain cached once per second; pan/zoom
updates do not scan actor properties. Retry work stops after startup succeeds,
the menu closes, the mod is disabled, or five seconds elapse.

Rendering now uses the captured `MapObjects` objective clip, duplicates it into
unique Mission Atlas clips in the same map container, and sets their positions
and opacity. Native map icons calibrate world-to-map coordinates, preserving the
game's own pan/zoom/rotation. Original icons and native map-object entries remain unchanged. Owned tooltip
entries are appended to `MapObjects` and removed on cleanup. Extra clips have no
copied click handlers or mission-selection behaviour. Disabling removes only the mod's own clips.

## Prototype limits

**Marker layout, startup and performance were confirmed in-game through 0.1.4.**
The user also confirmed the Flash registration fix in 0.1.8 works in game. Native methods,
ASValue fields and enum values are checked against reflected signatures before
any UI calls. Unsupported interfaces stay native and appear in the export;
failed probes back off instead of repeating on every mouse movement.

Only loaded waypoint actors matching the accepted mission's waypoint definition
and current map qualify. Numbered-objective selection uses native counters;
unusual mission layouts may need refinement. Shared locations can overlap.
Tooltip hover/focus uses the native map behavior. Co-op is unverified. Compass/HUD markers are unchanged.

## Development

`python3 -m unittest discover -s tests` runs local models, including uploaded
BL1E map-data fixtures. These do not execute the Windows renderer.
`python3 package.py` builds the SDK mod and versioned ZIP.

Native class research references:
[MOW531's Mission Selector](https://github.com/MOW531/MOW531-BL1-SDK-Mods/tree/master/Mission%20Selector)
and [Extended Item Cards](https://github.com/MOW531/MOW531-BL1-SDK-Mods/tree/master/Experimental%20mods/Extended%20Item%20Cards).
No external mod implementation is bundled.
