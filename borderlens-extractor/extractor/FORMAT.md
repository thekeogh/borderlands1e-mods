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

`status.json` and `latest.json` live beside `exports/`, outside individual captures. Status describes the running job; latest points at its checkpoint. A ZIP appears after capture and packaging finish. A `.zip.partial` is unfinished packaging, not an importable archive.

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
- `phase`, `progress`: last saved work state and largest measured work-step duration. These are diagnostic context, not a portable scan cursor.

Resume checks format, extractor version, configuration, safe paths, checksums, record counts and duplicate IDs. It rescans roots, skipping committed record IDs. A changed mod snapshot is recorded as mixed provenance. Previously committed records retain their original session and are not overwritten. Orphan/uncommitted files are not included in the ZIP.

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

Limited source evidence from actors already loaded on the current map, or explicitly referenced pawn/vehicle archetypes. Only fields matching definition/loot/drop/inventory/population/behavior/identity terms are read. IDs also include map name. Actors are never pinned, spawned, initialized or evaluated for stats. These records are **not** a complete actor dump or a complete list of drop sources.

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
