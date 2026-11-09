"""Build locally; never install into the game automatically."""

from pathlib import Path
import re
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(__file__).resolve().parent
source = root / 'Source/sdk_mods/MissionAtlas'
version = re.search(r'^version = "([^"]+)"', (source / 'pyproject.toml').read_text(), re.M).group(1)
assert f'**{version} ' in (root / 'README.md').read_text()
output = root / 'dist'
output.mkdir(exist_ok=True)
sdk = output / 'MissionAtlas.sdkmod'
with ZipFile(sdk, 'w', ZIP_DEFLATED) as archive:
    for path in sorted(source.iterdir()):
        if path.suffix == '.py':
            compile(path.read_bytes(), str(path), 'exec')
        if path.is_file():
            archive.write(path, 'MissionAtlas/' + path.name)
    for name in ('README.md', 'CHANGELOG.md'):
        archive.write(root / name, 'MissionAtlas/' + name)
with ZipFile(output / f'MissionAtlas-BL1E-{version}.zip', 'w', ZIP_DEFLATED) as archive:
    archive.write(sdk, 'sdk_mods/MissionAtlas.sdkmod')
    archive.write(root / 'README.md', 'README.md')
    archive.write(root / 'CHANGELOG.md', 'CHANGELOG.md')
print(sdk)
print(output / f'MissionAtlas-BL1E-{version}.zip')
