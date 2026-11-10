# Local checks

From this project's root, using Python 3.9 or later:

```sh
python3 -m unittest discover -s extractor/tests -v
python3 extractor/package.py
```

No third-party Python dependencies. Tests model Unreal reflection, object graphs, GC pin ownership, package failures, interrupted recovery, storage validation and mod/keybind lifecycle, upgrade behavior, exact-class lookup and the calculation/source graph. Catalogue tests also exercise unloaded English names, nested enemy grade labels, encoding, source checksums, repeated/changed-source resume, file/name budgets, symlink exclusion, exact actor subclasses and packaged JSON contents. Fixtures retain the nine nested paths and unresolved class names reported by the first BL1E capture. These checks do not load the real SDK or establish native BL1E package safety or catalogue completeness. The workshop/compiler is separate from this extractor release.

All paths resolve within this project; it can be moved to another repository unchanged. `temp/` holds ignored local evidence/scratch. Distribution checksums are generated in `extractor/dist/SHA256SUMS`.

`capture-0.2.0-indexing-gaps.json` retains selected real caller, NPC, mission-giver and travel fields; the same indexing gaps were confirmed in the 0.3.1 audit. Tests verify separate caller/giver categories, unchanged mission names, internal map/travel identifiers, field/source provenance, repeated localised fields and repair when only the source/primary section was committed before interruption. These fixtures are reduced evidence, not full captures or proof of complete NPC/location coverage.
