"""Global hotkeys: toggle, PTT, cancel - all on one listener."""
from pynput import keyboard


class ToggleHotkey:
    """Single combo, single-fire."""
    def __init__(self, combo, on_press):
        self.combo = combo
        self.on_press = on_press
        self.listener = None

    def start(self):
        self.listener = keyboard.GlobalHotKeys({self.combo: self.on_press})
        self.listener.daemon = True
        self.listener.start()

    def stop(self):
        if self.listener is not None:
            try:
                self.listener.stop()
            except Exception:
                pass
            self.listener = None


class MultiHotkey:
    """Primary (toggle or PTT) + optional cancel combo on one Listener.

    For 'ptt': on_press when primary becomes fully held, on_release when any drops.
    For 'toggle': on_press fires once per activation; on_release unused.
    Cancel: single-fire when its combo becomes fully held.
    """
    def __init__(self, primary_combo, primary_mode, on_press, on_release,
                 cancel_combo=None, on_cancel=None):
        self.primary_combo = primary_combo
        self.primary_mode = primary_mode
        self.cancel_combo = cancel_combo
        self._on_press = on_press
        self._on_release = on_release
        self._on_cancel = on_cancel

        self._primary_required = set(keyboard.HotKey.parse(primary_combo))
        self._cancel_required = (
            set(keyboard.HotKey.parse(cancel_combo)) if cancel_combo else set()
        )
        self._pressed = set()
        self._primary_active = False
        self._cancel_active = False
        self.listener = None

    def start(self):
        self.listener = keyboard.Listener(on_press=self._kp, on_release=self._kr)
        self.listener.daemon = True
        self.listener.start()

    def stop(self):
        if self.listener is not None:
            try:
                self.listener.stop()
            except Exception:
                pass
            self.listener = None
        self._pressed.clear()
        self._primary_active = False
        self._cancel_active = False

    def _canon(self, key):
        try:
            return self.listener.canonical(key)
        except Exception:
            return key

    def _kp(self, key):
        k = self._canon(key)
        self._pressed.add(k)
        if self._cancel_required and not self._cancel_active and \
                self._pressed >= self._cancel_required:
            self._cancel_active = True
            try:
                if self._on_cancel:
                    self._on_cancel()
            except Exception:
                pass
        if k in self._primary_required and not self._primary_active and \
                self._pressed >= self._primary_required:
            self._primary_active = True
            try:
                if self._on_press:
                    self._on_press()
            except Exception:
                pass

    def _kr(self, key):
        k = self._canon(key)
        self._pressed.discard(k)
        if self._cancel_active and not (self._pressed >= self._cancel_required):
            self._cancel_active = False
        if k in self._primary_required and self._primary_active:
            self._primary_active = False
            if self.primary_mode == "ptt":
                try:
                    if self._on_release:
                        self._on_release()
                except Exception:
                    pass


GlobalHotkey = ToggleHotkey
PTTHotkey = MultiHotkey
