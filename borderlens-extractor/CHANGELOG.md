# Changelog

## Workshop app 0.3.1

- Add Show more to each saved source card with a read-only full-source modal.
- Display complete stored text, structured sections/tables, the source record and cached HTML without rewriting or truncating data.
- Read HTML from local cache as inert text; never render source scripts or refetch the website.
- Add copy controls, source identity/checksum details, Escape close and focus restoration.
- Verify exact text/HTML equality, unchanged source records and script non-execution.

## Workshop app 0.3.0

- Bundle a local Chrome Page Capture extension with in-app setup, folder-copy controls, extension-page opener and connection status.
- Add source-card buttons that open the requested article in Chrome with an item-bound capture ticket.
- Send visible article HTML through the local workshop tab; no cookies or background wiki fetching.
- Cache captured sources, retain useful headings/tables and update provider status automatically.
- Queue captures at safe worker checkpoints, recover accepted captures after restart and preserve browsing/queue selection.
- Reject wrong-page, invalid/expired tickets and unreadable captures; repeated successful sends are idempotent.
- Add API/queue/recovery tests and a real MV3 extension browser fixture covering popup-to-app capture.

## Workshop app 0.2.1

- Change website export to an item-only ZIP matching type-folder/slug.json layout.
- Embed full part data in each item; omit separate parts, schemas, evidence, manifests and overrides.
- Add strict self-contained website schema 3 while retaining normalized compiler schema 2 internally.
- Show the website format in Final JSON and support round-trip manual edits without changing shared parts in other items.
- Use readable filename slugs and disambiguate same-name items without overwriting.
- Export only completed current-schema items and show the ready count.
- Preserve all workshop source/evidence/override data locally.

## Workshop app 0.2.0

- Introduce shared catalogue schema 2 and compiler-version tracking across all equipment categories.
- Add <=200-character summaries, paragraph descriptions, meaningful variants, richer acquisition details, scoped drop chances and source references.
- Rewrite useful cached wiki/Lootlemon content through Codex; reject substantial verbatim source passages.
- Preserve headings and tables, including div-based section content, and backfill existing saved pages without downloading them again.
- Add stable family part references, a separate shared parts catalogue/schema and provenance; require captured title links for defining parts and stronger evidence for compatibility claims.
- Show richer previews and referenced part definitions in Final JSON; export shared parts separately.
- Queue old generated outputs for rebuilding after schema/compiler upgrades; retain previous output and corrections, and preserve manual entries for review.
- Add tests for all-category schema use, bounds, source parsing, originality, parts compatibility, parts export and version upgrades.

## Workshop app 0.1.3

- Persist weapon classification corrections in a separate classification-overrides.json file; leave capture ZIPs and stable IDs untouched.
- Research unresolved weapon types from saved pages, requiring matching identity, obtainable status and exact supporting source quotes.
- Apply manual corrections before researched types, then raw classifications; ambiguous/cut/shared naming candidates remain in review.
- Move classified items into their sidebar group live while preserving selection and the active queue.
- Add manual type correction under Sources & evidence.
- Retain overrides through restart, reimport and generated resets; include them in catalogue ZIP exports. Full reset clears them.
- Apply external override-file edits on refresh/poll; invalidate completed drafts when the effective type changes.
- Verify override persistence, priority, safe classification and live sidebar moves.

## Workshop app 0.1.2

- Group internal machine-gun candidates under Combat rifles and machine-pistol candidates under Repeater pistols.
- Separate unresolved weapon types and internal grenade-launcher candidates into Needs review, with classification guidance.
- Preserve captured types, stable IDs, cached sources and completed output.
- Order new queues to match the grouped navigation.

## Workshop app 0.1.1

- Seek wiki and Lootlemon separately, including when one provider is already cached.
- Show saved/missing/unavailable status and fetch errors for each provider in Sources & evidence.
- Remember failed attempts until source refresh or correction instead of silently skipping or retrying every rebuild.
- Prioritize saved article passages over shared game context within the AI prompt budget.
- Rewrite source ability descriptions into brief player-facing effects; validate page citations and reject internal tech/accessory explanations.
- Keep research limitations in private uncertainties instead of public gameplay notes.

## Workshop app 0.1.0

- Add local React/TypeScript catalogue workspace with independent browsing and persistent progress.
- Verify extractor ZIPs, retain captures and discover item-family candidates.
- Process sequentially through evidence, cached source research, Codex drafting and validation.
- Add pause/resume, restart recovery, corrections, manual output, rebuilds and scoped resets.
- Add wiki/Lootlemon coverage comparison with remembered links and exclusions.
- Export public JSON, JSON Schema, evidence sidecars and explicit coverage limitations.
- Use ChatGPT-authenticated Codex CLI with no API-key fallback.
- Verify real capture import and one live draft; add API, subprocess, queue, simulation and browser checks.

## 0.2.1

- Start a fresh capture when the last-export pointer references a deleted folder or missing manifest. Preserve remaining files and continue rejecting corrupt checkpoints.
- Include missing file paths in startup error messages.
- Add deleted-folder and deleted-manifest regression tests.

## 0.2.0

- Follow expression trees/evaluators and non-actor population factories to collect missing calculation and source relationships.
- Recover nested objects through separator variants and exact-class enumeration, validating full path, class and process-local address.
- Use the same lookup checks when releasing temporary asset pins; report unresolved releases explicitly.
- Record lookup recovery diagnostics, streamed-level provenance and per-record source packages.
- Expand the reviewed package plan from 48 to 69 roots using real capture evidence, including additional DLC items, custom weapons, elemental rules and population data. Remove two unconfirmed candidate names.
- Automatically start a fresh capture after upgrading rather than resuming an incompatible extractor version. Existing exports remain intact.
- Add regression fixtures from the first BL1E capture and tests for graph traversal, nested lookup, identity checks and upgrade behavior.

## 0.1.0

- Initial Borderlands GOTY Enhanced raw-data extractor, author keogh.
- F9 start/pause/resume; menu controls for status, fresh captures and partial exports.
- Reflected definitions, class/struct schemas, typed references, parts, balance rules, loot graphs and limited current-map source bindings.
- Reviewed base-game/DLC data-package plan; missing, failed and interrupted package loads recorded explicitly.
- Bounded main-thread processing, temporary data-asset liveness pins and lifecycle cleanup.
- Atomic, checksummed JSON chunks, validated recovery, session provenance and incremental ZIP packaging.
- Standalone project layout; final family compiler deferred.
