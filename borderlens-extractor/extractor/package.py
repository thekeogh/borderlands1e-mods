"""Build self-contained SDKmod and player ZIP; Python 3.9+, no dependencies."""
from hashlib import sha256
from pathlib import Path
import re
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'extractor'/'src'/'BorderlensExtractor'
DIST = ROOT/'extractor'/'dist'


def build():
    DIST.mkdir(parents=True,exist_ok=True)
    version = re.search(r'^version\s*=\s*"([^"]+)"', (SOURCE/'pyproject.toml').read_text(), re.M).group(1)
    sdkmod = DIST/'BorderlensExtractor.sdkmod'
    included = sorted(p for p in SOURCE.rglob('*') if p.is_file() and p.suffix in ('.py','.json','.toml'))
    with ZipFile(sdkmod,'w',ZIP_DEFLATED) as archive:
        for path in included:archive.write(path,'BorderlensExtractor/'+path.relative_to(SOURCE).as_posix())
        for name in ('README.md','CHANGELOG.md','LICENSE'):archive.write(ROOT/name,'BorderlensExtractor/'+name)
        archive.write(ROOT/'extractor'/'FORMAT.md','BorderlensExtractor/FORMAT.md')
    with ZipFile(sdkmod) as archive:
        if archive.testzip() is not None:raise ValueError('Invalid SDKmod ZIP')
        names = archive.namelist()
        for required in ('__init__.py','pyproject.toml','package-plan.json','job.py'):
            if 'BorderlensExtractor/'+required not in names:raise ValueError('Missing '+required)
        if any('__pycache__' in n or n.startswith('/') or '..' in Path(n).parts for n in names):
            raise ValueError('Unsafe package entry')
    player = DIST/f'BorderlensExtractor-BL1E-{version}.zip'
    with ZipFile(player,'w',ZIP_DEFLATED) as archive:
        archive.write(sdkmod,'sdk_mods/'+sdkmod.name)
        for name in ('README.md','CHANGELOG.md','LICENSE'):archive.write(ROOT/name,name)
    (DIST/'SHA256SUMS').write_text(''.join(sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in (sdkmod,player)))
    print(sdkmod)
    print(player)
    return sdkmod


if __name__ == '__main__':build()
