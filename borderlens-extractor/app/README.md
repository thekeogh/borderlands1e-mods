# Borderlens workshop

A local workspace for turning BL1 Enhanced extractions into readable item-family JSON. Import a capture, press **Start from saved sources**, and browse while it researches and builds each entry. Progress, pages and corrections are saved on disk.

## Back up or restore the whole project

In **Settings → Project backup**, pause processing, then:

- **Export Data** → choose a Save As location. Filename defaults to `YYYY-MM-DD_HH-mm.zip`, e.g. `2026-10-27_13-16.zip`. Browsers without native Save As use their normal download behavior.
- **Import Data** → select that ZIP. The app validates it, replaces the saved project and reloads into its backed-up item/tab. No manual rename or unzip, and no extra confirmation step.

This is a complete saved-project backup, separate from the player catalogue export.
SQLite alone is insufficient. The ZIP includes a consistent database snapshot,
original extraction archives, captured HTML/manual evidence, inherited modes,
JSON/drafts/history, corrections/name/type/image overrides, AI caches/logs and the
entire image library. Selected item, tab, sidebar groups and filters are included.
Paused runs/checkpoints remain paused; restoring starts no AI or builds.

Restore checks file inventory, SHA-256 hashes, safe paths, database integrity and
required source/capture files before touching current data. Installation failure
rolls back. The previous project is retained next to `.data` as
`.data.before-restore-<timestamp>-<id>` for recovery. Restored images live inside
`.data/image-library`, so the backup is portable. Backups can be saved to your
Dropbox folder using Save As; the app makes no cloud upload itself.

The backup contains saved project data, not application code, CLI sign-in accounts,
browser extension installation/settings, unsent page boxes or unsaved text fields.
Import accepts the app’s complete backup ZIP, not a standalone SQLite or game ZIP.
Uploads support up to 1 GB compressed / 4 GB expanded. Keep using a compatible app
version for the same schema; later normal startup migrations still apply.

## Where data lives

Paths are relative to this folder (default configuration).

| Path                                  | Contents                                                                                                                                                                           |
| ------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `.data/workshop.sqlite`               | Built item JSON, drafts, extracted records, source facts, additional evidence requests/matches, corrections, shared evidence groups, removed items/sources, progress and settings. |
| `.data/captures/`                     | Imported extractor ZIPs.                                                                                                                                                           |
| `.data/sources/`                      | Saved Wiki/Lootlemon HTML, Chrome captures and manual text snapshots.                                                                                                              |
| `.data/classification-overrides.json` | Item category and weapon-type overrides.                                                                                                                                           |
| `.data/name-overrides.json`           | Manual name locks, verified names, original identity and supporting proof.                                                                                                         |
| `.data/image-overrides.json`          | Manual image selections.                                                                                                                                                           |
| `.data/ai/`                           | Agent requests, responses, caches and logs.                                                                                                                                        |
| `.data/ai/agent-failures.json`        | Last agent failures and fallback cooldowns.                                                                                                                                        |
| `img/borderlands/`                    | Item images, organised by type.                                                                                                                                                    |
| `src/shared/models.ts`                | Internal item and writer Zod schemas.                                                                                                                                              |
| `src/shared/website.ts`               | Final website JSON Zod schema.                                                                                                                                                     |
| `src/shared/versions.ts`              | Schema and compiler versions.                                                                                                                                                      |

**Export** downloads `borderlens-catalogue.zip`, containing final item `.json` files in type folders. Individual final JSON files are generated on export, not saved separately in the app folder.

Needs review previews include **Find duplicates**: inspect possible matches and optionally remove only the review entry. Removal is restorable; nothing is merged or transferred.

**Fetch evidence URLs only** can move a Needs review weapon into its verified type during discovery. It requires an exact obtainable BL1 identity; uncertain or prototype candidates stay in review. Overrides persist separately from the ZIP. Build checks discovery classifications against saved articles again; no build starts automatically.

During Build, the writer can propose a better item name from saved evidence. The app checks exact quotes and compatible extracted identity, then runs one separate medium-effort verification for supported proposals only. Ambiguous/cut/prototype identities keep their names. Successful corrections update navigation, Preview, final JSON and export filenames; IDs, raw game data and other items remain unchanged. Original names stay searchable aliases and are shown in Preview. Name corrections persist in `.data/name-overrides.json` across restarts/imports/generated resets. Full project reset clears them. Naming never merges items or starts another build.

