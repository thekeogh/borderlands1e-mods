# Releases

One Playthrough is the active mod in this directory. Keep playthrough-3/ (version
3) and reference/ unchanged. Record releases in CHANGELOG.md.
README.md is a concise player guide: installation, New Game, Continue and scope.
Always retain the full Easy / Normal / Hard spawn-percentage table in README.md
and keep it synchronized with the actual weights when changing difficulty.
Preserve vanilla regional/mission floors, native reward identities and money formulas.
Equipment rewards use the accepted mission level, not turn-in character level.
Scope inventory grade overrides to native reward calls and restore them afterward;
never clone saved item balance identities. Materialize inherited manufacturer
tables on the reward child temporarily, never edit shared parent tables. Convert
mission use requirement to internal level using the inventory definition's native
fallback bonus (not the player's proficiency); retain native equipped-card behavior.
Before native reward-item initialization, encode the accepted mission's internal
level in native non-interpolated ManufacturerGradeIndex high bits, preserving
low grade bits and original definition identities. Only encode mission balances in the
active reward scope. Explicitly recall the bound native function with replacement
input structs and block the original; SDK hook-argument mutation has no effect.
Preserve all inputs/returns; never retry after invocation. Discover signatures
from native metadata; skip unsupported output parameters and interpolated formats.
Loot level floor is a saved toggle, default on. Use the captured native
Engine.WillowInventory:InitializeInventory boundary for fresh world/container loot
(including skag piles) and vendor stock. Every equipment type uses the same
max(1, player - 2) floor: weapons, shields, grenade mods and class mods. Encode
before native stats are built, in both InGradeIndex and copied item definition data. Forward all
other arguments and the original native return value; never initialize twice.
Preserve higher native levels, rarity/legendary probabilities, pools, stage,
AwesomeLevel, parts and identities. Only the packed level may change.
Guard InitializeFromDefinitionData reconstruction with PRE/unconditional POST
scopes so save loads, pickup copies and player drops keep their levels. Never
apply the loot floor during mission rewards or to player-owned/live NPC gear;
do not reinitialize existing items. Player attribute-query context is not itself
ownership. Never call health methods on NPCs during native item construction;
require a confirmed death/loot scope for NPC query sources.
Leave unknown/interpolated/dynamic formats native and record skip reasons in F10.
Keep SDU progression upgrades and non-levelled consumables native.
Enemy difficulty is a saved Easy / Normal / Hard selector, default Normal.
Ordinary hostile roll weights (native / +1 / +2 / +3): Easy 70/20/9/1,
Normal 50/20/25/5, Hard 20/5/55/20. All preserve max(player, vanilla area)
as their base. Native ordinary levels floor at player level; keep the original
factory GameStage/grade bands when applying that floor. No extra +4 roll.
Retain naturally higher levels without stacking or capping them at +3.
Difficulty changes affect new spawns only; never rewrite existing pawn data.
Named enemies/bosses never use that roll. No fixed boss levels or completion
flags to enable scaling. Keep rare-level data private to those spawns.
Only log the loading/version line automatically. A manually requested diagnostic
export must log its request, saved path or failure; never swallow export errors.
Keep the legacy Playthrough3 settings path only for migration. Preserve historical
names in credits, changelog entries and captured-fixture provenance.

4.5.1's broad read-only trace hooks are no longer registered. Keep bounded native
initializer signatures/counters/samples in F10 until actual Windows generation,
copying and reload persistence have been checked. Local engine models are not
proof of native Windows behavior. Never claim unsupported loot paths are fixed.
