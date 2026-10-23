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
mission use requirement to internal level using the shared requirements module.
For captured context-free proficiency bonus attributes, call the native static
AttributeInitializationDefinition.EvaluateInitializationData(bonus, None) only after
validating NoContextNeeded plus SimpleMath/Constant resolver metadata. Respect its
resolved value and scaling; use the fallback constant only when no attribute exists.
Never evaluate actor-dependent attributes on uninitialized inventory or silently
substitute a guessed offset. Retain native equipped-card behavior. F10's separate
use_level_bonuses summaries must survive the broad definition graph limit.
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
do not reinitialize existing items. Carried hostile death drops may be replaced
with fresh, verified copies after native DropFrom. Commit at Died POST, preserving
parts, names, balance/manufacturer, quantity, rarity and physics; initialize each
copy once, disable name reselection, validate its detached pickup before retiring
the original. Keep originals until validation succeeds and clean failed copies.
BL1E refuses direct Destroy for these actors: hide/disable retired pickups and
schedule native LifeSpan=0.01 expiry instead. Let pickup expiry handle attached
inventory; expire only pickup-less failed copies directly. Respect static/no-delete
actors, restore original flags before failed commit, and retain no actor wrappers
for future ticks. Check both bDeleteMe and bPendingDelete. F10 changed counts plus
clean retirement records are required before claiming native replacement success.
Never run this for player/live NPC drops or outside confirmed hostile death scopes.
Player attribute-query context is not itself
ownership. Never call health methods on NPCs during native item construction;
require a confirmed death/loot scope for NPC query sources.
Leave unknown/interpolated/dynamic formats native and record skip reasons in F10.
Keep SDU progression upgrades and non-levelled consumables native.
Enemy difficulty is a saved Easy / Normal / Hard selector, default Normal.
Ordinary hostile roll weights (native / +1 / +2 / +3): Easy 70/20/9/1,
Normal 50/20/25/5, Hard 20/5/55/20. All preserve max(player, vanilla area)
as their base. Native ordinary levels floor at player level +1; keep the original
factory GameStage/grade bands when applying that floor. Native/+1 rolls overlap
at the +1 minimum; keep raw weights and named/boss player-level floors unchanged.
No extra +4 roll.
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

4.5.5 temporarily records Bone Head/Bone Shredder initialization decisions and
before/after death/drop ownership using properties only. Do not change gameplay,
call actor methods or reinitialize carried items for these probes. Keep records
bounded and indexed as primitive maps so F10 preserves nested detail. Remove the
targeted probes after the carried-unique path has been diagnosed and resolved.
