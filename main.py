"""WhisperTyper - main app.

Features: toggle/PTT hotkeys + cancel hotkey, VAD auto-stop, live waveform/spectrogram,
pre-paste preview with edit, LLM transcript cleanup, local TTS (Kokoro/Piper/OpenAI-compat),
transcript history, per-target preferences, streaming interim transcripts.
"""
import sys
import json
import threading
import time
from pathlib import Path

import numpy as np

from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtGui import QAction, QPalette, QColor
from PySide6.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout, QComboBox, QPushButton,
    QLabel, QSystemTrayIcon, QMenu, QCheckBox, QDialog, QMessageBox,
)

from audio_capture import Recorder
from transcriber import Transcriber
from target import list_windows, inject_text
from hotkey import MultiHotkey
from vad import StreamingVAD
from waveform import WaveformMeter
from spectrogram import SpectrogramMeter
from preview import PreviewDialog
from history import HistoryStore, HistoryDialog
from target_prefs import TargetPrefs
from llm import LLMClient, DEFAULT_SYSTEM_PROMPT
from tts import build_tts, stop_playback
from settings_dialog import SettingsDialog


CONFIG_PATH = Path.home() / ".whispertyper" / "config.json"
DEFAULT_CFG = {
    # Whisper
    "model_size": "base.en",
    "device": "auto",
    "compute_type": "auto",
    "language": None,
    "beam_size": 1,
    # Hotkeys
    "hotkey": "<ctrl>+<alt>+<space>",
    "hotkey_mode": "toggle",
    "cancel_hotkey": "<ctrl>+<alt>+x",
    # VAD / audio
    "vad_autostop": True,
    "vad_silence_ms": 1200,
    "vad_margin": 2.5,
    "vad_max_record_ms": 30000,
    "min_audio_peak": 0.005,
    # Streaming
    "interim_transcripts": False,
    "interim_interval_ms": 2000,
    # Preview & history
    "preview_before_paste": True,
    "preview_autosend_ms": 0,
    "save_history": True,
    # Visual
    "visualizer": "bars",  # bars | spectrogram | off
    "bar_opacity": 1.0,
    "always_on_top": True,
    "show_tray": True,
    # Behaviour
    "press_enter_apps": ["slack", "discord", "teams", "whatsapp", "signal", "chat"],
    "trim_trailing_period_for_enter": True,
    # LLM cleanup
    "llm_enabled": False,
    "llm_base_url": "http://100.99.213.97:11434/v1",
    "llm_api_key": "",
    "llm_model": "llama3.2:3b",
    "llm_timeout": 20,
    "llm_default_cleaned": True,
    "llm_system_prompt": DEFAULT_SYSTEM_PROMPT,
    # TTS
    "tts_enabled": False,
    "tts_backend": "kokoro",
    "tts_voice": "af_sky",
    "tts_speed": 1.0,
    "tts_lang": "en-us",
    "tts_piper_model": "",
    "tts_base_url": "http://127.0.0.1:8880/v1",
    "tts_api_key": "",
    "tts_model": "tts-1",
    "tts_autoread": False,
}


def load_cfg():
    if CONFIG_PATH.exists():
        try:
            return {**DEFAULT_CFG, **json.loads(CONFIG_PATH.read_text())}
        except Exception:
            pass
    return dict(DEFAULT_CFG)


def save_cfg(cfg):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))


class Signals(QObject):
    hk_press = Signal()
    hk_release = Signal()
    hk_cancel = Signal()
    transcribed = Signal(int, str, bool, dict)  # hwnd, text, press_enter, stats
    interim = Signal(str)
    cleaned = Signal(str)
    cleaned_failed = Signal(str)
    status = Signal(str)


