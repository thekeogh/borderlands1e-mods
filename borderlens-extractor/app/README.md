# Borderlens workshop

A local workspace for turning BL1 Enhanced extractions into readable item-family JSON. Import a capture, press **Start from saved sources**, and browse while it researches and builds each entry. Progress, pages and corrections are saved on disk.

## Where data lives

Paths are relative to this folder (default configuration).

| Path                                  | Contents                                                                                                     |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| `.data/workshop.sqlite`               | Built item JSON, drafts, extracted records, source facts, corrections, removed items, progress and settings. |
| `.data/captures/`                     | Imported extractor ZIPs.                                                                                     |
| `.data/sources/`                      | Saved Wiki/Lootlemon HTML, including Chrome captures.                                                        |
| `.data/classification-overrides.json` | Item category and weapon-type overrides.                                                                     |
| `.data/image-overrides.json`          | Manual image selections.                                                                                     |
| `.data/ai/`                           | Agent requests, responses, caches and logs.                                                                  |
| `.data/ai/agent-failures.json`        | Last agent failures and fallback cooldowns.                                                                  |
| `img/borderlands/`                    | Item images, organised by type.                                                                              |
| `src/shared/models.ts`                | Internal item and writer Zod schemas.                                                                        |
| `src/shared/website.ts`               | Final website JSON Zod schema.                                                                               |
| `src/shared/versions.ts`              | Schema and compiler versions.                                                                                |

**Export** downloads `borderlens-catalogue.zip`, containing final item `.json` files in type folders. Individual final JSON files are generated on export, not saved separately in the app folder.

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
3. Inspect **Preview**, **Sources & evidence**, **History**, or **Final JSON** while it works. Selecting another item never interrupts processing.
4. **Pause** saves the current step before stopping. **Resume** continues from that checkpoint, including after restarting the service.
5. If it needs help, add a source URL, saved page HTML, or correction under **Sources & evidence**, then resume. Corrections are remembered.
6. **Export** downloads completed item JSON files in type folders, ready for the website. Each file includes its full parts data; the ZIP contains no supporting files.

Website JSON groups each drop location with its conditional drop rates, including player counts when known. Stats distinguish card values from scoped or other conditional values. Empty note strings are omitted; unsupported level limits stay `null`. After a compiler upgrade, rebuild queued items to update their JSON; saved pages and previous output remain on disk.

**Rebuild from saved sources** reuses saved pages and their extracted facts, then writes and validates again. Switching agents does not repeat complete source analysis. Newly added or changed saved pages are read if needed; nothing is fetched.

**Rebuild from fresh sources** fetches current pages, reads their facts again, then rebuilds. Blocked refreshes keep the saved pages; capture the blocked article in Chrome and resume. Both options are in the dropdown beside the rebuild button. Saved sources is the default when pages exist.

The top Start dropdown offers the same two source choices for the batch. **Start from saved sources** uses each item's saved pages/facts and fetches sources for items with no saved pages. **Start from fresh sources** refreshes sources for each item. Both process unfinished items, skipping completed and excluded entries. If an item fails, it gets a red cross and the batch continues. Use **Needs attention** afterward to correct and retry failures. Individual rebuilds stop on errors. **Pause/Resume** keeps the selected mode and saved step; starting a new batch restarts unfinished work.

**Start from here** processes the remaining sidebar range, skipping ready items. Rebuilds requested during an active run queue behind it with the chosen source mode. Manually saved JSON survives rebuilds.

Completed items pass source checks and a final whole-document check for JSON syntax, schema and consistency. Preview shows **Final JSON checked**. Exports are checked again; malformed edits cannot replace the last valid item. Element names are consistent across all equipment.

**Coverage** compares extracted families with wiki/Lootlemon listings. Link ambiguous names to a family or exclude irrelevant candidates. Settings control writing style, optional game-evidence-only processing, run size, and resets.

Category and character-group badges show **completed / needs attention / total**. Hover for waiting and processing counts. Counts follow the current search/filter.

## Remove an item

In **Preview**, click the red **Remove from catalogue** button on the right. The item disappears from normal navigation and is skipped by batches and exports. **Removed items** in the sidebar lets you inspect it and **Restore to catalogue** later. Saved data is retained; removal survives restarts, capture imports and generated-data resets. Restoring does not start a build. Pause before removing the item currently being processed.

Verified item-specific BL1 Lootlemon shield/grenade pages can also correct entries initially grouped as **Other equipment**. Category overrides persist in `classification-overrides.json`; IDs and saved research stay intact. Corrected entries export under their actual category.

## Character equipment

**Class mods** and **Artifacts** expand into Roland, Lilith, Mordecai and Brick. Class mods are listed by their in-game family names; artifacts have one family per character and element, with upgrade ranks described within that entry. Final JSON includes the character restriction. Old broad placeholders are retired; their previous research/output stays on disk. Existing weapon builds are preserved.

## Item images

