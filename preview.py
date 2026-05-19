"""Pre-paste verification dialog with optional cleaned-text view + Speak button."""
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton,
    QCheckBox, QProgressBar, QRadioButton, QButtonGroup,
)


class PreviewDialog(QDialog):
    """Modeless preview. Shows raw + (optionally) cleaned transcript.
    Emits speak_requested(text) when user clicks Speak."""

    speak_requested = Signal(str)

    def __init__(self, raw_text, cleaned_text, audio_stats, press_enter_default,
                 auto_send_ms=0, tts_available=False, llm_pending=False,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle("Confirm before paste")
        self.setWindowFlags(
            Qt.Dialog | Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint
        )
        self.setMinimumWidth(560)
        self.setModal(False)

        self._raw = raw_text
        self._cleaned = cleaned_text
        self._press_enter = press_enter_default
        self._auto_send_ms = auto_send_ms
        self._elapsed = 0
        self._cancelled = False
        self._llm_pending = llm_pending

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(8)

        dur = audio_stats.get("duration_s", 0.0)
        peak = audio_stats.get("peak", 0.0)
        rms = audio_stats.get("rms", 0.0)
        voiced = audio_stats.get("voiced", False)
        header = QLabel(
            f"<b>Heard {dur:.1f}s</b> &middot; peak {peak:.2f} &middot; "
            f"rms {rms:.3f} &middot; {'voiced' if voiced else 'no speech detected'}"
        )
        header.setStyleSheet("color:#9aa0a6;")
        outer.addWidget(header)

        view_row = QHBoxLayout()
        self.raw_radio = QRadioButton("Raw")
        self.cleaned_radio = QRadioButton("Cleaned")
        self.view_group = QButtonGroup(self)
        self.view_group.addButton(self.raw_radio, 0)
        self.view_group.addButton(self.cleaned_radio, 1)
        if cleaned_text is not None:
            self.cleaned_radio.setChecked(True)
        else:
            self.raw_radio.setChecked(True)
            if llm_pending:
                self.cleaned_radio.setText("Cleaned (...)")
                self.cleaned_radio.setEnabled(False)
            else:
                self.cleaned_radio.setEnabled(False)
        view_row.addWidget(QLabel("View:"))
        view_row.addWidget(self.raw_radio)
        view_row.addWidget(self.cleaned_radio)
        view_row.addStretch(1)
        outer.addLayout(view_row)

        self.edit = QTextEdit()
        self.edit.setMinimumHeight(80)
        self.edit.setMaximumHeight(200)
        outer.addWidget(self.edit)
        self._sync_text()
        self.view_group.idClicked.connect(self._on_view_change)

        opts = QHBoxLayout()
        self.enter_cb = QCheckBox("Press Enter (send)")
        self.enter_cb.setChecked(press_enter_default)
        opts.addWidget(self.enter_cb)
        opts.addStretch(1)
        self.speak_btn = QPushButton("Speak")
        self.speak_btn.setEnabled(tts_available)
        if not tts_available:
            self.speak_btn.setToolTip("TTS not configured")
        self.speak_btn.clicked.connect(self._do_speak)
        opts.addWidget(self.speak_btn)
        outer.addLayout(opts)

        if auto_send_ms > 0:
            self.progress = QProgressBar()
            self.progress.setRange(0, auto_send_ms)
            self.progress.setValue(0)
            self.progress.setTextVisible(False)
            self.progress.setFixedHeight(4)
            outer.addWidget(self.progress)
            self._timer = QTimer(self)
            self._timer.setInterval(50)
            self._timer.timeout.connect(self._tick)
            self._timer.start()
        else:
            self.progress = None
            self._timer = None

        btns = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancel (Esc)")
        self.send_btn = QPushButton("Send (Ctrl+Enter)")
        self.send_btn.setDefault(True)
        self.send_btn.setStyleSheet(
            "background:#2d6cdf; color:white; border:1px solid #1f55b8;"
            " border-radius:6px; padding:6px 14px; font-weight:600;"
        )
        btns.addStretch(1)
        btns.addWidget(self.cancel_btn)
        btns.addWidget(self.send_btn)
        outer.addLayout(btns)

        self.send_btn.clicked.connect(self._accept)
        self.cancel_btn.clicked.connect(self._reject)

        QShortcut(QKeySequence("Ctrl+Return"), self, self._accept)
        QShortcut(QKeySequence("Ctrl+Enter"), self, self._accept)
        QShortcut(QKeySequence("Escape"), self, self._reject)

        self.edit.textChanged.connect(self._pause_autosend)

        self.setStyleSheet("""
            QDialog { background:#1e1f22; color:#e6e6e6;
                      border:1px solid #3a3d42; border-radius:8px;
                      font-family:'Segoe UI',sans-serif; font-size:12px; }
            QTextEdit { background:#15161a; border:1px solid #2a2c30;
                        border-radius:6px; padding:6px; color:#e6e6e6; }
            QPushButton { background:#2a2c30; border:1px solid #3a3d42;
                          border-radius:6px; padding:6px 12px; color:#e6e6e6; }
            QPushButton:hover { background:#34373c; }
            QProgressBar { background:#2a2c30; border:none; border-radius:2px; }
            QProgressBar::chunk { background:#2d6cdf; border-radius:2px; }
            QCheckBox, QRadioButton, QLabel { color:#e6e6e6; }
        """)

    def set_cleaned(self, cleaned_text):
        self._cleaned = cleaned_text
        self._llm_pending = False
        self.cleaned_radio.setEnabled(True)
        self.cleaned_radio.setText("Cleaned")
        if cleaned_text is not None:
            self.cleaned_radio.setChecked(True)

    def set_cleaned_failed(self, err_msg=""):
        self._llm_pending = False
        self.cleaned_radio.setText("Cleaned (failed)")
        self.cleaned_radio.setEnabled(False)
        if err_msg:
            self.cleaned_radio.setToolTip(err_msg)

    def update_interim(self, text):
        """Stream interim transcripts in while recording (called pre-finalization)."""
        if not self.raw_radio.isChecked() and self._cleaned is not None:
            return
        self._raw = text
        cur_pos = self.edit.textCursor().position()
        self.edit.blockSignals(True)
        self.edit.setPlainText(text)
        self.edit.blockSignals(False)

    def _sync_text(self):
        if self.cleaned_radio.isChecked() and self._cleaned is not None:
            self.edit.setPlainText(self._cleaned)
        else:
            self.edit.setPlainText(self._raw)
        self.edit.selectAll()
        self.edit.setFocus()

    def _on_view_change(self, _id):
        self._sync_text()

    def _do_speak(self):
        text = self.edit.toPlainText().strip()
        if text:
            self.speak_requested.emit(text)

    def _tick(self):
        self._elapsed += 50
        if self.progress is not None:
            self.progress.setValue(self._elapsed)
        if self._elapsed >= self._auto_send_ms:
            self._timer.stop()
            self._accept()

    def _pause_autosend(self):
        if self._timer is not None:
            self._timer.stop()
            if self.progress is not None:
                self.progress.setValue(0)
                self.progress.setVisible(False)

    def _accept(self):
        self._final_text = self.edit.toPlainText().strip()
        self._press_enter = self.enter_cb.isChecked()
        self._cancelled = False
        self.accept()

    def _reject(self):
        self._cancelled = True
        self.reject()

    @property
    def result_text(self):
        return getattr(self, "_final_text", self._raw)

    @property
    def result_press_enter(self):
        return self._press_enter

    @property
    def cancelled(self):
        return self._cancelled
