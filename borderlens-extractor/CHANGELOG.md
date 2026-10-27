# Changelog

## Workshop app 0.46.0 / Chrome helper 1.2.0

- Back to workshop selects Sources & evidence, opens the correct item/shared group and scrolls to/highlights the source.
- Add a persistent Close source tab when returning after capture checkbox in popup and selection panel. Close only the matching accepted-capture tab after the workshop acknowledges navigation; retain unsent/changed tabs and keep tabs open on navigation failure.

## Workshop app 0.45.0

- Add Recapture to external item/shared cards, inherited rows and source viewers. Reopen the exact source with a fresh Chrome capture ticket; sending replaces saved content at its owner. Manual text stays editable separately.

## Workshop app 0.44.2

- Fix Chrome capture reporting a website URL error after saving when the item also contains manual text. Compare old source identities without treating internal manual URLs as website captures.

## Workshop app 0.44.1

- Keep the source URL Chrome-capture link visible in the correction sidebar, disabled until a URL is entered.

## Workshop app 0.44.0 / Chrome helper 1.1.0

- Select page excerpts using Ctrl-drag boxes, with red/green structural checks, resize/move/remove, Fit content, overlap deduplication and a local preview/size counter. Sending is disabled until usable content is selected; partial captures require acknowledgement.
- Label selected sources throughout the app and pass excerpt context to AI. Keep selections scoped to their item/promoted parent and stable across website refreshes. Preserve HTML headings/tables without copying page controls/scripts.
- Keep existing local ticket relay and activeTab permissions; include selection.js in the helper ZIP. Compiler 0.11.2 records excerpt-aware instructions.

## Workshop app 0.43.2

- Separate inherited evidence into labelled Always include, Auto and Never include boxes with counts and spacing. Brighter green/blue included/Auto rows; retain purple manual rows and current Never fade.

## Workshop app 0.43.1

- Allow item-specific rejection of unrelated numerical facts from Always include evidence even when automatic relevance matched broadly. Require an exclusion reason; keep complete fact accounting and used-stat validation. Compiler 0.11.1 refreshes writer instructions.

## Workshop app 0.43.0

- Show stored-text totals beside item rebuild controls: dedicated + Always include, with separate muted Auto total. Exclude Never include, deduplicate URLs and identify unknown sizes.

## Workshop app 0.42.2

- Sort inherited evidence by Always include, Auto, Never include, then alphabetically within each group. Fade Never include rows further.

## Workshop app 0.42.1

- Give Cancel run a clear red outline, hover/focus states and circled X icon.

## Workshop app 0.42.0

- Edit manual evidence labels/text in place on item and shared cards. Preserve identity, inheritance and inclusion settings; save for the next requested build without starting work.

## Workshop app 0.41.0

- Add Cancel run beside Pause/Resume for active, paused and blocked single-item/batch/URL-discovery queues. Clear queue/deferred starts/build checkpoints while retaining saved evidence, drafts, outputs, corrections, revisions and caches.
- Stop active agent process groups without fallback or failure cooldowns. Keep controls in Cancelling until the active step settles; a new run can then start. Preserve cancelled evidence stats and recover interrupted cancellation as idle after restart.

## Workshop app 0.40.0

- Stripe standard inherited-evidence rows and highlight hovered/keyboard-focused rows. Keep manual entries purple, with a stronger purple interaction highlight.
- Fade Never include rows; restore full contrast during hover/focus so their controls remain easy to use. No evidence settings or processing changes.

## Workshop app 0.39.0

- Show exact saved-text UTF-8 byte sizes in inherited rows, item/shared evidence cards and source viewers, including manual text and its paste form. Use rounded B/KB/MB with exact bytes on hover.
- Add Small / Medium / Large / Very large document-size guides and excerpt suggestions, clearly separate from actual AI input/token counts. Unknown uncaptured sizes stay unknown. No inclusion, caching or build changes.

## Workshop app 0.38.0

