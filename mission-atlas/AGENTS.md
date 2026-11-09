# Mission Atlas

Standalone BL1E mod. Change only this folder for Mission Atlas tasks.
Do not change One Playthrough, other mods, reference mods or game installation.

Never accept/complete/reset missions, change tracked missions, edit saves or call
mission/waypoint resolvers to obtain inactive positions. Only current-playthrough
accepted missions with confirmed current-map waypoints qualify. Preserve native
tracked markers and default gameplay/HUD. Keep native wrappers within synchronous
map scopes; restore owned colour changes on every exit and disable.

Native interfaces must be reflected, signature checked and isolated to map calls.
Never invoke a native twice on errors. Unsupported layouts stay native and appear
in manually exported diagnostics. Do not claim Windows rendering works based on
local models. Keep version, changelog and README synchronized and package locally;
never install into the game automatically. F9 must export actionable native
schemas, arguments, bounded counts, mission statuses and actual waypoint fields.

The base renderer creates private Flash clip copies. Native MapObjects entries
keep their values/order. 0.1.4 may append/update/remove owned tooltip-only rows
for verified `_mission_atlas_` clips, as authorized by the hover-label feature. Only `_mission_atlas_` clips may be positioned/faded/removed. Validate
native Flash signatures and ASValue enums, calibrate against native icon positions,
and verify creation before counting a clip. No per-pan actor reflection or repeated
schema discovery once ready. Cache only primitive coordinates between calls.
Use one post callback per map event and function-specific identifiers; a failed
registration must not abort other discovery. Never replay or block native panning.

0.1.3 shows at most one extra marker per mission. Prefer a generic zero waypoint;
otherwise use native objective requirements/current counts to choose an unfinished
numbered step. Do not assume every objective requires one item/kill. Keep mission
keys stable. Initial rendering must not depend on input: observe native ApplyFlash
and use bounded viewport readiness retries; cancel them on close/disable/success.

Tooltip registration must use reflected MapObjectData / UpdateMapTooltips metadata.
Only native hover/focus queries decide label visibility; do not draw permanent
labels or change selection/mission state. Preserve non-owned rows and restore the
previous array after a failed native copy. Keep primitive ownership for cleanup
retries. Exclude own tooltip rows from native coordinate/template calibration.
Optional tooltip failures must not stop rendering diamonds.

0.1.5 hover-enabled clips keep native rollover/focus/keyboard-focus behavior. Only
activation handlers (onPress/onRelease/onReleaseOutside) are removed, including
on native binding failure. Use the native localized objective title and mission
name in TooltipBody, matching actual native tooltip rows. Do not install permanent
global Flash query observers; diagnostic hooks must be scoped to manual export
and removed in finally. Preserve working marker layout, count and performance.

0.1.6 queries native hover on unchanged rows and stationary open maps at most ten
times per second. Idle queries must not rescan actors/missions, recalibrate or
create clips. Skip hidden/closed/unloaded maps, back off failures, and retain only
primitive live diagnostic measurements. Keep global Flash tracing manual-only.

0.1.7 diagnostic exports may arm one-shot native map capture (four ApplyFlash
calls, two-minute limit). Temporary Flash hooks exist only between that native
call's PRE and the existing POST callback, which must clean them before overlay
work. No native replay. Autosave the live report after scope cleanup; cancel on
travel/disable/timeout. Normal gameplay must not arm capture automatically.

0.1.8 uses the verified status-menu Flash AddLandmark function. Its frame token
also names the new clip: pass a private `_mission_atlas_` token, verify returned
path/depth, then gotoAndStop the native objective frame. Mouse handlers and the
three Flash tooltip arrays are part of the registration contract. Preserve native
array values/order and clean only owned entries, with rollback after partial
splices. CheckCrosshair must not run over an active native mouse tooltip. Cache
primitive template fields before any MapObjects replacement. Never bundle game
assets, decompiled game scripts or research tooling in releases.

0.1.9 supersedes the earlier temporary diagnostics requirements: remove native
map capture/query tracing and periodic geometry sampling. Retain manual F9/Mods
export and bounded counters/errors; perform interaction snapshots only on demand.
Manual export must not arm subsequent work or install temporary Flash hooks.
The user confirmed 0.1.8 tooltips work; preserve that native registration path.
