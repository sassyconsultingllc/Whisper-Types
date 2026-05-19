"""faster-whisper wrapper with lazy load + device auto-detect."""
import os
import pathlib
import threading

# Add CUDA DLL directories so ctranslate2 can find cublas64_12.dll etc.
# Searches (in order):
#   1. _cuda_dlls/ folder next to the exe (populated by enable_gpu.bat)
#   2. nvidia/*/bin inside site-packages (pip nvidia-*-cu12 packages)
def _add_nvidia_dll_dirs():
    try:
        # Bundled exe: look for _cuda_dlls/ next to WhisperTyper.exe
        import sys
        exe_dir = pathlib.Path(sys.executable).parent
        cuda_dlls_dir = exe_dir / "_cuda_dlls"
        if cuda_dlls_dir.is_dir():
            os.add_dll_directory(str(cuda_dlls_dir))
    except Exception:
        pass
    try:
        import site
        for sp in site.getsitepackages():
            for d in pathlib.Path(sp).glob("nvidia/*/bin"):
                if d.is_dir():
                    os.add_dll_directory(str(d))
    except Exception:
        pass

_add_nvidia_dll_dirs()


def _cuda_available() -> bool:
    """Return True only if ctranslate2 can actually see a CUDA device."""
    try:
        import ctranslate2
        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        # Missing DLLs, driver too old, no GPU — fall back to CPU silently
        return False


class Transcriber:
    def __init__(self, model_size="base.en", device="auto", compute_type="auto",
                 beam_size=1):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.beam_size = beam_size
        self._model = None
        self._lock = threading.Lock()

    def _resolve(self):
        dev = self.device
        ct = self.compute_type
        if dev == "auto":
            dev = "cuda" if _cuda_available() else "cpu"
        if ct == "auto":
            ct = "float16" if dev == "cuda" else "int8"
        return dev, ct

    def ensure_loaded(self):
        if self._model is not None:
            return
        with self._lock:
            if self._model is not None:
                return
            from faster_whisper import WhisperModel
            dev, ct = self._resolve()
            try:
                self._model = WhisperModel(self.model_size, device=dev, compute_type=ct)
            except Exception:
                self._model = WhisperModel(self.model_size, device="cpu", compute_type="int8")

    def transcribe(self, audio_np, language=None, vad_filter=True):
        self.ensure_loaded()
        segments, _info = self._model.transcribe(
            audio_np,
            language=language,
            beam_size=self.beam_size,
            vad_filter=vad_filter,
            vad_parameters=dict(min_silence_duration_ms=300) if vad_filter else None,
            condition_on_previous_text=False,
        )
        return " ".join(s.text.strip() for s in segments).strip()
