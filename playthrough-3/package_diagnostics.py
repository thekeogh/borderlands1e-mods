"""Package only the diagnostic exporter; never the reference folder."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

root = Path(__file__).resolve().parent
source = root / "diagnostics/PT3EconomyDiagnostics"
output = root / "dist/PT3EconomyDiagnostics.sdkmod"
output.parent.mkdir(exist_ok=True)
with ZipFile(output, "w", ZIP_DEFLATED) as archive:
    for name in ("__init__.py", "exporter.py", "pyproject.toml"):
        archive.write(source / name, "PT3EconomyDiagnostics/" + name)
print(output)
