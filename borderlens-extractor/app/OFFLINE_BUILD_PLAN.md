# Plan: factual assembly in code, original prose from AI

Created: 27 October 2026. Starting point: app 0.49.0, compiler 0.12.0.

Status: implemented; current app 0.52.2 / compiler 0.15.1. Verification and subsequent policy changes are recorded below.
This file is the implementation checklist and can be reviewed independently of
the conversation. Verification limits and the progress log below are part of the result.

## What we are changing

The app will assemble the facts and own the structured JSON. AI will interpret
ambiguous evidence when necessary and write every public explanatory sentence
in original wording. It will no longer regenerate established structured data
while rewriting prose.

Keep the depth and usefulness of the finished entry. Reduce repeated input,
interpretation and correction work, rather than shortening the output.

## Start-to-finish workflow

| Step | What happens                                                                                                                                            | Who does it                                                       |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| 1    | Import the game ZIP, retain raw definitions, discover and group items.                                                                                  | App; existing workflow                                            |
| 2    | Find item evidence URLs.                                                                                                                                | AI; existing workflow                                             |
| 3    | Capture selected website content or add manual text; organise shared evidence.                                                                          | User and Chrome extension; existing workflow                      |
| 4    | Start a build; apply source modes and choose relevant saved facts.                                                                                      | App                                                               |
| 5    | Extract supported structured facts from game definitions and recognised page structures. Interpret remaining useful ambiguous content only when needed. | App first; cached AI interpretation as fallback                   |
| 6    | Resolve supported values and assemble a compact factual outline with provenance, conditions and relevant passages.                                      | App                                                               |
| 7    | Write original prose for the outline. Flag genuinely missing information through the existing saved-evidence request mechanism.                         | AI                                                                |
| 8    | Combine fixed structured data with AI prose, validate and request targeted corrections if necessary.                                                    | App; AI corrects only affected prose or unresolved interpretation |
| 9    | Save JSON, provenance, accepted interpretations and actual request statistics.                                                                          | App                                                               |

No website refetch is required merely because the compiler changes. A build from
saved sources continues using saved HTML/text. Stored captures remain unchanged.

## Rules that must remain true

- Every published explanatory sentence is AI-written in original wording. No
  deterministic prose templates and no pasted source passages in final JSON.
- Canonical names, enum labels, numeric values and exact red text remain factual
  literals; do not paraphrase names or alter quoted in-game flavour text.
- Source excerpts are private evidence. They may enter an AI request, but must not
  be copied into public descriptions, details, notes or other prose slots.
- Manual name/type overrides remain authoritative. Manual JSON remains protected.
- Always include makes the selected source facts available to the writer; it does
  not require every fact to appear in the finished entry. The compact outline
  must not silently filter out Always include facts by relevance.
- Auto uses relevance selection. Never include sources are excluded before reads,
  indexing and AI submission. Preserve the existing blocked-request notice flow;
  an AI request never silently overrides Never include.
- Evidence edits, corrections, imports and migrations never start builds.
- Unknown values stay unknown. Missing images remain valid and image matching is
  unchanged. There are no item-, character- or weapon-specific exceptions.
- Share facts only through applicable evidence ownership/scopes. A cached fact
  about a skill or another item does not automatically become this item's stat.

## Current implementation to build on

Do not replace the existing pipeline wholesale. Reuse and adapt:

- `src/server/evidence.ts`: captured definition packet and existing validation.
- `src/server/source-analysis.ts`: quoted facts, cached readings and source usage.
- `src/server/shared-source-index.ts`: reusable shared readings and relevance.
- `src/server/catalogue-meaning.ts`: item/mechanic/example/part/progression roles,
  manufacturer attribution and item-origin checks.
- `src/server/source-cache.ts`: saved-source rebuild eligibility.
- `src/server/worker.ts`: staged builds, retries, checkpointing and cancellation.
- `src/server/saved-evidence.ts`: bounded requests for additional saved evidence.
- `src/server/final-entry.ts` and `website-export.ts`: final document assembly.
- Existing stats/History, backup/import/reset and manual-edit facilities.

