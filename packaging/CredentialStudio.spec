# Build on Windows x64 with Python 3.12.
from pathlib import Path

root = Path(SPECPATH).parent
a = Analysis(
    [str(root / 'run.py')],
    pathex=[str(root)],
    binaries=[],
    datas=[(str(root / 'docs'), 'docs'), (str(root / 'README.md'), '.')],
    hiddenimports=['win32com.client', 'pythoncom', 'pywintypes',
                   'PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets',
                   'PySide6.QtPrintSupport'],
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='CredentialStudio',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='CredentialStudio')
