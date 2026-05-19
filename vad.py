"""Streaming VAD. Adaptive RMS energy threshold over noise floor.

Cheap, deterministic, no extra deps. Calibrates noise floor from the first
~300ms (assumed quiet). After that, a chunk is 'voiced' if its RMS exceeds
noise_floor * margin. Tracks how long since the last voiced chunk and whether
the user has spoken at all yet, so the caller can auto-stop on silence.
"""
import time
import numpy as np


class StreamingVAD:
    def __init__(
        self,
        samplerate=16000,
        calibration_ms=300,
        margin=2.5,
        min_floor=0.003,
        max_floor=0.05,
    ):
        self.sr = samplerate
        self.calibration_samples = int(samplerate * calibration_ms / 1000)
        self.margin = margin
        self.min_floor = min_floor
        self.max_floor = max_floor
        self.reset()

    def reset(self):
        self._calib_buf = []
        self._calib_done = False
        self._noise_floor = self.min_floor
        self._has_spoken = False
        self._last_voice_t = None
        self._last_chunk_t = time.monotonic()
        self._calib_started = time.monotonic()

    def feed(self, samples: np.ndarray):
        """Push a chunk of float32 mono samples. Returns is_voiced for this chunk."""
        if samples is None or len(samples) == 0:
            return False
        now = time.monotonic()
        self._last_chunk_t = now

        if not self._calib_done:
            self._calib_buf.append(samples)
            total = sum(len(c) for c in self._calib_buf)
            # Finish calibration once enough samples OR enough wall time elapsed
            if total >= self.calibration_samples or (now - self._calib_started) > 0.8:
                cat = np.concatenate(self._calib_buf)
                noise_rms = float(np.sqrt(np.mean(cat ** 2) + 1e-12))
                self._noise_floor = max(self.min_floor, min(self.max_floor, noise_rms))
                self._calib_done = True
                self._calib_buf = []
            return False

        rms = float(np.sqrt(np.mean(samples ** 2) + 1e-12))
        threshold = self._noise_floor * self.margin
        is_voiced = rms > threshold

        if is_voiced:
            self._has_spoken = True
            self._last_voice_t = now
        else:
            # Slowly adapt noise floor downward when quiet (handles fan turning on, etc.)
            self._noise_floor = min(
                self.max_floor,
                0.97 * self._noise_floor + 0.03 * rms,
            )

        return is_voiced

    @property
    def has_spoken(self):
        return self._has_spoken

    @property
    def ms_since_voice(self):
        if self._last_voice_t is None:
            return None
        return int((time.monotonic() - self._last_voice_t) * 1000)

    @property
    def calibrated(self):
        return self._calib_done

    @property
    def noise_floor(self):
        return self._noise_floor