Every item's **Preview** sidebar has an **Item type** dropdown. Select a weapon type or equipment category to apply a manual override immediately, with no AI calls, fetching or rebuild. **Automatic** removes that override and restores verified research/game classification. It updates navigation and existing JSON metadata, keeps descriptions and raw data, and persists across restarts. The same dropdown is available under Sources & evidence.

**Edit item name** in the Preview sidebar opens a text field with Save/Cancel. Saving updates navigation, existing JSON/drafts and export slugs immediately, without AI or rebuilding. Your manual name stays locked across builds, syncs, restarts, imports and generated-work resets; only another manual edit replaces it. Original identity and image matching remain intact. Full project reset clears all overrides.

**Sync type** and **Sync name** remain available. These check saved game data, individual/inherited evidence and existing JSON using the selected agent, without fetching or building. Strongly supported changes move navigation immediately and update existing JSON/draft metadata; wording and raw records remain intact. Completed entries stay ready, metadata edits increment their revision, and unbuilt items gain no generated JSON. Uncertain results report the specific validation reason. Rarity/prefix disagreements do not block an otherwise verified type; exact title and defining-body evidence can corroborate each other. Invalid redundant citations are recorded privately, and unsupported identity/type claims still remain unchanged. Manual type overrides take priority; manual name locks also take priority over explicit name sync. Pause an active job first; syncing preserves the paused batch and starts no build.

Each item's **Inherited evidence** header has **Set all**: Auto, Always include or Never include. It saves every inherited reference's mode for that item, including uncaptured pages, without starting work. Individual selectors remain editable. Auto selection is unchanged. Never include blocks the article before any AI reading/indexing, writing, sync or additional-context pass; a later permitted item can index it once and other permitted items reuse that saved analysis.

If AI requests a topic matching a Never include article, a persistent **AI requested evidence you excluded** alert lists the topic and sources. The match is checked locally after the request; no excluded content is sent to AI. Builds continue unattended. Enable the source and rebuild to use it, or **Dismiss notice** to clear the alert while keeping your exclusions.

The progress bar's **AI evidence** summary counts sources from the final payload at each actual CLI submission, after selection. Expand it for the exact source names, Direct/Auto/Always include mode, reading/indexing/writing/check phases, and saved analysis/response reuse. Repeated submissions count again; local cache hits are separate. This measures CLI input, not provider token usage/internal retries. The last item's stats stay visible until the next item. Completed/failed summaries are saved permanently in that item's **History**, beyond the rolling activity log. Existing builds have no retroactive counts.

**Sources & evidence → Add text evidence** saves a pasted passage for this item. An optional Source / name label helps identify it. Entries show a **Manual text** pill; Show more displays exactly what you pasted. Text stays plain, with line breaks preserved; labels are not factual proof. No URL or full-page HTML is required. Add starts no AI call or build. It is read on the next build, survives website refresh/restart/generated reset, and supports remove/restore. Use **Move evidence to…** to share an entry with its immediate parent, then move it further up from Shared evidence if needed. Matching descendants inherit it with Auto/Always include/Never include controls. Shared manual entries show their full text and support removal/restoration. They are never fetched or borrowed outside their assigned scope.

Use the **pencil** on any manual card to edit its label and text in place, then **Save changes** or **Cancel**. Shared edits apply to inheriting items on the next requested build; saving starts no build.

Manual text has a purple notebook icon, badge and tinted row/card throughout the workshop, including inherited/shared evidence, saved viewers and AI input stats. Its appearance stays distinct for every inclusion mode; its name needs no special prefix.

Beside each item’s rebuild button, **Included evidence** totals dedicated + Always include stored text, while **Auto · potential extra** stays separate. Never include is omitted; uncaptured sizes are flagged. These totals describe saved text, not actual AI payload or tokens.

Evidence rows, cards and viewers show exact stored-text UTF-8 size (B/KB/MB) and a size guide: **Small** <8 KB, **Medium** 8–32 KB, **Large** 32–96 KB, **Very large** ≥96 KB. Hover for exact bytes and guidance on using an excerpt. These are document-size guides, not model limits or token counts; HTML, instructions, tables/sections and selected fact payloads can have different sizes. Uncaptured sources show Size unavailable. The same badges cover manual text, including a live size while pasting.

