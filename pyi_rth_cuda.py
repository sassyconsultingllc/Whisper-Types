"""PyInstaller runtime hook for CUDA DLL discovery.

When PyInstaller bundles the app, CUDA DLLs (cublas64_12.dll, etc.) are
placed in the dist folder. This hook adds them to os.add_dll_directory()
before ctranslate2 imports, ensuring cublas and other libraries are found.
"""
import os
import pathlib


def _setup_cuda_dll_search():
    """Register CUDA DLL directories before ctranslate2 loads."""
    # The bundled app structure is dist/WhisperTyper/*.exe
    # DLLs are placed in dist/WhisperTyper/ or dist/WhisperTyper/nvidia/*/bin/
    try:
        # Add the main app directory
        app_dir = pathlib.Path(os.path.dirname(os.path.abspath(__file__)))
        os.add_dll_directory(str(app_dir))
        
        # Also add site-packages nvidia bin dirs (in case they're there)
        for nvidia_dir in app_dir.glob("nvidia/*/bin"):
            if nvidia_dir.is_dir():
                os.add_dll_directory(str(nvidia_dir))
    except Exception:
        pass


_setup_cuda_dll_search()
