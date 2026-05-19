"""Small live audio level meter. 16 bars, rolling RMS history."""
from collections import deque
import math
import numpy as np

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QColor, QBrush, QPen
from PySide6.QtWidgets import QWidget


class WaveformMeter(QWidget):
    BARS = 16

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(96, 30)
        self._levels = deque([0.0] * self.BARS, maxlen=self.BARS)
        self._latest_rms = 0.0
        self._peak = 0.0
        self._active = False
        self._voiced = False
        self._timer = QTimer(self)
        self._timer.setInterval(50)  # 20 fps
        self._timer.timeout.connect(self._tick)

    def start(self):
        self._levels = deque([0.0] * self.BARS, maxlen=self.BARS)
        self._latest_rms = 0.0
        self._peak = 0.0
        self._active = True
        self._timer.start()
        self.update()

    def stop(self):
        self._active = False
        self._timer.stop()
        self._levels = deque([0.0] * self.BARS, maxlen=self.BARS)
        self.update()

    def feed(self, samples: np.ndarray):
        """Called from audio thread. Keep light."""
        if samples is None or len(samples) == 0:
            return
        rms = float(np.sqrt(np.mean(samples ** 2) + 1e-12))
        # Smoothed envelope
        self._latest_rms = max(rms, self._latest_rms * 0.7)
        peak = float(np.max(np.abs(samples)))
        if peak > self._peak:
            self._peak = peak

    def set_voiced(self, voiced: bool):
        if voiced != self._voiced:
            self._voiced = voiced
            self.update()

    @property
    def peak(self):
        return self._peak

    def _tick(self):
        # Push current level into history, decay latest so bars fall naturally
        # Log-scale so quiet speech registers
        v = self._latest_rms
        if v > 1e-5:
            db = 20 * math.log10(v + 1e-9)  # ~ -100 to 0
            norm = max(0.0, min(1.0, (db + 60) / 60))  # -60dB floor
        else:
            norm = 0.0
        self._levels.append(norm)
        self._latest_rms *= 0.55  # decay between ticks
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        p.fillRect(self.rect(), QColor("#15161a"))
        p.setPen(QPen(QColor("#2a2c30"), 1))
        p.drawRect(0, 0, self.width() - 1, self.height() - 1)

        bars = list(self._levels)
        n = len(bars)
        if n == 0:
            return
        pad_x = 3
        pad_y = 3
        avail_w = self.width() - pad_x * 2
        avail_h = self.height() - pad_y * 2
        bar_w = max(2, (avail_w - (n - 1)) / n)
        gap = 1.0

        base = QColor("#3a8dde") if self._active else QColor("#3a3d42")
        hot = QColor("#5fd17a") if self._voiced else base

        for i, lvl in enumerate(bars):
            x = pad_x + i * (bar_w + gap)
            h = max(1, int(avail_h * lvl))
            y = pad_y + (avail_h - h)
            color = hot if (self._active and lvl > 0.15) else base
            p.fillRect(int(x), int(y), int(bar_w), int(h), QBrush(color))
        p.end()
