"""PyInstaller runtime hook for CUDA DLL discovery.

Registers CUDA DLL directories before ctranslate2 imports so cublas64_12.dll
etc. are found. Supports two layouts:
  - Bundled build (full):  DLLs placed directly in the app folder
  - Slim build + GPU:      DLLs in <app>/_cuda_dlls/ (added by enable_gpu.bat)
"""
import os
import pathlib
import sys


def _setup_cuda_dll_search():
    try:
        app_dirs = []
        app_dirs.append(pathlib.Path(os.path.dirname(os.path.abspath(__file__))))
        if getattr(sys, "frozen", False):
            app_dirs.append(pathlib.Path(sys.executable).parent)
            if hasattr(sys, "_MEIPASS"):
                app_dirs.append(pathlib.Path(sys._MEIPASS))

        for app_dir in app_dirs:
            os.add_dll_directory(str(app_dir))

            # Slim build: user-supplied DLLs in _cuda_dlls/ next to the exe
            cuda_dlls = app_dir / "_cuda_dlls"
            if cuda_dlls.is_dir():
                os.add_dll_directory(str(cuda_dlls))

            # Full build: nvidia/*/bin subdirs bundled by full spec
            for nvidia_dir in app_dir.glob("nvidia/*/bin"):
                if nvidia_dir.is_dir():
                    os.add_dll_directory(str(nvidia_dir))
    except Exception:
        pass


_setup_cuda_dll_search()
