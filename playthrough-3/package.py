"""Build a replacement SDK mod and a complete hybrid installation archive."""

from pathlib import Path
import re
from zipfile import ZIP_DEFLATED, ZipFile

root = Path(__file__).resolve().parent
source = root / "Source/sdk_mods/Playthrough 3"
output = root / "dist"
output.mkdir(exist_ok=True)
sdkmod = output / "Playthrough 3.sdkmod"
with ZipFile(sdkmod, "w", ZIP_DEFLATED) as archive:
    for name in ("__init__.py", "economy.py", "pyproject.toml"):
        archive.write(source / name, "Playthrough 3/" + name)

diagnostics = output / "PT3EconomyDiagnostics.sdkmod"
with ZipFile(diagnostics, "w", ZIP_DEFLATED) as archive:
    for name in ("__init__.py", "exporter.py", "pyproject.toml"):
        archive.write(root / "diagnostics/PT3EconomyDiagnostics" / name, "PT3EconomyDiagnostics/" + name)

version = re.search(r'^version = "([^"]+)"$', (source / "pyproject.toml").read_text(), re.MULTILINE).group(1)
hybrid = output / f"Playthrough3-Level1Economy-BL1E-{version}.zip"
with ZipFile(hybrid, "w", ZIP_DEFLATED) as archive:
    archive.write(sdkmod, "sdk_mods/Playthrough 3.sdkmod")
    archive.write(diagnostics, "sdk_mods/PT3EconomyDiagnostics.sdkmod")
    asset = "WillowGame/CookedPC/Mods/PT3/gd_GameStages_PT3.upk"
    archive.write(root / "Source" / asset, asset)
    archive.write(root / "README.md", "PT3-Level1Economy-README.md")
print(sdkmod)
print(diagnostics)
print(hybrid)
