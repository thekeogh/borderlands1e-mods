"""Build a replacement SDK mod and a complete hybrid installation archive."""

from pathlib import Path
import re
import runpy
from zipfile import ZIP_DEFLATED, ZipFile

root = Path(__file__).resolve().parent
source = root / "Source/sdk_mods/Playthrough 3"
output = root / "dist"
output.mkdir(exist_ok=True)
version = re.search(r'^version = "([^"]+)"$', (source / "pyproject.toml").read_text(), re.MULTILINE).group(1)
named = runpy.run_path(str(source / "named_enemies.py"))
listed = [name for names in named["NAME_GROUPS"].values() for name in names]
assert len(listed) == len(set(listed))
assert set(listed) == set(named["BALANCE_NAMES"].values()) | set(named["ARCHETYPE_NAMES"].values())
reference = root / "NAMED_ENEMIES.txt"
lines = [f"Playthrough 3 {version}: named enemies fixed at level {named['NAMED_LEVEL']}", "Author: keogh", "",
         f"{len(listed)} named entities; exact balance/archetype IDs, case-insensitive.",
         "Ordinary enemies and badasses retain the selected spread and probabilities.",
         "Applies to supported native population spawns/restores in PT3 on the host.",
         "Friendly/player/neutral spawns remain excluded, even if an ID matches.",
         "Underdome copies of listed base-game bosses are included where IDs are known.",
         "Scripted paths outside the existing factories are not covered; test in BL1E.",
         f"Mad Mel/Krom's Turret: native vehicle factory stage {named['NAMED_LEVEL']}; verify displayed level in-game.",
         "F10 named_enemy_counts reports successful matches; ordinary_assigned_counts excludes them.",
         "Existing enemies need a new spawn/restore; restart the game when installing.", ""]
for group, names in named["NAME_GROUPS"].items():
    lines += [f"{group} ({len(names)})", "=" * len(group)]
    lines.extend("- " + name for name in names)
    lines.append("")
lines += ["Sources (identifier data only; no foreign spawn/loot logic imported)", "================================================================"]
lines.extend(named["SOURCES"])
lines += ["", "Exact balance IDs", "================="]
lines.extend(f"{path} -> {name}" for path, name in sorted(named["BALANCE_NAMES"].items()))
lines += ["", "Exact archetype IDs", "==================="]
lines.extend(f"{path} -> {name}" for path, name in sorted(named["ARCHETYPE_NAMES"].items()))
reference.write_text("\n".join(lines) + "\n")
sdkmod = output / "Playthrough 3.sdkmod"
with ZipFile(sdkmod, "w", ZIP_DEFLATED) as archive:
    for name in ("__init__.py", "economy.py", "enemy_levels.py", "named_enemies.py", "pyproject.toml"):
        archive.write(source / name, "Playthrough 3/" + name)

diagnostics = output / "PT3EconomyDiagnostics.sdkmod"
with ZipFile(diagnostics, "w", ZIP_DEFLATED) as archive:
    for name in ("__init__.py", "exporter.py", "pyproject.toml"):
        archive.write(root / "diagnostics/PT3EconomyDiagnostics" / name, "PT3EconomyDiagnostics/" + name)

hybrid = output / f"Playthrough3-Level1Economy-BL1E-{version}.zip"
with ZipFile(hybrid, "w", ZIP_DEFLATED) as archive:
    archive.write(sdkmod, "sdk_mods/Playthrough 3.sdkmod")
    archive.write(diagnostics, "sdk_mods/PT3EconomyDiagnostics.sdkmod")
    asset = "WillowGame/CookedPC/Mods/PT3/gd_GameStages_PT3.upk"
    archive.write(root / "Source" / asset, asset)
    archive.write(root / "README.md", "PT3-Level1Economy-README.md")
    archive.write(reference, "PT3-Named-Enemies.txt")
print(sdkmod)
print(diagnostics)
print(hybrid)
