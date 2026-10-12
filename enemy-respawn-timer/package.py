"""Package this standalone private mod; never install into a game automatically."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

root = Path(__file__).resolve().parent
source = root / "Source/sdk_mods/EnemyRespawnTimer"
output = root / "dist/EnemyRespawnTimer.sdkmod"
output.parent.mkdir(exist_ok=True)
with ZipFile(output, "w", ZIP_DEFLATED) as archive:
    for name in ("__init__.py", "policy.py", "pyproject.toml", "LICENSE"):
        archive.write(source / name, "EnemyRespawnTimer/" + name)
    archive.write(root / "README.md", "EnemyRespawnTimer/README.md")
print(output)
