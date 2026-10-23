# Borderlens Extractor

Before app/compiler work, read [APP_PLAN.md](APP_PLAN.md) for the agreed product
context, workflow and implementation plan. App code belongs in app/. The SDK
extractor's no-network requirement below does not prohibit the app's explicitly
planned source research and supported Codex integration. Implement only when the
user requests implementation. The app was explicitly authorized on 23 October 2026.

Keep this project self-contained: extractor/ holds the SDK mod, tests and builds;
app/ holds the local catalogue workshop; compiler/ is reserved; temp/ holds ignored exports and scratch data.
Do not modify other mods, reference/, or the Borderlens website. Author: keogh.

The first tool exports raw evidence, not final family JSON or verified stat extrema.
Use stable Unreal paths and typed references; preserve inheritance, part/title rules,
loot graphs, field schemas, errors and explicit truncation. Never invent missing data
or claim a complete catalogue just because a collection job finished.

All SDK access runs on the game thread. Never retain live UObject/struct/property
wrappers across frames: queue primitive descriptors and resolve objects by path.
Only static data objects may receive temporary RootSet liveness pins; restore our
pins on completion, disable, failure or map change. Never pin gameplay actors.
Do not spawn items, call actor stat methods, change gear/loot/quests/economy or save
a character. Load only the reviewed data-package plan, never arbitrary map packages.

Checkpoints/chunks are atomic and checksummed. Resume validates every existing
chunk and recovers its IDs; conflicting provenance must be recorded. Bundle only
files belonging to the current export. No external network, account or API needed.

Test the serializer, graph traversal, limits, package policy, pause/resume, recovery,
GC/liveness cleanup, failure paths and package layout with modeled SDK objects.
Local tests cannot establish native Windows package safety or full game coverage.
Keep README a short player guide; record releases in CHANGELOG.md and raw format
in extractor/FORMAT.md. App/compiler context and current verification limits live in APP_PLAN.md.

For catalogue field/instruction changes, update shared Zod schemas, compiler prompts,
validation, UI/export and fixtures across equipment types. Bump the schema/compiler
constants so older entries are queued; retain their outputs and manual corrections.
Never invent migration prose or assume a shared part graph proves compatibility.
