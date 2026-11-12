# Changelog

## 0.1.1 — 2026-11-12

- Remove background transaction/wallet audit records and audit-only POST hooks.
  Keep the existing price refreshes, activation failure reporting and manual
  diagnostic export. Money formulas and transaction behavior unchanged.
- Validation: 34 local tests pass.

## 0.1.0 — 2026-11-10

- First standalone Economy Buster release; author keogh; GOTY Enhanced only.
- Apply six level-1 money inputs independently of character level/playthrough.
- Cover equipment cash values, cash pickup effects, mission cash rewards,
  respec formulas and the death-fee ceiling. Shared equipment pricing also
  covers ammo SDUs and Moxxi bank upgrades.
- Refresh existing cash caches on enable/load/level change and at vendor
  display/transaction boundaries. Refresh currency slots only on cash items.
- Preserve native transactions, gear/mission levels, XP, combat, rarity, loot,
  vendor markups, fixed consumable prices and existing wallet balances.
- Preserve One Playthrough's native reward/loot hooks; no PT3 dependency/assets.
- Restore captured inputs on disable; retain later external formula edits.
  Validate all six definitions before patching, roll back failed writes, and
  retain original static references if restoration needs a retry.
- Add **Export diagnostics** to the mod menu, with no keybind. Export formula
  state, bounded inventory/vendor data, currency slots, recent queries/wallet
  deltas, loaded mods, hook registration, errors and truncation notices.
- Validation: 34 local checks against captured BL1E definitions and modeled SDK
  callbacks, including native transaction forwarding, restoration/recovery,
  shared reward-level scopes, export safety and the absence of keybinds.
- Native Windows gameplay and co-op remain unverified.
