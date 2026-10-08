"""Build the private SDK archive without deploying or incrementing versions."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

root = Path(__file__).resolve().parent
source = root / "Source/sdk_mods/AutopickupBL1E"
output = root / "dist/AutopickupBL1E.sdkmod"
output.parent.mkdir(exist_ok=True)

with ZipFile(output, "w", ZIP_DEFLATED) as archive:
    for name in ("__init__.py", "pyproject.toml", "LICENSE"):
        archive.write(source / name, "AutopickupBL1E/" + name)
    archive.write(root / "README.md", "AutopickupBL1E/README.md")

print(output)
