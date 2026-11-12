# Mission Atlas changelog

## 0.1.10 — 2026-11-12

- Remove leftover automatic map-call argument/return sampling. Keep manual
  F9/menu diagnostics and lightweight counters/errors. Marker rendering, native
  tooltip registration and map event behavior unchanged.
- Validation: 96 local tests pass.

## 0.1.9 — 2026-11-06

- User confirmed the 0.1.8 tooltip registration works in game.
- Remove one-shot native map capture, temporary Flash query tracing and automatic
  background geometry/registry sampling. Remove obsolete tracing implementation
  and its feature-specific tests.
- Keep manual F9/Mods diagnostic export, bounded counters/recent errors, reflected
  signatures and on-demand interaction/registry inspection. Export saves one
  immediate report without arming subsequent work or installing Flash observers.
- Preserve the working native registration, mouse/controller hover, throttled
  queries, marker creation/positioning and owned cleanup.
- Validation: 96 local tests pass, including regression checks that ordinary
  updates do not sample diagnostics and manual export installs no Flash tracer.
  The extracted native Flash sandbox still passes. Archives verified locally.

## 0.1.8 — 2026-11-06

- Identify the missing registration from the supplied menus_ingame_redux asset:
  native Flash AddLandmark installs rollover handlers and appends mapItems,
  tooltipTitles and tooltipBodies. Native controller CheckCrosshair and mouse
  ShowTooltipMouse use those arrays, not the appended Unreal rows alone.
- Create private clips through AddLandmark; use a private frame token to guarantee
  owned instance names, then explicitly select the native objective frame. Verify
  the returned path/depth and retain existing calibration/opacity/selection.
- Update registered label bodies through the native Flash helper. Query native
  controller hit-testing only while a mouse tooltip is inactive.
- Clean only owned entries from the three Flash arrays. Preserve native/external
  values and relative order; roll back partial splices, including errors after
  native side effects. Cache primitive template fields before resetting arrays.
- Include Flash registry membership in live/exported interaction diagnostics.
- Validation: 111 Python tests pass. Execute five extracted native Flash functions
  in a JS sandbox: reproduce the old unregistered-copy failure, then verify native
  registration, mouse enter/leave, controller enter/leave, label edit and cleanup.
  This validates the asset contract; Windows rendering still needs testing.
- Game assets, decompiled scripts and research tools are not bundled in releases.

## 0.1.7 — 2026-11-06

- Diagnostic release: the uploaded 0.1.6 report has six enabled, visible clips and
  235 native queries without tooltips. Previous enable/refresh hypotheses did not
  solve the issue. No claim of a native tooltip fix in this release.
- Export now arms a one-shot capture of the next four actual native ApplyFlash
  calls. Reopening/panning the map automatically saves a native-map JSON while
  Flash is live, avoiding the unloaded map seen after opening Mods.
- Include reflected ActionScript bridges/overrides, native function flags, bounded
  arguments/returns and native icon row identities. Temporary global Flash hooks
  are confined to the manually requested native call scope and removed before
  overlay work. Do not replay native map drawing or panning.
- Reuse the existing single ApplyFlash POST observer for cleanup. Cancel on travel,
  disable or two-minute timeout; autosave only after all temporary hooks close.
- Preserve marker rendering, placement, selection and gameplay state.
- Validation: 101 local tests pass, including capture scope/ownership, partial
  registration failure, nested calls, callback cleanup ordering, bounds, native
  bridges, timeout/disable and automatic report saving. Native tooltip binding
  remains under investigation.

## 0.1.6 — 2026-11-06

- Fix unchanged metadata skipping native hover queries. Refresh the native lookup
  during throttled map updates and while the open map stays stationary. Idle work
  queries existing rows only: no mission scans, actor reflection or clip creation.
- Skip closed/hidden maps and unloaded clips; back off native query failures.
  Preserve the confirmed diamond layout, counts, opacity and activation suppression.
- Use a reflected boolean enabled setter where available. Cache primitive Flash
  getter descriptions rather than reflecting per hover update.
- Retain last live geometry for exports taken after opening Mods. Explicit manual
  query tracing no longer suppresses nested Flash hooks during the measured call;
  temporary observers are still removed in finally.
- Validation: 88 local tests pass, including stationary mouse/controller focus,
  viewport-only hover, ten-Hz throttling, unchanged-row reuse, closed/hidden map
  guards, unloaded clips, query backoff, typed setters and retained live geometry.
  Native in-game tooltip behavior remains unverified.

## 0.1.5 — 2026-11-06

- Address two differences between the registered extra tooltips and native icons:
  disabled clip interaction and empty tooltip bodies. Enable native rollover/focus
  behavior and match the localized objective heading plus mission-name body.
- Preserve native rollover, focus and keyboard-focus handlers; explicitly clear
  only click activation handlers before/after binding, including failure cleanup.
- Retain the confirmed marker layout, mission count, startup and caching behavior.
  No permanent labels, custom hover geometry or mission-selection actions.
- Add manual-export-only tracing of native tooltip queries plus own-clip geometry
  and optional enabled-state reads. Remove temporary hooks even on query failures;
  keep global Flash observers off during normal map/gameplay.
- Validation: 79 local tests pass, including the uploaded six-empty-body regression,
  hover-enabled targets, native title/body formatting, localized headings, focus
  handler preservation, click suppression, trace bounds and cleanup on failures.
  Mouse/controller behavior still needs native in-game confirmation.

## 0.1.4 — 2026-11-06