- Give manual text a consistent purple notebook icon, badge and tinted row/card in inherited/shared evidence, item cards, source viewers, removed entries, requested-context results, exclusion alerts and live/History AI stats.
- Keep names and all source ownership, promotion, caching and Auto/Always/Never behavior unchanged. No schema/compiler changes or rebuilds.

## Workshop app 0.37.0

- Enable one-level parent promotion for manual text evidence, from item to subgroup/category/Everything. Retain exact content, label, ID, checksum and file; reuse one shared index across permitted descendants. Start no builds or model calls.
- Show manual entries in inherited lists and shared evidence, with full text and remove/restore controls. Respect per-item modes/exclusions, hide website-fetch actions, keep private labels out of indexing prompts and reject fabricated local references.

## Workshop app 0.36.0

- Add item-specific pasted-text evidence with an optional private reference label. Show Manual text cards and exact stored text in Show more. No HTML/URL required, AI call, fetch or automatic build.
- Reuse source reading, fact validation, remove/restore and actual AI input stats. Preserve excerpts during website refresh, fresh builds, restart and generated reset. Keep them private to their item; never fetch local identifiers or export them as acquisition URLs.

## Workshop app 0.35.0

- Show AI evidence stats in progress: sources from actual serialized input arrays, unique articles versus repeated sends, per-phase requests, exact source lists/modes, shared/item analysis reuse and local response-cache hits. Count at CLI submission; skip auth/cooldown failures and count explicit fallback/retry submissions separately.
- Keep the last item’s stats visible until the next item. Persist complete/failed snapshots privately in History without the rolling log limit, including across restart. No additional AI calls, input-token estimates, catalogue/schema changes or automatic rebuilds.

## Workshop app 0.34.0

- Add Set all Auto / Always include / Never include to each item’s Inherited evidence header. Save once, invalidate only the selected item, preserve outputs/queues, and start no work.
- Keep Never include authoritative even after evidence bindings move; no first-read indexing or requested-context pass may send excluded source content. Retain existing Auto relevance and shared index reuse.
- Persist a private, dismissible item alert when AI requests a topic matching excluded saved evidence. Match locally, send no blocked content, and continue batches without interruption. Dismissing changes no source modes or output.

## Workshop app 0.33.0

- Add Edit item name in Preview: reveal a free-text field with Save/Cancel. Update navigation, existing JSON/drafts and export slugs without AI or rebuilding.
- Persist authoritative manual names across builds, syncs, restarts, imports and generated resets. Preserve raw identity, source aliases, image matches, prose and readiness. Only another manual edit replaces the lock.
- Keep original names searchable. No compiler or public schema change.

## Workshop app 0.32.0

- Add an Item type dropdown at the top of every Preview sidebar, with all weapon types and Shields, Class mods, Grenade mods, Artifacts and Other equipment. Automatic restores research/game classification. Keep the existing Sync buttons.
- Manual changes make no AI/network requests and start no builds. Persist authoritative overrides; update navigation, inheritance, existing JSON/draft metadata and export folders immediately while retaining prose, raw identity, readiness and queued checkpoints.
- Use the same picker in Sources & evidence and the same metadata path for the legacy weapon-classification action. No compiler/public schema change or automatic rebuild.

## Workshop app 0.31.1

- Fix Sync name's nullable response root: return an object with a nullable decision. Validate agent schema roots locally before provider calls and clear only stale cooldowns caused by this specific caller-side schema bug.
- Fix Sync type validation: related defining-part paths are valid identity evidence, exact raw property projections are checked structurally, and title/body/page citations can jointly establish identity and type. Keep unrelated rarity/prefix disagreements as private context; identity/type/availability conflicts still block.
- Record precise validation rejection reasons and ignored redundant citations rather than displaying the agent's affirmative explanation as an unchanged reason. Prefix sync notices with the actual item's name.

## Workshop app 0.31.0

- Add Sync type / Sync name to every Preview sidebar. Check saved raw definitions, allowed direct/inherited evidence and existing JSON with one medium-effort agent call; never fetch sources or rebuild content.
- Apply only high-confidence, quoted identity corrections; update live navigation, inheritance, existing JSON/draft/packet metadata and export folders/slugs while preserving prose, raw data and queue checkpoints. Keep completed validated entries ready; count saved metadata revisions. Unbuilt entries remain unbuilt.
- Preserve manual type overrides; explicit name sync can update identity on manual entries. Show live progress and unchanged reasons. Lock concurrent project writes during verification. Compiler and item schema versions unchanged.

