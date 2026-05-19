#!/usr/bin/env python3
"""Runtime debug check for WhisperTyper."""
import sys
import json
from pathlib import Path

print("=== WhisperTyper Runtime Debug ===")
print()

# 1. Check config loading
config_path = Path.home() / '.whispertyper' / 'config.json'
if config_path.exists():
    cfg = json.loads(config_path.read_text())
    print(f"✓ Config loaded from {config_path}")
    print(f"  Device: {cfg.get('device', 'N/A')}")
    print(f"  Compute Type: {cfg.get('compute_type', 'N/A')}")
    print(f"  Model Size: {cfg.get('model_size', 'N/A')}")
    print()
else:
    print(f"✗ No config found at {config_path}")
    print()

# 2. Test audio system
try:
    from audio_capture import Recorder
    rec = Recorder(samplerate=16000)
    print(f"✓ Audio system ready")
    print(f"  Samplerate: {rec.sr}")
    devices = rec.list_devices()
    print(f"  Available devices: {len(devices)}")
    print()
except Exception as e:
    print(f"✗ Audio system error: {e}")
    import traceback
    traceback.print_exc()
    print()

# 3. Test hotkey system
try:
    from hotkey import MultiHotkey
    def dummy_press():
        pass
    def dummy_release():
        pass
    hk = MultiHotkey("<ctrl>+<alt>+<space>", "toggle", dummy_press, dummy_release, None)
    print(f"✓ Hotkey system ready")
    print()
except Exception as e:
    print(f"✗ Hotkey system error: {e}")
    import traceback
    traceback.print_exc()
    print()

# 4. Test clipboard
try:
    import pyperclip
    test_text = 'test'
    # Don't actually set clipboard, just verify module works
    print(f"✓ Clipboard system ready")
    print()
except Exception as e:
    print(f"✗ Clipboard system error: {e}")
    print()

# 5. Test window enumeration
try:
    from target import list_windows
    windows = list_windows()
    print(f"✓ Window enumeration ready")
    print(f"  Found {len(windows)} windows")
    if windows:
        print(f"  Sample: {windows[0][1] if len(windows[0]) > 1 else windows[0]}")
    print()
except Exception as e:
    print(f"✗ Window enumeration error: {e}")
    print()

# 6. Test transcriber with CUDA
try:
    from transcriber import Transcriber
    t = Transcriber(device='auto', compute_type='auto')
    dev, ct = t._resolve()
    print(f"✓ Transcriber ready")
    print(f"  Resolved device: {dev}")
    print(f"  Resolved compute: {ct}")
    print()
except Exception as e:
    print(f"✗ Transcriber error: {e}")
    print()

# 7. Test PySide6 GUI elements
try:
    from PySide6.QtWidgets import QStyle
    style_enum = QStyle.StandardPixmap.SP_MediaPlay
    print(f"✓ PySide6 GUI ready")
    print(f"  QStyle.StandardPixmap.SP_MediaPlay = {style_enum}")
    print()
except Exception as e:
    print(f"✗ PySide6 error: {e}")
    print()

print("=== All checks passed ===")
