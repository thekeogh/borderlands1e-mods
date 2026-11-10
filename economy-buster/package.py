"""Build a standalone .sdkmod; never install into the game automatically."""

from hashlib import sha256
from pathlib import Path
import re
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


def build() -> Path:
    root = Path(__file__).resolve().parent
    source = root / "Source/sdk_mods/EconomyBuster"
    version = re.search(r'^version = "([^\"]+)"$',
                        (source / "pyproject.toml").read_text(), re.MULTILINE).group(1)
    if f"Version {version}" not in (root / "README.md").read_text():
        raise ValueError("README version does not match mod metadata")
    output = root / "dist/EconomyBuster.sdkmod"
    output.parent.mkdir(exist_ok=True)
    files = [(source / name, name) for name in
             ("__init__.py", "economy.py", "diagnostics.py", "pyproject.toml", "LICENSE")]
    files += [(root / name, name) for name in ("README.md", "CHANGELOG.md")]
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for path, name in files:
            info = ZipInfo("EconomyBuster/" + name, date_time=(2026, 11, 10, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    (output.parent / "SHA256SUMS").write_text(f"{sha256(output.read_bytes()).hexdigest()}  {output.name}\n")
    return output


if __name__ == "__main__":
    print(build())
