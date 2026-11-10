# Changelog

## 2.0.1 — 2026-11-10

- Fix the live 2.0.0 regression that changed native level-40 card text to 41.
  Null-context native evaluation returned the pistol fallback, contrary to the
  previous test model. Read the verified zero-proficiency resolver expression
  directly instead, without invoking attribute evaluation.
- Record resolved bonuses, resolution methods and math operation enums in exports.
- Skip uninitialized weapons and inactive UI prototypes without errors.
- Add captured equipped/backpack failures and tests for unsupported expressions.
- 30 local checks pass. Subsequent Windows exports and user testing confirmed
  inventory/equipped levels and comparisons. Other card contexts remain unverified.
- Record that silent rejection of overlevel shield/weapon comparison swaps also
  occurs with this mod disabled after reload; no dialog workaround is included.

## 2.0.0 — 2026-11-10

- Replace level-query overrides and temporary definition edits with UI-only card
  text updates after native rendering.
- Attempt to resolve the context-free attribute bonus through native evaluation.
  Subsequent game logs showed that null context still used the definition fallback.
- Remove the level-69 clamp; preserve native equip checks and requirement states.
- Expand diagnostics with player/equipped identity, item names, native checks,
  resolver metadata, loaded mods and bounded before/after card records.
- Replace obsolete scope/capping tests with regression and UI-isolation checks.
- Windows rendering/native resolver execution still require in-game verification.

## 1.0.1

- Cap displayed levels at 69 to hide the Lady Finger level-70 card.

## 1.0.0

- Initial card-scoped required-level query overrides using definition fallbacks.
