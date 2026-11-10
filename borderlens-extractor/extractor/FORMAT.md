# Raw format v1

A capture is evidence for building a catalogue, not the catalogue itself. Preserve the original ZIP; future compilation should retain references back to these records.

## Files

```text
borderlens-<UTC timestamp>/
  manifest.json
  data/
    records-00001.json
    records-00002.json
```

Each chunk is a JSON array. The manifest lists only committed chunks, with relative path, record count, byte length and SHA-256 digest. Chunks and checkpoints use temporary files followed by atomic replacement. The ZIP contains only the current capture's committed chunks and manifest, under its capture folder.

`latest.json` lives beside `exports/`, outside individual captures, and points at the checkpoint. From extractor 0.3.1, progress/status goes only to the SDK log; `status.json` is never written. Obsolete `status.json` and `status.json.tmp` are deleted on startup when possible; a locked file is ignored. A ZIP appears after capture and packaging finish. A `.zip.partial` is unfinished packaging, not an importable archive.

## Manifest

- `format_version`, `extractor_version`, `configuration`: protocol, tool version, scope, package-plan hash and explicit limits.
- `session`, `sessions`: initial and subsequent contexts, persistent map, streamed-level packages/loaded-level paths (or a read error), raw profile level, character class, SDK/Python versions and installed/enabled mod snapshots. No player name, save content or account identifiers are exported. The game executable's build is explicitly unverified.
- `status`: running, paused, failed or complete. **Complete means capture finished**, including an intentionally partial capture; it does not mean catalogue completeness. ZIP packaging follows capture completion.
- `counts`, `chunks`: record kinds and committed-file checksums.
- `discovered_classes`, `package_inventory`: eligible reflected class paths and packages already loaded at the start of each session; package presence is not proof that all exports are loaded.
- `package_results`: ordered attempts with names, evidence labels, timestamps and loaded/not_confirmed/failed/interrupted/quarantined outcomes. Candidate names may not exist in every edition.
- `failures`, `missing_objects`, `external_references`, `serialization`: bounded diagnostics and omission counts.
- `coverage`: limitations, recovery/provenance notes and `catalogue_complete: false`.
- `lookup`: direct/normalized/exact-class lookup counts and up to 100 recovery examples. Counts include liveness-pin release lookups; resumed sessions retain earlier totals.
- `catalogue` (0.3.0+): identity-record counts by category and with/without name labels. Counts describe evidence records, not distinct characters or final equipment families. `complete` remains false.
- `installation_scans` (0.3.0+, catalogue scope): per-session read-only disk-scan status, package/localisation-file counts, named-section counts, bounded errors/limit examples with omission counters and symlink skips. An unavailable scan does not prevent the SDK capture. No absolute installation path is needed in these records.
- `phase`, `progress`: last saved work state and largest measured work-step duration. These are diagnostic context, not a portable scan cursor.

Resume checks format, extractor version, configuration, safe paths, checksums, record counts and duplicate IDs. It rescans roots, skipping committed record IDs. A changed mod snapshot is recorded as mixed provenance. Previously committed records retain their original session and are not overwritten. Orphan/uncommitted files are not included in the ZIP.

From 0.3.2, resume first reindexes committed raw sources and localisation sections to repair identities missing if a chunk was committed between its source and dependent seeds. Existing identity IDs are skipped. Reindexing uses saved JSON only; it does not re-read native objects or replace their original evidence.

A checkpoint written immediately before each native package load identifies a load interrupted by a crash. Resuming quarantines that package; starting fresh retries it. Native faults cannot be caught by Python.

## Record types

### `object`

A non-actor data definition, resolver, rule, curve, expression tree/evaluator, population factory, behavior or supported sequence action/condition. Roots are discovered by class-name policy, then eligible referenced data assets are followed. This is intentionally broader than item instances so balance, title, part and source rules can be inspected.

```json
{
  "record_type": "object",
  "id": "object:gd_example.weapons.rifle",
  "path": "gd_Example.Weapons.Rifle",
  "class": "WillowGame.WeaponDefinition",
  "name": "Rifle",
  "outer": "gd_Example.Weapons",
  "is_default": false,
  "context": {"session": 0, "map": "Arid_P"},
  "properties": {
    "DisplayName": "Example only",
    "ManufacturerDefinition": {
      "$ref": "gd_Example.Manufacturers.Example",
      "class": "WillowGame.ManufacturerDefinition"
    }
  },
  "issues": [],
  "complete": true
}
```

The example illustrates structure, not actual game values. `complete` means this object's selected fields serialized without reported issues; it does not establish that all referenced assets were exported.

### `class_schema` / `struct_schema`

Stable `class:<Unreal path>` / `struct:<Unreal path>` IDs, parent struct path and reflected properties. Field metadata includes name, Unreal property type, flags, array dimension, and available object-class/struct/enum/array-inner information. Enum declarations include names/numeric values when exposed by the SDK. Runtime fields such as vtables, linker state, outer/class and object flags are excluded from property dumps; identity is captured separately. Struct fields retain their declared names, including fields called `Name`.