**Always include** makes all indexed facts available to the writer; it does not require every fact in the final JSON. The writer may exclude unrelated shared facts, including numerical stats, with a recorded reason. Used stats still require matching values and source claims.

Inherited webpage rows alternate backgrounds for easier scanning. Hover or keyboard focus highlights a row; manual rows use purple highlights. Never include rows fade until hovered/focused, while their controls remain usable.

**Cancel run** sits beside Pause/Resume for single-item and batch queues. It stops the current agent call and clears the queue, deferred runs and Resume checkpoint. Saved evidence, drafts, completed JSON, corrections and revisions stay intact. Start a new run with your chosen source option. Cancellation does not trigger agent fallback or provider cooldowns; in-flight website requests may finish before it settles.

## Start

Requires Node.js **22.13+**, pnpm, and a subscription CLI: **Grok Build** (`grok login`) or **Codex** (`codex login`). Install/sign in to both for automatic fallback. No API key needed.

From this folder:

```sh
pnpm install
pnpm dev
```

Open **http://127.0.0.1:4317**.

1. Import the ZIP produced by Borderlens Extractor. Keep the archive intact.
2. Select an item and **Rebuild from fresh sources** to try one first, or press **Start from saved sources** for the ordered catalogue queue.
3. Inspect **Preview**, **Game data**, **Sources & evidence**, **History**, or **Final JSON** while it works. Selecting another item never interrupts processing.
4. **Pause** saves the current step before stopping. **Resume** continues from that checkpoint, including after restarting the service.
5. If it needs help, add a source URL, saved page HTML, or correction under **Sources & evidence**, then resume. Corrections are remembered.
6. **Export** downloads completed item JSON files in type folders, ready for the website. Each file includes its full parts data; the ZIP contains no supporting files.

Website JSON includes item-level `dlc`: `Base Game`, a canonical expansion name, or `null` when unverified. Origin comes first from the family’s own extracted DLC identity package, otherwise from explicit saved item-source evidence. Drop-location DLC remains separate. Preview shows DLC and labels the game simply Borderlands; exported JSON has no game/series field. Rebuild older entries to produce the current format.

Website JSON groups each drop location with its conditional drop rates, including player counts when known. Stats distinguish card values from scoped or other conditional values. Empty note strings are omitted; unsupported level limits stay `null`. After a compiler upgrade, rebuild queued items to update their JSON; saved pages and previous output remain on disk.

Articles are cached across the whole catalogue by URL. If an item or shared group references a page already captured elsewhere, it immediately uses that saved content; no second Chrome capture is needed. Reused individual articles are labelled. Exclusions and selection of applicable facts remain specific to each item. Shared article analysis is reused across items. Fresh-source batches refresh a matching article once per run.

**Rebuild from saved sources** reuses saved pages and their extracted facts, then writes and validates again. Switching agents does not repeat complete source analysis. Newly added or changed saved pages are read if needed; nothing is fetched.

**Rebuild from fresh sources** fetches current pages, reads item-specific facts again, then rebuilds. Unchanged shared articles reuse their indexed facts. Blocked refreshes keep the saved pages; capture the blocked article in Chrome and resume. Both options are in the dropdown beside the rebuild button. Saved sources is the default when pages exist.

The top Start dropdown offers the same two source choices for the batch. **Start from saved sources** uses each item's saved pages/facts and fetches sources for items with no saved pages. **Start from fresh sources** refreshes sources for each item. Both process unfinished items, skipping completed and excluded entries. If an item fails, it gets a red cross and the batch continues. Use **Needs attention** afterward to correct and retry failures. Individual rebuilds stop on errors. **Pause/Resume** keeps the selected mode and saved step; starting a new batch restarts unfinished work.

**Start from here** processes the remaining sidebar range, skipping ready items. Rebuilds requested during an active run queue behind it with the chosen source mode. Manually saved JSON survives rebuilds.

Completed items pass source checks and a final whole-document check for JSON syntax, schema and consistency. Preview shows **Final JSON checked**. Exports are checked again; malformed edits cannot replace the last valid item. Element names are consistent across all equipment.

**Coverage** compares extracted families with wiki/Lootlemon listings. Link ambiguous names to a family or exclude irrelevant candidates. Settings control writing style, optional game-evidence-only processing, run size, and resets.

