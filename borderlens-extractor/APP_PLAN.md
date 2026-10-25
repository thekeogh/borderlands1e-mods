# Borderlens — app context and implementation plan

Last updated: 23 October 2026. Project owner/author: **keogh**.

This is the agreed product direction and working plan for future AI sessions.
Read this file and `AGENTS.md` before app/compiler work. This document records
intent. Implementation was explicitly authorized on 23 October 2026; the first
working app now lives in `app/`.
Later explicit user instructions override this plan.

## 1. Purpose

Build a local catalogue workshop for **Borderlands GOTY Enhanced (BL1E)**.
Turn raw game extractions, supplemented by locally saved research, into thorough,
accurate, readable item-family JSON files for the Borderlens website.

The user wants to import an extractor ZIP, press a large **Start** button, and let
the app work through the catalogue one item at a time. It researches, interprets,
writes, validates and saves each entry. It remembers progress and corrections,
pauses for blocking problems, and resumes without repeating successful work.
The user can inspect any item while the background run continues.

The output unit is an **item family**, not every generated item instance or part
combination. Examples: Thunder and Hellfire each have one family entry describing
their applicable manufacturers, rarities, elements, rules and ranges. Do not
produce millions of weapon-variation JSON files.

All equipment is in scope: ordinary/common families as well as named, unique,
legendary and pearlescent items; weapons, shields, grenade mods, class mods and
other relevant item types. Include main-game and all four DLC content. Use game
and edition distinctions explicitly; a BL2 Hellfire page is not BL1 evidence.

## 2. Existing project and boundaries

Everything belongs under this project so it can move to its own GitHub repository
without depending on the surrounding mod repository.

```text
borderlens-extractor/
  AGENTS.md
  APP_PLAN.md                 this context and plan
  README.md                   concise extractor/player guide for now
  CHANGELOG.md                release history
  extractor/                  existing BL1E SDK mod, format docs, tests, builds
  app/                        user-created location for the local UI and service
  compiler/                   reserved shared compiler/schema work
  temp/                       ignored local captures, experiments and prototypes
```

A persistent `data/` directory inside this project is a proposed default for app
projects, source caches, checkpoints and exports. It does not exist as an agreed
implementation yet. Support relocating project data without hard-coded paths.
Do not use `temp/` as the only durable home of important app state.

The app will use Node.js/TypeScript for its local service and a TypeScript web UI.
Use Zod for the catalogue contracts and validation. The frontend framework,
package manager and specific storage library are not selected yet. Choose simple
maintainable defaults when implementation is authorized, checking existing files
first. Avoid an unnecessary hosted deployment or account system.

Keep the compiler's pure data/schema logic reusable outside the UI, potentially
in `compiler/`, with the app importing it rather than duplicating it. All app UI,
server and job-runner code belongs in `app/`.

Do not modify `reference/`, other mods, One Playthrough or the existing Borderlens
website as part of app work unless separately instructed. The extractor and app
are distinct: the SDK mod needs no external network/account/API; the app's source
research and Codex integration intentionally use the internet.

## 3. What already exists

### Extractor

Borderlens Extractor is implemented. The current build is **0.2.1**:

- SDK mod: `extractor/dist/BorderlensExtractor.sdkmod`.
- Source: `extractor/src/BorderlensExtractor/`.
- Raw format: `extractor/FORMAT.md`.
- F9 starts/pauses/resumes; the mod menu can start fresh or finish a partial capture.
- Export ZIPs contain `manifest.json` and checksummed JSON record chunks.
- Captures include definitions, reflected schemas, typed references, parts,
  manufacturers, grade tables, formulas, naming conditions, loot pools,
  expression evaluators, population factories and limited map/archetype bindings.
- Work is incremental on the game thread. The extractor does not generate items
  or change gameplay values/saves. Its temporary static-asset liveness pins are
  released on completion, disable, failure or travel.

A new character is **not required**. An existing/copied solo save works. For a
clean capture, disable gameplay mods and fully restart the game before extraction.

The two reviewed captures are:

| Capture | Extractor | Data objects | Observations |
| --- | --- | ---: | --- |
| `borderlens-20261023-150958-597989.zip` | 0.1.0 | 15,097 | Initial capture; nine missing nested objects; two candidate packages unconfirmed |
| `borderlens-20261023-153827-931444.zip` | 0.2.0 | 20,508 | All 69 planned package roots loaded; all nine old missing objects recovered |

These object counts are **not item-family counts**. The second capture has no
missing-object entries or serialization truncation, but retains 278 unsupported
`MapProperty` reads from cinematic animation-state fields. It is not proof of
complete catalogue or source coverage. Captures differ with loaded state; keep
both and preserve their provenance rather than assuming one supersedes all data
in the other.

They were uploaded into the parent repository's `logs/` and copied into
`temp/imports/`. Temporary copies/review files are ignored by Git and may not be
present in a future checkout. The app must accept imports, not depend on these
absolute paths or silently assume these files are available.

The persistent world may be called `Loader`. Later captures also record streamed
levels and each object's source package; do not interpret `Loader` as the actual
playable region or assume every loaded level is active.

### Hellfire investigation

A capture-only demonstration exists in `temp/` when the local artifacts are
available:

- `hellfire.prototype.json`: exploratory family shape, not the final schema.
- `hellfire.evidence.json`: supporting game records, simplified from the raw data.
- Other Hellfire index/match/build scratch files are investigation tools, not the
  production compiler.

Confirmed examples include the HellFire title and accessory, explicit Maliwan
selection, legendary title-rarity input, incendiary tech-fire rules, red text,
part candidates, shared SMG defaults and shared loot-pool routes.

Important lessons:

- The accessory's spawn-stage gate is **22–100**. This is not a proven usable
  item-level range. The title's **1–100** gate is not that range either.
- Magazine 28, fire interval about 0.12 seconds and reload about 2.1 seconds are
  shared SMG-type defaults before parts, not final Hellfire card statistics.
- A raw tech-rule chance input of 100 is not sufficient proof of a 100% per-hit
  burn chance. Costs, rule selection, target resistance and application matter.
- Part candidate lists do not prove every cartesian combination is legal.
- A shared pool path is not a dedicated drop source or guaranteed reward.

The user liked the data but rejected internal prose such as “family identified by
its accessory/title, with incendiary tech-fire rules.” Final content must explain
what the weapon does and why a player might want it.

### Existing website data

The user has an existing website with older JSON at:
`/Users/keogh/Sites/thekeogh/borderlens/data/games/borderlands`.

Those files illustrate the desired **family grouping concept only**. The user
considers their AI/wiki-derived facts unreliable, incomplete and structurally due
for replacement. Do not import them as authoritative facts or assume their schema
is the target contract. Do not edit that website during this project by default.

## 4. Main experience: one workspace, one Start button

Do not require the user to manually visit six sections and run phases in sequence.
The default experience is an automated pipeline within one main workspace.

A rough layout:

```text
+-----------------------------------------------------------------------+
| Project / Import ZIP      START or PAUSE / RESUME       Settings        |
| Overall progress: 37 / 500   Hellfire — interpreting special effects    |
+--------------------------+--------------------------------------------+
| Search / filters         | Selected item: Thunder                     |
| Weapons                  |                                            |
|   SMGs                   | Preview / Sources & evidence / History     |
|     Hellfire  [working]   | Issues / Final JSON                        |
|   Snipers                |                                            |
|     Thunder   [done]     | Rebuild this item     Start from here      |
| Shields                  |                                            |
| Grenade mods             |                                            |
| Class mods               |                                            |
+--------------------------+--------------------------------------------+
| Latest activity / connection / saved-state indicator / jump to current |
+-----------------------------------------------------------------------+
```

This is a functional sketch, not a required visual design or a fixed count of
items. Use a clean readable interface; no elaborate dashboard is necessary before
the main queue works.

The sidebar:

- Groups families into collapsible categories and weapon subtypes.
- Lists **families**, not raw definitions or individual part permutations.
- Shows queued, processing, complete, needs attention and deliberately excluded
  states with text as well as visual indicators.
- Supports searching/filtering without changing the execution queue.
- Reflects the deterministic order the normal batch will process. Freeze the run
  order after discovery; expose deliberate changes rather than silently reordering.
- Can include externally discovered candidates, clearly marked as not yet linked
  to game data. They are not silently treated as verified extracted families.

### Browsing must not interrupt processing

**Selected item and running item are independent state.** Clicking Thunder while
Hellfire is running changes only the inspection panel. It must not stop, restart,
redirect or replace the active job or its prompt.

The overall progress strip remains visible and live on every view, including
item preview, source inspection and settings. It shows:

- Run state: preparing, running, pausing, paused, needs attention or complete.
- Current item and stage.
- Completed/total items and useful stage progress, without fabricated percentages.
- Pause/Resume and **Jump to current item**.

Update sidebar statuses and the selected item's view as evidence/results arrive.
Keep the current successful preview readable while a replacement is being built.

## 5. User actions and their meaning

### Import ZIP

Accept the extractor ZIP directly; the user should not have to unpack it. Support
an extracted folder/manifest import if straightforward. Verify archive paths,
format, chunk hashes/counts and IDs before adding the capture. Preserve the
original capture and import provenance. An identical import is idempotent.

Multiple captures enrich the project. Preserve disagreements and source sessions;
do not silently overwrite every old record with the newest one. Importing new
evidence identifies affected work, not an automatic full reset of all entries.

### Start

Start discovery if needed, then process the visible ordered queue sequentially.
Reuse existing research, corrections and successful checkpoints. Skip completed,
up-to-date entries. If everything is done, say so; do not secretly rebuild it all.

### Pause / Resume

Stop launching new stages at a safe checkpoint and persist the state. Show
“Pausing” while an in-flight operation is being settled. Closing/reopening the UI
must not lose progress. Resume continues from the saved stage, not item one.
Do not promise instant cancellation of an upstream Codex request unless the chosen
integration actually supports it.

### Rebuild this item

Process the selected family through the pipeline again, using saved source pages,
manual corrections and current rules. Its goal is an updated validated final JSON.
Do not re-import ZIPs or automatically re-download unchanged sources.

While a batch is running, enqueue the rebuild safely and show that it is queued.
Proposed default: append it behind the active batch so the normal sidebar order
stays intact. Deduplicate repeated requests. Never run two jobs against the same
family simultaneously. A future change to priority semantics should be explicit.

### Start from here

Process the selected family and following eligible items in sidebar order,
skipping completed/up-to-date work by default. This is not “force rebuild every
item after here.” If a batch is already running, change its pending range at a
safe boundary, retain completed work, and clearly show the new range.

### Refresh sources

Explicitly fetch newer external pages for the selected item and invalidate only
the dependent interpretation/writing/export stages. Separate this from Rebuild so
ordinary rewrites can use the local cache without another crawl.

### Resolve a problem

Show what failed, what evidence was found, what Codex tried and the specific input
needed. Allow retrying, selecting/correcting a source, editing a fact or match,
marking a deliberate exclusion, or leaving a permitted field unknown. Save the
resolution, its scope and provenance; then continue from the checkpoint.

Do not rely solely on a conversation transcript as “memory.” Store corrections
as explicit persistent rules/overrides. Preserve manual edits through rebuilds;
show a conflict when new evidence contradicts them.

### Reset

Provide two distinct operations:

1. Restart generated work while retaining captures, cached pages and corrections.
2. Clear the whole project, explicitly including those retained assets.

Make the destructive scope obvious and prevent accidental full deletion. A reset
is never an automatic response to a failed import, failed AI job or version change.

## 6. Automated pipeline

These are processing stages and inspectable tabs/tools, not required manual steps.

### A. Import, index and discover families

