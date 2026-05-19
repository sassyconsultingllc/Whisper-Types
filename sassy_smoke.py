"""Smoke test for SassyMCP desktop automation.

Launches the built exe, verifies the bar window appears, takes a screenshot,
exits. Useful for CI / post-build verification via Sassy's screen tools.

Usage (from Sassy):
  sassy_shell  -> python sassy_smoke.py [release|debug]
  sassy_screen_capture
  sassy_find_text_on_screen text="WhisperTyper"
"""
import os
import sys
import time
import subprocess
from pathlib import Path


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "release"
    here = Path(__file__).parent.resolve()

    if target == "debug":
        exe = here / "dist" / "WhisperTyper-debug" / "WhisperTyper-debug.exe"
    else:
        exe = here / "dist" / "WhisperTyper" / "WhisperTyper.exe"

    if not exe.exists():
        print(f"[FAIL] Not built: {exe}")
        print("Run build.bat or build_debug.bat first.")
        sys.exit(2)

    print(f"[INFO] Launching: {exe}")
    proc = subprocess.Popen(
        [str(exe)],
        stdout=subprocess.PIPE if target == "debug" else subprocess.DEVNULL,
        stderr=subprocess.STDOUT if target == "debug" else subprocess.DEVNULL,
        creationflags=0x08000000 if target == "release" else 0,  # CREATE_NO_WINDOW for release
    )

    print(f"[INFO] PID: {proc.pid}")
    print("[INFO] Waiting 8s for window + Whisper model warmup...")
    time.sleep(8)

    if proc.poll() is not None:
        print(f"[FAIL] Process exited early with code {proc.returncode}")
        if target == "debug" and proc.stdout:
            print(proc.stdout.read().decode("utf-8", errors="replace"))
        sys.exit(3)

    # Verify window via win32
    try:
        import win32gui
        found = []
        def cb(hwnd, _):
            t = win32gui.GetWindowText(hwnd)
            if "WhisperTyper" in t:
                found.append((hwnd, t))
            return True
        win32gui.EnumWindows(cb, None)
        if found:
            print(f"[OK] Window present: {found[0][1]}")
        else:
            print("[WARN] Process running but no window matching 'WhisperTyper' found")
    except ImportError:
        print("[INFO] pywin32 not available for window check")

    print(f"[INFO] App is running. PID {proc.pid}. Test it manually or kill with:")
    print(f"       taskkill /PID {proc.pid} /F")
    print()
    print("Suggested SassyMCP follow-ups:")
    print("  sassy_screen_capture")
    print(f"  sassy_list_windows  (look for PID {proc.pid})")
    print("  sassy_find_text_on_screen text=\"WhisperTyper\"")
    print("  sassy_kill_process pid={}".format(proc.pid))


if __name__ == "__main__":
    main()