**Restart generated work** clears generated outputs, drafts, retries, validation/follow-up state, current run/checkpoint, AI response caches and internal exports. Keeps captures, research, saved evidence, inclusion choices, corrections, history and manually saved JSON. No work starts automatically.

**Clear the entire project** recreates the project data folder and database: all captures, web/manual/shared evidence, JSON, histories, settings, overrides, restored images, caches, queued imports and automatic recovery copies are removed. Browser project selection/layout also resets. App code, built-in image assets, downloaded backups outside the project data folder and external account/extension settings remain. Pause processing first; type RESET to confirm.

**Current item** clears sidebar search/status filters, opens its category/character path and scrolls to the item. The sidebar collapse/expand controls work one level per click: collapse deepest groups first, expand parents first. Spinners mark the active category and character group even when collapsed.

Category and character-group badges show **completed / needs attention / total**. Hover for waiting and processing counts. Counts follow the current search/filter.

## Remove an evidence URL

Click the **X** beside a pending article’s Chrome button to remove a wrong link before capture. It is excluded from future discovery for that item. **Removed sources → Restore** brings the link back. Existing saved-source cards retain their X controls too. No Chrome extension update is needed.

## Remove an item

In **Preview**, click the red **Remove from catalogue** button on the right. The item disappears from normal navigation and is skipped by batches and exports. **Removed items** in the sidebar lets you inspect it and **Restore to catalogue** later. Saved data is retained; removal survives restarts, capture imports and generated-data resets. Restoring does not start a build. Pause before removing the item currently being processed.

Verified item-specific BL1 Lootlemon shield/grenade pages can also correct entries initially grouped as **Other equipment**. Category overrides persist in `classification-overrides.json`; IDs and saved research stay intact. Corrected entries export under their actual category.

## Game data

The **Game data** tab is available immediately after ZIP import. It shows supported identity facts, red text, defining parts, native settings and searchable linked definitions. Expand a record for its original extracted fields.

It reads only the imported extraction. Source captures, corrections and builds never alter this view. Native rule values are not final item stats or obtainable level ranges; related records can include alternatives and other families. Preview and Final JSON remain empty until you build an item.

## Shared evidence

Click **Shared evidence** above the tree for **Everything**: articles shared with the entire catalogue. Use this for elemental mechanics or other universal references. Click the book beside a sidebar category or character for that group. Add a Wiki/Lootlemon URL, then capture it with **Open in Chrome** or import saved HTML. Category sources apply to every child; character and weapon-type sources apply only to that subgroup. Use the group selector for **Weapons** to cover all weapon types.

Each shared-source card shows its saved text preview, capture method, date and character count. **Not captured yet** means only the URL is stored.

Capture a shared article once. Each item uses all applicable levels together: **Everything → category → weapon type/character → individual sources**. All saved articles are read; relevant facts inform the entry. Duplicate URLs are merged. The compact inherited-evidence list shows each shared article and its parent groups. White source cards and provider counts cover only item-specific evidence. Remove a URL in the shared panel to stop using it for that group. Re-adding the URL reuses its saved article. Changes queue affected items without starting a build.

## Group batches

Click **⋯** beside any sidebar category or character for **Rebuild from saved sources**, **Rebuild from fresh sources**, or **Fetch evidence URLs only**. It processes every active child in that group, including completed items; sidebar filters do not narrow the batch. Removed items are skipped. The configured run-size limit still applies.

Pause an active job before starting another group. Progress shows the selected group; pause/resume and restart retain that group’s queue. Failed children are marked for attention and the batch continues. Saved mode fetches sources only for children with none. Parent evidence is inherited as usual.

## Find URLs first

For one item, open its rebuild dropdown and select **Fetch evidence URLs only**. This finds links without fetching articles or rebuilding JSON. Pause an active job first; a paused build checkpoint is retained.

Every item’s **Sources & evidence** tab lists inherited references with their parent groups and **Saved / Awaiting capture** status. Click a parent name to manage/capture that shared source. Discovery never copies these links onto the item, even if the agent returns the same article under an equivalent URL.

Choose **Find evidence URLs only** from the top Start menu. It finds and stores Wiki/Lootlemon links across active items, including completed ones, without fetching article HTML or building JSON. Capture the pages in Chrome, then **Start from saved sources**. Failures are flagged and the queue continues; **Needs attention** includes discovery failures.

**Pause / Resume** works for URL discovery too. A paused build is kept separately: **Resume saved build** returns to it afterward. Starting a new build replaces that older checkpoint.