Current limitation: the writer returns a whole entry, so correcting prose can
reintroduce a bad manufacturer, stat or variant. Much of the writer input is also
larger than the factual content actually needed. Both are targets of this plan.

## Implementation checklist

### Phase 1 — establish the baseline and private contracts

- [x] Measure real request boundaries on isolated fixtures: submitted characters,
      UTF-8 bytes, actual provider token usage when available, calls, elapsed time,
      cached readings and retries. Label estimates as estimates.
- [x] Cover a weapon, shield, grenade mod, class mod and artifact, including a
      shared source reused by a second item, plus fresh and cached builds.
- [x] Define a versioned private fact schema: stable ID, subject/scope, property,
      typed value, units, conditions, role, provenance and acceptance state.
- [x] Distinguish candidates from accepted facts. AI-extracted claims do not become
      deterministic game facts simply because they were saved.
- [x] Define separate contracts for the factual outline, immutable structured
      entry data, requested prose slots and the AI prose response.
- [x] Keep the public website schema compatible where possible. Version private
      contracts independently; bump the compiler for changed instructions.

**Done when:** the app can represent facts and prose separately, and baseline
measurements exist without touching live user data or running paid model jobs.

### Phase 2 — deterministic extraction where it is reliable

- [x] Extract identity-linked game fields and existing authoritative metadata using
      typed definitions and explicit relationships, not display-name guesses.
- [x] Extract recognised website labels/tables from existing saved structures.
      Start with layouts supported by fixture evidence, not a universal scraper.
- [x] Preserve headers, units, level, player-count and conditional context. Detect
      partial selections, ambiguous columns and missing headers; fall back rather
      than manufacturing certainty.
- [x] Keep sample rolls, prices and build examples separate from family bounds.
      Keep shared mechanics and component modifiers out of item stat ranges.
- [x] Require explicit producer evidence for manufacturers. Keep item introduction
      separate from DLC drop locations; never infer Base Game just from an absent
      DLC prefix or a page's game label.
- [x] Resolve structured conflicts using the existing policy: manual authority;
      proven defining raw restrictions where applicable; verified Lootlemon over
      Wiki for genuinely equivalent conflicting claims. Retain complementary facts
      and flag conflicts the policy cannot resolve.
- [x] Limit game-stat calculations to implemented, tested formulas with known inputs
      and valid combinations. Do not claim final roll extrema from raw constants,
      multiply unrelated modifiers, or introduce a full game simulator here.

**Done when:** recognised data becomes auditable structured facts without AI;
ambiguous data remains available for interpretation rather than being lost.

### Phase 3 — reusable interpretation and accepted corrections

- [x] Send AI only evidence not already handled reliably, with enough neighbouring
      context to interpret it correctly. Do not split away essential table headers
      or relationships, or send recognised content twice.
- [x] Reuse compatible existing readings. If a new contract genuinely needs another
      interpretation, do it lazily on the next requested build and cache it.
- [x] Cache source interpretation by content hash, extraction policy and relevant
      source identity/settings; cache item applicability separately by item identity,
      source modes, corrections and policy.
- [x] Retain exact source quotations and references privately; preserve all useful
      supported facts, not just stats.
- [x] Persist a validated interpretation correction against the affected fact/source
      version. Other eligible items can reuse it without repeating the failed work.
- [x] Persist item-specific decisions against that item. Never promote them into
      global rules or spread them to unrelated descendants automatically.
- [x] Invalidate only affected derived data when captures, manual text, overrides or
      policies change. Keep the accepted correction's history and dependencies.
- [x] Do not treat a prose rewrite or a validator error as proof that the underlying
      evidence changed. Global rules change through code and tests, not unchecked
      AI self-modification.

**Done when:** repeated eligible builds reuse accepted interpretations and fixes;
changed evidence is reconsidered without discarding unrelated cached work.

### Phase 4 — assemble the factual outline in code

- [x] Resolve structured fields: identity, category/subtype, character, origin,
      supported manufacturers/rarities/elements, levels, stats, part relationships
      and acquisition entities/conditions/probabilities.