- Add hover/focus mission-name tooltip metadata for verified extra diamonds using
  captured MapObjectData and native UpdateMapTooltips(Movie). Mouse/controller
  focus share the game's lookup; no permanent labels or click-to-track handlers.
- Append only owned tooltip rows, preserving native rows and other mods' entries.
  Use actual world XYZ and native normalized map coordinates. Keep native tooltip
  fields intact; show the mission name as the extra tooltip's single title.
- Update/remove owned rows as objectives/missions change, on native map rebuild,
  and on disable/reset. Roll back partial UI-array copy failures; retain primitive
  ownership for cleanup retries. Exclude owned rows from calibration/templates.
- Stage owned struct copies before replacing native array storage, preserving
  original UObject references and a safe rollback snapshot.
- Isolate optional tooltip failures and back off retries without stopping diamonds.
  Export registered tooltip rows and errors separately. Guard reset reentry.
- Validation: 69 local tests pass, including hover-only mouse/controller lookup
  models, native tooltip preservation, coordinate registration, mission removal,
  external rows, native rebuilds, rollback/recovery and cleanup. Native in-game
  hover/focus behavior still requires testing.

## 0.1.3 — 2026-11-06

- Fix the captured overcount: 15 extra actors belonged to six untracked missions.
  Group by mission and choose one mission-wide marker or the first unfinished
  numbered objective using native required/current counts. Unknown counters use
  one deterministic fallback; known unloaded current objectives do not reveal
  future numbered steps. Keep marker keys stable as objectives advance.
- Fix input-dependent startup: SetupMapPage runs before native objective clips
  exist. Observe the captured ApplyFlash(Movie) completion and retry through the
  existing viewport hook, without requiring any pan or input call. Retry at most
  ten times per second for up to five seconds; cancel on success/close/disable.
- Retain primitive location caching and render throttling. Guard reentrant map
  notifications. Treat the temporary missing template as deferred readiness;
  preserve backoff timestamps when native setup resets renderer state.
- Export chosen mission/actor/number/reason and native objective requirements.
- Validation: 49 local tests pass, including the uploaded 15-to-6 regression,
  partial-count objectives, step advancement, duplicates, automatic delayed
  startup without input, bounded retry work and actual captured BL1E Flash APIs.
  0.1.2 diamonds were confirmed in-game; new selection/startup need retesting.

## 0.1.2 — 2026-11-06

- Fix the new captured failure: duplicate PanMap observation registration aborted
  discovery before reaching WillowGFxHelperMap. Use function-specific identifiers,
  clean owned legacy hooks and isolate registration failures. Use one post hook
  per map event; never replay or block native panning.
- Remove per-pan actor reflection and speculative marker getter/writer hooks.
  Cache primitive waypoint positions for one second and invalidate on mission
  changes. Stop periodic schema discovery once the map interfaces are ready.
- Render dedicated Flash copies of the captured MapObjects objective icon using
  checked Invoke/GetVariableNumber/SetVariableNumber signatures (including compatible
  reflected aliases). Resolve ASValue enum values from metadata, never guessed IDs.
- Calibrate coordinates from native icons with explicit world locations. Validate
  alignment, allocate depths through the map container, verify created clip depth
  and alpha, deduplicate clips, and update only changed positions/opacity.
  Native icons and MapObjects stay unchanged; extra clips are noninteractive.
- Clean owned clips on mission removal, disable and map changes. Rebuild verified
  clips after native container replacement. Throttle redraw work and back off
  failed interface probes. Export renderer plans, errors and primitive caches.
- Validation: 32 local tests pass, including captured Trash map coordinates,
  duplicate registration isolation, cache/throttle counters, pan/zoom alignment,
  clip ownership, cleanup and failed creation. Windows rendering remains unverified.

## 0.1.1 — 2026-11-06

- Fix the confirmed 0.1.0 hook-path bug: use UFunction declaring class and name,
  preserving BL1E's `Package.Class:Function` form. The first report had zero map
  scopes, zero marker adapters, and no observed calls despite accepted local missions.
- Register the actual captured SetupMapPage, extUpdateMapPage and MapUpdateBehavior
  entry points. Accept world-owned mission trackers in the current world.
- Discover the confirmed WillowGFxHelperMap class. Reuse tracked-marker templates
  only through compatible UI-only writers with reflected world-vector/waypoint inputs;
  skip caller-owned IDs and unsupported output parameters. Retain native results,
  deduplicate extras per build, and never retry native creation after an exception.
- Add an F9 fallback on the map's native input handler. Expand manual reports with
  raw function paths, helper schemas/values, nested structs, tracker ownership and
  player replication waypoint data. Native helper rendering still needs testing.
- Validation: 37 local tests pass, including a regression fixture from the uploaded
  report, real-format hook names, world-owned trackers, captured current-map missions,
  marker forwarding/fading and failure handling. No Windows rendering claim.

## 0.1.0 — 2026-11-06

- First standalone BL1E map-marker prototype. Select accepted, untracked missions
  from the current playthrough and exact current map, including optional turn-ins.
- Match loaded waypoint actors through reflected WaypointDefinition references.
  Supply extra markers through compatible native getters/predicates during map UI
  calls only; preserve original getter invocation and return on failures.
- Temporarily fade extra marker colours where native colour interfaces exist.
  Restore owned properties after nested calls, failures or disabling.
- Add bounded native interface/call diagnostics, exported manually with F9 or
  the Mods option. Native Windows map rendering is not yet verified; unsupported
  interfaces remain unchanged and need an in-game report for the next iteration.
- Validation: 25 local model tests pass, including mission/map filtering, shared
  tracked locations, native-call forwarding, failure cleanup and SDK registration.