### `world_binding` / `archetype_binding`

Limited source evidence from actors already loaded on the current map, or pawn/vehicle archetypes. In 0.3.0 exact subclasses of the supported actor bases are rescanned after data-package loads, including unreferenced templates. `AIPawnName`, menu/vehicle names and optional `binding_category` add identity evidence. Only fields matching definition/loot/drop/inventory/population/behavior/identity terms are read. IDs also include map name. Actors are never pinned, spawned, initialized or evaluated for stats. These records are **not** a complete actor dump or a complete list of drop sources.

### `catalogue_identity` (extractor 0.3.0+)

A lightweight crawl seed, stored in the same checksummed JSON chunks as raw records:

- Reflected assets use `id: "identity:<source record ID>"`, `identity_status: "asset_evidence"`, exact `asset_path`, `class`, `internal_name`, `source_record` and capture `context`. Defaults are excluded. `source_complete` follows the raw record's serialization status.
- `names` contains observed strings with their exact source field/index paths. Enemy balance grade names are retained separately even when multiple names share an asset. No readable name is invented for an enum or internal identifier; unnamed relevant assets still receive a seed.
- `category` identifies characters, missions, skills, character classes, manufacturers, regions, challenges, vehicle definitions, equipment names/parts/balances, weapon types, items and loot/population/interactive sources. Other definitions with recognized name fields use `named_definition`. Equipment-name records include prefixes and titles, not only final item families.
- `character_role`, `is_boss` and `is_named_enemy` remain null. Extracted labels/paths alone are not authoritative classifications. `origin_hint` is a DLC namespace hint or null; null does not assert base-game origin.
- English localisation candidates use `identity_status: "localisation_candidate"`, `source_file`, file `source_sha256`, `source_record`, `section`, `section_occurrence`, line/field-located `names` and `locator_id`. Their record ID combines a stable locator and source-file checksum so a changed file on resume retains both pieces of evidence. Repeated sections retain separate occurrences.
- Localisation `asset_path` and `class` remain null. Optional `asset_path_hint` and `class_hint` are reconstructed from the filename/section and need matching to reflected evidence. Category hints may come from a section class, label key or filename. These records can include unused/developer content and are not automatically merged with assets or external pages.
- Oversized localisation lines/name collections record omissions and `source_complete: false`; files over their byte budget are skipped explicitly.

Extractor 0.3.2 uses `configuration.catalogue_identity_version: 2` (raw format remains v1). Additional categories include `npc` for interactive NPC definitions, `contact` for ECHO caller definitions, `mission_giver`, `location`, `location_list`, `map` and `map_list`. A contact or mission giver is not necessarily a person, and a location definition is not a confirmed farming source. Unsupported/unreadable labels do not become invented names; relevant unnamed definitions retain asset IDs.

`CallerName` and station/outpost display-name fields contribute display labels. `MissionGiver` instead creates a separate `field_candidate`; it is not added to a mission's own `names`. `TargetFastTravelStation`, `TurnInFastTravelStation`, `OutpostName`, `OutpostPathName`, `PickUpMapName`, `PersistentLevelName` and `SubLevelName` produce location/map candidates with `internal_identifiers` and an `identifier_kind` (`travel_key`, `object_path` or `package_name`). These internal values do not become display names. FName-tagged values are accepted as observed field values.

Field-candidate IDs derive from the source record and field/index locator. Each retains `source_record`, `source_asset_path`, `source_field`, `source_value`, context and source completeness. Its `asset_path`/`class` remain null. Explicit map/object strings may provide an `asset_path_hint`; no native lookup is implied. Entity `origin_hint` remains null while `source_origin_hint` describes only the source namespace. Existing aliases remain distinct, with no fuzzy name merging.

For localisation, related fields are saved on the primary section as `related_fields`, separate from its display `names`. Child seeds use `identity_status: "localisation_field_candidate"`, preserve file/hash/section/line evidence and link `source_identity` to their primary section. A `source_asset_path_hint` remains a hint; `source_asset_path` is null. Repeated related fields retain occurrence-specific IDs, and saved `related_fields` permit resume repair even if the original localisation file subsequently changes.

`TeleportOutpostLookupObject` and `LevelDependencyList` are eligible reflected data classes in 0.3.2. String/ref evidence may identify unloaded maps, but neither these references nor the installed-file inventory cause map packages to load. The reviewed 219-root plan remains the only source of explicit native package-load requests.

Different raw assets, sessions/maps and localisation files can describe the same entity. These records preserve that evidence; they do not claim one ID per final website entry. Consumers should tolerate new record types under raw format v1 and keep all raw records intact.

### `package_file`, `localisation_file`, `installation_error` (0.3.0+)

Catalogue scope locates `WillowGame` from the executable/working-directory ancestry. It walks only CookedPC, localisation and DLC trees under that directory, skips symlinks and never accesses saves or loads packages from this inventory. Loaded-data-only scope skips this scan.

