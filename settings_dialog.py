"""Tabbed settings dialog. General, Audio/VAD, Hotkeys, LLM, TTS, Targets."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QTabWidget, QWidget,
    QComboBox, QLineEdit, QCheckBox, QSpinBox, QDoubleSpinBox, QPushButton,
    QDialogButtonBox, QLabel, QListWidget, QListWidgetItem, QMessageBox,
    QTextEdit, QFileDialog,
)

from tts import KOKORO_VOICES, OPENAI_VOICES
from llm import DEFAULT_SYSTEM_PROMPT


WHISPER_MODELS = [
    "tiny.en", "tiny", "base.en", "base", "small.en", "small",
    "medium.en", "medium", "large-v3",
    "distil-small.en", "distil-medium.en", "distil-large-v3",
]


class SettingsDialog(QDialog):
    def __init__(self, cfg, target_prefs, parent=None):
        super().__init__(parent)
        self.setWindowTitle("WhisperTyper Settings")
        self.setMinimumSize(640, 540)
        self.cfg = dict(cfg)
        self.target_prefs = target_prefs

        outer = QVBoxLayout(self)
        self.tabs = QTabWidget()
        outer.addWidget(self.tabs, 1)

        self._build_general()
        self._build_audio()
        self._build_hotkeys()
        self._build_visual()
        self._build_llm()
        self._build_tts()
        self._build_targets()

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        outer.addWidget(bb)

        self.setStyleSheet("""
            QDialog, QWidget { background:#1e1f22; color:#e6e6e6;
                               font-family:'Segoe UI',sans-serif; font-size:12px; }
            QTabWidget::pane { border:1px solid #3a3d42; border-radius:6px; padding:8px; }
            QTabBar::tab { background:#2a2c30; padding:6px 14px; margin-right:2px;
                           border:1px solid #3a3d42; border-bottom:none;
                           border-top-left-radius:6px; border-top-right-radius:6px; }
            QTabBar::tab:selected { background:#3a8dde; color:white; }
            QComboBox, QPushButton, QCheckBox, QLineEdit, QSpinBox, QDoubleSpinBox,
            QTextEdit, QListWidget {
                background:#2a2c30; border:1px solid #3a3d42;
                border-radius:6px; padding:4px 8px; color:#e6e6e6;
            }
            QPushButton:hover { background:#34373c; }
            QLabel { color:#e6e6e6; }
        """)

    def _build_general(self):
        w = QWidget(); f = QFormLayout(w)
        self.model_combo = QComboBox()
        self.model_combo.addItems(WHISPER_MODELS)
        self.model_combo.setCurrentText(self.cfg.get("model_size", "base.en"))
        self.device_combo = QComboBox()
        self.device_combo.addItems(["auto", "cuda", "cpu"])
        self.device_combo.setCurrentText(self.cfg.get("device", "auto"))
        self.compute_combo = QComboBox()
        self.compute_combo.addItems(["auto", "float16", "int8_float16", "int8", "float32"])
        self.compute_combo.setCurrentText(self.cfg.get("compute_type", "auto"))
        self.lang_edit = QLineEdit(self.cfg.get("language") or "")
        self.lang_edit.setPlaceholderText("blank = auto-detect; e.g. en, es")
        self.beam_spin = QSpinBox()
        self.beam_spin.setRange(1, 10)
        self.beam_spin.setValue(int(self.cfg.get("beam_size", 1)))
        self.preview_check = QCheckBox("Preview transcript before pasting")
        self.preview_check.setChecked(bool(self.cfg.get("preview_before_paste", True)))
        self.preview_auto = QSpinBox()
        self.preview_auto.setRange(0, 60000)
        self.preview_auto.setSingleStep(500)
        self.preview_auto.setSuffix(" ms (0 = manual)")
        self.preview_auto.setValue(int(self.cfg.get("preview_autosend_ms", 0)))
        self.history_check = QCheckBox("Save transcripts to history")
        self.history_check.setChecked(bool(self.cfg.get("save_history", True)))
        self.enter_apps_edit = QLineEdit(",".join(self.cfg.get("press_enter_apps", [])))
        self.enter_apps_edit.setPlaceholderText("slack,discord,teams,...")
        self.trim_period_check = QCheckBox("Trim trailing period when sending with Enter")
        self.trim_period_check.setChecked(bool(self.cfg.get("trim_trailing_period_for_enter", True)))

        f.addRow("Whisper model:", self.model_combo)
        f.addRow("Device:", self.device_combo)
        f.addRow("Compute type:", self.compute_combo)
        f.addRow("Language:", self.lang_edit)
        f.addRow("Beam size:", self.beam_spin)
        f.addRow(self.preview_check)
        f.addRow("Preview auto-send:", self.preview_auto)
        f.addRow(self.history_check)
        f.addRow("Auto-Enter apps:", self.enter_apps_edit)
        f.addRow(self.trim_period_check)
        self.tabs.addTab(w, "General")

    def _build_audio(self):
        w = QWidget(); f = QFormLayout(w)
        self.vad_check = QCheckBox("Auto-stop on silence (toggle mode)")
        self.vad_check.setChecked(bool(self.cfg.get("vad_autostop", True)))
        self.vad_ms = QSpinBox()
        self.vad_ms.setRange(200, 8000)
        self.vad_ms.setSingleStep(100)
        self.vad_ms.setSuffix(" ms")
        self.vad_ms.setValue(int(self.cfg.get("vad_silence_ms", 1200)))
        self.vad_margin = QDoubleSpinBox()
        self.vad_margin.setRange(1.1, 10.0)
        self.vad_margin.setSingleStep(0.1)
        self.vad_margin.setValue(float(self.cfg.get("vad_margin", 2.5)))
        self.vad_margin.setToolTip("Higher = louder speech needed to count as voiced")
        self.vad_max = QSpinBox()
        self.vad_max.setRange(2000, 600000)
        self.vad_max.setSingleStep(1000)
        self.vad_max.setSuffix(" ms")
        self.vad_max.setValue(int(self.cfg.get("vad_max_record_ms", 30000)))
        self.min_audio_peak = QDoubleSpinBox()
        self.min_audio_peak.setRange(0.0, 0.5)
        self.min_audio_peak.setSingleStep(0.001)
        self.min_audio_peak.setDecimals(3)
        self.min_audio_peak.setValue(float(self.cfg.get("min_audio_peak", 0.005)))
        self.min_audio_peak.setToolTip("Skip transcription if peak below this (mic muted check)")
        self.interim_check = QCheckBox("Live interim transcripts (streaming)")
        self.interim_check.setChecked(bool(self.cfg.get("interim_transcripts", False)))
        self.interim_ms = QSpinBox()
        self.interim_ms.setRange(500, 10000)
        self.interim_ms.setSingleStep(500)
        self.interim_ms.setSuffix(" ms")
        self.interim_ms.setValue(int(self.cfg.get("interim_interval_ms", 2000)))

        f.addRow(self.vad_check)
        f.addRow("Silence to auto-stop:", self.vad_ms)
        f.addRow("VAD sensitivity (margin):", self.vad_margin)
        f.addRow("Max record duration:", self.vad_max)
        f.addRow("Min audio peak threshold:", self.min_audio_peak)
        f.addRow(self.interim_check)
        f.addRow("Interim interval:", self.interim_ms)
        self.tabs.addTab(w, "Audio / VAD")

    def _build_hotkeys(self):
        w = QWidget(); f = QFormLayout(w)
        self.hotkey_edit = QLineEdit(self.cfg.get("hotkey", "<ctrl>+<alt>+<space>"))
        self.hotkey_edit.setPlaceholderText("<ctrl>+<alt>+<space>")
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["toggle", "ptt"])
        self.mode_combo.setCurrentText(self.cfg.get("hotkey_mode", "toggle"))
        self.cancel_hotkey_edit = QLineEdit(self.cfg.get("cancel_hotkey", "<ctrl>+<alt>+x"))
        self.cancel_hotkey_edit.setPlaceholderText("<ctrl>+<alt>+x (blank to disable)")

        help_lbl = QLabel(
            "<small>Format: combine modifiers with literal keys. Modifiers: "
            "&lt;ctrl&gt;, &lt;alt&gt;, &lt;shift&gt;, &lt;cmd&gt;. "
            "Special keys: &lt;space&gt;, &lt;f1&gt;-&lt;f12&gt;, &lt;esc&gt;, &lt;tab&gt;.<br>"
            "Examples: <code>&lt;ctrl&gt;+&lt;alt&gt;+&lt;space&gt;</code>, "
            "<code>&lt;ctrl&gt;+&lt;shift&gt;+r</code>, <code>&lt;f9&gt;</code></small>"
        )
        help_lbl.setWordWrap(True)

        f.addRow("Primary hotkey:", self.hotkey_edit)
        f.addRow("Mode:", self.mode_combo)
        f.addRow("Cancel hotkey:", self.cancel_hotkey_edit)
        f.addRow(help_lbl)
        self.tabs.addTab(w, "Hotkeys")

    def _build_visual(self):
        w = QWidget(); f = QFormLayout(w)
        self.viz_combo = QComboBox()
        self.viz_combo.addItems(["bars", "spectrogram", "off"])
        self.viz_combo.setCurrentText(self.cfg.get("visualizer", "bars"))
        self.bar_opacity = QDoubleSpinBox()
        self.bar_opacity.setRange(0.4, 1.0)
        self.bar_opacity.setSingleStep(0.05)
        self.bar_opacity.setValue(float(self.cfg.get("bar_opacity", 1.0)))
        self.always_on_top = QCheckBox("Always on top")
        self.always_on_top.setChecked(bool(self.cfg.get("always_on_top", True)))
        self.show_tray = QCheckBox("Show system tray icon")
        self.show_tray.setChecked(bool(self.cfg.get("show_tray", True)))

        f.addRow("Visualizer:", self.viz_combo)
        f.addRow("Bar opacity:", self.bar_opacity)
        f.addRow(self.always_on_top)
        f.addRow(self.show_tray)
        self.tabs.addTab(w, "Visual")

    def _build_llm(self):
        w = QWidget(); f = QFormLayout(w)
        self.llm_check = QCheckBox("Enable LLM cleanup of transcripts")
        self.llm_check.setChecked(bool(self.cfg.get("llm_enabled", False)))
        self.llm_url = QLineEdit(self.cfg.get("llm_base_url", "http://100.99.213.97:11434/v1"))
        self.llm_url.setPlaceholderText("http://localhost:11434/v1 (Ollama) or other")
        self.llm_key = QLineEdit(self.cfg.get("llm_api_key", ""))
        self.llm_key.setEchoMode(QLineEdit.Password)
        self.llm_key.setPlaceholderText("blank for local Ollama")
        self.llm_model = QLineEdit(self.cfg.get("llm_model", "llama3.2:3b"))
        self.llm_model.setPlaceholderText("e.g. llama3.2:3b, qwen2.5:7b, gpt-4o-mini")
        self.llm_timeout = QSpinBox()
        self.llm_timeout.setRange(2, 120)
        self.llm_timeout.setSuffix(" s")
        self.llm_timeout.setValue(int(self.cfg.get("llm_timeout", 20)))
        self.llm_auto_use = QCheckBox("Default to cleaned version in preview")
        self.llm_auto_use.setChecked(bool(self.cfg.get("llm_default_cleaned", True)))
        self.llm_prompt = QTextEdit(self.cfg.get("llm_system_prompt", DEFAULT_SYSTEM_PROMPT))
        self.llm_prompt.setMaximumHeight(120)

        self.llm_test_btn = QPushButton("Test connection")
        self.llm_test_btn.clicked.connect(self._test_llm)
        self.llm_test_lbl = QLabel("")

        f.addRow(self.llm_check)
        f.addRow("Base URL:", self.llm_url)
        f.addRow("API key:", self.llm_key)
        f.addRow("Model:", self.llm_model)
        f.addRow("Timeout:", self.llm_timeout)
        f.addRow(self.llm_auto_use)
        f.addRow("System prompt:", self.llm_prompt)
        test_row = QHBoxLayout()
        test_row.addWidget(self.llm_test_btn)
        test_row.addWidget(self.llm_test_lbl, 1)
        cont = QWidget(); cont.setLayout(test_row)
        f.addRow(cont)
        self.tabs.addTab(w, "LLM Cleanup")

    def _test_llm(self):
        from llm import LLMClient
        try:
            c = LLMClient(
                base_url=self.llm_url.text().strip(),
                api_key=self.llm_key.text(),
                model=self.llm_model.text().strip(),
                timeout=5,
            )
            ok, msg = c.ping()
            color = "#5fd17a" if ok else "#ff6b6b"
            self.llm_test_lbl.setStyleSheet(f"color:{color};")
            self.llm_test_lbl.setText(msg[:200])
        except Exception as e:
            self.llm_test_lbl.setStyleSheet("color:#ff6b6b;")
            self.llm_test_lbl.setText(str(e)[:200])

    def _build_tts(self):
        w = QWidget(); f = QFormLayout(w)
        self.tts_check = QCheckBox("Enable text-to-speech (Speak button + read-back)")
        self.tts_check.setChecked(bool(self.cfg.get("tts_enabled", False)))
        self.tts_backend = QComboBox()
        self.tts_backend.addItems(["kokoro", "piper", "openai_compat"])
        self.tts_backend.setCurrentText(self.cfg.get("tts_backend", "kokoro"))
        self.tts_voice = QComboBox()
        self.tts_voice.setEditable(True)
        self._populate_voices()
        self.tts_backend.currentTextChanged.connect(self._populate_voices)
        self.tts_voice.setCurrentText(self.cfg.get("tts_voice", "af_sky"))
        self.tts_speed = QDoubleSpinBox()
        self.tts_speed.setRange(0.5, 2.0)
        self.tts_speed.setSingleStep(0.05)
        self.tts_speed.setValue(float(self.cfg.get("tts_speed", 1.0)))
        self.tts_lang = QLineEdit(self.cfg.get("tts_lang", "en-us"))
        self.tts_piper_model = QLineEdit(self.cfg.get("tts_piper_model", ""))
        self.tts_piper_model.setPlaceholderText("path to piper .onnx voice")
        self.tts_piper_browse = QPushButton("Browse...")
        self.tts_piper_browse.clicked.connect(self._browse_piper)
        self.tts_url = QLineEdit(self.cfg.get("tts_base_url", "http://127.0.0.1:8880/v1"))
        self.tts_key = QLineEdit(self.cfg.get("tts_api_key", ""))
        self.tts_key.setEchoMode(QLineEdit.Password)
        self.tts_model = QLineEdit(self.cfg.get("tts_model", "tts-1"))
        self.tts_autoread = QCheckBox("Auto-read transcripts (after Whisper finishes)")
        self.tts_autoread.setChecked(bool(self.cfg.get("tts_autoread", False)))
        self.tts_autoread.setToolTip("Speaks the transcript out loud before/instead of pasting")

        f.addRow(self.tts_check)
        f.addRow("Backend:", self.tts_backend)
        f.addRow("Voice:", self.tts_voice)
        f.addRow("Speed:", self.tts_speed)
        f.addRow("Language (kokoro):", self.tts_lang)
        piper_row = QHBoxLayout()
        piper_row.addWidget(self.tts_piper_model)
        piper_row.addWidget(self.tts_piper_browse)
        piper_cont = QWidget(); piper_cont.setLayout(piper_row)
        f.addRow("Piper model:", piper_cont)
        f.addRow("API base (openai_compat):", self.tts_url)
        f.addRow("API key:", self.tts_key)
        f.addRow("Model name:", self.tts_model)
        f.addRow(self.tts_autoread)

        note = QLabel(
            "<small>Kokoro: 82M params, Apache 2.0, ~330MB model auto-downloaded on "
            "first use. Excellent quality, runs on CPU. Voices like af_sky, am_adam, "
            "bf_emma. <br>Piper: tiny (~20MB voices), very fast, decent quality. "
            "Download voices from rhasspy/piper-voices.</small>"
        )
        note.setWordWrap(True)
        f.addRow(note)
        self.tabs.addTab(w, "TTS")

    def _populate_voices(self):
        cur = self.tts_voice.currentText() if hasattr(self, 'tts_voice') else ""
        self.tts_voice.clear()
        backend = self.tts_backend.currentText()
        if backend == "kokoro":
            self.tts_voice.addItems(KOKORO_VOICES)
        elif backend == "openai_compat":
            self.tts_voice.addItems(OPENAI_VOICES)
        else:
            self.tts_voice.addItem("(set via model file)")
        if cur:
            self.tts_voice.setCurrentText(cur)

    def _browse_piper(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Piper voice", "", "ONNX models (*.onnx);;All files (*)"
        )
        if path:
            self.tts_piper_model.setText(path)

    def _build_targets(self):
        w = QWidget(); v = QVBoxLayout(w)
        v.addWidget(QLabel("Per-application preferences. Removes an entry resets that app to defaults."))
        self.targets_list = QListWidget()
        self._reload_targets()
        v.addWidget(self.targets_list, 1)
        row = QHBoxLayout()
        rm = QPushButton("Remove selected")
        rm.clicked.connect(self._remove_target)
        clear = QPushButton("Clear all")
        clear.clicked.connect(self._clear_targets)
        row.addWidget(rm); row.addWidget(clear); row.addStretch(1)
        v.addLayout(row)
        self.tabs.addTab(w, "Targets")

    def _reload_targets(self):
        self.targets_list.clear()
        for exe, prefs in sorted(self.target_prefs.all().items()):
            label = f"{exe}  -  {prefs}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, exe)
            self.targets_list.addItem(item)

    def _remove_target(self):
        item = self.targets_list.currentItem()
        if not item:
            return
        exe = item.data(Qt.UserRole)
        self.target_prefs.remove(exe)
        self._reload_targets()

    def _clear_targets(self):
        if QMessageBox.question(self, "Clear", "Remove all per-app prefs?") != QMessageBox.Yes:
            return
        for exe in list(self.target_prefs.all().keys()):
            self.target_prefs.remove(exe)
        self._reload_targets()

    def values(self):
        lang = self.lang_edit.text().strip() or None
        apps = [a.strip().lower() for a in self.enter_apps_edit.text().split(",") if a.strip()]
        return {
            "model_size": self.model_combo.currentText(),
            "device": self.device_combo.currentText(),
            "compute_type": self.compute_combo.currentText(),
            "language": lang,
            "beam_size": self.beam_spin.value(),
            "hotkey": self.hotkey_edit.text().strip() or "<ctrl>+<alt>+<space>",
            "hotkey_mode": self.mode_combo.currentText(),
            "cancel_hotkey": self.cancel_hotkey_edit.text().strip(),
            "vad_autostop": self.vad_check.isChecked(),
            "vad_silence_ms": self.vad_ms.value(),
            "vad_margin": self.vad_margin.value(),
            "vad_max_record_ms": self.vad_max.value(),
            "min_audio_peak": self.min_audio_peak.value(),
            "interim_transcripts": self.interim_check.isChecked(),
            "interim_interval_ms": self.interim_ms.value(),
            "preview_before_paste": self.preview_check.isChecked(),
            "preview_autosend_ms": self.preview_auto.value(),
            "save_history": self.history_check.isChecked(),
            "press_enter_apps": apps,
            "trim_trailing_period_for_enter": self.trim_period_check.isChecked(),
            "visualizer": self.viz_combo.currentText(),
            "bar_opacity": self.bar_opacity.value(),
            "always_on_top": self.always_on_top.isChecked(),
            "show_tray": self.show_tray.isChecked(),
            "llm_enabled": self.llm_check.isChecked(),
            "llm_base_url": self.llm_url.text().strip(),
            "llm_api_key": self.llm_key.text(),
            "llm_model": self.llm_model.text().strip(),
            "llm_timeout": self.llm_timeout.value(),
            "llm_default_cleaned": self.llm_auto_use.isChecked(),
            "llm_system_prompt": self.llm_prompt.toPlainText(),
            "tts_enabled": self.tts_check.isChecked(),
            "tts_backend": self.tts_backend.currentText(),
            "tts_voice": self.tts_voice.currentText(),
            "tts_speed": self.tts_speed.value(),
            "tts_lang": self.tts_lang.text().strip() or "en-us",
            "tts_piper_model": self.tts_piper_model.text().strip(),
            "tts_base_url": self.tts_url.text().strip(),
            "tts_api_key": self.tts_key.text(),
            "tts_model": self.tts_model.text().strip(),
            "tts_autoread": self.tts_autoread.isChecked(),
        }
