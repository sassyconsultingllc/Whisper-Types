"""Mic capture. 16kHz mono float32 for Whisper. Per-chunk callback + snapshot."""
import sounddevice as sd
import numpy as np
import threading


class Recorder:
    def __init__(self, samplerate=16000, device=None):
        self.sr = samplerate
        self.device = device
        self.frames = []
        self.stream = None
        self._recording = False
        self._lock = threading.Lock()
        self._chunk_cb = None

    def list_devices(self):
        try:
            return [d for d in sd.query_devices() if d.get('max_input_channels', 0) > 0]
        except Exception:
            return []

    def set_chunk_callback(self, cb):
        self._chunk_cb = cb

    def start(self):
        with self._lock:
            self.frames = []
            self._recording = True
            self.stream = sd.InputStream(
                samplerate=self.sr,
                channels=1,
                dtype='float32',
                device=self.device,
                callback=self._cb,
                blocksize=0,
            )
            self.stream.start()

    def _cb(self, indata, frames, time_info, status):
        if not self._recording:
            return
        chunk = indata.copy()
        with self._lock:
            self.frames.append(chunk)
        cb = self._chunk_cb
        if cb is not None:
            try:
                cb(chunk.flatten())
            except Exception:
                pass

    def snapshot(self):
        """Thread-safe snapshot of all audio captured so far. Returns float32 mono."""
        with self._lock:
            if not self.frames:
                return np.zeros(0, dtype='float32')
            try:
                return np.concatenate(self.frames, axis=0).flatten().astype('float32')
            except Exception:
                return np.zeros(0, dtype='float32')

    def stop(self):
        with self._lock:
            self._recording = False
            if self.stream is not None:
                try:
                    self.stream.stop()
                    self.stream.close()
                except Exception:
                    pass
                self.stream = None
            if not self.frames:
                return np.zeros(0, dtype='float32')
            audio = np.concatenate(self.frames, axis=0).flatten().astype('float32')
            self.frames = []
            return audio