## Workshop app 0.30.0 / compiler 0.11.0

- Allow the writer to propose a canonical item name privately. Require exact archived naming quotes and compatible extracted identity; run a separate medium-effort verification only for supported proposals. Keep uncertain, mismatched, cut/prototype or failed proposals unchanged without halting the build.
- Persist name corrections separately from the ZIP. Update navigation, Preview, compiled names and export slugs, retaining original names as aliases and stable IDs. Show the extracted name in Preview. Never merge entries or transfer evidence.
- Internal schema 7; website schema remains 9. Retain old generated output/corrections and queue it for the next requested compiler rebuild; no automatic builds.

## Workshop app 0.29.0 / compiler 0.10.0

- Add canonical item-level DLC/origin to every equipment schema, source reader checklist, writer claims and final JSON. Prefer the family's own extracted DLC package; use explicit saved item-origin evidence otherwise. Keep unknown origin null and distinguish it from DLC drop locations.
- Show DLC in Preview's sidebar, including extraction-derived origin before building. Label the game Borderlands; remove game/series metadata from item JSON.
- Website schema 9 / internal schema 6. Retain old outputs and corrections; queue earlier compiler entries for the next requested rebuild. No automatic builds.

## Workshop app 0.28.0

- Add Find duplicates to Needs review previews: explained name/alias/extracted-title matches, read-only inspection and restorable removal of only the review entry. Recheck its group before removal; no merge, evidence transfer or build.
- Verify exact obtainable BL1 identity/type during the existing URL-discovery call. Persist successful classifications separately, move navigation immediately and inherit new parent evidence. Leave ambiguous, cut/prototype and naming-modifier candidates in review. Build verifies discovery decisions from saved articles again.
- Keep compiler/public schemas unchanged; no automatic rebuilds or additional discovery calls.

## Workshop app 0.27.0 / compiler 0.9.0

- Let the writer request up to three specific missing topics alongside its best draft. Search existing saved text and cached fact indexes only; supply at most four short matches for one extra writing pass. No request or no match means no extra AI call.
- Respect Never include, per-item and applicable parent exclusions; keep retrieved context private to the draft without attaching sources or changing shared bindings. Preserve exact quotes, numeric facts and normal evidence validation.
- Persist answered rounds for retry/restart, invalidate changed source snapshots, and retain the original draft if lookup or the extra writer fails. Show requests, saved excerpts, misses and fallback status in Sources & evidence. Public website JSON schema stays unchanged.
- Make model-facing evidence-request and source applicability/tag fields explicit with safe defaults for strict structured-output schemas, retaining compatibility with older stored readings.

## Workshop app 0.26.0

- Replace inherited-source checkboxes with Auto / Always include / Never include dropdowns. Preserve existing Always choices; Auto stays the default.
- Never skips the inherited URL before per-item fetching, classification, source reading and writer input, including canonical aliases and duplicate direct bindings. Keep the saved reference visible, shared archives/indexes intact, and sibling items unchanged.
- Persist modes through restart/generated reset; restore use with Auto or Always. Mode changes retain output/revisions and never start builds or extend queues.

## Workshop app 0.25.0

- Add an item-only checkbox beside each inherited source: unchecked Auto (default) uses relevance selection; checked Always include sends every indexed fact from that source to the writer. This never forces irrelevant facts into the published JSON.
- Persist choices per item/canonical URL across restarts and generated resets. Changes invalidate only that item’s selected facts/draft, retaining output and shared indexes without fetching, invoking AI or extending queues. Category/shared-source controls stay unchanged.

## Workshop app 0.24.0 / compiler 0.8.0

