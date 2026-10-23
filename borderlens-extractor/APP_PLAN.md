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
