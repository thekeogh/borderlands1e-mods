# Borderlands GOTY Enhanced — Extracted Game Data

Raw game evidence and catalogue seeds for building a Borderlands database website. Includes equipment, enemies/bosses, NPC definitions, contacts, missions, skills, locations and their underlying rules/references, with base-game and DLC content represented.

**This capture is ready for catalogue discovery and external research. It is not a verified complete catalogue or finished website database.** Deduplication, classification, unused-content filtering and comparison against external inventories remain necessary.

## Capture details

- **Archive:** `borderlens-20261110-124546-348467.zip`
- **Extractor:** Borderlens Extractor **0.3.2**, by keogh
- **Game:** Borderlands GOTY Enhanced (`BL1E`), Windows; not BL2/TPS or a verified original-BL1 export
- **Raw format:** version **1**; catalogue identity version **2**
- **Captured:** 10 November 2026, **12:45:46–12:59:25 UTC**
- **Mod snapshot:** only Python SDK and Borderlens Extractor enabled; other listed mods disabled
- **Package loading:** **219/219** reviewed data packages reported loaded
- **Installation scan:** **3,273** package files inventoried; **280** English localisation files read

The manifest leaves the executable build and vanilla status unverified. The mod snapshot documents enabled state; it is not independent verification of original game files.

Archive SHA-256:

```text
6fd68f2216598192fe690943659a797b2d7b2863c2cea8c51f16c63798eeeada
```

## What is inside

- **Equipment evidence:** weapons, shields, grenade mods, class mods, artifacts/elemental upgrades and other items; parts, prefixes/titles, manufacturers, grades, balances, attributes and scaling rules.
- **Characters and sources:** enemy/boss names and definitions, NPC definition IDs, ECHO callers, mission givers, population/spawn definitions, loot pools and supported source relationships.
- **Other catalogue material:** missions, skills, challenges, character classes, vehicles, regions, readable travel/location labels and internal map/travel identifiers.
- **Raw supporting evidence:** reflected class/struct schemas, typed object references, supported behaviours/actions/conditions, expression/formula data and limited loaded-map/actor-template bindings.
- **Installed-file evidence:** package filenames, sizes and provisional header summaries; selected English localisation names with source-file checksums, sections, fields and line numbers.
- **Capture metadata:** package-load outcomes, counts/checksums, session/map context, mod snapshot, read errors, omissions and coverage limits.

Installed package records are **metadata**, not the package contents. Localisation records are selected extracted fields, not copies of the original INT/ENG files.

## ZIP layout and record counts

```text
borderlens-20261110-124546-348467/
  manifest.json
  data/
    records-00001.json
    ...
    records-00652.json
```

Each chunk is a JSON array containing mixed record types. Files are chunks, **not one file per item, enemy or category**.

| Record type | Count | Meaning |
| --- | ---: | --- |
| `object` | 41,802 | Reflected data definitions, rules and supporting objects |
| `catalogue_identity` | 9,924 | Asset identities and name/reference candidates for later research |
| `package_file` | 3,273 | Installed package-file metadata |
| `localisation_file` | 280 | English localisation-file metadata |
| `class_schema` | 581 | Reflected class fields and inheritance metadata |
| `struct_schema` | 213 | Reflected struct fields |
| `archetype_binding` | 493 | Limited actor-template evidence |
| `world_binding` | 125 | Limited loaded-world actor evidence |
| **Total** | **56,691** | Across **652** chunks |

The review verified ZIP CRCs, chunk SHA-256 hashes, byte/record counts, unique record IDs and catalogue-to-source record links. External game references can still point to unexported assets.

## Observed catalogue coverage

These counts describe extracted evidence, **not final website-entry totals**:

| Evidence | Count |
| --- | ---: |
| Distinct character/enemy labels, including variants | 647 |
| NPC definition IDs; these records have no readable names | 57 |
| Distinct ECHO caller labels | 33 |
| Distinct mission-giver labels | 46 |
| Distinct readable location labels | 75 |
| Distinct internal map identifiers in map candidates | 74 |