## Character equipment

**Class mods** and **Artifacts** expand into Roland, Lilith, Mordecai and Brick. Class mods are listed by their in-game family names; artifacts have one family per character and element, with upgrade ranks described within that entry. Final JSON includes the character restriction. Old broad placeholders are retired; their previous research/output stays on disk. Existing weapon builds are preserved.

## Item images

Put images in `img/borderlands/` under their type folder, for example `weapons/hellfire.png`. Matching uses item names and aliases; punctuation differences are handled automatically. Preview shows the image even before an item is built. Use **Change image** to correct a match, or return to automatic matching. Added a file or folder? Click **Refresh folder** beside the image selector to reload the list without refreshing the browser or interrupting your batch. Unsaved JSON edits stay intact.

**Coverage → Image coverage** lists missing and ambiguous images, with search and a link to each item. **Refresh images** picks up files you add. Captured candidates awaiting review are included; deliberately excluded items are hidden.

Website JSON includes `image: "weapons/hellfire.png"`, or `null` when missing. The export ZIP remains JSON-only. Your website supplies the base image URL. Saved choices live in `.data/image-overrides.json` and survive restarts and generated resets; a full project reset clears choices and restored project-local images; built-in app image files remain.

## Choose an agent

The toolbar dropdown defaults to **Grok 4.6**; choose **Codex** whenever you prefer. The choice is saved and applies to subsequent calls, including during a run. It does not rebuild completed items.

Writing/rewriting on subscription agents uses **low** effort; extraction, classification and research use **medium**. Grok is pinned to `grok-4.6`; the optional model setting applies only to Codex.

A failed or five-minute call switches to another available agent after the original call stops. Each available agent gets one attempt; if all fail, the queue stops with both reasons and retains progress. Failed agents cool down for ten minutes to avoid repeated delays. **Settings → Recheck agents** clears that cooldown after fixing a connection/account issue.

Grok must permit Build calls: if it reports **Legacy (no storage)** is unsupported, switch your Grok account to **Privacy Mode**. This app does not change account privacy settings. Codex remains available as fallback.

## Chrome capture for blocked sources

Click **Chrome helper** in the toolbar. The app opens Chrome’s extensions page and provides the folder path. Enable **Developer mode**, click **Load unpacked**, select that folder and pin **Borderlens Page Capture**. This one-time Chrome step cannot be installed silently by a website. The connection indicator turns green when ready.

1. Keep the workshop tab open. On an item’s **Sources & evidence**, click **Open wiki in Chrome** (or open a URL entered in the correction form).
2. Wait until the actual article is visible. Click the pinned extension → **Select content on page**.
3. Hold **Ctrl** and drag boxes around useful text. Move boxes by their labels, resize corners, remove with ×, or **Fit content** to complete paragraphs/tables. Green means structurally complete; red needs review. Empty boxes cannot be sent.
4. Check the floating panel’s preview and size. Partial selections require acknowledgement; click **Send to Borderlens**.
5. Return to the workshop. The page is cached, its status updates automatically, and the changes are saved for your next requested build. Click **Rebuild from saved sources** to use them.

No HTML copying or cookie sharing. It captures article content you explicitly send, not browser history or account fields. It makes no background wiki requests and does not solve access challenges. Imports received during processing wait for its next safe checkpoint. Each ticket is tied to one item/article and expires after 30 minutes; open the source again from the app if it expires. Capture does not automatically spend Codex allowance or start a new run.

**Back to workshop** opens Sources & evidence and highlights the captured source (or its shared group). The extension’s **Close source tab when returning after capture** checkbox remembers your choice across browser restarts; it closes the matching source tab only after a saved capture and acknowledged return. Unsent source tabs stay open.

Use **Recapture** on an external evidence card, inherited row or source viewer to reopen that exact URL for a fresh box selection. Shared recaptures save back to their displayed group. Sending replaces the previous saved content, including sections/tables and size; nothing changes until you send. Manual text entries use their pencil editor instead. No build starts automatically.

Selected captures are labelled **Selected page content**, preserve selected headings/tables and deduplicate overlapping boxes. Only those excerpts reach future builds; missing content is not proof of absence. Excerpts stay attached to their item or explicitly promoted parent, survive website refresh and are replaced by recapturing that source. Refresh/navigation/closing the panel discards unsent boxes.

