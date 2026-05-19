# PyInstaller spec - debug build (console visible, logs to stderr)
# Run: pyinstaller whispertyper_debug.spec --clean --noconfirm

from PyInstaller.utils.hooks import collect_all

block_cipher = None
datas = []
binaries = []
hiddenimports = []

for pkg in ['faster_whisper', 'ctranslate2', 'onnxruntime', 'sounddevice',
            'pynput', 'uiautomation', 'PySide6']:
    try:
        d, b, h = collect_all(pkg)
        datas += d; binaries += b; hiddenimports += h
    except Exception:
        pass

hiddenimports += [
    'numpy', 'numpy.core._methods', 'numpy.lib.format',
    'win32api', 'win32con', 'win32gui', 'win32process',
    'pythoncom', 'pywintypes', 'comtypes',
    'psutil', 'pyperclip', 'kokoro_onnx', 'piper',
]

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'PIL', 'pandas', 'pytest', 'IPython',
              'jupyter', 'notebook', 'sphinx', 'pyqt5', 'pyqt6'],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='WhisperTyper-debug',
    debug=True,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,            # console visible for log capture
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='WhisperTyper-debug',
)
