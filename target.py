"""Enumerate top-level windows, focus them, locate text input via UIA, paste."""
import time
import ctypes
import threading

import win32gui
import win32con
import win32process
import win32api
import psutil
import pyperclip

user32 = ctypes.windll.user32


def list_windows():
    """Return [(hwnd, title, exe)] of visible windows with non-empty titles."""
    out = []

    def cb(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return True
        title = win32gui.GetWindowText(hwnd)
        if not title:
            return True
        # Skip cloaked windows (e.g. minimized UWP shells)
        cloaked = ctypes.c_int(0)
        try:
            ctypes.windll.dwmapi.DwmGetWindowAttribute(
                hwnd, 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked)
            )
            if cloaked.value:
                return True
        except Exception:
            pass
        exe = ""
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            try:
                exe = psutil.Process(pid).name()
            except Exception:
                exe = ""
        except Exception:
            pass
        out.append((hwnd, title, exe))
        return True

    win32gui.EnumWindows(cb, None)
    return out


def focus_window(hwnd):
    """Bring window to foreground; uses AttachThreadInput to defeat focus lock."""
    if not win32gui.IsWindow(hwnd):
        return False
    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

    fg = user32.GetForegroundWindow()
    if fg == hwnd:
        return True

    target_tid, _ = win32process.GetWindowThreadProcessId(hwnd)
    cur_tid = win32api.GetCurrentThreadId()
    attached = False
    try:
        if target_tid and target_tid != cur_tid:
            attached = bool(user32.AttachThreadInput(cur_tid, target_tid, True))
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(cur_tid, target_tid, False)

    # ALT-key trick if still not foreground (Windows focus lock)
    if user32.GetForegroundWindow() != hwnd:
        VK_MENU = 0x12
        user32.keybd_event(VK_MENU, 0, 0, 0)
        user32.keybd_event(VK_MENU, 0, 2, 0)
        user32.SetForegroundWindow(hwnd)

    time.sleep(0.08)
    return user32.GetForegroundWindow() == hwnd


def _find_text_input(hwnd, max_depth=8):
    """Walk UIA tree, return first focused/edit/document control. None if nothing."""
    try:
        import uiautomation as auto
    except Exception:
        return None
    try:
        # Prefer currently-focused control (works for most apps once foreground)
        try:
            focused = auto.GetFocusedControl()
            if focused and _is_text(focused):
                return focused
        except Exception:
            pass

        root = auto.ControlFromHandle(hwnd)
        if not root:
            return None
        for ctrl in _walk(root, max_depth):
            if _is_text(ctrl):
                return ctrl
    except Exception:
        return None
    return None


def _is_text(ctrl):
    try:
        name = ctrl.ControlTypeName
        if name in ("EditControl", "DocumentControl"):
            return True
    except Exception:
        pass
    return False


def _walk(ctrl, depth):
    if depth <= 0:
        return
    try:
        children = ctrl.GetChildren()
    except Exception:
        return
    for ch in children:
        yield ch
        yield from _walk(ch, depth - 1)


def _send_paste():
    VK_CONTROL = 0x11
    V = 0x56
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    user32.keybd_event(V, 0, 0, 0)
    user32.keybd_event(V, 0, 2, 0)
    user32.keybd_event(VK_CONTROL, 0, 2, 0)


def _send_enter():
    VK_RETURN = 0x0D
    user32.keybd_event(VK_RETURN, 0, 0, 0)
    user32.keybd_event(VK_RETURN, 0, 2, 0)


def inject_text(hwnd, text, press_enter=False, find_input=True):
    """Focus hwnd, set clipboard, Ctrl+V, optional Enter. Restores clipboard after."""
    if not text:
        return False

    try:
        prev_clip = pyperclip.paste()
    except Exception:
        prev_clip = None

    ok = False
    try:
        if not focus_window(hwnd):
            # Try anyway; some apps still receive keys
            pass
        time.sleep(0.05)

        if find_input:
            ctrl = _find_text_input(hwnd)
            if ctrl is not None:
                try:
                    ctrl.SetFocus()
                    time.sleep(0.03)
                except Exception:
                    pass

        pyperclip.copy(text)
        time.sleep(0.06)
        _send_paste()
        if press_enter:
            time.sleep(0.08)
            _send_enter()
        ok = True
    finally:
        def _restore():
            time.sleep(0.6)
            try:
                if prev_clip is not None:
                    pyperclip.copy(prev_clip)
            except Exception:
                pass
        threading.Thread(target=_restore, daemon=True).start()

    return ok