class MiniBar(QWidget):
    def __init__(self):
        super().__init__()
        self.cfg = load_cfg()
        self.history = HistoryStore()
        self.target_prefs = TargetPrefs()
        self.tts = None
        self._rebuild_tts()

        self.setWindowTitle("WhisperTyper")
        flags = Qt.FramelessWindowHint | Qt.Tool
        if self.cfg.get("always_on_top", True):
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setFixedHeight(54)
        self.setMinimumWidth(720)

        self.recorder = Recorder()
        self.transcriber = self._build_transcriber()
        self.vad = StreamingVAD(margin=self.cfg["vad_margin"])
        self._recording = False
        self._record_start_t = 0.0
        self._drag_pos = None
        self._preview_dlg = None
        self._history_dlg = None
        self._peak = 0.0
        self._sum_sq = 0.0
        self._n_samples = 0
        self._interim_running = False
        self._latest_interim = ""

        # Signal bus
        self.sig = Signals()
        self.sig.hk_press.connect(self._on_hotkey_press)
        self.sig.hk_release.connect(self._on_hotkey_release)
        self.sig.hk_cancel.connect(self._on_hotkey_cancel)
        self.sig.transcribed.connect(self._post_transcribe_on_main)
        self.sig.interim.connect(self._on_interim)
        self.sig.cleaned.connect(self._on_cleaned)
        self.sig.cleaned_failed.connect(self._on_cleaned_failed)
        self.sig.status.connect(self._set_status)

        self.vad_timer = QTimer(self)
        self.vad_timer.setInterval(120)
        self.vad_timer.timeout.connect(self._vad_tick)

        self.interim_timer = QTimer(self)
        self.interim_timer.timeout.connect(self._kick_interim)

        self._build_ui()
        self._start_hotkey()
        self._build_tray()
        threading.Thread(target=self._warmup, daemon=True).start()

    def _build_transcriber(self):
        return Transcriber(
            model_size=self.cfg["model_size"],
            device=self.cfg["device"],
            compute_type=self.cfg["compute_type"],
            beam_size=self.cfg.get("beam_size", 1),
        )

    def _rebuild_tts(self):
        try:
            self.tts = build_tts(self.cfg)
        except Exception:
            self.tts = None

    def _build_ui(self):
        self.target_combo = QComboBox()
        self.target_combo.setMinimumWidth(220)
        self.target_combo.setToolTip("Target window")
        self.refresh_btn = QPushButton("\u21bb"); self.refresh_btn.setFixedWidth(28)
        self.refresh_btn.setToolTip("Refresh windows")
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["toggle", "ptt"])
        self.mode_combo.setCurrentText(self.cfg["hotkey_mode"])
        self.enter_check = QCheckBox("Enter")
        self.enter_check.setToolTip("Press Enter after pasting")
        self.preview_check = QCheckBox("Preview")
        self.preview_check.setChecked(bool(self.cfg.get("preview_before_paste", True)))
        self.preview_check.toggled.connect(self._on_preview_toggle)
        self.clean_check = QCheckBox("LLM")
        self.clean_check.setChecked(bool(self.cfg.get("llm_enabled", False)))
        self.clean_check.setToolTip("LLM cleanup")
        self.clean_check.toggled.connect(self._on_llm_toggle)

        self._build_visualizer()

        self.rec_btn = QPushButton("Record"); self.rec_btn.setMinimumWidth(80)
        self.status_lbl = QLabel("Ready")
        self.status_lbl.setStyleSheet("color:#9aa0a6;")
        self.status_lbl.setMinimumWidth(120)
        self.history_btn = QPushButton("\u2630"); self.history_btn.setFixedWidth(28)
        self.history_btn.setToolTip("History")
        self.settings_btn = QPushButton("\u2699"); self.settings_btn.setFixedWidth(28)
        self.settings_btn.setToolTip("Settings")
        self.close_btn = QPushButton("\u2715"); self.close_btn.setFixedWidth(28)

        row = QHBoxLayout()
        row.setContentsMargins(12, 8, 12, 8); row.setSpacing(6)
        row.addWidget(self.target_combo, 1)
        row.addWidget(self.refresh_btn)
        row.addWidget(self.mode_combo)
        row.addWidget(self.enter_check)
        row.addWidget(self.preview_check)
        row.addWidget(self.clean_check)
        if self.meter is not None:
            row.addWidget(self.meter)
        row.addWidget(self.rec_btn)
        row.addWidget(self.status_lbl)
        row.addWidget(self.history_btn)
        row.addWidget(self.settings_btn)
        row.addWidget(self.close_btn)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addLayout(row)

        self.setStyleSheet("""
            QWidget { background:#1e1f22; color:#e6e6e6; font-size:12px;
                      font-family: 'Segoe UI',sans-serif; }
            QComboBox, QPushButton, QCheckBox {
                background:#2a2c30; border:1px solid #3a3d42;
                border-radius:6px; padding:4px 8px;
            }
            QPushButton:hover { background:#34373c; }
            QPushButton:pressed { background:#22242a; }
            QComboBox QAbstractItemView { background:#2a2c30; selection-background-color:#3a8dde; }
        """)
        self.setWindowOpacity(self.cfg.get("bar_opacity", 1.0))

        self.refresh_btn.clicked.connect(self.refresh_windows)
        self.rec_btn.clicked.connect(self._on_rec_button)
        self.history_btn.clicked.connect(self._open_history)
        self.settings_btn.clicked.connect(self.open_settings)
        self.close_btn.clicked.connect(QApplication.quit)
        self.target_combo.currentIndexChanged.connect(self._on_target_change)
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)

        self.refresh_windows()
        self._on_target_change()

    def _build_visualizer(self):
        viz = self.cfg.get("visualizer", "bars")
        if viz == "spectrogram":
            self.meter = SpectrogramMeter()
        elif viz == "off":
            self.meter = None
        else:
            self.meter = WaveformMeter()

    def _build_tray(self):
        if not self.cfg.get("show_tray", True):
            self.tray = None
            return
        self.tray = QSystemTrayIcon(self)
        style = self.style()
        from PySide6.QtWidgets import QStyle
        self.tray.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        menu = QMenu()
        for label, cb in [
            ("Toggle Record", self._on_rec_button),
            ("Show Bar", self._show_bar),
            ("History", self._open_history),
            ("Settings", self.open_settings),
        ]:
            act = QAction(label, self); act.triggered.connect(cb); menu.addAction(act)
        menu.addSeparator()
        q = QAction("Quit", self); q.triggered.connect(QApplication.quit); menu.addAction(q)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda r: self._show_bar() if r == QSystemTrayIcon.Trigger else None)
        self.tray.setToolTip("WhisperTyper")
        self.tray.show()

    # ---- lifecycle helpers --------------------------------------------

    def _warmup(self):
        self.sig.status.emit("Loading model...")
        try:
            self.transcriber.ensure_loaded()
            self.sig.status.emit("Ready")
        except Exception as e:
            self.sig.status.emit(f"Model err: {str(e)[:40]}")

    def _show_bar(self):
        self.show(); self.raise_(); self.activateWindow()

    # ---- Hotkey wiring -------------------------------------------------

    def _start_hotkey(self):
        if hasattr(self, "hotkey") and self.hotkey is not None:
            self.hotkey.stop()
        cancel = self.cfg.get("cancel_hotkey", "").strip() or None
        self.hotkey = MultiHotkey(
            primary_combo=self.cfg["hotkey"],
            primary_mode=self.cfg["hotkey_mode"],
            on_press=self.sig.hk_press.emit,
            on_release=self.sig.hk_release.emit,
            cancel_combo=cancel,
            on_cancel=self.sig.hk_cancel.emit if cancel else None,
        )
        try:
            self.hotkey.start()
        except Exception as e:
            print("Hotkey start failed:", e)

    def _on_hotkey_press(self):
        if self.cfg["hotkey_mode"] == "ptt":
            if not self._recording:
                self.start_record()
        else:
            self._on_rec_button()

    def _on_hotkey_release(self):
        if self.cfg["hotkey_mode"] == "ptt" and self._recording:
            self.stop_record(reason="ptt-release")

    def _on_hotkey_cancel(self):
        if self._recording:
            self.cancel_record()
        elif self._preview_dlg is not None:
            try:
                self._preview_dlg.close()
            except Exception:
                pass

    def _on_mode_changed(self, mode):
        if mode == self.cfg["hotkey_mode"]:
            return
        self.cfg["hotkey_mode"] = mode
        save_cfg(self.cfg)
        self._start_hotkey()

    def _on_preview_toggle(self, on):
        self.cfg["preview_before_paste"] = bool(on)
        save_cfg(self.cfg)

    def _on_llm_toggle(self, on):
        self.cfg["llm_enabled"] = bool(on)
        save_cfg(self.cfg)

    # ---- Per-target prefs ----------------------------------------------

    def _current_target(self):
        idx = self.target_combo.currentIndex()
        if idx < 0:
            return None, None, None
        label = self.target_combo.currentText()
        hwnd = self.target_combo.currentData()
        exe = None
        if "[" in label and label.endswith("]"):
            exe = label.rsplit("[", 1)[1].rstrip("]").strip()
        return hwnd, label, exe

    def _on_target_change(self):
        hwnd, label, exe = self._current_target()
        if exe is None:
            return
        prefs = self.target_prefs.get(exe)
        # Apply Enter default
        if "press_enter" in prefs:
            self.enter_check.setChecked(bool(prefs["press_enter"]))
        else:
            default_enter = any(a in label.lower() for a in self.cfg["press_enter_apps"])
            self.enter_check.setChecked(default_enter)
        if "preview" in prefs:
            self.preview_check.setChecked(bool(prefs["preview"]))
        else:
            self.preview_check.setChecked(bool(self.cfg.get("preview_before_paste", True)))
        if "llm" in prefs:
            self.clean_check.setChecked(bool(prefs["llm"]))
        else:
            self.clean_check.setChecked(bool(self.cfg.get("llm_enabled", False)))

    def _save_target_prefs(self):
        _, _, exe = self._current_target()
        if not exe:
            return
        self.target_prefs.set(
            exe,
            press_enter=self.enter_check.isChecked(),
            preview=self.preview_check.isChecked(),
            llm=self.clean_check.isChecked(),
        )

    # ---- Recording -----------------------------------------------------

    def _on_rec_button(self):
        if not self._recording:
            self.start_record()
        else:
            self.stop_record(reason="manual")

    def refresh_windows(self):
        cur = self.target_combo.currentData()
        self.target_combo.clear()
        try:
            my_hwnd = int(self.winId())
        except Exception:
            my_hwnd = 0
        wins = list_windows()
        wins = [w for w in wins if w[0] != my_hwnd and "WhisperTyper" not in w[1]]
        priority = ("slack", "discord", "teams", "code", "word", "outlook",
                    "chrome", "firefox", "edge", "notepad", "obsidian")
        def key(w):
            ex = (w[2] or "").lower()
            for i, p in enumerate(priority):
                if p in ex:
                    return (0, i, w[1].lower())
            return (1, 0, w[1].lower())
        wins.sort(key=key)
        for hwnd, title, exe in wins:
            label = title if len(title) <= 60 else title[:57] + "..."
            if exe:
                label = f"{label}  [{exe}]"
            self.target_combo.addItem(label, hwnd)
        if cur is not None:
            idx = self.target_combo.findData(cur)
            if idx >= 0:
                self.target_combo.setCurrentIndex(idx)

    def _audio_chunk_cb(self, samples):
        self.vad.feed(samples)
        if self.meter is not None:
            self.meter.feed(samples)
        peak = float(np.max(np.abs(samples))) if len(samples) else 0.0
        if peak > self._peak:
            self._peak = peak
        self._sum_sq += float(np.sum(samples ** 2))
        self._n_samples += int(len(samples))

    def start_record(self):
        hwnd, _, _ = self._current_target()
        if hwnd is None:
            self._set_status("No target window")
            return
        if self._recording:
            return

        self._save_target_prefs()
        self.vad = StreamingVAD(margin=self.cfg["vad_margin"])
        self._peak = 0.0; self._sum_sq = 0.0; self._n_samples = 0
        self._latest_interim = ""
        self.recorder.set_chunk_callback(self._audio_chunk_cb)

        try:
            self.recorder.start()
        except Exception as e:
            self._set_status(f"Mic err: {str(e)[:40]}")
            return

        if self.meter is not None:
            self.meter.start()
        self._record_start_t = time.monotonic()
        self._recording = True
        self.rec_btn.setText("Stop")
        self.rec_btn.setStyleSheet(
            "background:#c0392b; color:white; border:1px solid #962d22;"
            " border-radius:6px; padding:4px 8px;"
        )
        if self.cfg["hotkey_mode"] == "toggle" and self.cfg.get("vad_autostop", True):
            self.vad_timer.start()
        if self.cfg.get("interim_transcripts", False):
            self.interim_timer.setInterval(int(self.cfg.get("interim_interval_ms", 2000)))
            self.interim_timer.start()
        self._set_status("Recording (hold)" if self.cfg["hotkey_mode"] == "ptt" else "Recording...")

    def cancel_record(self):
        """Stop recording without transcribing."""
        if not self._recording:
            return
        self._recording = False
        self.vad_timer.stop()
        self.interim_timer.stop()
        if self.meter is not None:
            self.meter.stop()
        self.recorder.set_chunk_callback(None)
        try:
            self.recorder.stop()
        except Exception:
            pass
        self.rec_btn.setText("Record"); self.rec_btn.setStyleSheet("")
        self._set_status("Cancelled")

    def _vad_tick(self):
        if not self._recording:
            self.vad_timer.stop(); return
        if self.meter is not None:
            voiced = self.vad.has_spoken and (self.vad.ms_since_voice or 999) < 300
            self.meter.set_voiced(voiced)
        elapsed_ms = int((time.monotonic() - self._record_start_t) * 1000)
        if elapsed_ms >= self.cfg["vad_max_record_ms"]:
            self.stop_record(reason="max-time"); return
        if not self.vad.has_spoken:
            if self.vad.calibrated:
                self._set_status(f"Listening... ({elapsed_ms // 1000}s)")
            return
        ms_quiet = self.vad.ms_since_voice or 0
        if ms_quiet >= self.cfg["vad_silence_ms"]:
            self.stop_record(reason="vad-silence")
        else:
            self._set_status(f"Recording (silence {ms_quiet}ms)")

    def _kick_interim(self):
        if not self._recording or self._interim_running:
            return
        snap = self.recorder.snapshot()
        if len(snap) < 16000:  # <1s
            return
        # Cap interim to last 15s to bound latency
        if len(snap) > 16000 * 15:
            snap = snap[-16000 * 15:]
        self._interim_running = True
        threading.Thread(target=self._interim_worker, args=(snap,), daemon=True).start()

    def _interim_worker(self, audio):
        try:
            text = self.transcriber.transcribe(audio, language=self.cfg["language"])
            if text:
                self.sig.interim.emit(text)
        except Exception:
            pass
        finally:
            self._interim_running = False

    def _on_interim(self, text):
        self._latest_interim = text
        preview = text if len(text) <= 60 else text[:57] + "..."
        self._set_status(f"...{preview}")
        if self._preview_dlg is not None:
            try:
                self._preview_dlg.update_interim(text)
            except Exception:
                pass

    def stop_record(self, reason="manual"):
        if not self._recording:
            return
        self._recording = False
        self.vad_timer.stop()
        self.interim_timer.stop()
        if self.meter is not None:
            self.meter.stop()
        self.recorder.set_chunk_callback(None)
        self.rec_btn.setText("Record"); self.rec_btn.setStyleSheet("")
        self._set_status(f"Transcribing ({reason})...")
        try:
            audio = self.recorder.stop()
        except Exception as e:
            self._set_status(f"Audio err: {str(e)[:40]}")
            return

        duration_s = self._n_samples / 16000.0 if self._n_samples else 0.0
        rms = (self._sum_sq / self._n_samples) ** 0.5 if self._n_samples else 0.0
        stats = {
            "duration_s": duration_s,
            "peak": self._peak,
            "rms": rms,
            "voiced": self.vad.has_spoken,
            "noise_floor": self.vad.noise_floor,
        }
        hwnd, _, _ = self._current_target()
        press_enter = self.enter_check.isChecked()
        threading.Thread(
            target=self._transcribe_worker,
            args=(audio, hwnd, press_enter, stats),
            daemon=True,
        ).start()

    def _transcribe_worker(self, audio, hwnd, press_enter, stats):
        try:
            min_peak = float(self.cfg.get("min_audio_peak", 0.005))
            if audio is None or len(audio) < 1600:
                self.sig.status.emit(f"Too short ({stats['duration_s']:.1f}s)")
                return
            if stats["peak"] < min_peak:
                self.sig.status.emit(f"No audio heard (peak {stats['peak']:.3f})")
                return
            text = self.transcriber.transcribe(audio, language=self.cfg["language"])
            if not text:
                self.sig.status.emit(
                    f"Empty (heard {stats['duration_s']:.1f}s, peak {stats['peak']:.2f})"
                )
                return
            if press_enter and self.cfg.get("trim_trailing_period_for_enter"):
                text = text.rstrip().rstrip(".")
            self.sig.transcribed.emit(hwnd, text, press_enter, stats)
        except Exception as e:
            self.sig.status.emit(f"Err: {str(e)[:50]}")

    # ---- Post-transcribe orchestration --------------------------------

    def _post_transcribe_on_main(self, hwnd, text, press_enter, stats):
        _, title, exe = self._current_target()
        use_llm = self.clean_check.isChecked() and self.cfg.get("llm_enabled", False)
        use_preview = self.preview_check.isChecked()

        if not use_preview:
            # Direct path: optional LLM, optional TTS, then inject
            if use_llm:
                threading.Thread(
                    target=self._direct_with_llm,
                    args=(hwnd, text, press_enter, stats, title, exe),
                    daemon=True,
                ).start()
            else:
                if self.cfg.get("tts_autoread", False) and self.tts:
                    threading.Thread(target=self._speak_async, args=(text,), daemon=True).start()
                self._do_inject(hwnd, text, press_enter)
                self._log_history(text, None, exe, title, stats, True, press_enter)
            return

        # Preview path
        self._show_preview(hwnd, text, press_enter, stats, use_llm, title, exe)

    def _direct_with_llm(self, hwnd, text, press_enter, stats, title, exe):
        try:
            cleaned = self._llm_clean(text)
        except Exception as e:
            self.sig.status.emit(f"LLM err: {str(e)[:40]}")
            cleaned = text
        final = cleaned if (self.cfg.get("llm_default_cleaned", True) and cleaned) else text
        if press_enter and self.cfg.get("trim_trailing_period_for_enter"):
            final = final.rstrip().rstrip(".")
        if self.cfg.get("tts_autoread", False) and self.tts:
            self._speak_async(final)
        # Marshal inject + log to main thread
        QTimer.singleShot(0, lambda: self._do_inject(hwnd, final, press_enter))
        QTimer.singleShot(0, lambda: self._log_history(text, cleaned, exe, title, stats, True, press_enter))

    def _llm_clean(self, text):
        if not self.cfg.get("llm_enabled", False):
            return None
        client = LLMClient(
            base_url=self.cfg["llm_base_url"],
            api_key=self.cfg.get("llm_api_key", ""),
            model=self.cfg["llm_model"],
            system_prompt=self.cfg.get("llm_system_prompt") or DEFAULT_SYSTEM_PROMPT,
            timeout=self.cfg.get("llm_timeout", 20),
        )
        return client.clean(text)

    def _show_preview(self, hwnd, text, press_enter, stats, use_llm, title, exe):
        if self._preview_dlg is not None:
            try:
                self._preview_dlg.close()
            except Exception:
                pass
            self._preview_dlg = None

        dlg = PreviewDialog(
            raw_text=text,
            cleaned_text=None,
            audio_stats=stats,
            press_enter_default=press_enter,
            auto_send_ms=int(self.cfg.get("preview_autosend_ms", 0) or 0),
            tts_available=self.tts is not None,
            llm_pending=use_llm,
            parent=self,
        )
        dlg.speak_requested.connect(self._speak_async)

        bar_geo = self.frameGeometry()
        dlg.adjustSize()
        x = max(20, bar_geo.right() - dlg.width())
        y = max(20, bar_geo.top() - dlg.height() - 8)
        dlg.move(x, y)

        def on_done(result):
            self._preview_dlg = None
            cleaned_used = None
            if dlg.cancelled or result == QDialog.Rejected:
                self._set_status("Cancelled")
                self._log_history(text, None, exe, title, stats, False, press_enter)
                return
            new_text = dlg.result_text.strip()
            new_enter = dlg.result_press_enter
            if not new_text:
                self._set_status("Empty - not sent")
                return
            if new_enter and self.cfg.get("trim_trailing_period_for_enter"):
                new_text = new_text.rstrip().rstrip(".")
            if dlg._cleaned and new_text == dlg._cleaned:
                cleaned_used = dlg._cleaned
            self._do_inject(hwnd, new_text, new_enter)
            self._log_history(text, cleaned_used, exe, title, stats, True, new_enter)

        dlg.finished.connect(on_done)
        self._preview_dlg = dlg
        dlg.show(); dlg.raise_(); dlg.activateWindow()
        self._set_status("Awaiting confirmation")

        if use_llm:
            threading.Thread(target=self._preview_llm_worker, args=(text, dlg), daemon=True).start()

    def _preview_llm_worker(self, text, dlg):
        try:
            cleaned = self._llm_clean(text)
            if cleaned:
                self.sig.cleaned.emit(cleaned)
            else:
                self.sig.cleaned_failed.emit("(no result)")
        except Exception as e:
            self.sig.cleaned_failed.emit(str(e)[:200])

    def _on_cleaned(self, cleaned):
        if self._preview_dlg is not None:
            try:
                self._preview_dlg.set_cleaned(cleaned)
            except Exception:
                pass

    def _on_cleaned_failed(self, msg):
        if self._preview_dlg is not None:
            try:
                self._preview_dlg.set_cleaned_failed(msg)
            except Exception:
                pass
        self._set_status(f"LLM failed: {msg[:60]}")

    def _do_inject(self, hwnd, text, press_enter):
        ok = inject_text(hwnd, text, press_enter=press_enter)
        preview = text if len(text) <= 50 else text[:47] + "..."
        self._set_status(f'Sent: "{preview}"' if ok else "Inject failed")

    def _log_history(self, raw, cleaned, exe, title, stats, sent, press_enter):
        if not self.cfg.get("save_history", True):
            return
        try:
            self.history.add(
                text=raw, cleaned=cleaned, target_exe=exe, target_title=title,
                stats=stats, sent=sent, press_enter=press_enter,
            )
        except Exception:
            pass

    # ---- TTS -----------------------------------------------------------

    def _speak_async(self, text):
        if not self.tts:
            self._set_status("TTS not configured")
            return
        threading.Thread(target=self._speak_worker, args=(text,), daemon=True).start()

    def _speak_worker(self, text):
        try:
            self.tts.speak(text)
        except Exception as e:
            self.sig.status.emit(f"TTS err: {str(e)[:60]}")

    # ---- History -------------------------------------------------------

    def _open_history(self):
        if self._history_dlg is not None:
            try:
                self._history_dlg.close()
            except Exception:
                pass
        dlg = HistoryDialog(self.history, parent=self)
        dlg.resend_requested.connect(self._resend_from_history)
        dlg.speak_requested.connect(self._speak_async)
        self._history_dlg = dlg
        dlg.show()

    def _resend_from_history(self, text, press_enter):
        hwnd, _, _ = self._current_target()
        if hwnd is None:
            self._set_status("No target window")
            return
        self._do_inject(hwnd, text, press_enter)

    # ---- Status --------------------------------------------------------

    def _set_status(self, msg):
        self.status_lbl.setText(msg)
        self.setToolTip(msg)
        self.setWindowTitle(f"WhisperTyper - {msg}")
        if self.tray is not None:
            self.tray.setToolTip(f"WhisperTyper: {msg}")

    # ---- Settings ------------------------------------------------------

    def open_settings(self):
        dlg = SettingsDialog(self.cfg, self.target_prefs, self)
        if dlg.exec() != QDialog.Accepted:
            return
        new_cfg = dlg.values()
        model_changed = (
            new_cfg["model_size"] != self.cfg["model_size"]
            or new_cfg["device"] != self.cfg["device"]
            or new_cfg["compute_type"] != self.cfg["compute_type"]
            or new_cfg["beam_size"] != self.cfg.get("beam_size", 1)
        )
        hotkey_changed = (
            new_cfg["hotkey"] != self.cfg["hotkey"]
            or new_cfg["hotkey_mode"] != self.cfg["hotkey_mode"]
            or new_cfg["cancel_hotkey"] != self.cfg.get("cancel_hotkey", "")
        )
        tts_changed = any(
            new_cfg.get(k) != self.cfg.get(k) for k in (
                "tts_enabled", "tts_backend", "tts_voice", "tts_speed", "tts_lang",
                "tts_piper_model", "tts_base_url", "tts_api_key", "tts_model",
            )
        )
        viz_changed = new_cfg["visualizer"] != self.cfg.get("visualizer")
        flags_changed = new_cfg["always_on_top"] != self.cfg.get("always_on_top")
        opacity_changed = new_cfg["bar_opacity"] != self.cfg.get("bar_opacity")
        self.cfg.update(new_cfg)
        save_cfg(self.cfg)
        self.mode_combo.setCurrentText(self.cfg["hotkey_mode"])
        self.preview_check.setChecked(bool(self.cfg["preview_before_paste"]))
        self.clean_check.setChecked(bool(self.cfg["llm_enabled"]))
        if model_changed:
            self.transcriber = self._build_transcriber()
            threading.Thread(target=self._warmup, daemon=True).start()
        if hotkey_changed:
            try:
                self._start_hotkey()
            except Exception as e:
                QMessageBox.warning(self, "Hotkey", f"Failed to bind hotkey: {e}")
        if tts_changed:
            self._rebuild_tts()
        if viz_changed:
            self._rebuild_visualizer()
        if flags_changed:
            self._rebuild_window_flags()
        if opacity_changed:
            self.setWindowOpacity(self.cfg["bar_opacity"])

    def _rebuild_visualizer(self):
        # Remove old meter from layout, add new
        if self.meter is not None:
            self.meter.setParent(None)
        self._build_visualizer()
        if self.meter is not None:
            row_layout = self.layout().itemAt(0).layout()
            # Insert before rec_btn
            row_layout.insertWidget(row_layout.indexOf(self.rec_btn), self.meter)

    def _rebuild_window_flags(self):
        was_visible = self.isVisible()
        flags = Qt.FramelessWindowHint | Qt.Tool
        if self.cfg.get("always_on_top", True):
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        if was_visible:
            self.show()

    # ---- Frameless drag -----------------------------------------------

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            e.accept()

    def mouseMoveEvent(self, e):
        if self._drag_pos and (e.buttons() & Qt.LeftButton):
            self.move(e.globalPosition().toPoint() - self._drag_pos)
            e.accept()

    def mouseReleaseEvent(self, e):
        self._drag_pos = None
        e.accept()


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor("#1e1f22"))
    pal.setColor(QPalette.WindowText, QColor("#e6e6e6"))
    pal.setColor(QPalette.Base, QColor("#2a2c30"))
    pal.setColor(QPalette.Text, QColor("#e6e6e6"))
    pal.setColor(QPalette.Button, QColor("#2a2c30"))
    pal.setColor(QPalette.ButtonText, QColor("#e6e6e6"))
    pal.setColor(QPalette.Highlight, QColor("#3a8dde"))
    app.setPalette(pal)

    bar = MiniBar()
    screen = app.primaryScreen().availableGeometry()
    bar.adjustSize()
    bar.move(screen.right() - bar.width() - 20, screen.bottom() - bar.height() - 20)
    bar.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
