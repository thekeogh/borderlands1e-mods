# Releases

One Playthrough is the active mod in this directory. Keep playthrough-3/ (version
3) and reference/ unchanged. Record releases in CHANGELOG.md.
README.md is a concise player guide: installation, New Game, Continue and scope.
Always retain the full Easy / Medium / Hard / Very Hard spawn-percentage table in README.md
and keep it synchronized with the actual weights when changing difficulty.
Preserve vanilla regional/mission floors, native reward identities and money formulas.
Unpaid missions follow max(player level, native mission floor), including accepted
and ready-to-turn-in missions. Ignore old acceptance locks for unpaid missions.
Freeze the mission level for the entire synchronous reward payout; XP level-ups
must not change later cash/equipment rewards. Preserve paid mission records.
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
Before native reward-item initialization, encode the payout mission's internal
level in native non-interpolated ManufacturerGradeIndex high bits, preserving
low grade bits and original definition identities. Only encode mission balances in the
active reward scope. Explicitly recall the bound native function with replacement
input structs and block the original; SDK hook-argument mutation has no effect.
Preserve all inputs/returns; never retry after invocation. Discover signatures
from native metadata; skip unsupported output parameters and interpolated formats.
Loot level floor is a saved toggle, default on. Use the captured native
Engine.WillowInventory:InitializeInventory boundary for fresh world/container loot
(including skag piles) and vendor stock. Every equipment type uses the same
max(1, player) floor: weapons, shields, grenade mods and class mods. Encode
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
Enemy difficulty is a saved Easy / Medium / Hard / Very Hard / Debug / Adaptive selector, default Medium.
Ordinary hostile roll weights (native / +1 / +2 / +3): Easy 0/40/60/0,
Medium 0/0/60/40. Hard uses 0/0/0/80/20 (+3/+4); Very Hard uses
0/0/0/20/75/5 (+3/+4/+5). Ordinary spawns preserve max(player, vanilla area)
as their base and naturally higher native levels without stacking or capping.
Easy ordinary spawns roll +1 at 40% and +2 at 60%, without a native roll.
Difficulty changes affect new spawns only; never rewrite existing pawn data.
Named enemies/bosses never roll. Easy/Medium fix them at exactly player +2; Hard fixes them at exactly player +3 and
Very Hard at exactly player +4, overriding higher native defaults/offsets/fixed
grade levels via private cloned exact level inputs. This also applies to supported
named hostile vehicles. Keep Debug unchanged.
Preserve native factory stage/grade identity when flooring named enemies. Apply
the same policy to supported named hostile vehicle balances. Leave unknown level
formulas/layouts native and record a diagnostic reason. No fixed boss levels or completion
flags to enable scaling. Keep rare-level data private to those spawns.
Only log the loading/version line automatically. A manually requested diagnostic
export must log its request, saved path or failure; never swallow export errors.
Keep the legacy Playthrough3 settings path only for migration. Preserve historical
names in credits, changelog entries and captured-fixture provenance.

4.5.1's broad read-only trace hooks are no longer registered. Keep native
initializer signatures and bounded gameplay counters/failure records
in F10. Legacy per-call loot argument/event/equipment sampling and broad trace
discovery are removed in 4.9.2; chest inspection runs only on manual export.
Local engine models are not
proof of native Windows behavior. Never claim unsupported loot paths are fixed.

4.5.5 temporarily records Bone Head/Bone Shredder initialization decisions and
before/after death/drop ownership using properties only. Do not change gameplay,
call actor methods or reinitialize carried items for these probes. Keep records
bounded and indexed as primitive maps so F10 preserves nested detail. Remove the
targeted probes after the carried-unique path has been diagnosed and resolved.

4.8.0's +5 skull is presentation-only. Use the supplied GfxHUD contract:
p1.ring.dangerous frame 2 is a native warning, frame 3 is deadly/skull, frame 4
is friendly; p1.ring.elevel.text is the target level. Override only a visible
warning at exactly player +5. Preserve friendly/normal and +6-or-higher native
skulls, scaling, enemy data and Globals difficulty thresholds. Reflect/check
Flash signatures/enums, cache primitive metadata only, and avoid per-frame object
scans/reflection. Restore only owned current-target overrides on disable/context
exit. Unsupported layouts remain native and appear in manual F10 diagnostics.
Never bundle supplied game assets or decompiled scripts in the release.

4.9.0 adds Debug for mod testing. Only this explicit mode bypasses hostile level
floors and higher native level inputs: exact max(1, player - 30) for supported
ordinary/named/boss/vehicle hostile spawns, with no RNG. Keep factory GameStage
and grade-selection bands/identity intact; use private cloned defaults and fixed
grade levels so native offsets cannot raise/lower the Debug target. Never alter
friendly/neutral/player actors or live spawned actors. Preserve all four play
difficulty policies, missions and loot rules. Append Debug to existing choices;
keep Medium as the default and preserve saved settings. Unknown layouts remain
native with an F10 reason. Easy/Medium/Hard/Very Hard named enemies also use exact levels as defined above.

4.9.2 removes obsolete background loot tracing. Keep F10/menu exports, the single
loading/version log, bounded gameplay counters and failure/retirement records.
Do not reintroduce per-call diagnostic payload sampling or broad trace hooks.
HUD per-frame work implements the +5 skull and is gameplay, not a debug probe.

5.0.0 adds Adaptive, appended after Debug without moving existing choices.
Preserve all existing presets, Medium default, Normal->Medium saved migration,
and saved selection/keybinds. Adaptive percentages use player-level anchors:
5: +1 20/+2 80; 15: +2 80/+3 20; 25: +2 40/+3 60;
35: +2 20/+3 70/+4 10; 45: +3 70/+4 30;
55: +3 45/+4 52/+5 3; 65: +3 20/+4 75/+5 5.
Linearly interpolate at every integer player level, clamping at endpoints.
Use 1,000 uniform tickets and exact integer tenths of percentages, never round
away fractional chances. Weight selection depends on player level, not area;
ordinary spawn base remains max(player, native area), preserving higher native
levels. Adaptive named/bosses and supported named hostile vehicles do not roll:
exact player +2 through 22, +3 through 52, +4 from 53. Keep their factory stage,
grade bands and identity. No live pawn edits, extra spawn calls, gear/death
tracking, background logging or diagnostic sampling. F10 reports the current
player/percentages and delayed boss offset; menu exports show no invented level.
