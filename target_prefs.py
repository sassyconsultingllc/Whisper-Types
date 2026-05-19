"""Per-exe preferences. Remembers Enter/Preview/Cleanup defaults per target app."""
import json
from pathlib import Path


PREFS_PATH = Path.home() / ".whispertyper" / "target_prefs.json"


class TargetPrefs:
    def __init__(self, path=PREFS_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    def _load(self):
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save(self):
        try:
            self.path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        except Exception:
            pass

    @staticmethod
    def _key(exe):
        return (exe or "").lower().strip()

    def get(self, exe):
        """Returns dict of prefs or empty dict. Keys: press_enter, preview, llm_cleanup."""
        return dict(self._data.get(self._key(exe), {}))

    def set(self, exe, **kwargs):
        k = self._key(exe)
        if not k:
            return
        cur = self._data.get(k, {})
        for key, val in kwargs.items():
            if val is None:
                cur.pop(key, None)
            else:
                cur[key] = val
        if cur:
            self._data[k] = cur
        else:
            self._data.pop(k, None)
        self._save()

    def all(self):
        return dict(self._data)

    def remove(self, exe):
        self._data.pop(self._key(exe), None)
        self._save()
