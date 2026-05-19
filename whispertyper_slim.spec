# PyInstaller spec - WhisperTyper SLIM build (no bundled CUDA, CPU default)
# GPU users: run enable_gpu.bat after extracting to add CUDA DLLs alongside exe.
# Run: pyinstaller whispertyper_slim.spec --clean --noconfirm

import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_data_files

block_cipher = None

datas = []
binaries = []
hiddenimports = []

# Core ML inference (no CUDA DLLs - they're optional and huge)
for pkg in ['faster_whisper', 'ctranslate2', 'onnxruntime']:
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
        print(f"[spec] Collected {pkg}")
    except Exception as e:
        print(f"[spec] Warning collecting {pkg}: {e}")

# PySide6 - collect but strip WebEngine and unused modules (done via global filter below)
try:
    d, b, h = collect_all('PySide6', include_py_files=True)
    binaries += b
    datas += d
    hiddenimports += h
    print(f"[spec] Collected PySide6 (WebEngine stripped by global filter)")
except Exception as e:
    print(f"[spec] Warning: {e}")

# Sounddevice
try:
    d, b, h = collect_all('sounddevice')
    binaries += b
    print(f"[spec] Collected sounddevice")
except Exception:
    pass

hiddenimports += [
    'pynput', 'uiautomation', 'pyperclip', 'psutil',
    'numpy', 'numpy.core._methods', 'numpy.lib.format',
    'win32api', 'win32con', 'win32gui', 'win32process',
    'pythoncom', 'pywintypes', 'comtypes',
    'kokoro_onnx', 'piper',
]

# Hard-exclude large DLLs we don't need
EXCLUDE_DLL_SUBSTRINGS = [
    # CUDA (never bundled in slim build)
    'cublas', 'cudnn', 'cudart', 'nvrtc', 'cufft', 'curand',
    'cusolver', 'cusparse', 'nccl', 'nvjpeg',
    # Qt WebEngine (~280 MB browser engine - not used)
    'qt6webenginecore', 'qt6webengine', 'qtwebengine',
    # Duplicate avcodec (av package ships two versions; keep the newer one)
    'avcodec-61',
    # Unneeded SQL drivers
    'qsqlibase', 'qsqlmimer', 'qsqloci',
]

binaries = [
    (src, dst) for src, dst in binaries
    if not any(ex in Path(src).name.lower() for ex in EXCLUDE_DLL_SUBSTRINGS)
]

# Strip .pak webengine resource files from datas too
datas = [
    (src, dst) for src, dst in datas
    if 'webengine' not in str(src).lower()
]

# Deduplicate binaries by (dest_dir, filename)
seen = {}
deduped = []
for src, dst in binaries:
    key = (dst, Path(src).name.lower())
    if key not in seen:
        seen[key] = True
        deduped.append((src, dst))
binaries = deduped
print(f"[spec] Binaries after dedup + exclusion: {len(binaries)}")

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
        'PySide6.QtQml', 'PySide6.QtWebEngine', 'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineWidgets', 'PySide6.QtWebChannel',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Post-analysis strip: remove anything the dependency resolver snuck back in
STRIP_FROM_BUNDLE = [
    'qt6webenginecore', 'qt6webengine', 'qtwebengineprocess',
    'qtwebengine_devtools', 'qtwebengine_resources',
    'cublas', 'cudnn', 'cudart', 'nvrtc', 'cufft', 'curand',
    'cusolver', 'cusparse',
]
a.binaries = [(name, path, t) for name, path, t in a.binaries
              if not any(s in name.lower() for s in STRIP_FROM_BUNDLE)]
a.datas = [(name, path, t) for name, path, t in a.datas
           if not any(s in name.lower() for s in STRIP_FROM_BUNDLE)]
print(f"[spec] Final binaries after post-analysis strip: {len(a.binaries)}")

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
