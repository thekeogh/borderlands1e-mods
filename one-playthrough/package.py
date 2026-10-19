"""Package One Playthrough without changing other mods or reference files."""

from pathlib import Path
import re
from zipfile import ZIP_DEFLATED, ZipFile

root = Path(__file__).resolve().parent
source = root / "Source/sdk_mods/OnePlaythrough"
version = re.search(r'^version = "([^"]+)"$', (source / "pyproject.toml").read_text(), re.MULTILINE).group(1)
assert f"**{version} " in (root / "README.md").read_text()
output = root / "dist"
output.mkdir(exist_ok=True)
sdkmod = output / "OnePlaythrough.sdkmod"
with ZipFile(sdkmod, "w", ZIP_DEFLATED) as archive:
    for path in sorted(source.glob("*.py")):
        compile(path.read_bytes(), str(path), "exec")
        archive.write(path, "OnePlaythrough/" + path.name)
    archive.write(source / "pyproject.toml", "OnePlaythrough/pyproject.toml")
    for name in ("README.md", "CHANGELOG.md", "LICENSE"):
        archive.write(root / name, "OnePlaythrough/" + name)
with ZipFile(output / f"OnePlaythrough-BL1E-{version}.zip", "w", ZIP_DEFLATED) as archive:
    archive.write(sdkmod, "sdk_mods/OnePlaythrough.sdkmod")
    archive.write(root / "README.md", "README.md")
    archive.write(root / "CHANGELOG.md", "CHANGELOG.md")
    archive.write(root / "LICENSE", "LICENSE")
print(sdkmod)
print(output / f"OnePlaythrough-BL1E-{version}.zip")