- [x] Attach provenance and conditions to every resolved value. Leave unsupported
      fields empty/null. Keep unresolved contradictions private and reviewable.
- [x] Select useful explanatory topics and facts using the existing inclusion modes.
      Preserve substantive mechanics, interactions, acquisition and meaningful
      variants; group ordinal progression without inventing distinct versions.
- [x] Deduplicate repeated facts while retaining supporting references and accounting
      for every selected fact. Respect full Always include availability and source
      priority; deduplication must not discard different conditions or values.
- [x] Build compact input from accepted facts and necessary context. Remove repeated
      raw graphs, duplicate descriptions, unused schema fields and bookkeeping that
      the prose writer does not need. Retain uncertain facts with their uncertainty.
- [x] Give facts and prose slots stable IDs. Keep the complete provenance ledger
      locally; send the minimum references needed to support correct wording.

**Done when:** before the writer runs, the app has a stable, auditable factual
outline and can show exactly what structured information is already established.

### Phase 5 — AI writes prose; code assembles JSON

- [x] Replace the whole-entry writer response with prose keyed to stable slot IDs:
      summary, description, titled sections, effects, useful notes and explanations
      for stats, parts, variants and acquisition where required.
- [x] Require AI to write every explanatory phrase, including acquisition conditions
      and notes; do not hide copied sentences in otherwise structured fields.
- [x] Keep structured numeric values, identifiers, classifications, conditions and
      relationships outside the writable response. The app assembles them from
      accepted facts, not from AI's retyped copy.
- [x] Let the writer propose a missing topic or factual concern privately. Such a
      proposal cannot silently edit accepted facts; route it through evidence
      interpretation/validation first.
- [x] Preserve the bounded saved-evidence request and user notice mechanism. Do not
      add a mandatory critique/review AI call to every build.
- [x] Validate prose coverage, original wording, numerical mentions and consistency
      with the fixed outline. Continue schema and source accounting checks.
- [x] Return precise, scoped feedback on failure. Preserve accepted facts and valid
      prose; retry affected slots and necessary linked passages, with prior feedback
      retained. Do not regenerate the whole entry for one sentence or bad label.
- [x] Assemble final public JSON and save it atomically only when checks pass.

**Done when:** rewriting a paragraph cannot change a manufacturer, origin, stat or
other established structured field, and source prose never becomes fallback output.

### Phase 6 — migration, visibility and persistence

- [x] Preserve previous output/revisions and manual edits during migration. Apply the
      new pipeline only on requested work, using normal compiler version handling.
- [x] Migrate compatible derived records; lazily refresh incompatible ones. Keep
      original HTML/text and game archives untouched. No recapture requirement.
- [x] Record real request counts and payload sizes for extraction, interpretation,
      writing and repairs, plus cache hits and provider usage when available.
- [x] Label retries with their reason and attempt number; do not make a retry look
      like an unexplained duplicate source submission.
- [x] Keep progress readable: assembling facts, interpreting uncached evidence,
      writing prose, checking and saving. Preserve detailed History records.
- [x] Include new facts, interpretations, corrections and dependencies in complete
      backups/imports. Audit full reset and generated-work reset against the new
      artifacts: generated reset retains accepted research/corrections; full reset
      clears them.
- [x] Preserve pause/resume/cancel, category batches, source promotion, recapture,
      source exclusions, manual text editing and per-item overrides.

**Done when:** old projects remain usable, backups restore exact state, resets
match their labels, and the user can see where AI input and time were spent.

### Phase 7 — prove correctness and measure the result

- [x] Test every equipment category, structured and irregular pages, manual text,
      partial captures, conditional values, examples, shared reuse and conflicts.
- [x] Prove that Never include content cannot enter normal AI calls; Always include
      remains available without becoming mandatory public content.
- [x] Prove that a prose retry cannot alter fixed facts or resurrect a resolved error.
- [x] Test persisted corrections across restart/rebuild and eligible item reuse,
      with invalidation when the supporting evidence or scope changes.
