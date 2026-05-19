"""Local TTS abstraction.

Backends (in priority order):
  - kokoro: kokoro-onnx package, 82M-param model, excellent quality, fast on CPU.
            pip install kokoro-onnx; downloads model from HF on first use.
  - piper:  piper-tts, tiny ONNX models (~20MB), good quality, very fast.
            pip install piper-tts.
  - openai_compat: any OpenAI-compatible TTS endpoint (AllTalk, OpenAudio, etc).

Audio plays via sounddevice. Falls back to next backend on failure.
"""
import json
import io
import threading
import urllib.request
import urllib.error
import wave

import numpy as np


class TTSError(Exception):
    pass


class _BaseTTS:
    def synthesize(self, text):
        raise NotImplementedError

    def speak(self, text, samplerate_hint=None):
        sr, audio = self.synthesize(text)
        _play(audio, sr)
        return sr, audio


class KokoroTTS(_BaseTTS):
    """kokoro-onnx. Voices: af_sky, af_bella, am_adam, bf_emma, bm_george, etc."""
    def __init__(self, voice="af_sky", speed=1.0, model_path=None, voices_path=None,
                 lang="en-us"):
        try:
            from kokoro_onnx import Kokoro  # noqa
        except Exception as e:
            raise TTSError(f"kokoro-onnx not installed: {e}")
        from kokoro_onnx import Kokoro
        from pathlib import Path

        # Auto-locate model files if not specified
        if model_path is None or voices_path is None:
            cache = Path.home() / ".whispertyper" / "kokoro"
            cache.mkdir(parents=True, exist_ok=True)
            model_path = model_path or str(cache / "kokoro-v0_19.onnx")
            voices_path = voices_path or str(cache / "voices-v1.0.bin")
            if not Path(model_path).exists() or not Path(voices_path).exists():
                _download_kokoro(model_path, voices_path)
        self._k = Kokoro(model_path, voices_path)
        self.voice = voice
        self.speed = float(speed)
        self.lang = lang

    def synthesize(self, text):
        audio, sr = self._k.create(text, voice=self.voice, speed=self.speed, lang=self.lang)
        if isinstance(audio, np.ndarray):
            return int(sr), audio.astype('float32')
        return int(sr), np.asarray(audio, dtype='float32')


class PiperTTS(_BaseTTS):
    """piper-tts. Requires a voice .onnx file + .onnx.json config."""
    def __init__(self, model_path, config_path=None):
        try:
            from piper import PiperVoice  # noqa
        except Exception as e:
            raise TTSError(f"piper-tts not installed: {e}")
        from piper import PiperVoice
        self.voice = PiperVoice.load(model_path, config_path=config_path)

    def synthesize(self, text):
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            self.voice.synthesize(text, wf)
        buf.seek(0)
        with wave.open(buf, "rb") as wf:
            sr = wf.getframerate()
            n = wf.getnframes()
            raw = wf.readframes(n)
        audio = np.frombuffer(raw, dtype='int16').astype('float32') / 32768.0
        return sr, audio


class OpenAITTS(_BaseTTS):
    """OpenAI-compatible /audio/speech endpoint."""
    def __init__(self, base_url, api_key, model="tts-1", voice="alloy", fmt="wav"):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or ""
        self.model = model
        self.voice = voice
        self.fmt = fmt

    def synthesize(self, text):
        url = f"{self.base_url}/audio/speech"
        body = json.dumps({
            "model": self.model,
            "input": text,
            "voice": self.voice,
            "response_format": self.fmt,
        }).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
        except urllib.error.HTTPError as e:
            raise TTSError(f"TTS HTTP {e.code}: {e.read()[:200]}")
        except Exception as e:
            raise TTSError(f"TTS error: {e}")
        buf = io.BytesIO(data)
        with wave.open(buf, "rb") as wf:
            sr = wf.getframerate()
            audio = np.frombuffer(wf.readframes(wf.getnframes()),
                                  dtype='int16').astype('float32') / 32768.0
        return sr, audio


def _download_kokoro(model_path, voices_path):
    """Pull Kokoro v0.19 model + voices from HF mirror."""
    urls = [
        ("https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v0_19.onnx",
         model_path),
        ("https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin",
         voices_path),
    ]
    from pathlib import Path
    for url, dst in urls:
        if Path(dst).exists():
            continue
        try:
            urllib.request.urlretrieve(url, dst)
        except Exception as e:
            raise TTSError(f"Failed to download Kokoro asset {url}: {e}")


def _play(audio, sr):
    """Non-blocking playback via sounddevice."""
    try:
        import sounddevice as sd
        sd.play(audio, samplerate=sr)
    except Exception as e:
        raise TTSError(f"Playback failed: {e}")


def stop_playback():
    try:
        import sounddevice as sd
        sd.stop()
    except Exception:
        pass


def build_tts(cfg):
    """Factory from config dict. Returns instance or None if disabled/unavailable."""
    if not cfg.get("tts_enabled", False):
        return None
    backend = cfg.get("tts_backend", "kokoro")
    try:
        if backend == "kokoro":
            return KokoroTTS(
                voice=cfg.get("tts_voice", "af_sky"),
                speed=cfg.get("tts_speed", 1.0),
                lang=cfg.get("tts_lang", "en-us"),
            )
        if backend == "piper":
            return PiperTTS(
                model_path=cfg.get("tts_piper_model", ""),
                config_path=cfg.get("tts_piper_config") or None,
            )
        if backend == "openai_compat":
            return OpenAITTS(
                base_url=cfg.get("tts_base_url", "http://127.0.0.1:8880/v1"),
                api_key=cfg.get("tts_api_key", ""),
                model=cfg.get("tts_model", "tts-1"),
                voice=cfg.get("tts_voice", "alloy"),
            )
    except TTSError:
        return None
    except Exception:
        return None
    return None


# Common voice lists for the UI dropdown
KOKORO_VOICES = [
    "af_sky", "af_bella", "af_sarah", "af_nicole",
    "am_adam", "am_michael",
    "bf_emma", "bf_isabella",
    "bm_george", "bm_lewis",
]
OPENAI_VOICES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