Confirmed examples include Sledge, Bone Head, Krom, The Destroyer, Crawmerax the Invincible, General Knoxx, Undead Ned and MINAC. Caller/giver evidence includes Dr. Zed, Marcus Kincaid, Scooter, Patricia Tannis and T.K. Baha. Readable locations include Fyrestone and New Haven.

All 59 caller/mission-giver labels missed by the previous index are now indexed. That verifies the identified indexing fix, **not every possible NPC or source**. Generic variants, aliases, duplicate evidence, test entries and unused content remain present.

## Known errors and warnings

1. **80 read errors:** 40 `Engine.SeqAct_Interp` objects each failed to expose `SavedActorTransforms` and `SavedActorVisibilities`, reporting `Unknown object type MapProperty`. These are cinematic transform/visibility caches, not failed name-field reads. Errors remain recorded explicitly; values were not invented.
2. **One cleanup warning:** the extractor could not resolve this temporarily pinned asset when releasing its liveness pin:

   ```text
   gd_CommandDecks.Body_Loyalty.Loyalty_Gearbox:Behavior_AddInstanceData_38
   ```

   Its exported object record is present with `complete: true`. The warning concerns cleanup after capture, not a missing export of that object. Restart the game after extraction to clear session state.

There were **no reported missing-object entries during scanning, no serialization truncation, no installation-scan errors, no configured limits hit and no failed/unconfirmed package loads**. The manifest correctly retains `coverage.data_issues: true` because of the errors/warning above.

## What is absent or not established

- A deduplicated, classified website database or one canonical record per item family/character.
- An exhaustive list of every published item, named enemy, boss, NPC, mission, map or drop source. `coverage.catalogue_complete` and `catalogue.complete` are both **false**.
- Authoritative boss/enemy/NPC roles, alias equivalence, or separation of released content from unused/developer content.
- Every generated equipment combination, final stat minima/maxima, verified drop probabilities or complete dynamic/mission-dependent source associations. Raw rules/weights alone do not establish those results.
- Complete dumps of every map, gameplay actor, script or native-code rule. Only reviewed data packages were explicitly requested; the extractor did not request map-package loads. Map-specific bindings come from the loaded session.
- Original UPK/map files, binary assets, textures, audio, screenshots or website-ready images.
- Wiki/Lootlemon pages, external descriptions, verified page matches or a ready-made crawl queue.
- Character save files, account identifiers or player save inventories. Session provenance is included separately.

`status: "complete"` means the configured capture finished. It does **not** override these coverage limitations.

## Guidance for AI and database consumers

1. **Read `manifest.json` first.** Check edition, format/version, checksums, sessions, package results, limits and diagnostics. Read every listed chunk; do not infer categories from chunk filenames.
2. **Preserve evidence.** Keep record `id`, asset `path`, class, source record/file, field/index, line, checksum and session context. `$ref` values are references; `$type` wrappers distinguish structs, arrays, names and error/truncation markers.
3. **Distinguish evidence types.** `asset_evidence` links to reflected assets. `localisation_candidate` uses file/section evidence; its asset/class hints are not verified paths. `field_candidate` and `localisation_field_candidate` identify related labels/keys, not resolved actor IDs.
4. **Keep names and identifiers separate.** Internal map package names/travel keys are not display names. A caller may be an organisation; a mission giver may be a bounty board or device. Unnamed NPC definitions still have useful IDs.
5. **Group carefully.** Multiple assets, localisation sections and source fields can describe the same entity. Prefixes/titles are not automatically item families; manufacturer labels can include grade variants. Preserve aliases and source-specific differences until a match is supported. Null role/origin fields mean unknown, not false or base-game confirmation.
6. **Research remaining gaps.** Compare edition-appropriate Wiki/Lootlemon inventories, resolve identities, classify entries and filter test/unused candidates before publishing. Do not fabricate missing facts or treat a successful capture as proof of completeness.