- Index unchanged shared articles once across items, with quoted facts tagged by category, character, weapon type, item, skill and element. Reuse persisted indexes across restarts; re-index changed content or analysis configuration.
- Read item-specific evidence first, then omit only confidently unrelated shared facts before writing. Require quoted complete item skill/element lists for those filters; keep general rules, uncertain interactions and unknown applicability. Failed indexing falls back to full item-specific reading.
- Add a shared-analysis summary with kept/skipped reasons and cache/fallback counts. Preserve complete original articles, per-item exclusions, source accounting and all selected numeric facts. Public JSON schema stays unchanged; older outputs are retained for the next requested compiler rebuild.

## Workshop app 0.23.0

- Add Move to parent on individual/shared evidence cards: promote exactly one tree level, retaining saved content and inheriting it across descendants. Everything has no further promotion. Duplicate parent URLs merge; individual exclusions remain intact.
- Evidence changes invalidate drafts for the next requested build, retain outputs, and never append automatic rebuilds to active or paused queues. Protect affected items currently processing.

## Workshop app 0.22.1

- Add coloured source-domain pills to individual and shared evidence cards, and the saved-source viewer. Wiki and Lootlemon have distinct colours; other sites show their domain. Source content and builds unchanged.

## Workshop app 0.22.0

- Reuse saved Wiki/Lootlemon articles across the catalogue by matching canonical URLs, including URL-only references and shared evidence. Show matching pages as saved immediately and label reused individual articles.
- Keep exclusions and AI fact interpretation per item; do not attach unrelated cached pages. Identical captures reuse stored HTML. Explicit refreshes update matching references while retaining previous output.
- Refresh each shared URL once per batch; automatic refreshes stay within the selected remaining queue. No public schema/compiler changes.

## Workshop app 0.21.1

- Add an X beside unsaved evidence URL capture buttons. Remove links before capture, suppress aliases in future discovery and restore them from Removed sources.
- Support URL-based exclusions without a saved page ID; preserve existing captures and reject stale Chrome tickets for removed URLs. Hide empty provider warnings after their last URL is removed.

## Workshop app 0.21.0

- Add a three-dot batch menu beside each sidebar category/weapon group and character subgroup, with saved-source rebuild, fresh-source rebuild and URL-only discovery. Show the full descendant count independently of sidebar filters.
- Persist scope and rebuild-all policy in the existing queue. Group rebuilds include completed children exactly once, skip removed/retired candidates, continue failures and retain the selected group across pause/resume/restart.
- Keep later source-change/restoration queue additions inside the selected scope; require pause before explicit work outside an active group. Show the group in the progress bar. Public item schemas remain unchanged.

## Workshop app 0.20.0

- Add a Game data tab available before building: supported ZIP identity facts, red text, native values, defining parts and searchable linked definitions with original record JSON.
- Reconstruct family identity from extracted records, isolating this view from source captures, classification overrides, corrections and generated output. Use a read-only lazy endpoint and cache by extraction identity.
- Label internal rule values and shared context separately from finished stats/part compatibility. Preserve existing Preview and build behaviour; public item schemas remain unchanged.

## Workshop app 0.19.1

- Show shared sources only in the compact inherited-evidence list. White article cards and provider counts now represent item-specific evidence, with equivalent inherited URLs filtered too. Hide provider panels that contain only inherited references. Build evidence remains unchanged.

## Workshop app 0.19.0

- Add per-item **Fetch evidence URLs only** to the rebuild dropdown, preserving item JSON, revisions and paused build checkpoints.
- Exclude inherited article URLs and aliases from locally saved discovery links/matches in item and batch workflows. Still search for individual pages on each provider; inherited-only references are valid when no individual page exists.
- Add a compact inherited-evidence list to every item’s Sources tab, showing all contributing parent groups and Saved/Awaiting capture status. Parent links open shared evidence controls; item capture buttons omit inherited references.
- Return the top primary button to Start from saved/fresh sources after URL discovery completes. Public item schemas remain unchanged.

## Workshop app 0.18.0

- Add **Everything** shared evidence for the entire catalogue; the sidebar Shared evidence button opens this scope.
- Combine global, category, weapon-type/character and individual sources for each item. Read all applicable saved articles, deduplicate matching URLs and retain per-item exclusions. Existing public item schemas remain unchanged.