- [x] Test migration/manual-output protection, source edits, parts, backup/import,
      both reset scopes and cancellation using isolated projects.
- [x] Run appropriate automated checks and browser flows. Do not run a live catalogue
      build, replace user JSON or incur real model calls just to execute tests.
- [x] Compare fresh and cached fixtures with the Phase 1 baseline. Report actual
      input sizes, calls, retries and output completeness. Measure provider time and
      tokens only with real available measurements; never present a mock as proof.
- [x] Document verification limits, update release notes/context and mark this plan's
      completed phases with the evidence used to accept them.

## Expected benefit, not a release guarantee

The earlier discussion estimated roughly one-third less build time and half the
input on eligible cached builds. These are hypotheses, not acceptance thresholds.
The new writer must keep equivalent depth and coverage. Fresh ambiguous sources
still need interpretation; Always include can still make the outline large.
Provider latency and output generation remain outside the app's control.

## Scope limits

Keep URL discovery and Chrome capture working as today. No automatic evidence
selection wizard, global AI memory service, website redesign, new external service,
full game simulation or item-specific patch rules. Do not edit the SDK extractor
or public website as part of this app change.

## Progress log

- 27 October 2026: plan saved after reviewing the existing worker, fact-reading,
  shared-cache, semantic-validation and final-assembly paths. No implementation or
  user-data changes made as part of writing this plan.

- 27 October 2026: implemented private typed facts/provenance, conservative local
  table extraction, cached structured interpretation and repair journals, compact
  factual assembly, prose-only writing and targeted patches. Source modes, manual
  overrides, saved-evidence requests and original captures remain protected.
- 27 October 2026: added atomic publication and per-revision factual snapshots;
  extended prompt/CLI telemetry and reset/backup coverage. Synthetic fresh/cached
  profiles across five categories include shared source reuse by a second item.
  See OFFLINE_BUILD_BASELINE.md; no real token or latency claims are made.

## Implementation boundaries and verification limits

- Local website parsing intentionally supports only unambiguous item-owned complete
  Property/Value and explicit min/max tables. Unqualified rarity/maker/element
  labels establish confirmed possibilities, not exhaustive sets. Other layouts,
  cross-game signals, samples, spans, partial selections and unknown context fall
  back to interpretation. The user does not need to format captures specially.
- Raw game extraction contributes identity-linked facts and supported restrictions.
  No new final-damage simulator or speculative roll-range formula was introduced.
- Structured interpretations remain visibly identified as model-derived provenance;
  accepting them under the policy does not turn them into raw game facts.
- Prose condition/difference checks preserve exact digit values. They do not claim
  complete machine understanding of every possible natural-language implication.
- All measurements/tests use isolated fixtures and mocks. Real provider token
  counts, provider speed and real-world wording quality must be observed on
  user-requested builds; no paid/live catalogue run is performed for testing.

## Final verification — 27 October 2026

- TypeScript check and production build passed.
- Automated suite: 268 checks, 264 passed, 4 optional skipped, zero failures.
- Full browser smoke passed using the real capture fixture and mocked AI.
- Backup browser flow passed: timestamped save/download, restore, evidence/images/
  manual-name/layout round trip and full reset, in an isolated project.
- OpenAPI parsed at app version 0.50.0; whitespace checks passed.
- Final synthetic writer payloads were 8,970–8,980 characters, roughly 61% below
  the original fixture prompts. Fresh ambiguous-source builds made two requests;
  cached rebuilds and a second item reusing shared analysis made one. These
  demonstrate fixture behavior only; real model quality, tokens and speed remain
  unmeasured. No real models called and no live catalogue changed.

To use: restart the app and rebuild an item from saved sources. Existing captures
need no refetch. Ambiguous evidence may receive a new policy-versioned analysis;
its accepted interpretation is reused on subsequent eligible builds.

### 0.50.1 schema compatibility correction

