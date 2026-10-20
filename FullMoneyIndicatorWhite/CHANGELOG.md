# Changelog

## 3.0.1 — 2026-10-20

- Address missing money elements when the live HUD uses a compiled movie that
  predates the prepared RawData. Diagnostics showed both elements missing
  despite their definitions being present in the prepared source.
- Create a separate prepared HUD resource with a unique identity and bind it
  before native SetMovieInfo/Start. Do not reload an already running HUD.
- Include prepared/live resource identities and binding counts in manual F11
  diagnostics. Keep appearance at 105 / 7 / 100, Y offset and wallet behavior.
- Offline lifecycle/cache tests pass; Windows confirmation remains pending.
  Fully exit to Windows before installing.

## 3.0.0 — 2026-10-20

- Finalize appearance: dollar size 105%, spacing 7 scaled pixels, amount 100%.
- Remove the three temporary tuning sliders; retain saved Y offset. Previous
  tuning values no longer override the fixed appearance.
- Shorten the in-game description to describe the integrated native HUD look.
- Keep the black symbol border, loading-flash fix, wallet behavior and original
  credit in the README and license.

## 2.1.6 — 2026-10-20

- Restore the three saved tuning sliders, defaulting to dollar size 90%, spacing
  7 and amount size 100%. Retain Y offset and the solid black symbol border.
- Create both HUD elements with zero alpha in the native movie. Reveal only
  after setting their scale and position, preventing the unscaled symbol at
  the top left during loading before the first gameplay update.
- Make the amount size slider scale the native text itself. Keep combined
  centring and scaled spacing correct as text size changes.

## 2.1.5 — 2026-10-20

- Bake in the chosen appearance: dollar sign 90%, spacing 7 scaled pixels,
  amount 100%. Remove the three temporary tuning sliders; retain saved Y offset.
- Add a solid black vector stroke around the gold dollar contour for contrast.
  Expand shape bounds to include the stroke and keep the existing glyph layout.
- Keep native amount size, wallet behavior and polling unchanged.

## 2.1.4 — 2026-10-20

- Replace the text dollar sign with the inventory’s native gold vector symbol.
  Read its contour from the installed inventory movie; exclude decorative bars
  and apply the HUD’s black edge. No game artwork is bundled or changed on disk.
- Add three temporary saved sliders: dollar sign size (25–300%, default 100%),
  symbol spacing (0–40 scaled pixels, default 6), and amount size (50–200%,
  default 100%). Changes apply live; centre the icon and amount as one group.
- Keep the existing Y offset, native white lettering, wallet behavior, update
  interval and overflow protection. Both elements follow HUD visibility and
  hide on disable. F11 also captures icon state and tuning values.
- Verify extraction, native movie structure and layout offline. Windows visual
  testing remains required. Fully restart after installing the update.

## 2.1.3 — 2026-10-20

- Live 2.1.2 diagnostics confirm the HUD is on frame 10, but the money field
  placed in that frame does not exist. Restore first-frame placement.
- Import the native LV font before creating the money field, using a separate
  resource ID. Preserve all existing HUD tags and their order.
- Set embedded-font rendering and explicit WillowHead HTML formatting, matching
  the live native level label. Wallet handling and Y offset are unchanged.
- Windows visual verification remains pending. Fully restart after updating.

## 2.1.2 — 2026-10-20

- Diagnostic build: F11 now captures the live money field, native LV field,
  timeline frame, visibility, position, text and last rendering error.
- No further rendering changes; investigate the missing display reported with
  2.1.1 using live HUD state. All added reads are manual, never per frame.

## 2.1.1 — 2026-10-20

- Fix native money-field creation order: wait until the LV font has been
  imported before defining and placing the new text field. Enhanced imports
  that font in frame 10; the previous build created the field in frame 1.
- Keep appearance, placement, Y offset and money handling unchanged.
- Add a regression test for delayed HUD font imports. In-game confirmation
  of the missing-glyph fix remains pending. Fully restart after updating.

## 2.1.0 — 2026-10-20

- Replace the enlarged Canvas bitmap font with native HUD/Scaleform text.
- The user’s BL1E export identifies the solo LV label as `$WillowHead`, size 12
  in the HUD’s 1280×720 design space, white with a zero-distance black edge
  filter (blur 2, strength 7, alpha 178). Reuse those native settings directly.
- Generate one independent text field from the installed HUD movie at runtime.
  Retain every original HUD tag byte-for-byte; add only a text definition and
  placement. Do not change the existing level label or distribute game assets.
- Prepare the field before HUD startup. A full game restart is required after
  updating. Hide the field and restore owned movie-data changes on disabling.
- Keep horizontal centering, scaled Y offset, separate settings, wallet reader,
  formatting, 0.25-second polling and overflow protection. Native HUD visibility
  is respected. Remove all Canvas text/outline drawing.
- Keep manual F11 diagnostics; no background diagnostic scans. Drawing failures
  are reported once per distinct consecutive error, rather than every frame.
- Validation: 11 synthetic parser/lifecycle tests, integration checks, and an
  independent JPEXS parse of the patched real exported HUD. The exported HUD
  needs only 114 extra bytes; all original tags compare identically. Windows
  rendering and 4K visual confirmation remain pending.

## 2.0.1 — 2026-10-20

- Add a manual F11/button export of native HUD object fields, font assets and
  available GFx method signatures, plus readable loaded HUD/font Flash assets
  where exposed. Save a bounded diagnostic ZIP without modifying native objects.
- Keep the current drawing and wallet code unchanged. This is an investigation
  build, not a claim that the native LV typeface or 4K sharpness is fixed.
- No diagnostic scans or exports run automatically during rendering.

## 2.0.0 — 2026-10-20

- Fork Full Money Indicator 1.0.1 by eeriegoesd as Full Money Indicator White.
- Larger white Willow-body lettering with a black outline.
- Add a saved Y offset slider: −200 to +200, default 0; positive down, negative up.
- Keep original bottom spacing, horizontal centering, wallet reader, formatting,
  0.25-second polling and overflow protection.
- Separate settings and SDK module identity from the original mod.
- Native LV font-size/outline matching still needs a Windows visual check.
