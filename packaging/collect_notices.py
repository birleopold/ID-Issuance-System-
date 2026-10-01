"""Collect installed distribution notices beside replaceable, bundled libraries."""
from importlib.metadata import distribution
from pathlib import Path
import shutil
import sys

destination = Path("dist/CredentialStudio/THIRD_PARTY_NOTICES")
destination.mkdir(parents=True, exist_ok=True)
for name in ("PySide6", "PySide6-Essentials", "PySide6-Addons", "shiboken6", "pywin32", "pyinstaller"):
    package = distribution(name)
    folder = destination / name
    folder.mkdir(exist_ok=True)
    (folder / "METADATA.txt").write_text(str(package.metadata), encoding="utf-8")
    for file in package.files or []:
        if any(word in str(file).lower() for word in ("license", "licence", "copying", "notice")):
            source = Path(package.locate_file(file))
            if source.is_file():
                target = folder / str(file).replace("/", "_").replace("\\", "_")
                shutil.copy2(source, target)
for source in (Path(sys.base_prefix) / "LICENSE.txt", Path(sys.base_prefix) / "LICENSE"):
    if source.exists():
        shutil.copy2(source, destination / "PYTHON-LICENSE.txt")