The helper lives in `chrome-extension/`; the setup screen also offers a separate helper ZIP. Keep it in place after loading it. After moving this project or updating extension files, reload the helper through `chrome://extensions/` and refresh the workshop. Website catalogue ZIPs remain item-only.

## Remove a source

In **Sources & evidence**, click the **X** on a saved source card. The article is excluded from this item’s future builds, discovery results and fetching—including fresh-source runs. The change is saved for your next requested build; **Rebuild from saved sources** updates its JSON using the remaining pages. Add a correct source first if none remain. Previous output stays inspectable but is not exported while queued.

Expand **Removed sources** to restore an article. Saved HTML is retained; exclusions survive restarts and generated-data resets and affect only this item. Pause before changing the current processing item’s sources. Manually edited JSON requires review and saving after its sources change.

## Inspect a saved source

Each source card has **Show more**. The read-only modal displays the full stored text, saved sections/tables, the complete source record and archived HTML. Nothing is summarized or rewritten. Formatting wraps text for readability; **Copy** retains the stored values. HTML is shown as inert text, never executed, and is read from the local cache without fetching the website again. The displayed snapshot remains stable while background processing continues.

## Rich catalogue JSON

`schemaVersion` identifies the shared JSON format. `compilerVersion` identifies the compiler rules. `revision` counts successfully saved versions of that item, including saved edits; failed attempts, pause/resume and exports do not increment it. Existing items retain their recorded revision history.

The compiler stores schema **5** internally; **Final JSON** and website exports use self-contained schema **8**. Each item uses a short summary (maximum 200 characters), longer paragraph-array description, additional titled `details` sections, concise special effects, useful notes, meaningful variants, supported stats/levels, and acquisition details including location, DLC, conditions and scoped drop chances. Source references and coverage are private workshop data, excluded from the website JSON. Published numeric ranges appear directly as catalogue stats; no source-reporting labels are attached. The same schema and research instructions apply across every equipment category; unsupported information stays null or empty.

**Source priority:** Lootlemon wins direct contradictions with the Wiki about the same item and conditions. Complementary Wiki facts are still included. Rejected claims and the reason stay in the private source audit. Different editions, roll ranges and conditions remain separate.

Individual articles are read for the item. Shared articles are indexed in full once, with quoted facts tagged by category, character, skill, element, weapon type and item. Unchanged shared indexes survive restarts and fresh-source builds; changed content, model/agent configuration or compiler policy triggers new analysis. Item-specific sources are read first, then only confidently unrelated shared facts are omitted before writing. General rules, uncertain interactions and unknown applicability stay included. Skill/element filters need quoted complete item lists; failed indexing falls back to full item-specific reading. The writer uses all selected facts plus game evidence; selected numeric ranges remain validated. Expand **Last shared-source analysis** in Sources & evidence for kept/skipped decisions and cache counts. Complete original articles remain saved. **Sources & evidence → Compilation coverage** shows the private audit.

Each agent must rewrite all human-readable content in its own language, including descriptions, effects, notes, variants, acquisition text and parts. Copied passages fail validation. Names and exact red flavour text are retained. Research limitations remain in evidence rather than padded public descriptions. Saved HTML is reusable, with headings and tables preserved for future schema improvements.

Each item’s `parts` contains complete readable part objects, including family-specific relationships and notes. The workshop resolves its internal shared catalogue before displaying Final JSON or exporting, so the website needs no joins. Defining parts need a direct captured title relationship. Required/possible options need stronger selection and source evidence; graph proximity alone never establishes compatibility.

Schema/compiler upgrades queue older generated entries for rebuilding while retaining their previous output, sources, overrides and corrections. Old-schema entries remain inspectable but are excluded from current-schema exports. Manually edited old entries are retained for review rather than silently rewritten. Each new entry records schema/compiler versions so later improvements can be applied consistently.

## Website export layout

```text
weapons/hellfire.json
weapons/ajaxs-spear.json
shields/…json
class-mods/…json
grenade-mods/…json
```

Only populated folders are included. Additional supported equipment types use the same naming convention (`artifacts/`, `other-equipment/`). Filenames use readable name slugs; collisions receive type/ID suffixes rather than overwriting data. Each item includes a matching `slug`.

Only completed current-schema entries are exported. Export’s count shows how many are ready. Raw captures, evidence, schemas, overrides, manifests and separate part files stay out of the ZIP. Older generated entries are queued for rebuilding with the new field checklist. Rebuild one item to test, or press Start to process the queue; saved sources are reused. Final JSON shows the same self-contained shape and supports manual prose/part edits.