## Workshop app 0.17.1

- Show the first 550 characters of saved text on shared-source cards, directly from the stored article. Include capture method, date and saved character count; distinguish Chrome captures, imported HTML and fetched pages from URLs awaiting capture.

## Workshop app 0.17.0

- Add shared evidence for categories, weapon types and character subgroups. Capture each article once; matching children inherit it alongside individual sources, with duplicates merged and per-item exclusions retained.
- Add sidebar book controls and a shared evidence panel with URL, Chrome capture, HTML import and group removal controls. Source changes queue dependent builds without starting them.
- Add **Find evidence URLs only** to batch actions: discover links without article fetching, source reading or JSON compilation; include completed items, continue failures, and preserve a separate paused build checkpoint.
- Keep shared captures and discovery progress on disk; expose inherited evidence and discovery errors in the existing item/sidebar views. Public JSON schemas remain unchanged.

## Workshop app 0.16.0

- Add an X to saved source cards, with a Removed sources list and Restore controls. Exclude the article per item, including URL aliases, without deleting archived HTML.
- Filter exclusions from evidence packets, source reading, discovery and fresh fetching; reject manual/Chrome imports until restored. Preserve exclusions across restart and generated-data resets.
- Invalidate affected drafts/audits and queue rebuilding; old output remains inspectable but is not exported until rebuilt. Clear research classifications supported by a removed page. Manually edited output requires review.
- Protect current in-flight processing while allowing source changes to other items. Refresh keeps removed-source archives and rebuilds its evidence packet.

## Workshop app 0.15.3

- Reveal every ancestor and scroll to the selected item when jumping to Current item, including repeat jumps to the same selection. Clear sidebar filters so the current item can be seen.
- Add level-by-level collapse/expand controls above the sidebar search; preserve open branches during expansion and saved collapse preferences.
- Show an activity spinner on the current category and character subgroup, including collapsed groups; stop it while paused.

## Workshop app 0.15.2

- Replace category/character-group totals with compact coloured completed / needs attention / total badges. Hover text and accessible labels also report waiting/processing counts.
- Update counts live from item state and honour the visible search/status filter; add subtle highlights for completed groups and groups needing attention.

## Workshop app 0.15.1

- Correct Other equipment entries from verified item-specific BL1 Lootlemon shield/grenade pages. Require a matching item/alias URL and a matching typed BL1 title; generic pages/navigation cannot classify items.
- Persist category overrides alongside weapon types, keep original category/subtype and stable IDs, and update sidebar grouping and JSON/export categories. Respect manual overrides and removed items.
- Revalidate completed drafts after category metadata corrections without rewriting their content; retain source readings and allow future category-specific rebuilds. Correct Ironclad and Omega using their saved shield pages.

## Workshop app 0.15.0

- Add a red **Remove from catalogue** button to Preview and a **Removed items** sidebar view with restoration. Hidden items are skipped in normal navigation, batches, image coverage and exports; their saved research/output stays intact.
- Support removing future items during a batch; protect the item currently being built until paused. Prevent accidental rebuilding of removed items until restored.
- Preserve removal through restart, reimport and generated-data resets. Restore ready items without rebuilding when valid output remains, otherwise return them to the queue.
- Remove the six standalone Storage Deck Upgrade level-label candidates from this catalogue; retain them in Removed items.

## Workshop app 0.14.0

- Preserve pending queue order on service restarts when character-family discovery adds nothing.

- Prefer verified Lootlemon facts over directly contradictory Wiki facts about the same item, edition and conditions, while retaining complementary facts from both. Preserve scoped variations such as maximum rolls versus full rarity ranges.
- Add private overridden fact accounting linked to the exact used Lootlemon fact. Validate direction, target field, source provider and use of the preferred fact; reject publishing superseded rarity/stat values.
- Give drafts that still flag a cross-source conflict one policy-aware retry. Unresolved identity, same-provider disagreements and unsupported evidence can still require attention.
- Keep public JSON schema, item revisions and existing source readings intact. Queue the blocked MIRV entry to retry using its saved pages/facts; preserve the paused batch.

