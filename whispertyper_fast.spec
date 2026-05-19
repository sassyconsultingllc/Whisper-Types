# PyInstaller spec - WhisperTyper release build (minimal, fast, reliable)
# Run: pyinstaller whispertyper_fast.spec --clean --noconfirm

import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_data_files

block_cipher = None

datas = []
binaries = []
hiddenimports = []

# Collect heavy dependencies (simplified)
for pkg in ['faster_whisper', 'ctranslate2', 'onnxruntime']:
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
        print(f"[spec] Collected {pkg}")
    except Exception as e:
        print(f"[spec] Warning collecting {pkg}: {e}")

# PySide6 - collect minimal (skip problematic QML)
try:
    d, b, h = collect_all('PySide6', include_py_files=True)
    datas += d
    binaries += b
    hiddenimports += h
    print(f"[spec] Collected PySide6")
except Exception as e:
    print(f"[spec] Warning: {e}")

# Sounddevice
try:
    d, b, h = collect_all('sounddevice')
    binaries += b
    print(f"[spec] Collected sounddevice")
except Exception:
    pass

# Other core packages (skip collect_all, just add imports)
hiddenimports += [
    'pynput', 'uiautomation', 'pyperclip', 'psutil',
    'numpy', 'numpy.core._methods', 'numpy.lib.format',
    'win32api', 'win32con', 'win32gui', 'win32process',
    'pythoncom', 'pywintypes', 'comtypes',
    'kokoro_onnx', 'piper',  # optional TTS
]

# Explicitly add CUDA DLLs (nvidia-*-cu12 packages)
try:
    import site
    for sp in site.getsitepackages():
        nvidia_bin = Path(sp) / "nvidia"
        if nvidia_bin.exists():
            for dll_dir in nvidia_bin.glob("*/bin"):
                if dll_dir.is_dir():
                    for dll in dll_dir.glob("*.dll"):
                        binaries.append((str(dll), "."))
                    print(f"[spec] Added CUDA DLLs from: {dll_dir}")
except Exception as e:
    print(f"[spec] Warning: Could not add CUDA DLLs: {e}")

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['pyi_rth_cuda.py'],
    excludes=[
        'tkinter', 'matplotlib', 'PIL', 'pandas', 'pytest', 'IPython',
        'jupyter', 'notebook', 'sphinx', 'pyqt5', 'pyqt6',
        'PySide6.QtQml',  # Exclude problematic QML
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='WhisperTyper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='WhisperTyper',
)
