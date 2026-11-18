"""Package the private diagnostics mod; no installation or version changes."""

import hashlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "Source/sdk_mods/SmoothFPS"


def build():
    output = ROOT / "dist/SmoothFPS.sdkmod"
    output.parent.mkdir(exist_ok=True)
    files = [(SOURCE / name, "SmoothFPS/" + name) for name in (
        "__init__.py", "capture.py", "environment.py", "runtime.py", "pyproject.toml", "LICENSE")]
    files.extend((ROOT / name, "SmoothFPS/" + name) for name in ("README.md", "CHANGELOG.md"))
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for source, destination in files:
            info = ZipInfo(destination, date_time=(2026, 11, 16, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, source.read_bytes())
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    (output.parent / "SHA256SUMS").write_text(f"{digest}  {output.name}\n", encoding="ascii")
    print(output)
    return output


if __name__ == "__main__":
    build()
