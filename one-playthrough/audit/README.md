# Capture audit — 23 October 2026

One Playthrough **4.5.10** uses two Borderlens captures as evidence. Their hashes,
reviewed reward chains, regional rows and audit limits are in
[2026-10-23.json](2026-10-23.json). Focused raw regression fields are preserved in
`tests/fixtures/bl1e_catalog_audit.json`; no extractor is required to run the tests.

Reviewed: **218 missions**, **74 distinct reward balances** (68 equipment, four
native progression SDUs, two non-levelled rewards), **59 PT1 regional rows**,
and **113 enemy level definitions**. Every captured reward chain resolved to an
inventory definition and manufacturer table. Captured ordinary enemy formula
shapes are supported by the existing exact/plus/minus/constant evaluator.

## Changes

- **Humanoid allegiance:** actual game paths use `gd_allegiance.HumanoidEnemy`.
  The old explicit match used `HumanEnemy`; its `_Enemies` balance-path fallback
  covered most bandits but missed the captured enemy Scorpio turret under
  `gd_Balance_SkillActors`. Recognition now works without depending on that path.
  Player/neutral/friendly exclusions and the older spelling remain supported.
- **Moe's mission-specific factory:** captured `PD_AlphaSkag_Named1` references
  `Z0_MissionData.BalanceDefs.BAIP_Alpha_Named1_E3`, with later grades explicitly
  named Moe. It now uses the named policy rather than an ordinary difficulty roll.
- **Named grade selection:** a floor correction previously reduced factory stage
  to player level. It now keeps the incoming/player regional maximum and changes
  only the private level inputs. At native stage 30, Moe's 29–35 grade remains
  eligible at level 32 rather than selecting an earlier low-stage variant.
- **Grade-less defaults:** modeled boundary regression found that a higher native
  default could be lost on a rare roll when no grade existed to carry an absolute
  override. The private definition now retains that higher default. This boundary
  case was found by code review; no live non-default occurrence is claimed.
- **Safe deferred death loot:** replace the health-method fallback with captured
  `bIsDead`/`bPlayedDeath` BoolProperties plus existing synchronous death scopes.
  Uninitialized/live and deleted/pending-delete actors do not qualify. This closes
  an unsafe actor-method path without touching player inventory or rerolling loot.
- **Resolved probes:** remove temporary Bone Head/Bone Shredder automatic traces
  now that carried-drop generation and retirement have been verified in game.
  General F10 diagnostics and native initializer counters remain available.
- **Native mission queries:** restore the original MinimumLevel alongside the
  original GameStage/ExpLevel while asking native code for the floor. Restore the
  live values afterward, including failures. No accepted level is rewritten.

Difficulty percentages, regional floors, rarities, native reward identities,
pricing, grenades and save/quest progress are unchanged. The equipment floor
remains player minus two; mission equipment remains tied to acceptance level.

## Limits and useful in-game checks

These are definition audits and local native-call models, **not Windows gameplay
verification**. Only loaded data and reviewed roots were captured. Remaining map
scripts, dynamic/native paths and DLC-only behavior cannot be declared covered.
The dynamic DLC2 regional resolver stays native. No speculative spawn hooks were
added for a factory seen only as a default object.

Continue your existing save. Watch named/mission-specific enemies, custom
humanoids and enemy turrets when encountered; verify ordinary equipment rewards
and drops still behave normally. If something looks wrong, use F10 before picking
up the affected item where possible. No new save or full playthrough is needed.
