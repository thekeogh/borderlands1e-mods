# Local checks

From this project's root, using Python 3.9 or later:

```sh
python3 -m unittest discover -s extractor/tests -v
python3 extractor/package.py
```

No third-party Python dependencies. Tests model Unreal reflection, object graphs, GC pin ownership, package failures, interrupted recovery, storage validation and mod/keybind lifecycle, upgrade behavior, exact-class lookup and the calculation/source graph. Fixtures retain the nine nested paths and unresolved class names reported by the first BL1E capture. They do not load the real SDK or establish native BL1E package safety. The compiler remains deferred.

All paths resolve within this project; it can be moved to another repository unchanged. `temp/` holds ignored local evidence/scratch. Distribution checksums are generated in `extractor/dist/SHA256SUMS`.
