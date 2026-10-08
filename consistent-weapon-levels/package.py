"""Build a private SDK archive; never deploy or increment the version."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

root = Path(__file__).resolve().parent
source = root / "Source/sdk_mods/ConsistentWeaponLevels"
output = root / "dist/ConsistentWeaponLevels.sdkmod"
output.parent.mkdir(exist_ok=True)
with ZipFile(output, "w", ZIP_DEFLATED) as archive:
    for name in ("__init__.py", "pyproject.toml", "LICENSE"):
        archive.write(source / name, "ConsistentWeaponLevels/" + name)
    archive.write(root / "README.md", "ConsistentWeaponLevels/README.md")
print(output)