## Workshop app 0.13.0

- Add `revision` beside schema/compiler versions in Final JSON and item-only exports, using the existing persistent per-item saved-version counter. Successful builds and validated saved edits increment it; failed attempts, viewing, exporting and pause/resume do not.
- Upgrade website JSON schema to 8 for the required positive revision field. Internal schema/compiler stay unchanged, so completed items need no AI rebuild. Existing recorded revisions are preserved.
- Keep the counter compiler-owned when saving edited JSON; an edited revision value cannot override it. Document the distinction between schema, compiler and item versions.

## Workshop app 0.12.3

- Retain applicable equipment-wide rarity/skill rules during research; distinguish Lootlemon rarity labels from exhaustive legal tiers and respect family-specific exceptions.
- Label class-mod ammo regeneration card bonuses separately from weapon-specific maximum per-second rates. Clarify that team bonuses also benefit the wearer in solo play.
- Correct the saved Support Gunner rarity tiers, regeneration contexts and solo wording against its saved sources; preserve numeric values, research and future rebuild support.

## Workshop app 0.12.2

- Match source quotations across literal JSON table line-break/tab/quote escapes and their displayed equivalents. Preserve checks on all words, numbers and punctuation.
- Include the rejected quotation and chunk in extraction repair feedback; include character/element context in equipment source reading. Reuse saved pages and successful reading checkpoints.

## Workshop app 0.12.1

- Fix Codex structured-output rejection of the optional character field. Use a required nullable character in the writer schema, then supply the authoritative captured restriction; saved/public JSON stays backwards compatible.
- Persist agent failures and cooldown skips in the active item History, including the task, reason and fallback agent. Keep existing private CLI logs and provider cooldown diagnostics.
- Add regression checks for every required writer-schema property and persisted fallback History.

## Workshop app 0.12.0

- Discover class-mod families from their character-restricted body/prefix links, including fixed DLC part collections. Replace generic manufacturer/title placeholders with 44 named class-mod families from the current capture.
- Discover 16 artifact families: four elements for each character, with ranks kept within the family. Group both equipment categories by character in the sidebar; include the character restriction in generated JSON.
- Retire broad placeholders without deleting their research/output; preserve weapons and add the new families to existing pending batch work. Disambiguate same-name export filenames by character.
- Batch runs in either source mode save item failures, show a red cross and continue. Individual rebuilds stop on failure. Completed batches report items needing attention.
- Keep compiler/schema versions unchanged; the character field is optional and additive. No blanket rebuild of completed weapons.

## Workshop app 0.11.1

- Add **Refresh folder** beside the image selector, with loading, success and error feedback. Reload local files without interrupting the batch or losing unsaved JSON edits.
- Discover images in newly added safe top-level folders as well as the standard category folders. Preserve actual relative paths and existing manual image choices.
- Keep catalogue schemas/compiler unchanged; no item rebuild required.

## Workshop app 0.11.0

- Add **Start from saved sources** / **Start from fresh sources** to the top batch control, matching the individual rebuild choices.
- Saved batches reuse saved pages/facts for cached items and fetch sources for items with no saved pages. Fresh batches refresh each unfinished item.
- Preserve the selected source mode and per-item initialization through pause/resume and service restarts; do not repeat source preparation at a saved checkpoint.
- Keep completed/excluded items skipped and respect the existing run-size limit. Explicit individual rebuilds queued during a batch keep their own source mode.
- Migrate older run metadata without resetting active checkpoints or altering completed JSON. Catalogue schemas/compiler remain unchanged.

## Workshop app 0.10.0

