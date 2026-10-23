# Borderlens workshop

A local workspace for turning BL1 Enhanced extractions into readable item-family JSON. Import a capture, press **Start**, and browse while it researches and builds each entry. Progress, pages and corrections are saved on disk.

## Start

Requires Node.js **22.13+**, pnpm, and the **Codex CLI signed in with ChatGPT** (`codex login`). No OpenAI API key needed.

From this folder:

```sh
pnpm install
pnpm dev
```

Open **http://127.0.0.1:4317**.

1. Import the ZIP produced by Borderlens Extractor. Keep the archive intact.
2. Select an item and **Rebuild this item** to try one first, or press **Start** for the ordered catalogue queue.
3. Inspect **Preview**, **Sources & evidence**, **History**, or **Final JSON** while it works. Selecting another item never interrupts processing.
4. **Pause** saves the current step before stopping. **Resume** continues from that checkpoint, including after restarting the service.
5. If it needs help, add a source URL, saved page HTML, or correction under **Sources & evidence**, then resume. Corrections are remembered.
6. **Export** downloads completed item JSON files in type folders, ready for the website. Each file includes its full parts data; the ZIP contains no supporting files.

**Start from here** processes the remaining sidebar range, skipping ready items. **Rebuild this item** reuses research; during an active run it queues behind that run. **Refresh sources** explicitly requests fresh research. Manually saved JSON survives rebuilds.

**Coverage** compares extracted families with wiki/Lootlemon listings. Link ambiguous names to a family or exclude irrelevant candidates. Settings control writing style, optional game-evidence-only processing, run size, and resets.

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

The compiler stores schema **2** internally; **Final JSON** and website exports use self-contained schema **3**. Each item uses a short summary (maximum 200 characters), paragraph-array description, concise special effects, useful notes, meaningful variants, supported stats/levels, and acquisition details including location, DLC, conditions and scoped drop chances. `references` credits the archived source pages. The same schema and research instructions apply across every equipment category; unsupported information stays null or empty.

Codex rewrites useful source content in original language. Names and exact red flavour text are retained. Research limitations remain in evidence rather than padded public descriptions. Saved HTML is reusable, with headings and tables preserved for future schema improvements.

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

Only completed current-schema entries are exported. Export’s count shows how many are ready. Raw captures, evidence, schemas, overrides, manifests and separate part files stay out of the ZIP. Existing saved entries need no AI rebuild for this export change. Final JSON shows the same self-contained shape and supports manual prose/part edits.

## Classification overrides

When a **Needs review** weapon has matching saved-page evidence, Codex verifies its released-game identity and type. A successful classification moves it into the right sidebar group immediately; selection and active processing stay on the same item.

Corrections live in `.data/classification-overrides.json`. Priority: **manual correction → verified research → raw type**. Captures and item IDs remain untouched. You can set a manual type under **Sources & evidence → Weapon classification**; selecting **Use researched / raw classification** removes the manual choice.

Overrides survive imports, restarts and **Restart generated work**. Keep this file in your workshop backup; it is excluded from website ZIPs. **Clear the entire project** clears them. Back up the file with your project. To restore it into another project using the same capture IDs, put it in that project's data folder and refresh. External file edits are loaded on refresh/poll. A changed type queues an existing completed entry for rebuilding so exported JSON can follow the new classification.

Ambiguous matches, cut content and shared naming modifiers cannot be promoted automatically. Already-running queues keep their captured item order as entries move between sidebar groups; new runs follow the updated navigation.

## Your data

`.data/` contains the SQLite project, original ZIPs, saved HTML, and Codex inputs/results. Back up this folder; browser storage holds only viewing preferences. Both the extractor and this app can move with the containing project to another repository.

The app listens on this machine only. Codex uses your ChatGPT allowance and sends selected evidence to OpenAI for processing; web research also needs internet. No paid API-key fallback is enabled. Closing the browser leaves the service working. Stopping the service interrupts work; reopen it and resume.

## First-build limits

The current capture yields **255 family candidates**, not a verified complete catalogue. Discovery uses captured title definitions; coverage matching and shared part rules still need review. Unknown stat ranges and level bounds remain unknown rather than inferred from shared defaults. Evidence references and schema validation help catch mistakes but cannot prove every AI interpretation correct.

Research seeks both wiki and Lootlemon. **Sources & evidence** shows each provider’s saved pages or failure reason. Special-effect explanations are rewritten by Codex from saved articles in short, plain gameplay language.

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
