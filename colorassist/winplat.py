# Copyright (C) 2026 EQQX0
# SPDX-License-Identifier: GPL-3.0-or-later
"""Windows-only helpers via ctypes. Every function is a safe no-op elsewhere.

All rectangles here are physical screen pixels (x, y, w, h), the same space mss captures in.
"""
import ctypes
import os
import sys

IS_WIN = sys.platform == "win32"

if IS_WIN:
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int, wintypes.UINT]
    user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
    user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetWindow.restype = wintypes.HWND
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                    ctypes.POINTER(wintypes.DWORD)]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    try:
        dwmapi = ctypes.WinDLL("dwmapi")
        dwmapi.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    except OSError:
        dwmapi = None
    _ENUM_PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

WDA_EXCLUDEFROMCAPTURE = 0x11
HWND_TOPMOST = -1
SWP_NOACTIVATE, SWP_SHOWWINDOW = 0x0010, 0x0040
WM_HOTKEY = 0x0312
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000

OWN_TITLE = "MineColorTrack"


def exclude_from_capture(hwnd):
    """Hide our overlay from screen capture so we never re-detect our own drawings.

    Needs Windows 10 version 2004 or newer. Returns False if it could not be applied.
    """
    if not IS_WIN:
        return False
    return bool(user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE))


def place_window(widget, rect):
    """Move/resize a Qt window to a physical-pixel rect (avoids Qt's DPI scaling maths)."""
    x, y, w, h = (int(v) for v in rect)
    if IS_WIN:
        user32.SetWindowPos(int(widget.winId()), HWND_TOPMOST, x, y, w, h,
                            SWP_NOACTIVATE | SWP_SHOWWINDOW)
    else:
        widget.setGeometry(x, y, w, h)


def _title(hwnd):
    n = user32.GetWindowTextLengthW(hwnd)
    if n <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def _exe(hwnd):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    handle = kernel32.OpenProcess(0x1000, False, pid.value)   # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(1024)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return os.path.basename(buf.value)
        return ""
    finally:
        kernel32.CloseHandle(handle)


def _cloaked(hwnd):
    """Hidden 'cloaked' windows (background Store apps, other virtual desktops) are not really on screen."""
    if dwmapi is None:
        return False
    val = ctypes.c_int(0)
    if dwmapi.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(val), ctypes.sizeof(val)) != 0:
        return False
    return val.value != 0


def list_windows():
    """Open windows a person would recognise: [{'hwnd', 'title', 'exe', 'minimised'}], top-most first."""
    if not IS_WIN:
        return []
    out = []

    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd) or user32.GetWindow(hwnd, 4):      # 4 = GW_OWNER (popups)
            return True
        if user32.GetWindowLongW(hwnd, -20) & 0x80:                            # WS_EX_TOOLWINDOW
            return True
        title = _title(hwnd)
        if not title or OWN_TITLE in title or _cloaked(hwnd):
            return True
        exe = _exe(hwnd)
        if exe.lower() == "explorer.exe" and title == "Program Manager":       # the desktop itself
            return True
        minimised = bool(user32.IsIconic(hwnd))
        rc = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rc))
        if not minimised and (rc.right - rc.left < 120 or rc.bottom - rc.top < 80):
            return True
        out.append({"hwnd": hwnd, "title": title, "exe": exe, "minimised": minimised})
        return True

    user32.EnumWindows(_ENUM_PROC(cb), 0)
    return out


def _client_rect(hwnd):
    rc = wintypes.RECT()
    pt = wintypes.POINT(0, 0)
    if not user32.GetClientRect(hwnd, ctypes.byref(rc)) or not user32.ClientToScreen(hwnd, ctypes.byref(pt)):
        return None
    if rc.right < 32 or rc.bottom < 32:
        return None
    return (pt.x, pt.y, rc.right, rc.bottom)


def find_window(title_part, exe=""):
    """Client area of the chosen window.

    Best match: same program and title containing `title_part`; then title alone; then program alone
    (titles often change, e.g. when a game shows its version or the current level).
    """
    if not IS_WIN or not (title_part.strip() or exe.strip()):
        return None
    needle, exe_l = title_part.strip().lower(), exe.strip().lower()
    wins = [w for w in list_windows() if not w["minimised"]]
    for rule in (lambda w: exe_l and w["exe"].lower() == exe_l and needle in w["title"].lower(),
                 lambda w: needle and needle in w["title"].lower(),
                 lambda w: exe_l and w["exe"].lower() == exe_l):
        for w in wins:
            if rule(w):
                rect = _client_rect(w["hwnd"])
                if rect:
                    return rect
    return None


_VK_NAMED = {"SPACE": 0x20, "PAGEUP": 0x21, "PAGEDOWN": 0x22, "END": 0x23, "HOME": 0x24,
             "INSERT": 0x2D, "DELETE": 0x2E, "PAUSE": 0x13, "SCROLLLOCK": 0x91}


def parse_hotkey(text):
    """'Ctrl+Alt+M' -> (modifiers, virtual key) or None."""
    mods, vk = 0, None
    for part in [p.strip().upper() for p in text.split("+") if p.strip()]:
        if part in ("CTRL", "CONTROL"):
            mods |= MOD_CONTROL
        elif part == "ALT":
            mods |= MOD_ALT
        elif part == "SHIFT":
            mods |= MOD_SHIFT
        elif part == "WIN":
            mods |= MOD_WIN
        elif len(part) == 1 and part.isalnum():
            vk = ord(part)
        elif part.startswith("NUM") and part[3:].isdigit() and len(part) == 4:
            vk = 0x60 + int(part[3:])
        elif part.startswith("F") and part[1:].isdigit() and 1 <= int(part[1:]) <= 24:
            vk = 0x6F + int(part[1:])
        elif part in _VK_NAMED:
            vk = _VK_NAMED[part]
        else:
            return None
    return (mods, vk) if vk is not None else None


def register_hotkey(hwnd, hotkey_id, text):
    """Returns True on success. False if unparsable, taken by another app, or not on Windows."""
    if not IS_WIN:
        return False
    parsed = parse_hotkey(text)
    if not parsed:
        return False
    return bool(user32.RegisterHotKey(hwnd, hotkey_id, parsed[0] | MOD_NOREPEAT, parsed[1]))


def unregister_hotkey(hwnd, hotkey_id):
    if IS_WIN:
        user32.UnregisterHotKey(hwnd, hotkey_id)


def hotkey_id_from_msg(message_ptr):
    """If a native MSG is WM_HOTKEY, return its id, else None."""
    if not IS_WIN:
        return None
    msg = wintypes.MSG.from_address(int(message_ptr))
    return int(msg.wParam) if msg.message == WM_HOTKEY else None


def set_app_id(app_id):
    """Give the process its own taskbar identity so Windows shows our icon, not Python's."""
    if IS_WIN:
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        except (AttributeError, OSError):
            pass


_mutex = None


def hold_running_mutex(name="MineColorTrackRunning"):
    """Named mutex the installer/uninstaller checks (Inno Setup AppMutex) to ask you to close the app first."""
    global _mutex
    if IS_WIN and _mutex is None:
        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        _mutex = kernel32.CreateMutexW(None, False, name)


def release_running_mutex():
    """Let the installer run without asking to close us (used just before an update quits the app)."""
    global _mutex
    if IS_WIN and _mutex:
        kernel32.CloseHandle(_mutex)
        _mutex = None