A real source-reading request exposed nested `oneOf` emitted by Zod discriminated
unions. Codex strict output rejects that keyword. The common CLI schema boundary
now emits `anyOf`; literal kind fields retain exclusive branches and runtime Zod
validation remains intact. Restart clears only cooldowns matching the corrected
schema failures. Regression coverage traverses actual provider-bound reading,
prose and patch schemas and tests persisted cooldown recovery. All 28 focused
router/Codex/offline tests and production build passed. No live model calls made.

### 0.50.2 / compiler 0.13.1: factual scope and effects feedback

A live draft exposed an uncertain shared fact tagged for another equipment
category being promoted into fixed manufacturer data. Fixed-property acceptance
now checks category, character, element and weapon type as well as item/skill
ownership; retaining uncertain evidence does not establish applicability. Original
saved facts stay unchanged; the next requested build reassembles with fact policy 2.
The prose prompt explicitly requests zero to two special-effect entries and 45
words combined. Targeted feedback recognises the hyphenated special-effect label
and cannot replace unrelated valid prose. Genuine review/conflict messages take
precedence over cosmetic limits, so a blocked factual draft reports its actual
reason. No hand edits to final JSON or live model calls performed.

Verification: 271 automated checks, 267 passed and 4 optional skipped; all 17
offline-build regressions and production build pass. No live data changed.

### 0.51.0 / compiler 0.14.0: best-effort automatic builds

Supersedes earlier perfection/blocking requirements for ordinary uncertainty.
Private writer review flags, optional source spellings, rank progression and
same-priority numerical disagreements no longer prevent publication. Keep the
first equally ranked supported scalar value; record alternatives privately.
Allow the writer to omit optional source/variant slots and acquisition conditions
that merely describe missing evidence. Numeric prose differences become notes.
Best-effort validation runs every remaining check: quality/context/exact source
stat coverage are advisory; explicit wrong/unresolved core item identity, invalid
JSON/schema, reversed bounds, unsupported makers/parts and copied source prose
remain blocking. Manual JSON review keeps its existing explicit validation path.
Publish uncertainties and advisories as finalValidation.warnings, shown under
Built with … notes in Preview, and in provenance/revision/History. Standard backup
and generated reset handle these existing artifacts without special data files.
Fact policy 3 changes assembly; original source captures/readings stay reusable.
No live catalogue changes or model calls performed during implementation/tests.

Verification: 274 automated checks (270 passed, 4 optional skips), TypeScript/production
build and full browser smoke pass. The browser verifies successful publication and
expandable Preview notes for optional spelling/progression uncertainty; screenshot
`.test-data/screenshots/build-notes.png` inspected. All tests use isolated data and
mock AI. Restart the app, then rebuild from saved sources; no recapture needed.

### 0.52.0 / compiler 0.15.0: acquisition consolidation and origin

Consolidate accepted acquisition facts before sending the prose outline. Keep
all fact IDs and per-fact private detail/conditions in the source slot, including
complementary reward/rank/playthrough notes even when structural fields match.
Merge exact names or aliases explicitly equated in a saved quote; no fuzzy
spelling guesses or item-specific alias rules. Prefer the named source's own URL
over a generic overview; retain all evidence claims/references. Preserve separate
known locations and typed rate/player/edition scopes, including aliased names.
Writer instructions retain useful acquisition outcomes in original notes, treating
playthroughs as alternatives and missing evidence as private uncertainty. Existing
best-effort validation remains in place; no new quality-blocking retry is added.

Origin now recognises original identity roots in reviewed base packages from the
extractor's checked-in package plan (self-contained app snapshot at
src/server/base-content-packages.json). Unknown/missing/mod or mixed identity
packages remain unknown; linked loot graphs never assign origin. Explicit
item-owned Origin/DLC/Content Pack tables can establish origin locally. Known
Base Game stays the existing JSON enum; unknown stays null and displays Unknown.
Manual-save claims now include DLC so known origin round-trips through editing.

Fact policy 4 and parser policy 2 update assembly/local parsing. Compatible direct
source interpretations retain their 0.14 contract cache keys independently of
writer/compiler releases; shared reading policy stays 3. No refetch, paid model
call or live catalogue rewrite performed. Apply via next requested saved-source
rebuild. Existing output, manual corrections and captures remain retained.

