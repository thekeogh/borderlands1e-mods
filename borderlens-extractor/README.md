# Borderlens Extractor

Export raw Borderlands GOTY Enhanced item data for the Borderlens catalogue: weapons, shields, grenade mods, class mods, parts, manufacturers, loot pools and their relationships.

This first build collects evidence. It does **not** produce final item-family JSON or guarantee that every item and drop source has been found. No full playthrough is needed.

## Use

Requires the [BL1 Enhanced Python SDK](https://bl-sdk.github.io/).

1. Copy [`BorderlensExtractor.sdkmod`](extractor/dist/BorderlensExtractor.sdkmod) into the game's `sdk_mods` folder.
2. Disable gameplay mods, including One Playthrough. Fully restart the game, then enable **Borderlens Extractor**. Keep the SDK's required framework mods enabled.
3. Load any solo character, or start a new one. Wait until you can move and see the HUD.
4. Close menus and press **F9**. Leave **Export scope** on **Catalogue packages**. Stay on this map while it runs; you do not need to collect anything or fight enemies.
5. Wait for **Export ZIP ready** in `Binaries/Win64/Plugins/unrealsdk.log`. Live progress is also written to `sdk_mods/settings/BorderlensExtractor/status.json`.
6. Copy the resulting ZIP from `sdk_mods/settings/BorderlensExtractor/exports/` into this project's `temp/imports/` folder for inspection. Keep its contents intact.

Expect some loading pauses. F9 pauses/resumes the export. Upgrading the extractor starts a fresh capture and keeps older exports intact. If the previous export folder was deleted, F9 starts a new capture automatically. After a crash or restart, load a solo character and press F9 to resume committed data; an interrupted package load is skipped and reported. The mod menu also offers **Show export status**, **Start fresh export**, and **Finish partial export now**.

If something fails, bring back the export folder/ZIP and relevant SDK log lines. **Loaded data only** provides a smaller diagnostic snapshot. Disable the extractor when finished.

The extractor generates no items and changes no gameplay values or character saves. It temporarily keeps data assets loaded while scanning, then releases its own liveness pins. First-build native Windows testing is still needed.

## Catalogue app

Use the [local Borderlens workshop](app/README.md) to import an export ZIP, research item families and build validated JSON. Runs independently of the game.

## Project layout

- `extractor/` — SDK mod source, builds, tests and [raw format](extractor/FORMAT.md).
- `app/` — local catalogue UI, processing service, schema and checks.
- `compiler/` — reserved; compilation currently lives in the app service.
- `temp/` — ignored exports and scratch files.

Release history: [CHANGELOG.md](CHANGELOG.md).
