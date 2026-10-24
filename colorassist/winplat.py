"""Windows-only helpers via ctypes. Every function is a safe no-op elsewhere.

All rectangles here are physical screen pixels (x, y, w, h), the same space mss captures in.
"""
import ctypes
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
    _ENUM_PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

WDA_EXCLUDEFROMCAPTURE = 0x11
HWND_TOPMOST = -1
SWP_NOACTIVATE, SWP_SHOWWINDOW = 0x0010, 0x0040
WM_HOTKEY = 0x0312
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000

OWN_TITLE = "ColorAssist"


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


def find_window(title_part):
    """Client area of the first visible window whose title contains `title_part`."""
    if not IS_WIN or not title_part.strip():
        return None
    needle = title_part.lower()
    found = []

    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        if n <= 0:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        title = buf.value
        if needle in title.lower() and OWN_TITLE not in title:
            found.append(hwnd)
            return False
        return True

    user32.EnumWindows(_ENUM_PROC(cb), 0)
    if not found:
        return None
    rc = wintypes.RECT()
    pt = wintypes.POINT(0, 0)
    if not user32.GetClientRect(found[0], ctypes.byref(rc)) or not user32.ClientToScreen(found[0], ctypes.byref(pt)):
        return None
    if rc.right < 32 or rc.bottom < 32:
        return None
    return (pt.x, pt.y, rc.right, rc.bottom)


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