Verification: 279 automated checks (275 passed, 4 optional skips), production build,
OpenAPI/version parsing and full browser smoke passed. Preview screenshot confirms
Base Game for captured character artifacts. Follow-up manual-save regression
(22 passed, 3 optional skips) and final production build passed after allowing an
older null origin to be filled from verified extraction during explicit manual
save. Explicit user origin values and all user prose remain unchanged. Original
sources/live catalogue were not modified; no provider calls made.

### 0.52.1 / Chrome helper 1.3.0: optional whole-page capture

Restore Capture whole page in both extension popup and floating selection panel.
Box selection remains unchanged. A separate injected capture-page.js sanitises the
loaded DOM, retaining article headings, complete tables and loaded tab contents.
Wiki uses its article container; Lootlemon uses body content rather than assuming
a main wrapper. Forms/editable values, scripts/active attributes, navigation and
selection UI are excluded. No fetch, image/canvas OCR or unloaded tab-data request.

Both modes use the same background-validated ticket, requested URL, owner-bound
capture/recapture and safe checkpoint. Full recapture clears excerpt metadata;
selection recapture can replace it again. Return focuses Sources & evidence and
retains the persistent close-tab preference. Success disables an existing panel
if a whole capture was sent from the popup. The downloadable helper includes the
new script; manifest/metadata 1.3.0. Reload extension and refresh workshop/source
tabs after updating. No compiler/public schema change and no automatic builds.

Verification: eight Chrome helper/ticket/ZIP tests and the actual MV3 extension
browser flow pass. The browser retains all existing selection/resize/fit/overlap
checks, then tests a zero-box whole Wiki recapture and a Lootlemon body without
main markup, loaded hidden tables, removed forms/scripts/navigation, excerpt
metadata replacement, ownership, persistent close-tab return and unchanged run/AI
call counts. Popup screenshot inspected. Final TypeScript/production build and
whitespace checks pass. Tests use isolated data and synthetic pages; no live
website fetch or user source changes performed.

### 0.52.2 / compiler 0.15.1: preserve prose-slot citations

A saved HellFire run supplied an appropriate parts claim, including its exact
source fact, but assembly discarded all model claims outside the main prose
fields. The code-owned parts claim omitted that source page, and source usage
validation then repeatedly demanded a citation the model had already provided.
Preserve parts/stats/sources/variants/levels prose citations alongside the main
prose claims; union them with code-owned factual claims, without exposing fixed
values or relationships to model edits. Clone claims so assembly does not mutate
the saved model result. Retain compatible interpretations; fact policy 5 updates
assembly. In automatic best-effort validation only, an incomplete used-fact field
citation is a non-blocking note; unknown/missing/duplicate fact IDs and unrelated
core validators retain their checks. No fabricated citations or live JSON edits.

Verification: 281 checks (277 pass, 4 optional skips). Regression covers part
citations surviving assembly, unchanged fixed parts, saved-prose immutability,
strict/manual validation and advisory automatic accounting. A read-only snapshot
of the reported HellFire prose was assembled locally (only compiler metadata
updated in memory) and passed draft/parts/source-usage validation with zero notes,
zero provider calls and no live writes.

Final TypeScript/production build, OpenAPI version parsing and whitespace checks passed.

### 0.52.3: restored image rendering

Reported HellFire PNG exists and matches correctly, but the image endpoint returned
500/Not Found. Restored backups use .data/image-library; Express sendFile treated
hidden ancestors in the absolute filepath as dotfiles. Serve the already
allowlisted/realpath-validated basename relative to its directory, keeping default
dotfile filtering and all existing library confinement checks. No image files,
image choices, catalogue data or compiler schema changed. Restart app and refresh
the page; no rebuild/recapture needed.

Verification: nine image/backup tests passed, including hidden-directory PNG bytes
and MIME type plus blocked hidden/non-image/missing paths. Real backup-browser
flow now uses a .data project, restores images and asserts successful browser
image decoding; restored-image.png inspected. TypeScript/production build and
whitespace checks passed. Tests use isolated projects; live images/data untouched.
