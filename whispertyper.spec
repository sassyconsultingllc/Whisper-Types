# PyInstaller spec - release build (windowed, no console)
# Run: pyinstaller whispertyper.spec --clean --noconfirm

from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_data_files

block_cipher = None

datas = []
binaries = []
hiddenimports = []

# Heavy deps that need full collection
for pkg in ['faster_whisper', 'ctranslate2', 'onnxruntime', 'sounddevice',
            'pynput', 'uiautomation', 'PySide6']:
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

# Extra hidden imports for dynamic loading
hiddenimports += [
    'numpy', 'numpy.core._methods', 'numpy.lib.format',
    'win32api', 'win32con', 'win32gui', 'win32process',
    'pythoncom', 'pywintypes', 'comtypes',
    'psutil', 'pyperclip',
    'kokoro_onnx',  # optional
    'piper',  # optional
]

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'PIL', 'pandas', 'pytest', 'IPython',
              'jupyter', 'notebook', 'sphinx', 'pyqt5', 'pyqt6'],
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
    console=False,           # no console window for release
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