- Add whole-document validation after inline parts, images and acquisition sources are assembled, before promoting generated output and whenever exporting. Serialize and parse the actual consumer JSON to verify syntax and quoting.
- Check numeric bounds, repeated stat contexts/parts/sources, URLs, player-count conflicts, drop-rate scopes/ranges, edition conditions and public wording. Record successful checks privately and show **Final JSON checked** in Preview.
- Enforce canonical element labels across all equipment: Non-elemental, Incendiary, Shock, Corrosive and Explosive. Upgrade internal schema to 5, website schema to 7 and compiler to 0.7.0.
- Remove stat notes that only repeat structured values; retain meaningful context. Deduplicate edition/player conditions without changing probabilities or losing explicit player counts.
- Group acquisition labels with explicit player/edition qualifiers under their source identity. Reject contradictory scopes instead of choosing a rate arbitrarily.
- Repair unclear scope comparisons with one focused original-wording call; preserve numeric facts and rerun every check. Reject malformed manually submitted JSON with HTTP 400.
- Preserve old outputs/drafts and source captures through the schema upgrade. Apply the cleanup and a short wording repair to the saved Bessie entry without fetching sources or rebuilding the full item.

## Workshop app 0.9.0

- Separate known game/manual evidence usage from extracted page-fact accounting without rewriting the item. Keep those extra records privately; missing, duplicate and invented fact IDs still fail with exact diagnostics.
- Clarify the private sourceUsage schema and writer instructions: only extracted page-fact IDs belong there; raw evidence IDs belong in claims.
- Add **Rebuild from saved sources** and **Rebuild from fresh sources**, with a dropdown and saved sources as the default when pages exist.
- Reuse complete, matching source analysis across agent/model changes. Newly added or changed saved pages can be read without fetching them again.
- Fresh rebuilds explicitly fetch current pages and reread facts, preserving failed-page copies and historical HTML. Chrome captures can satisfy a blocked refresh before resuming.
- Preserve source mode for deferred rebuilds and across pause/restart. Keep legacy rebuild behavior for older callers.
- Upgrade compiler to 0.6.1; preserve paused validation drafts and saved source analysis. Public JSON schemas remain unchanged.

## Workshop app 0.8.0

- Match local item images by category, name and aliases; handle punctuation differences, expose ambiguous/missing matches and allow saved manual corrections.
- Show item images before or after building, with a clear missing/load-failure state and a compact image picker.
- Add searchable Image coverage with missing/matched filters, expected filenames and links to candidate pages; excluded candidates stay hidden.
- Add a nullable relative image path to website schema 6. Image assignments update dynamically without AI or item regeneration; export remains item JSON only.
- Serve only supported local raster images, reject unsafe paths/symlinks and refresh files without changing the active queue.
- Preserve image choices in a separate override file across imports, restarts and generated resets. Full reset clears choices while retaining the image library.
- Bump compiler to 0.6.0; retain earlier output and source captures for rebuilding. Images remain outside the AI draft schema and source claims.

## Workshop app 0.7.1

- Distinguish base, multiplier and total quantities sharing a stat name; preserve all supported values with explicit context labels.
- Repair missing or ambiguous cited stat rows with a focused label/notes call before attempting a complete rewrite. Copy numeric values directly from saved evidence and reject incomplete or ambiguous repairs.
- Preserve captured-part modifier safeguards, per-fact citations, bounded retries and full validation after repairs.
- Upgrade compiler to 0.5.1 without changing public field shapes. Retain paused 0.5.0 validation drafts through a metadata-only migration and archive their originals.

## Workshop app 0.7.0

- Group acquisition locations with conditional drop rates in website JSON and Preview; preserve solo/multiplayer rates and reject contradictory rates with identical conditions.
- Add explicit player counts and stat contexts; distinguish card and scoped accuracy without changing published ranges or inventing units.
- Omit empty optional note strings from website output; retain unknown level bounds as null.
- Require player-facing part/mechanics wording, preserve numeric modifiers in the relevant part effects, and keep raw scope constants and unscoped damage benchmarks private.
- Tighten original-writing instructions and reduce repetition between overview, mechanics and notes.
- Preserve conditional rate arrays through Final JSON editing; keep manual part edits local and allow cited generated part definitions to gain missing numerical effects.
- Upgrade internal schema to 4, website schema to 5 and compiler to 0.5.0. Queue older generated entries for rebuilding while preserving their output, captures, source pages and corrections.

## Workshop app 0.6.2