## Classification overrides

When a **Needs review** weapon has matching saved-page evidence, The selected agent verifies its released-game identity and type. A successful classification moves it into the right sidebar group immediately; selection and active processing stay on the same item.

Corrections live in `.data/classification-overrides.json`. Priority: **manual correction → verified research → raw type**. Captures and item IDs remain untouched. Use **Preview → Item type** (or the same dropdown in Sources & evidence) for any weapon/equipment category; **Automatic** removes the manual choice.

Overrides survive imports, restarts and **Restart generated work**. Keep this file in your workshop backup; it is excluded from website ZIPs. **Clear the entire project** clears them. Back up the file with your project. To restore it into another project using the same capture IDs, put it in that project's data folder and refresh. External file edits are loaded on refresh/poll. A changed type queues an existing completed entry for rebuilding so exported JSON can follow the new classification.

Ambiguous matches, cut content and shared naming modifiers cannot be promoted automatically. Already-running queues keep their captured item order as entries move between sidebar groups; new runs follow the updated navigation.

## Processing status

History records validation failure reasons. Source-page/extraction counters and writing-attempt counters are separate. An active call shows its build attempt, elapsed time and time since the active agent last produced output. Quiet output does not confirm a crash: the local process may still be waiting on the service. Exits/errors stop visibly; each agent attempt is limited to five minutes before automatic fallback. Private `activity.json` and `events.jsonl` files under `.data/ai/` update during the call for diagnosis. Pause waits for the current saved stage.

## Your data

`.data/` contains the SQLite project, original ZIPs, saved HTML, and agent inputs/results. Back up this folder; browser storage holds only viewing preferences. Both the extractor and this app can move with the containing project to another repository.

The app listens on this machine only. Grok uses your Grok subscription and sends selected evidence to xAI; Codex uses your ChatGPT allowance and sends it to OpenAI; web research also needs internet. No paid API-key fallback is enabled. Closing the browser leaves the service working. Stopping the service interrupts work; reopen it and resume.

## First-build limits

The current capture yields **255 family candidates**, not a verified complete catalogue. Discovery uses captured title definitions; coverage matching and shared part rules still need review. Missing stat ranges and level bounds remain null rather than inferred from shared defaults. Useful published ranges are retained even when no specific item level is stated. Evidence references and schema validation help catch mistakes but cannot prove every AI interpretation correct.

Research seeks both wiki and Lootlemon. **Sources & evidence** shows each provider’s saved pages or failure reason. Special-effect explanations are rewritten by the selected agent from saved articles in short, plain gameplay language. Generic site-wide farming tips, routes and fast-travel advice are excluded; notes stay specific to the item.

Some websites may block automated requests. The app reports this and supports the Chrome capture helper, importing saved HTML, or explicitly using game evidence only. A partial coverage scan never counts as proof that all items were found. The exported item schema is defined by `src/shared/website.ts` (Zod).

## Checks

```sh
pnpm check
pnpm test
pnpm build
```

`pnpm test:chrome` checks the real extension bridge/popup with an isolated project and synthetic article. Its temporary test copy grants the fixture host for automation; the shipped helper uses user-invoked activeTab for article access.

For research HTTP simulation, see [postman/README.md](postman/README.md). Optional browser check: `pnpm exec playwright install chromium`, then `pnpm build` and `pnpm exec tsx tests/browser-smoke.ts`. It uses an isolated test database and fake drafting, with the existing capture at `../temp/imports/borderlens-20261023-153827-931444.zip`.

For one real capture check: `pnpm exec tsx tests/real-capture.ts path/to/export.zip`. Adding `--codex` drafts Hellfire using game evidence and your Codex allowance. Temporary test data is removed afterward.

Production build: `pnpm build`, then `pnpm start`. Optional `PORT`, `BORDERLENS_DATA_DIR`, and `BORDERLENS_CODEX` environment variables change the port, local data folder, and CLI executable.

Author: **keogh**. Product context: [APP_PLAN.md](../APP_PLAN.md). Release history: [CHANGELOG.md](../CHANGELOG.md).

Optional live subscription/fallback check: `pnpm exec tsx tests/live-agents.ts`. This sends a tiny test prompt and keeps diagnostics under `../temp/agents-live-*`.