`package_file` stores a relative filename, package stem, size, session and up to 4 KiB of interpreted header context: signature/version and a provisional standard UE3 summary prefix where supported. `summary_status: "standard_prefix_candidate"` is diagnostic, not a verified Enhanced parser. Unknown formats keep their signature/version instead of guessed exports. Header bytes, package export contents, binary name tables and compressed assets are not dumped. `loaded_by_scan` is always false. Presence is not evidence of a published/usable catalogue entry.

`localisation_file` describes an English INT/ENG file, its encoding, size, checksum and read/size-limit status. UTF-16 BOM, UTF-16LE, UTF-8 and Windows-1252 text are supported. Recognized name fields, including dotted/indexed keys and struct tuples, produce candidate identities; descriptions/dialogue are not copied. `installation_error` preserves individual file errors. Installation diagnostics are also retained in the manifest. File record IDs include their session; unchanged candidate identities deduplicate across resume.

Explicit defaults: 100,000 data objects, 10,000 bindings, 500,000 references, 150,000 identities, 30,000 matching installed files, 4,000 directories and 16 MiB per localisation file. Existing array/string/node limits also bound parsed localisation. A finished scan proves only that this bounded procedure finished. Missing/packed localisation or map/script-only associations can still leave gaps.

Format references: Epic's [UE3 localisation reference](https://docs.unrealengine.com/udk/Three/LocalizationReference.html), [localized text file format](https://docs.unrealengine.com/udk/Three/LocalizedTextFiles.html), and the standard summary layout in [UE Viewer](https://github.com/gildor2/UEViewer/blob/master/Unreal/UnrealPackage/UnPackage3.cpp). Enhanced-specific compatibility still needs a native capture.

### Values

- Null, booleans, integers, finite floats and strings retain JSON types. Integer enum values can be interpreted using their schema's enum declaration.
- UObject: `{"$ref":"<path>","class":"<class path>"}`. References remain references; they do not recursively inline objects.
- Struct: `{"$type":"struct","struct":"<path>","fields":{...}}`.
- Array: `{"$type":"array","length":4,"items":[...],"truncated":false}`.
- FName (when exposed separately): `{"$type":"name","value":"..."}`.
- Nonfinite float: `{"$type":"nonfinite","value":"nan"}` or infinity equivalent.
- Unreadable, unsupported or truncated values carry explicit tagged markers and record-local issues. Truncated strings retain only a short prefix. Issue counts can exceed the bounded per-record issue list.

## Coverage and interpretation

The bundled plan loads data-package roots, **not maps**, and scans currently loaded definitions. It deliberately does not load every UPK found on disk. Loading an already present package is still requested because a package object alone does not prove its exports are fully loaded. Dependencies may add more assets than the explicit plan names.

Only data-class references are traversed. Visual/audio assets and unrelated references remain unresolved paths with class-level omission counts. Some scripts, native code, DLC maps, dynamic source associations and stat rules may remain absent. Level limits and reference/serialization budgets are explicit in configuration; omission counters reveal where limits were reached. No attempt is made to enumerate millions of generated variants, calculate true minimum/maximum stats, determine actual drop probabilities, or deduce authoritative family groupings yet.

All reflection/package work runs in viewport callbacks on the game thread. Processing aims for three work steps or four milliseconds per frame; a single native scan, object read, disk checkpoint or package load can exceed that budget. The largest observed step is recorded. No actor stat or item initialization methods are called. Non-actor assets receive temporary RootSet pins, removed on completion, disable, failure or travel. Queues store paths/classes, not live Unreal wrappers. Travel interrupts capture; resume rescans the new session and records map-specific evidence separately. Enhanced may report `Loader` as its persistent world: session streamed-level entries and each object's `context.source_package` provide additional location evidence. Loaded levels are not asserted to be currently visible or active.

For a clean capture, disable gameplay mods **and restart the game** before exporting. The mod snapshot records configuration but cannot prove pristine game memory or unmodified game files. Use the main-menu scope control before starting; changing scope requires a fresh capture.

SDK behavior references: [Python bindings](https://github.com/bl-sdk/pyunrealsdk), particularly `src/pyunrealsdk/base_bindings.cpp` and `unreal_bindings/`; [mod framework](https://github.com/bl-sdk/mods_base).

## Lookup refinement (extractor 0.2.0)

Queued descriptors include a process-local address for identity checking. Lookup first tries the original path, then a colon-to-dot separator variant, then exact-class enumeration comparing canonical full paths and class paths. Queued objects and liveness releases must also match their original address; an object reusing a path cannot be silently substituted. These addresses are never dereferenced or reused as recovery cursors after a restart. Missing-object diagnostics may retain historical descriptor addresses as evidence.

Package-plan expansion is explicit and based on namespaces observed in the first BL1E capture. It remains a reviewed plan, not an automatic directory crawl. The first capture's unsupported `MapProperty` reads belonged to cinematic animation-state caches; those SDK limitations remain tagged read errors rather than invented values.
