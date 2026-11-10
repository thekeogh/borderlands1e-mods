# Borderlens Extractor

Export raw Borderlands GOTY Enhanced game data and catalogue crawl seeds: equipment, characters/enemies, missions, skills, regions, manufacturers, loot pools and their relationships.

**Extractor 0.3.2** includes name/ID records, 219 reviewed data packages, and a read-only scan of installed English localisation. It adds NPC definitions, ECHO callers, mission givers and travel/map identifiers. This can find names from content you have not visited. It does **not** guarantee a complete catalogue or identify every character as a boss, named enemy or NPC. No full playthrough is needed.

## Use

Requires the [BL1 Enhanced Python SDK](https://bl-sdk.github.io/).

1. Copy [`BorderlensExtractor.sdkmod`](extractor/dist/BorderlensExtractor.sdkmod) into the game's `sdk_mods` folder.
2. For this clean test, disable other mods, including One Playthrough, **fully restart the game**, and enable **Borderlens Extractor**. Keep the Python SDK and its required framework mods enabled.
3. Load any solo character, or start a new one. Wait until you can move and see the HUD.
4. Close menus and press **F9**. Leave **Export scope** on **Catalogue packages**. Stay on this map while it runs; you do not need to collect anything or fight enemies.
5. Follow progress and wait for **Export ZIP ready** in `Binaries/Win64/Plugins/unrealsdk.log`. The mod menu's **Show export status** also writes to this log. No `status.json` is written; obsolete status files are deleted on startup when possible.
6. Copy the resulting ZIP from `sdk_mods/settings/BorderlensExtractor/exports/` into this project's `temp/imports/` folder for inspection. Keep its contents intact.

Expect some loading pauses. F9 pauses/resumes the export. Upgrading the extractor starts a fresh capture and keeps older exports intact. If the previous export folder was deleted, F9 starts a new capture automatically. After a crash or restart, load a solo character and press F9 to resume committed data; an interrupted package load is skipped and reported. The mod menu also offers **Show export status**, **Start fresh export**, and **Finish partial export now**.

The ZIP now includes `catalogue_identity` JSON records alongside raw evidence. Names retain their source fields; entries without readable names retain asset IDs. Installed localisation candidates keep their file/section locators and are not automatically merged with game assets. Package filenames/header summaries and scan diagnostics help identify gaps after testing. The scan never loads maps. Keep the whole ZIP when returning a capture for review.

Callers can be people or organisations; mission givers can be characters, bounty boards or devices. They retain separate categories. Map package names and travel keys stay internal identifiers, not invented display names. Existing evidence is retained for later matching and alias cleanup.

If something fails, bring back the export folder/ZIP and relevant SDK log lines. **Loaded data only** provides a smaller diagnostic snapshot. Disable the extractor when finished.

The extractor generates no items and changes no gameplay values or character saves. It temporarily keeps data assets loaded while scanning, then releases its own liveness pins. Native Windows testing of 0.3.2 is still needed.

## Catalogue app

Use the [local Borderlens workshop](app/README.md) to import an export ZIP, research item families and build validated JSON. Runs independently of the game.

## Project layout

- `extractor/` — SDK mod source, builds, tests and [raw format](extractor/FORMAT.md).
- `app/` — local catalogue UI, processing service, schema and checks.
- `compiler/` — reserved; compilation currently lives in the app service.
- `temp/` — ignored exports and scratch files.

Release history: [CHANGELOG.md](CHANGELOG.md).
