"""Transcript history. JSONL on disk, viewer dialog with re-send / copy / TTS."""
import json
import time
from pathlib import Path
from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QPushButton,
    QLabel, QTextEdit, QSplitter, QWidget, QApplication,
)


HISTORY_PATH = Path.home() / ".whispertyper" / "history.jsonl"
MAX_ENTRIES = 500


class HistoryStore:
    def __init__(self, path=HISTORY_PATH, cap=MAX_ENTRIES):
        self.path = Path(path)
        self.cap = cap
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._entries = self._load()

    def _load(self):
        if not self.path.exists():
            return []
        out = []
        try:
            for line in self.path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
        except Exception:
            pass
        return out[-self.cap:]

    def _save(self):
        try:
            self.path.write_text(
                "\n".join(json.dumps(e, ensure_ascii=False) for e in self._entries) + "\n",
                encoding="utf-8",
            )
        except Exception:
            pass

    def add(self, text, target_exe=None, target_title=None, stats=None, sent=False,
            press_enter=False, cleaned=None):
        entry = {
            "ts": time.time(),
            "text": text,
            "cleaned": cleaned,
            "target_exe": target_exe,
            "target_title": target_title,
            "stats": stats or {},
            "sent": bool(sent),
            "press_enter": bool(press_enter),
        }
        self._entries.append(entry)
        if len(self._entries) > self.cap:
            self._entries = self._entries[-self.cap:]
        self._save()

    def all(self):
        return list(self._entries)

    def clear(self):
        self._entries = []
        self._save()


class HistoryDialog(QDialog):
    resend_requested = Signal(str, bool)  # text, press_enter
    speak_requested = Signal(str)

    def __init__(self, store: HistoryStore, parent=None):
        super().__init__(parent)
        self.setWindowTitle("WhisperTyper History")
        self.setMinimumSize(720, 460)
        self.store = store

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(6)

        header = QHBoxLayout()
        header.addWidget(QLabel(f"<b>History</b> ({len(store.all())} entries)"))
        header.addStretch(1)
        self.clear_btn = QPushButton("Clear all")
        self.clear_btn.clicked.connect(self._clear)
        header.addWidget(self.clear_btn)
        outer.addLayout(header)

        split = QSplitter(Qt.Horizontal)
        outer.addWidget(split, 1)

        self.list_w = QListWidget()
        self.list_w.itemSelectionChanged.connect(self._on_select)
        split.addWidget(self.list_w)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        self.detail = QTextEdit()
        self.detail.setReadOnly(False)
        rl.addWidget(self.detail, 1)

        self.meta_lbl = QLabel("")
        self.meta_lbl.setStyleSheet("color:#9aa0a6;")
        rl.addWidget(self.meta_lbl)

        btns = QHBoxLayout()
        self.copy_btn = QPushButton("Copy")
        self.copy_btn.clicked.connect(self._copy)
        self.speak_btn = QPushButton("Speak")
        self.speak_btn.clicked.connect(self._speak)
        self.send_btn = QPushButton("Re-send to current target")
        self.send_btn.clicked.connect(self._resend)
        self.send_btn.setStyleSheet(
            "background:#2d6cdf; color:white; border:1px solid #1f55b8;"
            " border-radius:6px; padding:6px 12px; font-weight:600;"
        )
        btns.addWidget(self.copy_btn)
        btns.addWidget(self.speak_btn)
        btns.addStretch(1)
        btns.addWidget(self.send_btn)
        rl.addLayout(btns)

        split.addWidget(right)
        split.setSizes([280, 440])

        self.setStyleSheet("""
            QDialog { background:#1e1f22; color:#e6e6e6;
                      font-family:'Segoe UI',sans-serif; font-size:12px; }
            QListWidget, QTextEdit { background:#15161a; border:1px solid #2a2c30;
                                     border-radius:6px; color:#e6e6e6; }
            QListWidget::item:selected { background:#2d6cdf; }
            QPushButton { background:#2a2c30; border:1px solid #3a3d42;
                          border-radius:6px; padding:6px 12px; color:#e6e6e6; }
            QPushButton:hover { background:#34373c; }
        """)

        QShortcut(QKeySequence("Escape"), self, self.close)
        self._populate()

    def _populate(self):
        self.list_w.clear()
        for entry in reversed(self.store.all()):
            ts = datetime.fromtimestamp(entry["ts"]).strftime("%m-%d %H:%M")
            text = entry.get("cleaned") or entry.get("text") or ""
            preview = text[:50] + ("..." if len(text) > 50 else "")
            tgt = entry.get("target_exe") or "?"
            sent_marker = "" if entry.get("sent") else "[draft] "
            item = QListWidgetItem(f"{ts}  [{tgt}]  {sent_marker}{preview}")
            item.setData(Qt.UserRole, entry)
            self.list_w.addItem(item)
        if self.list_w.count() > 0:
            self.list_w.setCurrentRow(0)

    def _on_select(self):
        item = self.list_w.currentItem()
        if not item:
            self.detail.clear()
            self.meta_lbl.clear()
            return
        entry = item.data(Qt.UserRole)
        text = entry.get("cleaned") or entry.get("text") or ""
        self.detail.setPlainText(text)
        stats = entry.get("stats") or {}
        meta = (
            f"Target: {entry.get('target_title') or '?'} [{entry.get('target_exe') or '?'}] | "
            f"Sent: {entry.get('sent')} | Enter: {entry.get('press_enter')} | "
            f"Duration: {stats.get('duration_s', 0):.1f}s | "
            f"Peak: {stats.get('peak', 0):.2f}"
        )
        if entry.get("cleaned") and entry.get("cleaned") != entry.get("text"):
            meta += f"\nRaw: {entry.get('text')[:120]}"
        self.meta_lbl.setText(meta)

    def _copy(self):
        QApplication.clipboard().setText(self.detail.toPlainText())

    def _speak(self):
        self.speak_requested.emit(self.detail.toPlainText())

    def _resend(self):
        item = self.list_w.currentItem()
        if not item:
            return
        entry = item.data(Qt.UserRole)
        text = self.detail.toPlainText().strip()
        if not text:
            return
        self.resend_requested.emit(text, bool(entry.get("press_enter")))

    def _clear(self):
        self.store.clear()
        self._populate()
