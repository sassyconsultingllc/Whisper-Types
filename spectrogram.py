"""Scrolling mel-ish spectrogram visualizer. Pure numpy FFT, no librosa."""
from collections import deque
import numpy as np

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QColor, QImage
from PySide6.QtWidgets import QWidget


class SpectrogramMeter(QWidget):
    """Rolling spectrogram. Audio thread feeds chunks; UI thread paints."""
    N_BANDS = 24
    N_COLS = 64
    FFT_SIZE = 512
    SR = 16000

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(160, 30)
        self._cols = deque([np.zeros(self.N_BANDS, dtype='float32')] * self.N_COLS,
                           maxlen=self.N_COLS)
        self._pending = np.zeros(0, dtype='float32')
        self._active = False
        # Pre-compute mel-style log-spaced band edges over FFT bins
        n_bins = self.FFT_SIZE // 2 + 1
        edges = np.logspace(np.log10(2), np.log10(n_bins - 1), self.N_BANDS + 1).astype(int)
        edges = np.unique(edges)
        if len(edges) < self.N_BANDS + 1:
            # Pad with linear fill if dedupe shortened it
            edges = np.linspace(2, n_bins - 1, self.N_BANDS + 1).astype(int)
        self._edges = edges
        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self.update)

    def start(self):
        self._active = True
        self._cols = deque([np.zeros(self.N_BANDS, dtype='float32')] * self.N_COLS,
                           maxlen=self.N_COLS)
        self._pending = np.zeros(0, dtype='float32')
        self._timer.start()
        self.update()

    def stop(self):
        self._active = False
        self._timer.stop()
        self.update()

    def feed(self, samples: np.ndarray):
        """Audio thread. Buffer + compute STFT frames."""
        if samples is None or len(samples) == 0:
            return
        self._pending = np.concatenate([self._pending, samples])
        # Slide FFT window with 50% overlap
        hop = self.FFT_SIZE // 2
        while len(self._pending) >= self.FFT_SIZE:
            frame = self._pending[:self.FFT_SIZE]
            self._pending = self._pending[hop:]
            window = np.hanning(self.FFT_SIZE).astype('float32')
            spec = np.fft.rfft(frame * window)
            mag = np.abs(spec) + 1e-9
            db = 20 * np.log10(mag)
            # Bucket into N_BANDS
            bands = np.zeros(self.N_BANDS, dtype='float32')
            for i in range(self.N_BANDS):
                lo, hi = self._edges[i], self._edges[i + 1]
                if hi > lo:
                    bands[i] = db[lo:hi].mean()
            # Normalize -80dB .. 0dB -> 0..1
            norm = np.clip((bands + 80) / 80, 0.0, 1.0)
            self._cols.append(norm)

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#15161a"))
        p.setPen(QColor("#2a2c30"))
        p.drawRect(0, 0, self.width() - 1, self.height() - 1)

        cols = list(self._cols)
        if not cols:
            return
        w = self.width() - 4
        h = self.height() - 4
        col_w = max(1.0, w / len(cols))
        band_h = max(1.0, h / self.N_BANDS)

        for ci, col in enumerate(cols):
            x = 2 + ci * col_w
            for bi in range(self.N_BANDS):
                v = col[bi]
                if v < 0.05:
                    continue
                # Blue -> green -> yellow -> red ramp
                if v < 0.33:
                    color = QColor(int(58 + 30 * v / 0.33), int(141 - 50 * v / 0.33), 222)
                elif v < 0.66:
                    t = (v - 0.33) / 0.33
                    color = QColor(int(90 + 100 * t), int(180 + 30 * t), int(120 - 80 * t))
                else:
                    t = (v - 0.66) / 0.34
                    color = QColor(int(220 + 30 * t), int(180 - 100 * t), int(60 - 40 * t))
                y = 2 + h - (bi + 1) * band_h
                p.fillRect(int(x), int(y), int(col_w) + 1, int(band_h) + 1, color)
        p.end()

    # Compatibility methods
    def set_voiced(self, _voiced):
        pass

    @property
    def peak(self):
        return 0.0