Validate captures, index classes/objects/references and identify candidate family
identities from titles, defining parts, balances and related rules. Separate
prefixes, materials, technical parts, unused/developer definitions and families.
Record aliases and source paths. Codex may investigate ambiguous grouping, but
must cite evidence instead of deciding from a familiar-looking name alone.

### B. Build external inventories and compare coverage

Collect BL1/Enhanced item listings from the wiki and Lootlemon. Traverse relevant
wiki categories/subcategories with pagination and game filtering. Normalize
redirects, aliases and page identities, then compare with the discovered families.
Prepare a stable queue and an explicit coverage report. Newly found external-only
items are candidates needing linkage or investigation, not invented game records.

This global inventory step can be cached. Do not re-enumerate every category for
each individual item. When discovery changes the total, label that preparation
phase and update the denominator honestly.

### C. Research the current item

Find candidate pages; inspect their game, edition, item type, manufacturer, aliases
and actual contents. Codex should resolve straightforward matches automatically
and try alternatives where appropriate. Only unresolved ambiguities require user
attention. Store chosen/rejected matches and reasons so future runs remember.

Fetch and save the actual allowed page HTML and useful API responses locally.
Search results/snippets alone are not a substitute for the archived evidence.
Record URL, retrieval date, page/revision ID where available, content hash and
fetch result. Use incremental fetching, sensible timeouts, bounded retries and
request spacing. Respect each site's access rules; do not build bypasses for
blocked pages. An access failure is resumable and visible, not an empty success.

### D. Extract and reconcile facts

Parse useful sections/infoboxes/tables from saved sources and combine them with
the game's definitions. Codex can interpret messy pages and investigate conflicts.
Keep evidence attached to individual claims. Separate verified game values,
derivations, external statements, disputed claims and unknowns.

For actual mechanics, compare unique parts/behaviours with their ordinary
counterparts. A description must explain the benefit or tradeoff, not merely
repeat red flavour text or convert an Unreal identifier into a sentence.

External sources supplement the extraction. They must not silently override
conflicting game/edition values. There is no automatic rule that every wiki fact
is wrong or every raw field directly expresses the final player-visible result.
When a conflict matters, investigate or flag it.

### E. Write player-facing content with Codex

Use AI to write natural original descriptions, summaries, special-effect
explanations and relevant notes. The user explicitly prefers this to templated
sentences assembled in code. Keep a consistent editorial style without forcing
every entry into the same sentence pattern.

Give Codex the selected item evidence, supported comparisons, source passages,
required schema and writing instructions. Tell it which facts remain unknown.
Do not let it fill gaps from memory, copy whole third-party descriptions, or add
unsupported superlatives and mechanics. Exact game names/red flavour text are
separate sourced fields, not prose to invent.

### F. Validate and save

Validate structure with Zod and validate evidence/semantics separately. Check
identity, edition, enum values, units, bounds, contradictory statements and
whether claimed special effects have support. Schema conformity alone does not
prove factual correctness. Optional unknown values do not become zero, empty
confirmed lists or fabricated numbers.

Save a new final revision only after validation. Preserve the last successful
revision if the replacement fails. Store the supporting evidence and processing
history alongside it, separately from the website-facing entry. Mark the item
complete and continue to the next queue item.

### G. Finish and export

Each successfully processed family has a validated final JSON; do not wait until
the end of the whole catalogue to persist it. A final export action packages the
website-facing files and an appropriate manifest/coverage report. Report omitted,
blocked or deliberately excluded entries. Never label a partial export complete
without qualifying its scope.

## 7. Coverage tool

A Coverage view/tab is useful within the main workspace. It is automatically
populated by the pipeline and can also be refreshed explicitly.

Use these comparison statuses:

| Status | Meaning |
| --- | --- |
| Matched | External item linked to extracted family evidence |
| Missing extraction | External item exists; no adequate extraction match yet |
| Extraction only | Extracted family exists; no external page identified |
| Ambiguous | Competing family/page matches need resolution |
| Excluded | Guide, duplicate, wrong game or confirmed unused content, with reason |

Report per equipment type, game/edition, DLC and source where possible. Page
counts are not family counts: categories may mix guides, titles, grenades, unused
content and similarly named items from different games. Class-mod categories can
span the entire franchise. Preserve aliases and page IDs to avoid false misses.

Lootlemon is useful for its listed special items, but is not assumed to cover all
ordinary/common families. The wiki matters for those. Neither source is a complete
oracle; the defensible target is “all known candidates accounted for,” with
uncertainty and exclusions visible.

Produce a targeted missing-data checklist when extraction is insufficient, such
as specific definitions, packages, source relationships or native behaviours to
investigate. Do not ask for another larger dump without knowing what is missing.

## 8. Final catalogue and editorial requirements

Design Zod schemas with the compiler using representative families first. The
Hellfire prototype is evidence about possible fields, not a schema to copy as-is.
Some of its strings and nested data are deliberately technical investigation data.

Potential family content:

- Stable identity, display name, aliases, game/edition and equipment category.
- Manufacturer, rarity and elemental arrays where multiple values are valid.
- Player-facing summary and specific special-effect descriptions/tradeoffs.
- Exact red flavour text, separately from what the effect actually does.
- Legal level ranges where established, with context rather than one instance's
  required level masquerading as a property of the entire family.
- Stat ranges or level-dependent values/formulas with units, assumptions and scope.
- Relevant variations, part effects and naming behaviour in readable form.
- Drop/source information, location/content requirements and verified probability
  only where evidence supports it.
- Useful limitations/notes and source attribution.

A fixed required-level field from an observed instance is generally inappropriate
for the family. Likewise damage, fire rate, capacity, reload and accuracy must not
be presented as one universal stat when parts/level change them.

Keep raw Unreal paths, resolver names, packed level fields, research prompts and
internal confidence/debug messages in evidence/build sidecars. Stable machine IDs
and schema keys are fine; **user-visible strings** should read like a finished
player reference, not extraction logs. The UI may expose technical evidence in its
inspection tabs without putting it in the public description.

Unknowns should be explicit internally and use schema-approved null/omission in
public output. The website can display a clear “Not established” where helpful.
Distinguish “not found in these sources” from “does not exist.” Do not claim
precise damage extrema, stacking rules, proc rates or source coverage merely
because related coefficients or pool references were captured.

The app must retain source attribution and evidence even when generating original
wording. Later website presentation is outside this app's implementation scope
unless explicitly requested.

## 9. Codex integration and billing decision

The user's preferred AI path is **local Codex using ChatGPT sign-in**, rather
than requiring a separately billed OpenAI API key for the first implementation.

The local Node service can run a supported non-interactive Codex integration,
provide item evidence/instructions, request structured final JSON and consume
progress/events. `codex exec` is a viable initial route; the official TypeScript
SDK is another option to evaluate before implementation. Do not automate a
terminal UI by scraping its rendered text.

The installed CLI was checked as **codex-cli 0.163.0**, with `codex exec` exposing
`--json`, `--output-schema`, stdin input and final-message output. Re-check the
installed version/help and current official documentation when implementing;
these observations are not a permanent interface guarantee or proof of login.

Billing distinctions as checked on 23 October 2026:

- ChatGPT-authenticated Codex uses the plan's Codex allowance, subject to limits.
- API-key usage is separately billed; a ChatGPT subscription is not API credit.
- Hundreds of item jobs can consume allowance shared with normal Codex work.
- The UI/service/files run locally; OpenAI model processing still happens online.

Handle unavailable login, expired authentication, usage limits and transient
failures as visible resumable states. Do not silently switch to paid API usage
or request that the user paste authentication tokens into the UI. Use supported
Codex sign-in; do not read or repurpose OAuth credentials directly.

An optional API-key provider may be added later if requested. It is not required
for the initial product. Keep any future key on the service side, out of browser
bundles, exports, logs and version control.

Codex may help with source discovery, ambiguous matches, page interpretation,
mechanics explanation, prose generation and entry checking. Results need evidence;
a second AI opinion alone is not proof. Keep tasks scoped per item/stage, use
bounded retries, and cache successful outputs so a retry does not redo the catalogue.

Relevant official references, not a requirement to browse them during ordinary
use of this plan:

- [Codex non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode)
- [Codex authentication](https://learn.chatgpt.com/docs/auth)
- [Codex SDK](https://learn.chatgpt.com/docs/codex-sdk)
- [Codex pricing/usage](https://learn.chatgpt.com/docs/pricing)

## 10. Wiki and Lootlemon research

Confirmed useful discovery locations:

- [Wiki: Weapons in Borderlands](https://borderlands.fandom.com/wiki/Category:Weapons_in_Borderlands)
- [Wiki: Class Mods](https://borderlands.fandom.com/wiki/Category:Class_Mods) — cross-game category; filter it.
- [Lootlemon: BL1 weapons](https://www.lootlemon.com/db/borderlands-1/weapons)

MediaWiki supports category members/subcategories, pagination, page listing and
content retrieval. Prefer an API adapter for discovery and structured page data
where accessible; retain useful HTML for local inspection/reprocessing.

- [MediaWiki category members](https://www.mediawiki.org/wiki/API:Categorymembers)
- [MediaWiki page parsing](https://www.mediawiki.org/wiki/API:Parsing_wikitext)
- [MediaWiki all pages](https://www.mediawiki.org/wiki/API:Allpages)

The live Borderlands Fandom API endpoint was **not verified working** in this
session because tool access was blocked. Check actual accessibility and site
rules before implementing an adapter. Do not describe it as already integrated.
Lootlemon's inventory is readable, but no public API was established here.

User-supplied HTML can be a future fallback for inaccessible pages. Preserve
whether evidence was fetched, API-derived, user-imported or manually entered.
Do not claim a search response itself provides the full original HTML.

## 11. Persistent state and recovery

Use service-owned storage on disk for authoritative project state. A local
database plus files is a proposed approach; the exact library is not selected.
Use localStorage only for small UI preferences such as collapsed groups and
selection. Clearing browser storage must not erase catalogue work.

Persist at least:

- Imported capture identities, hashes, formats, sessions and relevant raw records.
- Family identities, aliases, grouping decisions and exclusions.
- External inventories, candidate/chosen page matches and revisions.
- Cached source documents and parsed claims with their evidence.
- Manual corrections, reason, scope and conflicts with later evidence.
- AI inputs/context hashes, model/provider, prompt version, output and validation.
- Queue order/range, active operation, per-item stage and completed checkpoints.
- Failures/retries, unresolved issues, final revisions and export manifests.

Use atomic writes/transactions and stable IDs. Resume only from committed stages.
After a service crash, mark the in-flight operation interrupted and reconcile any
saved result before retrying. A browser reconnect must not start a second run.
Only one active worker processes the default queue; requests must not duplicate
jobs or overwrite a newer revision with an older result.

Invalidate stages deliberately: a description rewrite need not fetch sources;
a changed source page invalidates dependent facts/prose; a changed schema requires
revalidation; a new capture invalidates affected evidence-dependent work. Keep
successful unrelated stages and all user corrections.

Avoid false activity: report actual item/stage transitions. Show elapsed work and
counts; mark an estimate as an estimate. Do not animate an invented completion
percentage while waiting on a long-running Codex or fetch operation.

## 12. Failures, AI assistance and user attention

The user's desired default is: **stop at a blocking problem, resolve it, remember
what worked, then continue.** Do not silently skip a failed family and claim success.

Transient failures may get bounded automatic retries. Codex can attempt evidence-
based recovery and alternative matching. After the retry budget or an unresolved
material conflict, pause the batch and explain the specific problem.

Missing optional facts can remain unknown if the schema and quality policy allow
it; not every unknown must block a whole run. Identity conflicts, wrong-game
matches, corrupt input and unsupported required claims must not pass as complete.
A deliberate skip/exclusion is recorded and appears in coverage/export summaries.

The user can continue browsing while paused or blocked. Resolutions should have
an appropriate scope: a Hellfire page correction is item-specific; an alias or
parsing rule can apply more broadly when supported. Do not generalize a one-off
workaround to every item without evidence.

## 13. Proposed implementation order

These are engineering milestones, not extra stages the player must run manually.

1. **Import and durable skeleton:** validate real ZIPs, index raw evidence,
   establish persistent project state and show initial family candidates.
2. **Core workspace and worker:** sidebar, independent selection, persistent
   progress strip, ordered single-worker queue, Start/Pause/Resume, recovery and
   per-item actions. Use a deterministic fake worker before connecting paid/AI work.
3. **Codex connection:** supported sign-in check, scoped jobs, structured output,
   progress events and resumable failures, with recorded model/prompt provenance.
4. **Source adapters and coverage:** wiki/Lootlemon inventories, matching, local
   HTML/API cache, comparison statuses and targeted missing-data reporting.
5. **Representative end-to-end entries:** Hellfire, Thunder, Lady Finger, a shield,
   a grenade mod and a class mod. Exercise unique mechanics and ordinary families.
   Design/refine Zod schemas from these without freezing a misleading early shape.
6. **Writing, validation and review:** evidence-backed prose, contradictions,
   manual corrections, readable preview, history and safe per-item rebuilds.
7. **Scale and export:** full queue, rate limiting, targeted invalidation, final
   files/manifests, reset scopes and user documentation.

Do not fetch hundreds of pages or process the entire catalogue before the small
end-to-end batch demonstrates reliable matching, readable content and recovery.
Only request targeted extractor changes when that work exposes a specific gap.

## 14. Acceptance checks

Before considering the first app usable, demonstrate:

- Import a real extractor ZIP; reject bad hashes and unsafe paths clearly.
- Duplicate import does not duplicate families or destroy previous work.
- Press Start once and automatically get validated output for a representative batch.
- During Hellfire processing, selecting another item does not interrupt the run.
- Progress remains visible, current and accurate on every view.
- Pause/restart/reconnect resumes from persisted checkpoints without duplicate jobs.
- A simulated fetch/AI failure pauses clearly; a saved correction survives restart
  and lets the job continue without repeating successful earlier work.
- Rebuild uses caches/corrections; Refresh sources deliberately updates evidence.
- Start from here respects the selected range and completed work.
- Every exported family passes Zod; unsupported facts remain unknown or blocked.
- User-visible descriptions explain effects naturally, with no Unreal/debug prose.
- Source/edition ambiguity and excluded candidates are visible in coverage.
- A failed rebuild preserves the last successful JSON and manual edits.
- The two reset scopes behave differently and match their displayed descriptions.
- Raw input, caches, evidence, public JSON and secrets are kept in their intended places.

Local tests should cover real capture fixtures, queue ordering, selection
independence, persistence/recovery, adapter failures, correction reuse and schema/
evidence validation. Mock external/Codex work for routine tests; do not spend
subscription allowance or make live bulk requests as a side effect of the suite.

## 15. Boundaries and unresolved decisions

Not authorized by this plan alone: building the app now, modifying the website,
publishing a hosted service, changing other mods, purchasing credits, adding a
required paid API path, or claiming the full catalogue is verified.

Still to decide during implementation: frontend stack, storage library, exact
public Zod schemas, model selection, editorial style details, completeness policy
for optional values, source refresh policy and exact export layout. Use sensible
small defaults where appropriate, but preserve the product behaviours above.

The essential direction is settled: **import evidence, press Start, browse freely
while a durable background queue researches and builds readable family JSON, and
resume around problems without losing work.**

## 16. First implementation — 23 October 2026

`app/README.md` covers running the local React/Node workshop. TypeScript/Zod
contracts live in `app/src/shared/models.ts`; Express API in `src/server/http.ts`;
SQLite storage in `store.ts`; verified imports in `importer.ts`; evidence linking
in `evidence.ts`; supported ChatGPT CLI execution in `codex.ts`; cached research
and coverage in `research.ts`; sequential checkpoints in `worker.ts`. The client
is `src/client/`. Everything remains inside this project.

Implemented: ZIP checksums and retained captures; family candidates; per-stage
queue and recovery; independent browsing; source HTML caching and manual import;
Codex source discovery and structured drafting; schema/evidence checks with bounded
repair; manual edits/corrections; coverage comparison and manual identity links;
ZIP export; scoped resets. The first research stage automatically attempts a
coverage inventory; Coverage can also be run separately.

Verification includes real capture import (255 candidates), one live Hellfire
game-evidence draft through ChatGPT-authenticated Codex, local HTTP API checks,
Postman research simulation (pagination, robots rejection and 503), and isolated
browser checks for background browsing, pause/resume and UI persistence. Browser
fixtures never supply production data.

Remaining validation: title-based discovery is a heuristic, not exhaustive family
reconciliation. Review family grouping, shared part constraints and edition/source
identity across real entries before publishing. Numeric extrema and drop rates
are deliberately not fabricated. External-only coverage candidates require
investigation; they are not silently promoted into game-backed families. Websites
may block automated fetching, requiring saved HTML or explicit game-only choice.
Claim checks establish referenced evidence exists, not that every AI reading is
semantically correct. The final website schema is still subject to review.

The app uses built-in Node SQLite (Node 22.13+), not browser storage for project
state. No OpenAI API-key fallback, Postman account, hosted workspace or deployment
is required. Keep `.data/`, exports and sources out of Git.

### Workshop 0.1.1 research/editorial refinement

Always seek wiki and Lootlemon independently; an existing page from one provider
does not complete the other provider. Per-family `research` artifacts retain
provider status, attempted URLs and failure reasons. Missing or blocked sources
remain visible in Sources & evidence; successful cached pages still support a
partial-source draft. Source refresh or a saved correction clears prior attempts.
Do not bypass website access restrictions; import saved HTML when needed.

Saved pages/manual corrections are budgeted before shared raw records in drafting
prompts. Special effects primarily paraphrase the saved articles' gameplay
descriptions through Codex: up to two short entries, 45 words total, with article
evidence citations. Raw data is supporting verification, not public implementation
prose. Keep exact red flavour text; do not surface internal tech levels/accessory
comparisons or research uncertainty as player notes. Explicit game-only mode
remains supported when no archived page is available.

### Workshop 0.1.2 navigation taxonomy

Use `app/src/shared/taxonomy.ts` for player-facing navigation and ordering.
Internal machine guns group under Combat rifles, and machine pistols under
Repeater pistols. Internal grenade-launcher and unresolved weapon candidates
appear under Needs review with explicit classification guidance. This is a
presentation grouping: captured subtype, roots and IDs remain intact, distinct
families are not merged, and existing outputs/corrections remain available.
Future queues follow this navigation order; previously saved queues retain their
IDs/order. DLC titles and shared name parts still need identity/type resolution.

### Workshop 0.1.3 durable classification overrides

`.data/classification-overrides.json` is authoritative for classification overrides,
not the extractor ZIP or SQLite projection. Its schemaVersion 1 entries are keyed
by stable family ID, with optional manual/research records. Each contains family
name, canonical weaponType, reason, verifiedAt and evidence snapshots (page ID,
URL, title, exact quote, content hash). Priority: manual > research > captured type.
`src/server/classifications.ts` validates and atomically writes the file.

Unresolved weapon types are classified before drafting from archived page evidence
using a separate strict Codex decision. Obtainable identity and canonical type must
be supported by exact quotes from available pages. Actual conflicts/cut identities
block classification; shared elemental naming definitions are not auto-promoted.
Explicit game-only mode cannot create researched overrides without saved pages.

The effective Family.classification is a derived view used by shared taxonomy,
sidebar grouping, queue preparation, drafting and final weaponType. Raw subtype,
roots and IDs stay unchanged. Saving a researched type publishes a state revision
so the sidebar moves the same selected item immediately. Current queues retain
ID order; new queues follow updated navigation. Manual type choices are available
in Sources & evidence via the classification item action. Removing manual falls
back to research, then raw. A changed type invalidates completed generated drafts.

Overrides survive restart, capture import and generated reset. Catalogue exports
include the portable file; full reset clears it. State/detail/export refreshes
reload externally edited files, retaining the last good view if parsing fails.
Tests cover live movement before writing finishes, unchanged captures/IDs, exact
quotes and identity gates, priority, restart/import/reset/export, manual UI choices
and selected-item persistence. Model identity judgments still require review;
matching quotes validate provenance, not infallible interpretation.

### Workshop 0.2.0 rich catalogue schema and shared parts

`app/src/shared/versions.ts` defines catalogue schema 2 and compiler 0.2.0.
All equipment uses one strict Zod PublicEntry with <=200-character summary,
paragraph-array description, meaningful variants, surplus gameplay notes, sources
with location/DLC/conditions/scoped dropChance, source references, and part IDs.
Unknowns stay null/empty. Codex combines archived sources and game evidence into
original prose; exact names/red text and citation labels remain exact. A validator
rejects substantial 12-word verbatim runs from saved articles, but this is a useful
copying check, not proof of perfect originality or factual correctness.

`source-content.ts` retains section headings/text (including div-based text) and
HTML tables. Source contentVersion 2 is backfilled from cached HTML on access.
Pages and manual evidence take prompt-budget priority. No bulk scrape is required
to regenerate entries already having sources. Each completed family gets a
researchAudit recording fields sought and available page structure. Later audit
passes can inspect these caches before adding more category-specific fields.

`parts.ts` maps captured weapon-part definitions to stable hashed part IDs. A
Draft returns partDefinitions separately; family entries reference these IDs with
defining/required/possible relationships. Defining requires captured title linkage.
Required/possible relationships require a cited part selection rule referencing
the exact part, archived-page support and an explicit per-part claim basis.
Shared graph presence is not compatibility. Existing current-version shared
definitions are reused; parts live in `_parts` artifacts, with raw/source evidence
in provenance. Exports include parts/*.json, parts.schema.json and evidence/parts/.
Public strings use readable part names/effects; Unreal paths remain in sidecars.

Startup detects old schema/compiler outputs and queues their dependent work,
retaining last output/source caches/corrections/classification overrides. Old
manual output is retained for review instead of inventing new prose. Legacy
outputs remain inspectable but are not exported under the new schema. Update
versions when schema or compiler instructions meaningfully change. Field additions
need shared schema, prompt, validation, UI/export, migration and test updates,
including non-weapon fixtures.

### Workshop 0.2.1 item-only website export (overrides earlier export plan)

The user explicitly requires a ZIP containing ONLY per-item JSON files in flat
equipment folders matching the existing website: weapons/, shields/, class-mods/,
grenade-mods/. Additional supported types follow the same slug convention. No
manifest, schema, evidence, classification override or separate part files belong
in this website ZIP. Keep that material inside the workshop for backups/research.

`shared/website.ts` defines strict WebsiteEntry schema 3, with full inline parts
(name, slot, manufacturers, effects, notes, relationship, familyNotes) and slug.
`server/website-export.ts` resolves normalized internal schema 2 into standalone
website records, using per-family part edits before shared definitions. No website
or Fuse.js joins are needed. Final JSON uses the same shape; save-output accepts
website v3 and normalizes it back to internal storage, preserving edited per-family
parts without modifying other families' canonical shared records. No AI rebuild
is needed solely for this projection change.

Export completed current-schema entries only; show the ready count in the toolbar.
Readable name slugs remove apostrophes, and same-name collisions are disambiguated
with type/ID suffixes instead of overwriting. Stable family IDs are unchanged.
Classification overrides remain authoritative locally but are NOT bundled in
website exports; copy the overrides file or .data/ for workshop backups.
The existing website data was inspected for folder/filename conventions only;
no website files or raw extraction archives were modified.

### Workshop 0.3.0 Chrome browser-assisted capture

`app/chrome-extension/` is a bundled MV3 extension loaded once with Chrome Developer
mode / Load unpacked. Chrome does not allow silent website installation. In-app
setup opens the fixed Chrome extensions URI using OS tooling, copies the real
folder path, offers a separate extension ZIP and detects the helper via a local
content-script handshake. The website catalogue ZIP remains item-only.

The helper uses activeTab+scripting for explicitly invoked article capture, local
loopback host permissions for its workshop bridge and storage.session for pending
ticket metadata. It does not ask for permanent wiki host access, cookies or history.
Open-source buttons request a 30-minute backend ticket bound to one family and
expected article URL, then ask the helper to open that article. The popup captures
the rendered wiki article (.mw-parser-output) or Lootlemon main content after a
user click, strips scripts/forms/ads and relays HTML to the originating app tab.
No backend cookie copying, CAPTCHA solving or automated source-site fetch occurs.

The app’s existing same-origin API protections stay intact: extension messages
are relayed through the local app’s content script and window.postMessage with
request IDs/origin checks, then submitted by the app to /api/chrome-helper/capture.
The backend verifies a random ticket secret and URL binding, archives the source,
updates source status and invalidates dependent work. Active-worker imports are
persisted under _chrome artifacts and flushed at safe stage boundaries; queued
acceptances recover after restart. Imported HTML is removed from pending artifacts
after archival. Replay is idempotent; wrong URLs/expired tickets fail visibly.
Previously processed captures are appended to an active/paused queue as needed,
without changing selection or automatically starting a new Codex run.

Source.captureMethod=chrome distinguishes captures from downloads/manual paste.
The browser check uses a real extension in isolated Chromium with a synthetic wiki
article. Its temporary manifest grants the fixture host to automate popup tab
navigation; the production manifest retains activeTab-only article access. This
checks extension messaging, DOM stripping, local HTTP archival, tables and live
provider status, not successful access to Fandom in a new browser profile. The
user must load the helper in their regular Chrome profile and view the article.

### Workshop 0.3.1 exact stored-source viewer

Show more on every saved source card opens `src/client/source-viewer.tsx`. It
receives a snapshot of the existing Source object: Full text displays source.text
verbatim, Sections & tables uses only saved fields, Source record pretty-prints
the complete object, and Stored HTML reads the exact cached file through the
read-only /api/sources/:id/html endpoint. No AI, new source parsing, truncation or
source-site fetch happens in this viewer. Layout/labels are presentation only.

The HTML endpoint resolves only registered source filenames within the cache
directory, returns text/plain with no-store, nosniff and sandbox CSP, and reports
missing metadata/files. React preformatted text escapes markup; never insert this
HTML into the DOM as active markup or an iframe. Preserve all stored characters.
The modal retains its opened snapshot through background updates, supports Copy,
Escape/backdrop close, focus containment and opener focus restoration. Checks
compare exact DOM text and HTML against saved values, compare the source record,
verify no live fetch/record modification and assert embedded scripts do not run.
Chrome extension files/protocol, compiler schema and website exports are unchanged.


### Workshop 0.4.0 full-source reading and consistent enrichment

Compiler 0.4.0 uses internal catalogue schema 3 and self-contained website schema 4.
Public numeric ranges are ordinary catalogue facts, without source-reported flags,
provenance labels or verification disclaimers. Missing levels stay null; do not
turn raw modifiers into final stat extrema. Website JSON excludes references;
acquisition sources remain acquisition data. Exact HTML and private evidence stay
in the workshop, never bundled in the item-only website ZIP.

`source-analysis.ts` defines stable per-category field/stat checklists. Every saved
source's full text plus saved sections/tables is split into exact 18k-character
chunks with short neighbouring context to preserve boundary meaning, never dropped by the synthesis budget. Each chunk gets an independently
cached Codex extraction with short exact supporting quotes, stat objects, field
coverage and proposed structured fields. Cache keys include compiler version,
content, family/category, model and user corrections. Checkpoints survive failed
subsequent steps. Missing quotes/checklist entries block the build.

Synthesis receives ALL fact ledgers plus bounded game context. Draft.sourceUsage
accounts for every fact exactly once: used with matching source claims, duplicate
linked to a used fact, genuinely irrelevant with a reason, or conflict requiring
review. Used catalogue stats must survive unchanged. Private researchAudit stores
checklists, ledger, usage, proposals and manual-review status; the Sources tab
exposes it without including it in public JSON. These checks establish mechanical
coverage, not infallible semantic interpretation by AI.

Summary remains <=200 characters; descriptions may contain up to 30 substantial
paragraphs, normally 4–8 for rich evidence. `details` contains titled paragraph
sections for surplus mechanics, usage, interactions or trivia. Special effects
stay short (<=45 words). ALL prose must be newly written by Codex; names, exact
red text, numbers and necessary labels are exceptions. Copy detection covers
description/details, effects, notes, variants, parts and acquisition/stat notes.
A matched passage can receive a bounded, targeted Codex rewrite; facts, numeric
values, claims and fact dispositions stay unchanged and are validated again.
Current-schema validation checkpoints survive restarts even while the previous
completed output is still on an older schema.
Never paraphrase using templates or copy source sentences.

New useful numeric stats fit named stats[] without schema changes. Potential new
structured fields are saved as private proposals; never let an item rewrite Zod
on the fly. A reviewed schema/checklist change must bump versions and queue older
generated entries for another pass from caches. Preserve manual prose/corrections;
manual old entries remain blocked for explicit review, never auto-rewrite them.

Verification: 45 local tests passed; 2 optional research-HTTP simulation tests
skipped. TypeScript/build, OpenAPI syntax and browser smoke passed. Real cached
rebuilds completed for HellFire (70 source facts, 4 paragraphs, 2 detail sections,
6 stats) and Volcano (73 facts, 4 paragraphs, 4 detail sections, 6 stats). Both
used both archived providers and accounted for every extracted fact privately.
The live UI audit and item-only ZIP were checked. These examples establish
mechanical coverage, not correctness of every AI interpretation or all 255
candidate families. Browser capture/snapshot behaviour is unchanged.


### Workshop 0.4.1 scope policy and Codex liveness

Compiler 0.4.1 retains catalogue schema 3 / website schema 4 (no field-shape
change). `shared/catalogue-policy.ts` excludes generic site-wide farming guides,
routes, respawn/fast-travel tips and generic luck explanations. Apply the scope
instruction at both full-source extraction and final synthesis, and reject known
boilerplate in every public prose field. Keep item-specific mechanics, modifiers,
locations, acquisition conditions and drop probabilities. Saved text/HTML stays
verbatim. Filtered source facts carry private excludedReason and must be marked
irrelevant; coverage must not force irrelevant guide text into public notes.
Prior generated entries are queued to rebuild, preserving their last output;
manual edits are retained for review. Unfinished old drafts are archived by
compiler version before restarting them.

CodexRunner reports a 15-second heartbeat: elapsed time, age of last stdout/stderr
and the existing 12-minute per-call ceiling. Local process liveness does not prove
remote service progress. `activity.json` and `events.jsonl` update during calls and
record terminal state/errors. A dead process fails promptly; quiet calls wait up
to the bound, then fail visibly. Build messages include attempt 1/3 through 3/3,
and keep a pause-request prefix. Do not auto-resume a user's paused queue.
Scope modifiers are valid part modifiers too: numeric bonuses may be preserved
in part/mechanics text, rather than incorrectly treated as final card damage.

0.4.1 verification: 51 tests passed, 2 optional HTTP simulations skipped;
TypeScript/build, browser smoke and OpenAPI syntax passed. New modeled subprocess
checks verify live heartbeat/event persistence, quiet-call timeout, crash failure
and heartbeat cleanup. Both user-provided generic tips are rejected in public
notes/details; item-specific modifiers and acquisition facts remain allowed.
The saved Bessie draft's source coverage passes the corrected scope-modifier
check without a new Codex call. The observed slow run had two validation retries,
then returned and paused normally. The restarted service preserves that pause;
no batch or new real Codex call was automatically started for this update.


### Workshop 0.5.0 interchangeable subscription agents

The user explicitly added local Grok Build alongside Codex. AgentRouter is now
Worker's production AI. Settings.agent defaults/migrates to grok; the toolbar
selector persists grok/codex and may change during processing. It applies to the
next AI call and does not invalidate completed entries. Existing model is a Codex
model override only; Grok is pinned to grok-4.6. Build/Rewrite labels use low
reasoning effort; Read source/Classify/Find sources use medium. No high effort.

CliRunner implements shared validated caching, live heartbeat/activity/event
files, bounded output and process error handling. CodexRunner and GrokRunner
provide provider identity/commands. Grok uses --prompt-file, streaming-messages-json,
--json-schema, read-only sandbox, dontAsk, no subagents/plan and restricted tools;
structured_output is validated with the same Zod schema. Existing subscription
login must be confirmed before running. Strip inherited API-key environment vars;
never silently use paid API billing or substitute another Grok model. Grok auth
status via models is not proof that a subsequent model request is permitted.

Each production provider has a five-minute call budget. Terminate its process
(group on POSIX), escalate if needed, and wait for close before fallback starts.
Try the alternate once; if both fail, block visibly with both reasons. Failure
cooldowns last ten minutes and persist; Settings/Recheck agents explicitly clears
them without starting a model call or resuming the queue. The default choice stays
unchanged during fallback. Never bounce indefinitely or erase successful work.
Provider/model/effort are included in CLI cache keys; only successful validated
results are cached. Source-reading keys include preferred agent. Last actual draft
agent/model/effort/fallback provenance stays private, outside website exports.

GET /api/agents reports both CLI statuses, selected default, failures and cooldowns.
POST /api/agents/recheck clears cooldowns; /api/codex remains Codex-only compatibility.
PATCH /api/settings permits agent-only changes during work; other settings still
require pause. Catalogue schema 3, website schema 4 and compiler 0.4.1 stay unchanged
because this feature changes execution/provider selection, not item field shapes.

During integration, the real installed Grok 1.0.70 listed grok-4.6 and confirmed
OAuth grok.com authentication, but a tiny model call failed with HTTP 403: Build
is unsupported in Legacy (no storage), requiring the user's account Privacy Mode.
Do not change their account setting automatically. Implement and test fallback;
report this remaining account prerequisite honestly. Modeled Grok protocol tests
cannot establish that a real Grok generation succeeds until that restriction is
removed. tests/live-agents.ts is an optional tiny live subscription/fallback check.

0.5.0 verification: 58 local tests passed; 2 optional research-HTTP simulations
skipped. TypeScript/build, OpenAPI syntax, browser smoke (including persistent
Grok/Codex dropdown) and live production UI/API checks passed. A real tiny call
confirmed the Grok OAuth privacy-mode 403, then successful automatic Codex fallback
at low effort, with actual-provider metadata retained. Modeled subprocess tests
cover successful Grok structured output, low/medium effort, fixed 4.6 model,
subscription environment, tool restrictions, cache separation, cooldown/recheck,
reverse fallback and waiting for timed-out Grok to exit before Codex starts.
Real Grok generation remains unverified until the user resolves the account mode.
The user's catalogue queue remains paused; no catalogue batch was auto-started.


### Workshop 0.5.1 Bessie validation/retry diagnosis

Observed three medium source calls of 87–148 seconds and three low writing calls
of 140–153 seconds. These all completed; the full draft retried due to our
validation, not a hung Grok process. elements=[] correctly represented no elemental
options but the source-use validator demanded non-empty output; variants=[] had
the same issue. Accept a cited explicit absence for elements/variants/parts/sources,
without relaxing required numeric ranges. A scope FOV percent was also attributed
to a captured WeaponPartDefinition but lacked the literal word modifier. Recognize
that exact captured-part attribution, while still requiring the numeric value in
public mechanics/part text. Both cases have regressions; the saved Bessie response
passes all 83 fact checks, schema, copy checks and part validation without AI.

History now records the actual validation error. Source progress says page N of M
and extraction attempt; writing progress says draft attempt; prose repair is named
explicitly. Two processes had the real SQLite project open with divergent in-memory
states. Stop the stale dev process and production server before restart, preserving
the latest on-disk project checkpoint and refreshed source captures. Do not overwrite
newly captured sources with the older cached draft just to mark it complete. The
latest saved state stays paused for user resume; raw captures/HTML and cached model
responses are retained. Run only one app instance for this project.

0.5.1 verification: 60 local tests passed; 2 optional HTTP simulations skipped.
TypeScript/build and API syntax passed. The archived real Bessie response passes
all four validators, including all 83 source facts, without new AI. Production is
restarted as a single database owner, with the latest refreshed wiki/Lootlemon
captures retained and queue paused. Historical sources/AI results remain archived.


### Workshop 0.6.0 local Ollama option

User installed Ollama and gemma4:e4b-mlx, and requested it as an additional agent.
Agent enum/settings/UI/API now include ollama; keep the existing Grok default
until the user chooses otherwise. OllamaRunner uses only loopback HTTP (default
127.0.0.1:11434, optional BORDERLENS_OLLAMA_URL for local protocol simulation).
Pin gemma4:e4b-mlx, never download or substitute models. /api/tags confirms the
installation; /api/show provides context length and supported thinking values.
The real installed 0.40.4 server advertises boolean thinking and 131072 context:
writing => think:false, analysis => think:true; do not send unsupported low/medium
strings. POST /api/chat uses Zod JSON schema format, NDJSON streaming, temperature
0, no tools, bounded generation and explicit context capacity. Conservatively
reject input exceeding the context budget rather than truncating evidence.

Track activity/events and final runtime statistics; validate all output before
caching. Abort/cancel a timed-out HTTP request, never kill the user's Ollama daemon.
The same catalogue validators still apply. Local inference has no live web tools:
source discovery skips Ollama and uses an available subscription provider. Ordered
fallback tries each available provider once; Ollama preference may fall back to
Grok/Codex. Disclose this in Settings/README; do not claim the whole pipeline stays
offline. Existing model setting remains Codex-only; no field-shape/compiler change.

postman/simulations/ollama.sim.yaml models official tags/show/chat HTTP contracts.
Run with port 4326, then BORDERLENS_OLLAMA_SIM=http://127.0.0.1:4326/ollama pnpm test.
Its handlers support Postman's pre-parsed req.body. This checks the real client's
streaming, schema validation, cache, HTTP failure, timeout and size/search guards.
Do not publish mock/workspace data. tests/live-ollama.ts uses Ollama directly,
without cloud fallback or writes to the real project; --bessie uses the archived
full request and preserves private diagnostics under temp/ollama-live-*.

0.6.0 live results: local warm tiny JSON request passed in ~0.7s (first model load
was ~16s). A full archived Bessie request initially ran for 260s, emitted repeated
whitespace partway through JSON and hit 16000 output tokens; reject incomplete
output. Compact-JSON prompting plus an early repeated-whitespace guard was added.
The compact full request returned schema-valid JSON in 199.9s, but failed semantic
validation: 82 of 83 facts accounted for, duplicate family part reference and
specialEffects exceeding 45 words. No local output was published or installed in
the real project. Do not claim this model is faster/reliable for complete family
compilation; keep the option for experimentation and report the benchmark honestly.

65 local/protocol tests passed, 2 optional research simulations skipped; TypeScript,
build, OpenAPI syntax and browser smoke passed. Postman logs confirm real HTTP to
tags/show/chat, including schema failure, HTTP error, timeout and whitespace-loop
cases. Existing Grok preference and paused queue are retained. The current API
reports Bessie.issue=null: the screenshot repeats a historical error banner.


### Workshop 0.6.1 removal of the local experiment

User explicitly instructed removal if Gemma was not up to catalogue quality.
The full test already demonstrated failure, so remove Ollama completely from the
active app: enum, selector/status cards, router/fallback, HTTP adapter, protocol
mocks and live/test harness. Keep historical benchmark artifacts and release notes;
do not uninstall or delete user-managed Ollama models. Only Grok/Codex remain,
with their existing five-minute limits, bounded fallback and cooldowns. Grok stays
the default. Invalid/removed saved provider preferences migrate to Grok, preserving
other settings and user work. No model calls or catalogue rebuilds are needed.
This section supersedes the 0.6.0 implementation guidance above; do not restore
Gemma merely because its old benchmark scripts or cache files exist under temp.

0.6.1 verification: 61 tests passed, 2 optional research simulations skipped;
TypeScript/build, browser smoke and API syntax passed. The toolbar offers exactly
Grok/Codex; invalid/removed provider preferences migrate safely to Grok. Production
was restarted with the user's Grok preference and paused queue preserved. The
retired local adapter and its mocks/harness are absent from active source code.

### Workshop 0.6.2 source usage and focused modifier repair

Source-usage validation must check field presence and a matching source-page claim,
not truthiness/nonempty arrays or absence keywords. A cited fixed-parts source can
legitimately support variants: []. Missing fields and missing citations still fail.
Numeric range/modifier, part, schema and originality checks remain enforced.

MissingCatalogueStat carries the precise missing fact. For modifiers explicitly
attributed to a captured, referenced part and saved source page, worker validation
can request a low-effort rewrite of just the relevant mechanics paragraph. Save
the repaired draft and rerun every validator, with at most three focused repairs.
Do not infer final weapon-card stats from accessory modifiers. Unattributed stats
retain the normal validation failure/retry path. No schema/compiler upgrade or
completed-entry requeue is needed.

Live Bessie recovery: resumed its saved validate-stage draft, preserved refreshed
sources and used one short Grok call to include the omitted +30% scope damage
modifier. Entry is done, issue=null, website output saved; no full build repeated.
Verification: 62 tests passed, 2 optional research simulations skipped;
TypeScript, production build and OpenAPI syntax passed.

### Workshop 0.7.0 public catalogue refinement

Internal schema 4 / compiler 0.5.0 adds nullable stat context and player count,
and keeps probability conditions as arrays. Website schema 5 groups acquisition
identities into one source with dropChances[] (percent, players, conditions[]).
Unknown player counts remain null; no implicit solo assumption, highest-rate
selection, rounding or merging distinct locations. Preserve edition/player/other
conditions for every rate and reject contradictory probabilities for identical
scopes. Conditions on unknown-rate rows are preserved as distinct source entries
when necessary. Preview uses the same grouping; manual website JSON round-trips
the condition arrays losslessly. The first retained source URL is a link only,
not a reason to select a probability; full provenance stays private.

Repeated stat names at the same level require distinct evidenced contexts such
as Card and While scoped. Preserve source stat names/ranges; never label card
accuracy as a percentage without support. Use meaningful units only when known.
Website levels/stat/source notes and inline familyNotes omit empty strings;
internal storage keeps these as strings for strict AI synthesis. Unknown level
bounds remain null, never inferred from example card damage.

Shared quality instructions cover all equipment and source reading/synthesis:
original AI wording, player language, useful supported numeric part effects,
no raw part/material IDs, numbered engine scopes, Zoom End FOV constants or
title-link explanations. Keep internal FOV constants in the private source ledger
with an explicit exclusion reason. Vague damage/one-shot benchmarks lacking
reproducible build requirements also remain private, while useful supported
mechanics and trivia remain available. Description has no required paragraph
count; avoid repeated facts across overview/mechanics/notes. Numeric modifiers
explicitly attributed to captured parts must appear in that part's effects;
focused repair can update effects and mechanics together. Known generated shared
parts may be enriched with verified modifiers; manual edits stay local.

Upgrades preserve raw ZIPs, pages, outputs and manual corrections, queue older
generated output, and clear obsolete retry counters. No automatic live model
rebuild was launched for this release; rebuild Bessie to generate new prose and
schema. Its prior output and both source pages were verified retained after
restart. Local verification: 65 tests passed, 2 optional research simulations
skipped; TypeScript, production build, browser smoke and OpenAPI syntax passed.
The focused tests exercise grouped probabilities, conflict rejection, precision,
unknown-rate conditions, optional notes, API/manual-edit round-trips, contextual
stats, public wording checks and attributed modifier repairs. These checks do
not establish the historical correctness of every sourced weapon claim.

### Workshop 0.7.1 focused stat role repair

Compiler 0.5.1, app 0.7.1; internal/public schema shapes remain 4/5. Sources can
describe a base bonus, a multiplicative component and a resulting total with the
same stat name. These are distinct quantities, not contradictory alternatives.
The writer must preserve all such useful numeric facts with distinct context
labels, even when mechanics also explains them. This supersedes any implication
that one stat row per name is sufficient.

StatContextError identifies an ambiguous group. MissingCatalogueStat still
identifies a precise omitted value. Before spending another full draft attempt,
repairCatalogueStats gathers the used, nonexcluded numeric facts for that name,
checks their source pages, and makes a low-effort label/notes-only model call.
The model returns fact IDs and original player-facing contexts/notes; code copies
the exact names, units, levels and numeric bounds from the existing ledger. No
model arithmetic or replacement numeric values are accepted. Corroborating rows
can merge only when their numbers and contexts match; different quantities cannot
share a role label. Reject missing/extra/duplicate fact IDs. Update the stats claim
and per-fact field accounting, save the draft, then rerun every validator.

Explicit captured-part modifiers retain their existing dedicated repair path;
do not promote them into final card-stat ranges. Identity, source captures,
description, mechanics, parts and unrelated stats are preserved by context repair.
Limit stat repairs to two per item run; clear their counter on invalidation.
Manual entries, unresolved conflicts and requiresReview entries remain protected.

Paused 0.5.0 validate-stage drafts with the same schema can migrate compiler
metadata to 0.5.1, including their part definitions, only after strict Draft
validation. Archive the original draft first. Preserve the source ledger and
queue; do not restart research or invent migration prose. Other old outputs
follow the usual retained-output/requeue behavior.

Live Bessie: the third draft already contained 150%, 200% and 500%, but all three
contexts were null. One small Grok label repair restored distinct component/base/
total labels; schema/content, part and full source-usage validators all passed.
Saved the repaired validate-stage draft and left the queue paused. Resume saves
the existing draft; Rebuild would unnecessarily restart generation.

0.7.1 verification: 67 tests passed, 2 optional research simulations skipped;
TypeScript/production build, browser smoke and OpenAPI syntax passed. Live local
API checks confirmed all three distinct stat values/contexts, both saved source
pages and the paused validation checkpoint. The worker regression also verifies
focused recovery after both full-draft retries have already been exhausted.

### Workshop 0.8.0 local item images

User-provided raster library is app/img/borderlands/<type>/<filename>. Support
PNG, JPEG, WebP and AVIF; never edit those originals, download replacements or
bundle images into the website ZIP. Website schema 6 adds required image:
relative path or null. Internal schema remains 4; compiler becomes 0.6.0. Images
are resolved by the filesystem-owned app/export layer, never invented by AI or
added to game/source claims. A filename change or manual image choice does not
require a rebuild. Existing older generated entries follow the normal retained-
output/requeue upgrade; same-shape validate drafts can retain metadata-only
migration from compiler 0.5.0/0.5.1.

Images matches exact canonical slugs in the candidate's category, then normalized
punctuation/spacing, then aliases. Do not fuzzy-match unrelated names or choose
the first ambiguous file. Other equipment, whose raw category can be unresolved,
can use a globally unique name match; multiple matches still require review.
Store manual paths (including an explicit null) separately by stable family ID
in .data/image-overrides.json. This survives imports, reclassifications, restarts
and generated resets. Automatic mode removes the manual entry. A deleted chosen
file becomes missing, rather than silently selecting another image. Full reset
clears overrides but never deletes app/img/borderlands.

GET /api/images returns file paths, a content revision, per-candidate matches and
matched/missing/ambiguous counts. Excluded candidates are omitted; this is a
candidate audit, not proof that all captured names are obtainable items. POST
/api/items/:id/image saves a valid local choice or restores automatic matching;
it does not invalidate research/output, invoke AI or touch the processing queue.
GET /api/images/file/:folder/:filename serves indexed raster files with no-cache
revalidation. Enforce the path schema, known type folders and realpath containment;
do not follow symlink files or escaping folder symlinks. Missing/unsafe files get
404. Item detail also includes image metadata for unbuilt candidates.

Preview places a contained image on a white stage with path/match status, a clear
missing/load-error placeholder and a collapsible image selector. Coverage includes
a separate Image coverage section, defaulting to missing/ambiguous, searchable by
name/category, with links to items and expected paths. Refresh rescans files;
regular polling updates image revision and item details without overwriting dirty
JSON edits. Website/manual JSON round-trips retain the chosen path. ZIP export
contains only item JSON, with image paths kept relative to the website's base URL.

0.8.0 verification: 70 tests passed, 2 optional research simulations skipped;
TypeScript/production build, browser smoke and OpenAPI syntax passed. Browser
checks load actual images, change/restore a match without changing the run, and
open Bessie through Image coverage. API tests exercise asset bytes/content type,
missing/unsafe paths, overrides, manual JSON/export agreement and reset behavior.
Live read-only API checks found 216 files, 181 matched candidates, 74 missing and
no ambiguous matches. Those 74 include unreviewed raw candidates, not necessarily
74 obtainable items. Bessie resolves to weapons/bessie.png; previous output and
both source captures are retained. No live AI rebuild was started.

### Workshop 0.9.0 fact accounting and rebuild source modes

App 0.9.0 / compiler 0.6.1; internal schema 4 and website schema 6 remain unchanged.
sourceUsage accounts only for extracted page FACT IDs, not game:, manual: or page-
level evidence IDs. Before validation, separateEvidenceUsage removes ONLY known
game/manual IDs actually present in the packet and retains their records in the
private additionalEvidenceUsage artifact. Do not delete unknown IDs, synthesize
missing rows, collapse duplicate page rows or weaken source/part/numeric checks.
Real accounting failures name missing, duplicate and unexpected IDs plus counts.
Writer/schema instructions explicitly distinguish claims from page-fact usage.

UI labels are exactly Rebuild from saved sources / Rebuild from fresh sources.
The primary action uses saved sources when pages exist; dropdown exposes both,
with saved disabled when no pages are present. Public actions are rebuild-saved
and rebuild-fresh; legacy rebuild keeps prior behavior. GET item detail reports
savedRebuild availability/reason. Images and manual output remain protected.

Saved mode starts at draft: no coverage scan, source discovery or HTTP fetching.
savedSourceCache checks current page IDs/hashes, complete source/chunk coverage,
strict reading shape, exact fact IDs/content, and the evidence/correction snapshot.
Source analysis can be reused across model/agent/compiler changes if compatible.
SourceLedgerInput records the packet fingerprint after a complete read; legacy
ledgers can use the last inputHash when it still matches. A source nonce/cache key
also includes the individual source ID, preventing identical-content pages from
silently sharing page-specific analysis. Saved pages remain usable if analysis is
absent/stale: read the necessary saved data without any HTTP. Classification may
still run against saved evidence when the item's identity/type needs resolution;
already classified Bessie skips that step. Complete matching ledgers skip source
reading entirely, so agent comparisons synthesize from the same facts.

Fresh mode starts at evidence, skips the unrelated catalogue-wide coverage scan,
and forces HTTP refresh of known pages (or discovery for missing providers).
Successful fetches replace current same-URL references; historical HTML stays on
disk. Failed refreshes keep the stored page and block rather than pretending old
data is fresh. A fresh-request timestamp identifies pages refreshed/captured after
the request, allowing Chrome imports to satisfy blocked pages on Resume. The
request nonce forces fact-reading passes for the refreshed corpus. Preserve
rebuildPlan and pendingRebuild mode/timestamp for queued and interrupted work.
Deferred preparation failures become a visible blocked state, not an unhandled
worker promise. Same-shape 0.6.0 validation drafts receive metadata-only migration
with an archived original; the queue and source ledger stay preserved.

Verification: 78 tests passed, none skipped with the existing local Postman
research simulation enabled. Logs confirm real application HTTP requests to the
stand-in source pages, including 200 refreshes and 503 failure preservation; no
live wiki/Lootlemon fetch or production model rebuild was performed. Tests cover
agent/model-independent saved reuse, missing-analysis reads without fetching,
fresh fetch/read behavior, deferred saved mode, and exact accounting failures.
TypeScript/build, browser smoke and OpenAPI syntax pass. The live app remains
paused with Codex selected; both Bessie pages and previous output are retained,
and savedRebuild confirms complete facts are ready without another source read.

### Workshop 0.10.0 whole-document validation and public consistency

App 0.10.0 / compiler 0.7.0. Internal schema 5 and website schema 7 enforce the
same element enum across all equipment: Non-elemental, Incendiary, Shock,
Corrosive, Explosive; unknown stays []. Do not publish None or lowercase aliases.
This is a schema upgrade: archive older drafts and retain output/corrections for
rebuilding rather than relabeling incompatible data as current. Source readings
have unchanged shapes, so matching saved analysis remains reusable.

cleanPublicEntry removes stat notes only when they repeat the structured number/
range/unit (allowing formatting differences), retains notes with additional facts,
and translates the context label scale to Multiplier. It never rewrites human
sentences or changes the numeric values. Acquisition grouping recognizes only
explicit edition/player qualifiers in labels, keeps their conditions, preserves
the first original spelling for equivalent conditions, and groups the source.
Pure player text can map to players only when explicit and unambiguous; conflicting
counts fail. Remove common edition conditions from rates and redundant player
conditions already represented structurally; never round or select probabilities.

assembleWebsiteEntry creates the exact self-contained consumer object from the
validated entry, inline parts and local image match. validateWebsiteDocument runs
the strict WebsiteEntry Zod schema and cross-field checks: numeric bounds, canonical
weapon types/elements, unique contexts/parts/sources, URLs, condition/player/scope
consistency, unsupported scalar probability ranges, original-only edition claims
and public wording. serializeWebsiteDocument serializes that complete object and
parses/validates it again. The generated worker invokes this before promoting any
output; API/manual-save and export paths reuse the same checks. ZIPs still contain
only per-item JSON. This validates schema/consistency, not every historical gameplay
claim independently; existing source usage, evidence, numeric and part checks stay.

Successful checks create private finalValidation metadata and a Preview badge;
the stage label is Validate final JSON. No validation/provenance flags are added
to public files. UnclearPublicProse identifies vague unnamed scope comparisons
or listing commentary. A bounded low-effort repair rewrites only that exact prose
slot in original words without inventing a baseline or altering numeric facts,
then reruns every validator. Manual text is not silently rewritten. Malformed
manual HTTP JSON gets 400 and cannot replace prior valid output.

Live Bessie recovery used the existing Codex draft, source ledger and captures.
Confirmed its stored JSON was already syntactically valid (the user's pasted
quote formatting differed). Updated schema/compiler metadata on a strictly parsed
candidate, applied deterministic cleanup, made one short Codex wording call for
the scope, and passed all evidence/source/part/final-document checks before saving.
Numeric ranges and 0.143%/0.159% Crawmerax rates are unchanged; root edition/DLC
conditions remain, and the rates use players 1/4 without duplicate text. Saved
analysis is still available without source fetching or rereading. Prior data is
archived; no fresh source fetch or complete model rebuild was performed.

Verification: 83 tests passed with the existing Postman research simulation,
none skipped; TypeScript/build, browser badge/flows and API syntax pass. Tests
cover quoted text and malformed JSON, all equipment categories, enum enforcement,
value-only note cleanup, missing parts, reversed bounds, duplicate/conflicting
contexts and rates, and blocking bad final data before promotion. The live ZIP
is parsed with the same whole-document validator, alongside read-only local API
assertions. Simulation results establish source HTTP behavior against existing
stand-ins; they do not claim a new live wiki/Lootlemon fetch.

### Workshop 0.11.0 batch source controls

App/API version 0.11.0; catalogue compiler remains 0.7.0 and schemas remain 5/7.
No catalogue fields or writing instructions changed, so completed items must not
be requeued or regenerated by this upgrade. The top run control adds Start from
saved sources / Start from fresh sources. Saved is the initial/default API choice;
the primary button reflects the current run's saved/fresh mode when starting a
new batch. Pause/Resume remains the primary action during active/paused work.
The dropdown is unavailable while running. While paused it explains that Resume
keeps the checkpoint whereas starting a new batch restarts unfinished work.

POST /api/run accepts sourceMode saved|fresh only for action=start; omitted mode
defaults to saved. Reject starting a new batch while a worker is active (409),
and reject mode fields on pause/resume (400). Both batch modes retain existing
unfinished-item ordering, maxItems limit and completed/excluded skipping. Starting
fresh does not rebuild already-completed items; use the per-item rebuild action
for those. No batch was started on the user's real catalogue for verification.

Run.sourceMode stores saved|fresh|auto and Run.sourcePrepared stores the IDs whose
source policy was already initialized. Saved batches choose the existing saved
rebuild path when an item has pages, otherwise fresh; this is per-item fallback,
not an instruction to refetch missing providers on already-cached items. Missing
or stale analysis for saved pages follows the existing saved-page reading rules.
Fresh batches choose the existing fresh rebuild path for each unfinished item.
Initialize policy exactly once before the first step and persist the marker
before processing; Resume must not invalidate the checkpoint or reset freshSince.

Older runs missing these fields migrate to auto plus an empty prepared list.
Auto preserves legacy/single-item behavior and must not reinitialize old active
checkpoints. Per-item rebuilds continue to use their explicit rebuildPlan. Deferred
individual rebuilds are marked prepared after their own mode is applied, so the
batch policy cannot overwrite a requested saved-item rebuild in a fresh batch.
Generated reset restores default batch metadata; source/page/JSON data stay
governed by the existing reset rules.

Verification: 89 tests passed with the existing local Postman research simulation,
none skipped. Added cached/uncached mixed-batch tests for both modes, completed-item
protection, fresh checkpoint recovery across process restart, strict API modes,
legacy run migration and deferred mode overrides. Browser checks exercise the
batch dropdown, select fresh, pause and reload to Resume with the mode retained.
TypeScript/build and OpenAPI syntax pass. These are isolated/fake-agent and local
HTTP simulation checks; no production model call or live-source batch was run.


### Workshop 0.11.1 image-folder refresh

Add Refresh folder inside Change image. Fetch GET /api/images with no-store,
update the shared image-library state, and show local loading/success/error
feedback. Do not mutate run state or use the global working lock. Preserve dirty
JSON edits and selection while the background batch continues.

Scan safe actual top-level subdirectories under the configured image root, not
only the category-folder whitelist. Retain safe folder/filename raster paths,
realpath containment and symlink exclusion. Allow arbitrary safe folders for
manual selection, plus singular artifact as an automatic Artifacts alias. Do not
rename user files. The image API response disables caching. App/API version
0.11.1; compiler 0.7.0 and schemas 5/7 stay unchanged to preserve active work.

Verification: 11 focused image/export/document tests passed, plus build and
browser smoke. Browser checks add a new folder during a running fake batch,
refresh the picker, verify the new option, preserve dirty JSON and leave the run
active. HTTP checks verify new folder indexing, raster bytes, no-store, symlink
exclusion and unchanged active run state. User batch checkpoint-paused for the
service update and resumed with its saved-source mode and queue intact.


### Workshop 0.12.0 character equipment and unattended batches

Discovery must be category-aware: class mods use their meaningful prefix linked
from a body part selected by a character-restricted ItemDefinition. Include
enabled fixed BodyPartData collections (DLC custom items), where zero default
weight does not mean a forced part is unavailable. Use RequiredCharacter 1/2/3/4
for Roland/Mordecai/Lilith/Brick. Merge manufacturer variants of the same named
family for one character. Preserve defining prefix, body, item, custom collection
and balance evidence. Current capture yields 44 named class mods. Artifacts use
the character-restricted item and right-side element parts: 16 families, four
elements per character; ranks belong within each family. Do not treat a generic
Class Mod, Loyalty Mod, manufacturer Enhancement Mod or Artifact title as a
standalone family. Discovery IDs include category, character and family name.

Family metadata has optional character/element/discoveryVersion. Character is an
optional typed PublicEntry/WebsiteEntry field, set authoritatively from the game
restriction during drafting/validation. Existing schema5/website7/compiler0.7.0
remain valid; no weapon rebuild is needed. Research prompts include the character
and element and warn against mixing sibling bonuses. Export same-name families
using character-qualified slugs. Sidebar groups Class mods/Artifacts, then
character, then item. Character participates in search, sorting and the inspector.

At import/startup reconcile new families and retire old broad candidates as
excluded with supersededBy IDs. Keep their sources, drafts, corrections and
outputs privately. Do not transfer a broad generated entry as a verified named
family. Completed weapon entries and raw captures remain unchanged. Remove old
IDs from pending work and add newly discovered families to the pending queue;
pause if its current placeholder is retired. Never automatically start paid work
as part of migration. Startup remains idempotent.

Run.continueOnError is true for batch starts in either source mode, false for
individual work. Old multi-item queues infer true. On item failure save blocked
status, issue and history, advance the index and continue; honor pause at the next
checkpoint. Single-item failures retain blocked run status. Deferred rebuild
preparation failures also continue for batches. Failed items remain selectable
with red X and Needs attention filter; completion reports the failure count.
Starting another batch retries unfinished/blocked entries while done/excluded
entries stay skipped. Pause/resume retains this behavior.

Verification: full local suite passed (92 tests, three unchanged external research
simulation tests skipped); production build and real-capture browser smoke
passed. Browser imports 299 active families and checks four character subgroups
inside both categories. Batch saved/fresh tests exercise the actual local HTTP
start endpoint with an injected failing step and prove later items finish.
OpenAPI syntax passes. Local migration was backed up and checked against the
original SQLite database: every weapon metadata record and every raw/source/
generated-artifact row is unchanged. The existing blocked batch becomes paused
with 297 pending entries, including the new families; no agent work auto-started.


### Workshop 0.12.1 writer schema and fallback history

PublicEntry.character remains optional for old data. Do not send that optional
field directly in a Codex response schema: all properties must be required.
WriterDraft extends Draft with entry.character required-nullable (Zod default
null accommodates older fake/cached entries). Parse the returned draft through
Draft with the character replaced by Family.character; artifacts also retain the
known element. The model cannot override the captured character restriction.

AgentRouter records failure switches and cooldown skips in the current family's
History, with task label, reason and cooldown timestamp. Ordinary heartbeats stay
only in live progress. ai/agent-failures.json retains the last provider errors;
per-call CLI directories retain schema, events and stderr. Schema/compiler
versions stay unchanged. 36 focused tests passed, three unchanged external HTTP
simulation tests skipped. Schema test recursively checks required properties;
fallback test checks both failure and cooldown History persisted to SQLite.


### Workshop 0.12.2 quotation presentation matching

The source reader compares chunks containing JSON-serialized sections/tables.
Codex may quote a displayed newline while the packet contains literal backslash-n.
sourceQuoteMatches canonicalizes only JSON layout/quote/backslash escapes and
whitespace/case, preserving words/numbers/punctuation. Do not use fuzzy matching
or silently discard unsupported facts. Repair errors now identify the actual
rejected quote and chunk. Source-reader prompts include the character/element.
No compiler/schema bump or global source-reading invalidation is needed. Twelve
source-analysis tests pass, including altered manufacturer/number rejection.
All 13 facts from the actual failed Support Gunner reading match after this fix.


### Workshop 0.12.3 class-mod rarity and regeneration semantics

Source/writer scope must retain category-wide rules that genuinely constrain the
family (rarity tiers and skill combinations), while still excluding shared farming
boilerplate. A Lootlemon Epic tag is not an exhaustive rarity restriction. Consult
applicable class-mod rules plus family selection exceptions, not a universal
hardcoded rarity list. Writer instructions distinguish a card regeneration bonus
from weapon-specific maximum /s rates, and acknowledge wearer/solo benefits.
cleanPublicEntry labels a class-mod ammo regeneration stat with blank unit and
generic Team bonus context as Card bonus; numeric values and explicit /s stats
are unchanged.

Reviewed Support Gunner directly against saved Wiki/Lootlemon: rarities Uncommon,
Rare, Epic; +2..25 Card bonus; weapon-type /s contexts marked maximum rate; original
solo/co-op wording. Add the saved Wiki rarity evidence claim and a persistent user
correction; preserve the original draft/output privately and retain manualOutput
false so later builds can still incorporate new research. Full draft/source-usage/
final JSON validation passed without a model call or refetch. Nineteen focused
policy/document/source-reader tests passed. No compiler/schema version change.


### Workshop 0.13.0 per-item revision metadata

Website schema 8 requires revision: positive integer, placed after schemaVersion
and compilerVersion. This is the existing persistent Family.revision counter,
not an AI-invented field and not a counter for each CLI call. Successful validated
builds/saved edits increment it exactly once. Failures, retries that have not
saved output, browsing, downloads and pause/resume do not increment it. Export
uses Family.revision (legacy zero baseline treated as one for ready entries);
prepromotion validation uses revision+1. Manual website-to-internal conversion
strips submitted revision, so users cannot spoof/reset the counter in JSON.

Internal schema 5/compiler0.7.0 remain unchanged, retaining existing completed
entries and their recorded counters. No scrape, source reread or model rebuild
is needed to expose the metadata. Final document validation orders all three
version fields first. Documentation distinguishes shared format changes from
compiler rule changes and successful per-item saved versions. Thirty-two focused
export/schema/character/manual-edit tests and build passed; explicit checks cover
repeat exports, persistence, and an attempted manual revision override.


### Workshop 0.14.0 Lootlemon-first conflict decisions

Use all saved sources. For genuine like-for-like Wiki/Lootlemon contradictions,
prefer the verified Lootlemon fact. Applies across rarity, stats, timers, effects,
manufacturers and acquisition; do not let speculative raw constants overturn
the decision. User corrections and captured family identity/restrictions remain
authoritative. Distinguish complementary ranges, maximum rolls, editions, player
counts, levels and conditions. A page Epic tag does not contradict a supported
broader set of class-mod rarities. Unrelated Wiki details must remain included.

Draft.sourceUsage supports disposition overridden. Reuse duplicateOf as the
exact USED preferred Lootlemon fact ID; fields must be empty and reason must
explain the same-scope conflict. Validate Wiki -> Lootlemon direction, same field,
known target actually used, exhaustive accounting and no suppressed Wiki rarity
or stat value left in public output. Preferred numeric facts must still pass
normal preservation checks. Keep the source HTML/facts unchanged and record
sourcePolicy lootlemon-first-v1 in the private research audit. Public JSON never
contains disputed-source commentary. No new public field or schema bump.

Resolved disagreements do not set requiresReview/conflicts/reviewReason. If a
draft still flags source conflicts and both providers exist, permit one bounded
policy-aware rewrite before failing. Do not merely clear flags. Same-provider or
identity conflicts still fail if unresolved. Invalidate clears the policy-repair
marker. Existing source ledgers remain valid; no scrape/re-reading/global item
reset needed. Keep the paused batch and enqueue MIRV for a saved-source retry.

Verification: full suite 100 passed, three unchanged external research simulation
tests skipped. Added direct rarity/timer conflict tests, reverse/unknown/unused
priority target rejection, complementary Wiki fact accounting and bounded
policy-aware rewrite validation. Build, TypeScript, OpenAPI syntax and diff checks
pass. Saved MIRV's old rejected draft, queued it immediately after the current
item for a saved-source retry, and retained the batch pause/checkpoint. No live
agent/source call was started as part of this update.

Also corrected a discovered restart bug: character-family reconciliation sorted
pending work even when no new families existed. Sort only during genuine family
addition; regression test verifies an arbitrary pending order/current checkpoint
survives reconciliation. Restored the original pending order from the pre-update
backup, with MIRV inserted just after the current item. Six character/batch tests
and TypeScript passed after the fix; API confirms paused/current/next alignment.


### Workshop 0.15.0 reversible catalogue removal

Reuse excluded status for deliberate removal. The API accepts remove/exclude and
restore. Remove saves previous status/stage/issue in the private removal artifact,
marks excluded, drops deferred rebuild requests and retains raw/source/output
data. A repeated removal is idempotent. Reject removal of the active in-flight
item; future items may be removed while another runs. Existing queues skip them,
and no model call is started. Guard excluded item mutations/rebuilds until restore.

Restore rejects obsolete superseded placeholders. Restore ready status only if
complete/current output remains; preserve prior blocked issue when stage still
matches; otherwise queued, restarting missing complete output at evidence. Restore
never auto-starts a build. Pending active/paused queues may append restored
unfinished work. Reimport preserves status; refreshImported must skip excluded
families. Generated reset preserves removal; restore after reset queues missing
output. Full data reset intentionally clears the project.

Normal sidebar filters omit excluded items. A separate Removed items link/count
lists deliberate exclusions, excluding internal superseded placeholders. Preview
inspector shows a red remove button or a restore button/retention explanation.
Rebuild/start-from controls are disabled for removed selections. Selection adjusts
when removing/restoring or entering/leaving Removed items. No irreversible delete
or confirmation modal is needed. Removal state is in workshop.sqlite, not the raw
ZIP. The six gd_StorageDeckUpgrade.Title.Title_Level_1..6 candidates are SDU name
modifiers, and are deliberately removed using this facility, remaining restorable.

Verification: full suite 104 passed, three unchanged external research tests
skipped; build/TypeScript, browser smoke, OpenAPI syntax and diff checks pass.
New local HTTP tests cover removal/export exclusion, retained source/output data,
restart/reimport persistence, rebuild guards, safe removal of future items while
busy, current-item protection, and restore after generated reset. Browser checks
exercise Preview removal, disappearance from normal navigation, Removed items
inspection and restoration. Removed the six SDU level labels through the same
worker action without model calls, leaving the user's batch paused.


### Workshop 0.15.1 equipment category correction

Weapon subtype classification previously did not change top-level categories.
DLC item title paths such as Ironclad/Omega/Rose fell into Other equipment, and
the writer was locked to that category despite shield research.

equipmentCategoryCandidate accepts Other equipment families only, excluding
removed/superseded/manual-classified items. Require a saved Lootlemon exact
/shield|grenade-mod/<name-or-alias>-bl1 route AND matching name + BL1 + type in
the archived article title. Conflicting typed candidates remain unresolved; no
name-only guesses, navigation inference, image-folder inference or model call.

ClassificationOverride gains optional category and nullable weaponType for
equipment; existing schemaVersion1 override files remain compatible. The model
weapon ClassificationDecision stays strict and unchanged. Category overrides
are authoritative in classification-overrides.json. Family.rawCategory/rawSubtype
preserve native grouping; stable IDs/roots never change. Store applies effective
category/subtype and adjusts draft/manualDraft/packet category metadata; completed
entries queue validation when a saved draft exists, otherwise drafting. No output
is promoted until normal validation passes. Removing an override restores native
category. Manual overrides win. Reimport/reset retain the file and effective view.

Worker classifies after sources are available and before writing, rebuilding the
packet for the effective category; saved source cache hashes then naturally
request category-specific analysis on future rebuilds. Correct category controls
sidebar, inspector, source checklist, images, Final JSON and export folder. The
three unknown DLC shield IDs remain stable even though the IDs contain the old
category name. No public schema or compiler version change is needed.

Verification: 107 unit/integration tests passed, three unchanged external research
tests skipped. New tests reject generic/wrong-game/mismatched typed pages, respect
manual/removal priority, retain stable IDs on reimport/restart, verify shield
export paths and revalidate ready content without model calls. Build/TypeScript,
OpenAPI syntax and diff checks pass. Browser smoke confirms an actual imported
Ironclad moves from Other equipment to Shields with its stable ID and correct
Final JSON category. Browser fake source readings now use the effective category;
API waits use awaited expect.poll rather than async waitForFunction predicates.

Applied the saved-proof correction to Ironclad (ready, revision2, categoryShields)
and Omega (queued at validation, categoryShields). Kept the paused Omega checkpoint
and all source data. No fresh fetch/AI rewrite was used for these corrections.
Rose has no saved typed proof yet and will be handled when its item source exists.


### Workshop 0.15.2 sidebar group progress

GroupStatus renders one compact blue done / red blocked / muted total capsule
for every main category and nested character group. It uses the group's current
visible items, preserving existing search/status-filter count semantics. Queued
and running counts appear in the native hover title and accessible role-img
label; excluded counts appear when browsing Removed items. Zero values are muted.
Entirely complete groups have a subtle blue border/background; attention groups
have a subtle red border. Tabular numerals and non-shrinking inline-flex layout
keep columns tidy. Badges remain inside the existing collapse button, without a
new tab stop or behaviour change. Counts update from the normal live state feed;
no backend/source/compiler changes, new polling or model work.

Verification: TypeScript/production build passed. Inspected the live sidebar in
an isolated headless browser, including collapsed/expanded character groups.
Actual examples rendered 1/0/16 for Artifacts and 1/0/4 for Brick, with hover
counts showing the remaining queued work. Screenshot checked for compact layout
and legible status colours; no browser errors. No worker pause/restart or model
call was needed; the active user batch remained running.


### Workshop 0.15.3 sidebar tree navigation

familyTreePath returns the catalogue group plus character key for class mods and
artifacts. Selecting opens all ancestors; Current item also clears search/status
filters and sets a pending reveal. After rendering, scroll the matching stable
data-family-id row into view. Repeat selection of the same ID must still reveal
it. Selection/category changes open the path, but ordinary progress updates must
not reopen manually collapsed groups. Existing collapse preferences persist.

Collapse/Expand toolbar controls apply to the currently visible tree. Collapse
closes deepest visible child groups first, then all root groups and normalizes
their hidden children closed. Expand opens closed parents first, keeping their
children closed and preserving already-open branches; the next click opens
children. Step functions never mutate previous state or unrelated saved keys.

Busy run/current family determines active ancestor keys independently of selection.
Show one small spinner on each visible active group header; collapsed root/group
headers retain the signal. Paused/blocked/complete runs do not spin. Counters keep
their existing filtered semantics. Group toggles expose aria-expanded; toolbar
icons have labels and level-order tooltips. No worker restart, backend API or
source/schema/compiler changes.

Verification: four navigation tests cover depth ordering, mixed open branches,
immutability and full ancestor reveal. TypeScript/build and diff checks pass.
Read-only browser checks exercise stored nested selection, staged toolbar actions,
filter clearing and current-item scrolling. An isolated UI state fixture verifies
active ancestor spinners with root/child collapsed and repeated jump to the same
ID; asserted zero write requests. Screenshots inspected for toolbar/spinner layout.
No active user batch was paused/restarted or otherwise changed.


### Workshop 0.16.0 reversible per-item source exclusions

Source cards have a labelled red X. Removed sources is a collapsible restore
list. Actions exclude-source/restore-source require a saved sourceId belonging
to the item. getItem exposes active sources plus excludedSources. Removal is
reversible and does not start a model call. Block changing the in-flight current
item until paused; non-current items may be changed during a batch.

Persist sourceExclusions in workshop.sqlite artifacts, recording source ID, URL,
title and date. sourceKey normalizes host alias, encoded Wiki spaces/underscores,
case and trailing slash, ignoring query tracking/revision parameters. The scope
is family + article URL, not global. allSources retains metadata/HTML; sources
returns only active pages. Fetch, discovery URL aggregation/results, putSource
and Chrome ticket creation/import honor the block. A capture queued before
removal fails at save rather than resurrecting the article. Retain exclusions
on generated reset, reimport and service restart; full project reset clears all.

Removing/restoring sources invalidates the affected draft, packet, source ledger,
audit and research report while retaining old output/archived audit and valid
per-chunk caches. Queue evidence rebuilding (then reuse remaining saved pages);
if no sources remain discover alternatives or require explicit game-only mode.
Clear research category/type overrides that cite the removed URL; manual choices
remain. Old output is not ready/exportable until a successful rebuild. For manual
JSON, mark manualSourceReviewRequired and block promotion until the user reviews
and saves it; do not silently regenerate or preserve stale reviewed content.
Restoration restores saved pages without an automatic model run. Shared part
definitions and other items' use of the same URL remain untouched.

Explicit Refresh sources deletes only active source metadata, retains excluded
archives and starts at evidence so the next collection step has a fresh packet.
No public item schema/compiler change is needed. Exclusions and private source
changes remain outside website exports.

Verification: full suite 115 passed, three unchanged external research tests
skipped. New local HTTP tests cover scoped exclusion/restore, preserved archived
HTML/output, stale draft/ledger invalidation, restart persistence, URL aliases,
blocked direct fetch/import, pending Chrome capture rejection, excluded discovery
results, active-call protection, category-override invalidation and generated
reset/manual-review behaviour. Browser smoke clicks the source X, observes card
removal, opens Removed sources and restores the card without a build. Build,
TypeScript, OpenAPI syntax and diff checks passed. Loaded the backend update with
the user's Lady Finger checkpoint still paused. No actual source was removed on
the user's behalf; they can select the incorrect card themselves.


### Shared evidence and URL-only discovery (workshop 0.17.0)

Shared scope definitions live in Project.sharedScopes in workshop.sqlite metadata.
They are synthetic Family owners with evidenceScope {category, group?, character?},
stable shared-* IDs, and sourceUrls. They never enter actual families, catalogue
counts, exports, coverage, image matching or build queues. GET/POST
/api/shared-sources exposes scopes, URLs, pages and descendant counts. The UI
opens the manager via category/character book buttons or Shared evidence. Its
selector includes all Weapons, individual weapon types, categories and character
subgroups. Sources can be added, Chrome-captured, imported as HTML or detached.
A detached article stays archived and can be reused by re-adding its URL.

Store.sources(item) merges owned and matching inherited articles, deduplicates
canonical article URLs, selects the newest capture and honors group/item
exclusions. inheritedFrom is transient display metadata. Shared cache rows/HTML
are stored once and reused when binding a URL in another scope. Each family
still gets its own applicability-filtered source reading, facts and validation;
sharing an overview never transfers sibling-specific facts. Fresh fetching reuses
shared captures within the run, avoids repeating a failed shared request per
child and retains archived versions. Chrome capture changes notify all scopes
bound to that article, invalidate dependent source work and queue actual items;
never enqueue the synthetic scope. Protect affected in-flight items against
direct edits; Chrome jobs apply at a saved-step boundary. Manual outputs require
review after evidence changes. Public item schema/compiler versions stay intact.

Run.mode is build or discover (absent means legacy build). Discover queues every
active item including completed ones, skips removed/retired entries, and runs
source URL discovery ONLY. Persist URL matches, provider urls_ready statuses,
sourceUrls and separate family.urlDiscovery completion/error metadata. Never
change item output, revision, build status or stage just for finding links.
Continue discovery after individual failures; sidebar attention/filter includes
URL failures. The progress bar and current-path spinners work during either job.

When URL discovery replaces a paused/blocked build, clone that Run into
Project.buildCheckpoint. /api/run discover, pause and resume control discovery;
resume-build restores that saved build and resumes it. Starting a new build
explicitly drops the older checkpoint. Captures arriving during discovery queue
affected items in buildCheckpoint, never change the discovery queue. Both
checkpoints survive restarts. Generated-data reset clears checkpoints but retains
shared definitions/captures; full reset removes all. No URL-only pass or model
run should be started merely to deploy these capabilities.


Verification for 0.17.0: all 128 tests passed with the local Postman research
simulation enabled (no skipped tests), including real HTTP capture reuse for
shared descendants, shared detach/pending-ticket rejection, scope isolation,
per-item exclusion, paused-build recovery and URL-only output immutability.
Browser smoke covers the shared manager, URL binding and saved HTML import,
inherited source labels and URL-only batch controls. Screenshot inspected.
TypeScript, production build, OpenAPI syntax lint and diff checks pass. No
live external agent/source run was started, and no user catalogue source was
added or removed. Existing Lady Finger checkpoint and all item states retained.


Workshop 0.17.1: shared-source cards render source.text.slice(0,550) verbatim from
the stored article, with ellipsis only when truncated. Show captureMethod=chrome
as Captured in Chrome, otherwise imported as Imported HTML or Fetched & cached,
alongside fetchedAt and saved text character count. URL-only entries explicitly
say Not captured yet. Do not generate, summarize or fetch preview text. Canonical
URL matching uses the same sourceKey as server-side inheritance/exclusions.


### Global shared evidence (workshop 0.18.0)

EvidenceScope.category additionally accepts Everything, a private scope only;
actual item Category/public Zod enums remain unchanged. The synthetic global
owner uses Other equipment as a storage-only Family.category and evidenceScope
is authoritative for matching. scopeMatches(Everything,actual item) is true
across every category/character/type; synthetic scopes themselves never match.
No subgroups/characters are valid under Everything. The sidebar Shared evidence
link opens this global scope and it appears first in the manager selector.

Store.sharedScopesFor enumerates ALL matching scopes, so item sources combine
global, category, character/weapon subgroup and directly owned articles. No
nearest-parent override. Canonical URLs deduplicate, latest capture wins, and
explicit per-item exclusions suppress an article from every inherited scope.
readSources traverses the full resulting list and every chunk; the synthesis
packet includes every extracted source ledger without per-source count caps.
Only applicable facts should enter item prose: general corrosion references do
not make a non-corrosive item corrosive. URLs without saved content are not yet
readable evidence. Manual/game-only handling and source-priority rules persist.
Adding/removing/recapturing global evidence queues matching active items, respects
in-flight guards and retains captured HTML, outputs and paused checkpoints.


Verification for 0.18.0: 126 tests pass, four existing external-simulation tests
skipped in the normal suite. New hierarchy tests verify all four evidence levels
reach full-page reading and the writing packet together, cross-category global
matching, narrower subgroup isolation, canonical deduplication, item exclusions,
global invalidation without output/revision loss and invalid subgroup rejection.
Browser smoke creates/captures Everything, verifies it on weapons, artifacts and
class mods, and passes the existing group/discovery workflows. Production build,
TypeScript and local OpenAPI syntax lint pass. No real global evidence was added
on the user's behalf and no catalogue rebuild was triggered.