Put images in `img/borderlands/` under their type folder, for example `weapons/hellfire.png`. Matching uses item names and aliases; punctuation differences are handled automatically. Preview shows the image even before an item is built. Use **Change image** to correct a match, or return to automatic matching. Added a file or folder? Click **Refresh folder** beside the image selector to reload the list without refreshing the browser or interrupting your batch. Unsaved JSON edits stay intact.

**Coverage → Image coverage** lists missing and ambiguous images, with search and a link to each item. **Refresh images** picks up files you add. Captured candidates awaiting review are included; deliberately excluded items are hidden.

Website JSON includes `image: "weapons/hellfire.png"`, or `null` when missing. The export ZIP remains JSON-only. Your website supplies the base image URL. Saved choices live in `.data/image-overrides.json` and survive restarts and generated resets; a full project reset clears choices but keeps the image files.

## Choose an agent

The toolbar dropdown defaults to **Grok 4.6**; choose **Codex** whenever you prefer. The choice is saved and applies to subsequent calls, including during a run. It does not rebuild completed items.

Writing/rewriting on subscription agents uses **low** effort; extraction, classification and research use **medium**. Grok is pinned to `grok-4.6`; the optional model setting applies only to Codex.

A failed or five-minute call switches to another available agent after the original call stops. Each available agent gets one attempt; if all fail, the queue stops with both reasons and retains progress. Failed agents cool down for ten minutes to avoid repeated delays. **Settings → Recheck agents** clears that cooldown after fixing a connection/account issue.

Grok must permit Build calls: if it reports **Legacy (no storage)** is unsupported, switch your Grok account to **Privacy Mode**. This app does not change account privacy settings. Codex remains available as fallback.

## Chrome capture for blocked sources

Click **Chrome helper** in the toolbar. The app opens Chrome’s extensions page and provides the folder path. Enable **Developer mode**, click **Load unpacked**, select that folder and pin **Borderlens Page Capture**. This one-time Chrome step cannot be installed silently by a website. The connection indicator turns green when ready.

1. Keep the workshop tab open. On an item’s **Sources & evidence**, click **Open wiki in Chrome** (or open a URL entered in the correction form).
2. Wait until the actual article is visible. Click the pinned extension → **Send page to Borderlens**.
3. Return to the workshop. The page is cached, its status updates automatically, and the item is queued for rebuilding. Click **Rebuild this item**, or resume your existing run.

No HTML copying or cookie sharing. It captures article content you explicitly send, not browser history or account fields. It makes no background wiki requests and does not solve access challenges. Imports received during processing wait for its next safe checkpoint. Each ticket is tied to one item/article and expires after 30 minutes; open the source again from the app if it expires. Capture does not automatically spend Codex allowance or start a new run.

The helper lives in `chrome-extension/`; the setup screen also offers a separate helper ZIP. Keep it in place after loading it. After moving this project or updating extension files, reload the helper through `chrome://extensions/` and refresh the workshop. Website catalogue ZIPs remain item-only.

## Inspect a saved source

Each source card has **Show more**. The read-only modal displays the full stored text, saved sections/tables, the complete source record and archived HTML. Nothing is summarized or rewritten. Formatting wraps text for readability; **Copy** retains the stored values. HTML is shown as inert text, never executed, and is read from the local cache without fetching the website again. The displayed snapshot remains stable while background processing continues.

## Rich catalogue JSON

`schemaVersion` identifies the shared JSON format. `compilerVersion` identifies the compiler rules. `revision` counts successfully saved versions of that item, including saved edits; failed attempts, pause/resume and exports do not increment it. Existing items retain their recorded revision history.

The compiler stores schema **5** internally; **Final JSON** and website exports use self-contained schema **8**. Each item uses a short summary (maximum 200 characters), longer paragraph-array description, additional titled `details` sections, concise special effects, useful notes, meaningful variants, supported stats/levels, and acquisition details including location, DLC, conditions and scoped drop chances. Source references and coverage are private workshop data, excluded from the website JSON. Published numeric ranges appear directly as catalogue stats; no source-reporting labels are attached. The same schema and research instructions apply across every equipment category; unsupported information stays null or empty.

**Source priority:** Lootlemon wins direct contradictions with the Wiki about the same item and conditions. Complementary Wiki facts are still included. Rejected claims and the reason stay in the private source audit. Different editions, roll ranges and conditions remain separate.

Every saved article is read in full, in cached chunks when necessary. First builds take longer; subsequent builds reuse readings unless source content, corrections, model or compiler version changes. The selected agent extracts facts using a category-specific checklist, then writes one entry from all source ledgers plus game evidence. Every extracted fact must be used or explicitly accounted for; missing numeric ranges fail validation. **Sources & evidence → Compilation coverage** shows the private audit.

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

Corrections live in `.data/classification-overrides.json`. Priority: **manual correction → verified research → raw type**. Captures and item IDs remain untouched. You can set a manual type under **Sources & evidence → Weapon classification**; selecting **Use researched / raw classification** removes the manual choice.

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
