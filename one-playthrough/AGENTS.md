# Releases

One Playthrough is the active mod in this directory. Keep playthrough-3/ (version
3) and reference/ unchanged. Record releases in CHANGELOG.md.
README.md is a concise player guide: installation, New Game, Continue and scope.
Preserve vanilla regional/mission floors, native reward identities and money formulas.
Equipment rewards use the accepted mission level, not turn-in character level.
Scope inventory grade overrides to native reward calls and restore them afterward;
never clone saved item balance identities. Keep SDU progression upgrades native.
Ordinary hostile enemies use 85% native, 8% at least area-base +1, 6% at least
area-base +2, 1% at least area-base +3; retain naturally higher levels without stacking the bonus.
Named enemies/bosses never use that roll. No fixed boss levels or completion
flags to enable scaling. Keep rare-level data private to those spawns.
Only log the loading/version line automatically. A manually requested diagnostic
export must log its request, saved path or failure; never swallow export errors.
Keep the legacy Playthrough3 settings path only for migration. Preserve historical
names in credits, changelog entries and captured-fixture provenance.