**Move evidence to parent** (up-arrow on an evidence card) shares the article one level higher: item → character/weapon group → category → Everything. Move again from its new shared group to go higher. Saved content is retained; duplicates merge. Evidence edits never start builds or add items to a running queue; affected entries use the changed evidence on your next requested build.

On an item's **Sources & evidence** tab, each inherited source has **Auto / Always include / Never include**. Saved rows also have **View stored content**, opening the full-text, sections/tables, source record and stored HTML/text tabs. Works for manual text and Never include rows too. Auto (default) selects relevant facts and retains uncertain ones. Always include sends every indexed fact to the writer, which can still omit irrelevant information from final JSON. Never include skips that source before fetching, classification, source reading and writing for this item. The article remains saved and visible; other items can still use it. Choices apply on the next requested build and survive restarts/generated resets. Changing a mode never starts a build. Shared category controls have no inclusion dropdowns.

**Additional saved evidence:** while drafting, the agent can request up to three specific missing topics. The workshop searches saved articles and cached fact indexes, then supplies at most four short matches for **one** extra writing pass. No request or no match costs no extra writing call. No new scraping occurs. Never include and removed sources remain excluded. If the extra pass fails, the original draft continues. Sources & evidence shows the requests, exact saved excerpts and any misses. Answers are reused across retries/restarts until their inputs or saved sources change; retrieved pages are not permanently attached to the item. Compiler 0.9.0 adds this step; existing output stays retained until you request a rebuild.

**Build pipeline (compiler 0.13.0):** the app extracts supported game properties
and recognised complete tables, interprets remaining evidence through cached AI
readings, then assembles the factual data. AI writes original prose only; code
combines it with established values and validates the result. Missing data stays
unknown. Shared mechanics, sample values and ordinal progression remain separate
from item stats. Unsupported calculations are not guessed.

Keep capturing useful content with the Chrome selection tool as before. No special
format is required; complete table headers and nearby conditions help. Unknown
layouts and partial selections use interpretation rather than guessed parsing.
Saved HTML/text is never rewritten. The first requested build under this contract
may refresh readings from saved content; no website recapture is required.

Accepted shared interpretations and validated corrections are cached against their
evidence version and scope. Prose corrections preserve established facts and valid
text; changes to sources/overrides invalidate dependent results. No automatic
global AI rules are created. Existing JSON/manual corrections remain retained.

AI evidence statistics show actual prompt bytes/characters and CLI round-trip time
when recorded, plus source sends, cache hits and labelled retries. Prompt sizes
exclude schemas/wrappers; provider token counts are not estimated as exact usage.
See [the implementation plan](OFFLINE_BUILD_PLAN.md) and
[isolated payload measurements](OFFLINE_BUILD_BASELINE.md).

### Builds with incomplete evidence

Automatic builds save the best supported entry instead of waiting for perfect
research. Optional names, progression uncertainty, numerical disagreements and
minor wording issues become **Built with … notes** in Preview and are retained
in History/provenance. Unsupported optional sources and conditions may be omitted;
missing evidence is not a player acquisition requirement. Equally ranked source
values use the first supported value; existing source priority still applies.
Original AI wording, valid JSON, core item identity, valid bounds and captured
part relationships remain checked. No recapture required: rebuild from saved sources.

Acquisition facts for the same named source are combined before the AI wording
pass, keeping separate reward/playthrough contexts. Different known locations
and conditional drop rates remain distinct. Alternate names merge only when a
captured quote explicitly establishes the alias. Source slots carry original
reward/drop facts so the writer can retain useful rank and random-reward details.

The DLC field distinguishes **Base Game** from **Unknown**. Original identity
roots in reviewed base-game packages establish Base Game; DLC identity packages
or explicit origin evidence establish expansions. Shared drop locations and a
missing DLC prefix alone do not establish origin. Existing outputs are retained
until rebuilding; compatible saved interpretations need no new AI read.

**Whole-page Chrome capture:** in the extension popup or floating selection panel,
choose **Capture whole page** to save all loaded article text/tables without boxes.
The box selection tools remain available. Whole-page capture includes loaded
Lootlemon content even without a main/article wrapper; it does not fetch unloaded
data. Recapture replaces the saved source at its existing owner and never starts
a build. After updating, reload the extension in chrome://extensions and refresh
the workshop/source tabs.