- Validate source usage by field presence and matching source claims; valid empty arrays no longer depend on particular absence wording.
- Keep numeric coverage checks enforced. Repair omitted, explicitly attributed part modifiers with a focused mechanics-paragraph rewrite before considering a full rebuild.
- Preserve saved drafts and source captures; recover the blocked Bessie entry without restarting its build.

## Workshop app 0.6.1

- Remove the experimental Ollama/Gemma integration after its full Bessie run was slower and failed coverage, part-reference and effect-length checks.
- Remove its selector/status entry, adapter, mocks and test harness; fallback is exclusively Grok and Codex again.
- Migrate removed-provider preferences back to Grok while preserving writing settings, sources and catalogue work.

## Workshop app 0.6.0

- Add Ollama/Gemma 4 to the toolbar agent selector and connection statuses, pinned to the installed gemma4:e4b-mlx model.
- Stream schema-constrained JSON from the local Ollama API with heartbeat, timing/token statistics, validated cache and bounded cancellation.
- Use thinking off for local writing and on for local analysis, matching the installed model's advertised boolean controls.
- Preserve the same schema, evidence, originality and numeric checks; reject oversized context, incomplete output and requested tools rather than silently dropping evidence.
- Extend bounded fallback across available providers; local inference is loopback-only and live web discovery uses subscription agents. Settings explicitly disclose cloud fallback.
- Add local protocol simulation and full-request diagnostics; retain the existing Grok default and paused catalogue queue.

## Workshop app 0.5.1

- Accept empty element/variant/part/source arrays when a cited source explicitly establishes absence, rather than rebuilding a correct entry repeatedly.
- Recognize numeric modifiers attributed to captured weapon parts even when their notes omit the word modifier; preserve their values in mechanics/part text.
- Record exact validation failures in History; distinguish source-page/extraction counters from full writing attempts and copied-passage rewrites.
- Verify the saved Bessie draft against schema, originality, captured parts and all 83 extracted facts without another model call.

## Workshop app 0.5.0

- Add a persistent toolbar agent selector, defaulting to Grok with Codex available.
- Integrate the authenticated Grok Build CLI, pinned to grok-4.6; use low effort for writing/rewriting and medium for extraction, classification and research on both agents.
- Stop timed-out jobs after five minutes before trying the other agent; bound fallback to one attempt per provider, with a ten-minute failure cooldown and explicit recheck.
- Share subprocess heartbeat/error handling across providers; isolate provider/model/effort caches and retain actual draft-provider metadata privately.
- Keep subscription authentication; strip API-key environment variables, restrict model tools/filesystem use and report actionable account errors.
- Preserve catalogue schemas, saved corrections, completed entries and paused queues. Changing the default affects future calls without rebuilding completed work.

## Workshop app 0.4.1

- Exclude generic farming, route, fast-travel/respawn and shared loot-guide boilerplate during extraction and synthesis; reject known templates in public catalogue text.
- Keep filtered facts privately auditable and retain item-specific mechanics, acquisition conditions and gear bonuses.
- Show per-call elapsed time, last-output age and timeout, plus build attempt; persist live process activity and JSONL events.
- Detect process failures promptly and retain the existing bounded timeout without assuming quiet output means a crash.
- Recognize scope modifiers alongside other part modifiers, avoiding false missing weapon-stat validation retries.
- Queue prior generated entries for the revised compiler and archive unfinished drafts; retain captures, corrections and manual edits. Catalogue/website field shapes are unchanged.

## Workshop app 0.4.0

- Read every saved source in full through independently cached source/chunk passes, then synthesize all extracted facts alongside game evidence.
- Add category checklists and private fact dispositions; reject omitted facts, unsupported quotations and silently discarded numeric ranges.
- Accept published catalogue stat ranges directly, with no source-reporting labels or invented levels.
- Allow longer descriptions and titled detail sections; require freshly written prose and reject copied passages across public text fields.
- Keep source references, coverage, field proposals and extraction provenance private; website ZIP still contains only self-contained item JSON.
- Bump compiler to 0.4.0, internal catalogue schema to 3 and website schema to 4; queue older generated entries while retaining outputs, sources and manual corrections.

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
