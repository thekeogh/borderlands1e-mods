# Releases

One Playthrough is the active mod in this directory. Keep playthrough-3/ (version
3) and reference/ unchanged. Record releases in CHANGELOG.md.
README.md is a concise player guide: installation, New Game, Continue and scope.
Preserve vanilla regional/mission floors, native rewards and money formulas.
Ordinary hostile enemies use 95% native, 4% at least area-base +1, 1% at least
area-base +2; retain naturally higher levels without stacking the bonus.
Named enemies/bosses never use that roll. No fixed boss levels or completion
flags to enable scaling. Keep rare-level data private to those spawns.
Only log the loading/version line automatically. A manually requested diagnostic
export must log its request, saved path or failure; never swallow export errors.
Keep the legacy Playthrough3 settings path only for migration. Preserve historical
names in credits, changelog entries and captured-fixture provenance.
