"""Win32 primitives that PyAutoGUI doesn't provide.

Three problems this solves, each observed in comparable projects:

1. **Clipboard pollution** - `type_text` used to overwrite the user's clipboard
   and never restore it, and a failed clipboard write could paste whatever the
   user had copied. We now type with `SendInput`/`KEYEVENTF_UNICODE` so the
   clipboard is untouched at all; the paste path keeps a save/verify/restore
   only when explicitly requested.

2. **Black screenshots of GPU windows** - GDI screen captures return black for
   hardware-accelerated windows (games, Electron, media players). `PrintWindow`
   with `PW_RENDERFULLCONTENT` reads the window's own DWM surface instead.

3. **No window-level control** - only full-screen coordinates were available.
   `list_windows` / `focus_window` / `capture_window` let the model target one
   window instead of guessing where it sits on screen.
"""

from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

from PIL import Image

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32

# ---------------------------------------------------------------- constants
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
PW_RENDERFULLCONTENT = 0x00000002
SW_RESTORE = 9
CF_UNICODETEXT = 13


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("padding", ctypes.c_byte * 32)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


# ------------------------------------------------------------------ typing
def type_unicode(text: str, per_char_delay: float = 0.002) -> int:
    """Type `text` as Unicode key events. Leaves the clipboard untouched.

    Returns the number of UTF-16 code units sent. Surrogate pairs are split so
    emoji and CJK beyond the BMP work too.
    """
    sent = 0
    for char in text:
        code = ord(char)
        if code > 0xFFFF:
            code -= 0x10000
            units = [0xD800 + (code >> 10), 0xDC00 + (code & 0x3FF)]
        else:
            units = [code]
        for unit in units:
            for flags in (KEYEVENTF_UNICODE, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP):
                inp = INPUT(type=INPUT_KEYBOARD)
                inp.u.ki = KEYBDINPUT(0, unit, flags, 0, None)
                user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
                sent += 1
            time.sleep(per_char_delay)
    return sent


# --------------------------------------------------------------- clipboard
def clipboard_has_text() -> bool:
    return bool(user32.IsClipboardFormatAvailable(CF_UNICODETEXT))


def clipboard_get_text() -> str | None:
    """Return the clipboard text, or None when the clipboard holds non-text data."""
    if not clipboard_has_text():
        return None
    try:
        import pyperclip

        return pyperclip.paste()
    except Exception:  # noqa: BLE001
        return None


def clipboard_set_text(text: str) -> bool:
    try:
        import pyperclip

        pyperclip.copy(text)
        return pyperclip.paste() == text
    except Exception:  # noqa: BLE001
        return False


# ----------------------------------------------------------------- windows
def _window_title(hwnd) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def window_title(hwnd: int) -> str:
    return _window_title(hwnd)


def window_rect(hwnd: int) -> dict:
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return {
        "x": rect.left,
        "y": rect.top,
        "width": rect.right - rect.left,
        "height": rect.bottom - rect.top,
    }


def _is_cloaked(hwnd) -> bool:
    """UWP/UWP-hosted windows stay 'visible' but are cloaked when suspended."""
    cloaked = wintypes.DWORD(0)
    try:
        user32.DwmGetWindowAttribute(
            wintypes.HWND(hwnd), 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked)
        )
    except Exception:  # noqa: BLE001
        return False
    return cloaked.value != 0


def _window_class(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


# Shell windows that are technically visible but useless as targets.
# Do NOT add ApplicationFrameWindow here - that is the host class of every UWP
# app (Settings, Calculator, ...); filtering it would hide real applications.
SHELL_CLASSES = {
    "Progman",          # desktop
    "WorkerW",          # wallpaper host
    "Shell_TrayWnd",    # taskbar
}


def list_windows() -> list[dict]:
    """Visible top-level windows with a non-empty title, front-to-back order.

    Minimised windows are included but flagged: Windows parks them at
    (-32000, -32000) with a placeholder size, which is useless as a click
    target and would silently produce a tiny "screenshot". Shell/overlay
    windows (desktop, taskbar, input host) are skipped.
    """
    results: list[dict] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _enum(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        title = _window_title(hwnd)
        if not title:
            return True
        if _window_class(hwnd) in SHELL_CLASSES:
            return True
        if _is_cloaked(hwnd):
            return True
        minimized = bool(user32.IsIconic(hwnd))
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        results.append(
            {
                "hwnd": int(hwnd),
                "title": title,
                "minimized": minimized,
                "x": rect.left,
                "y": rect.top,
                "width": rect.right - rect.left,
                "height": rect.bottom - rect.top,
            }
        )
        return True

    user32.EnumWindows(_enum, 0)
    return results


def find_window(title_part: str) -> int | None:
    """First non-minimised window whose title contains `title_part`."""
    needle = title_part.strip().lower()
    if not needle:
        return None
    windows = list_windows()
    for win in windows:
        if not win["minimized"] and needle in win["title"].lower():
            return win["hwnd"]
    for win in windows:  # minimised still beats "not found"
        if needle in win["title"].lower():
            return win["hwnd"]
    return None


def focus_window(hwnd: int, allow_click: bool = False) -> bool:
    """Restore and raise a window, working around SetForegroundWindow's rules.

    Windows only lets the *current* foreground process change the foreground
    window. Three escalating tricks, cheapest first:
      1. attach to the foreground thread and call SetForegroundWindow
      2. tap ALT to release the foreground lock, then retry
      3. flip the window to topmost and back (forces a z-order change)
    """
    if not user32.IsWindow(hwnd):
        return False
    user32.ShowWindow(hwnd, SW_RESTORE)
    if user32.GetForegroundWindow() == hwnd:
        return True

    def _attach_and_set() -> bool:
        foreground = user32.GetForegroundWindow()
        fg_thread = user32.GetWindowThreadProcessId(foreground, None)
        my_thread = kernel32.GetCurrentThreadId()
        attached = False
        try:
            if fg_thread and fg_thread != my_thread:
                attached = bool(user32.AttachThreadInput(my_thread, fg_thread, True))
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
        finally:
            if attached:
                user32.AttachThreadInput(my_thread, fg_thread, False)
        return user32.GetForegroundWindow() == hwnd

    if _attach_and_set():
        return True

    # Release the foreground lock: a synthetic ALT keypress marks this process
    # as the last input source, which is what Windows checks.
    user32.keybd_event(0x12, 0, 0, 0)  # ALT down
    user32.keybd_event(0x12, 0, 2, 0)  # ALT up
    if _attach_and_set():
        return True

    HWND_TOPMOST = ctypes.c_void_p(-1)
    HWND_NOTOPMOST = ctypes.c_void_p(-2)
    SWP_NOSIZE_NOMOVE = 0x0001 | 0x0002
    user32.SetWindowPos(wintypes.HWND(hwnd), HWND_TOPMOST, 0, 0, 0, 0, SWP_NOSIZE_NOMOVE)
    user32.SetWindowPos(wintypes.HWND(hwnd), HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOSIZE_NOMOVE)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.15)
    if user32.GetForegroundWindow() == hwnd:
        return True

    # NOTE: SwitchToThisWindow() was tried here and removed: it "works" by
    # activating whatever alt-tab picks, which in practice was an invisible
    # window with no title - a focus change nobody asked for. Better to fail
    # loudly and let the caller decide.

    # Last resort (opt-in): a real click inside the window. Windows lets the
    # *user's* input change the foreground, so a synthetic click is the one move
    # that survives the foreground lock - but it also lands on whatever the
    # window has at that spot, so it must never be automatic.
    if allow_click:
        rect = window_rect(hwnd)
        if rect["width"] > 0 and rect["height"] > 0:
            px = rect["x"] + rect["width"] // 2
            py = rect["y"] + 10
            user32.SetCursorPos(int(px), int(py))
            user32.mouse_event(0x0002, 0, 0, 0, 0)  # LEFTDOWN
            user32.mouse_event(0x0004, 0, 0, 0, 0)  # LEFTUP
            time.sleep(0.25)
    return user32.GetForegroundWindow() == hwnd


# ----------------------------------------------------------------- capture
def _grab_window_bits(hwnd: int, width: int, height: int, full_content: bool):
    """Return a PIL image of the window's own surface, or None on failure."""
    hwnd_dc = user32.GetWindowDC(hwnd)
    if not hwnd_dc:
        return None
    mem_dc = gdi32.CreateCompatibleDC(hwnd_dc)
    bitmap = gdi32.CreateCompatibleBitmap(hwnd_dc, width, height)
    old = gdi32.SelectObject(mem_dc, bitmap)
    try:
        flags = PW_RENDERFULLCONTENT if full_content else 0
        ok = user32.PrintWindow(wintypes.HWND(hwnd), mem_dc, flags)
        if not ok:
            return None

        header = BITMAPINFOHEADER()
        header.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        header.biWidth = width
        header.biHeight = -height  # top-down
        header.biPlanes = 1
        header.biBitCount = 32
        header.biCompression = 0  # BI_RGB

        buffer = ctypes.create_string_buffer(width * height * 4)
        got = gdi32.GetDIBits(
            mem_dc, bitmap, 0, height, buffer, ctypes.byref(header), 0
        )
        if not got:
            return None
        return Image.frombuffer("RGB", (width, height), buffer, "raw", "BGRX", 0, 1)
    finally:
        gdi32.SelectObject(mem_dc, old)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(mem_dc)
        user32.ReleaseDC(hwnd, hwnd_dc)


def capture_window(hwnd: int) -> Image.Image:
    """Capture one window's own surface.

    PrintWindow handles most GPU-accelerated windows. When it comes back empty
    (DirectComposition / protected content), grabbing that screen rectangle is
    only safe if the window is actually in front - otherwise the crop would
    silently return whatever window covers it, which is a wrong answer dressed
    up as a right one. In that case we fail loudly instead.
    """
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    if user32.IsIconic(hwnd):
        raise ValueError("窗口已最小化，先调用 focus_window 还原再截图")
    width = rect.right - rect.left
    height = rect.bottom - rect.top
    if width <= 0 or height <= 0:
        raise ValueError("window has an empty rectangle (minimised?)")

    for full_content in (True, False):
        image = _grab_window_bits(hwnd, width, height, full_content)
        if image is not None and image.getbbox() is not None:
            return image

    if user32.GetForegroundWindow() == hwnd:
        from PIL import ImageGrab

        try:
            return ImageGrab.grab(
                bbox=(rect.left, rect.top, rect.right, rect.bottom), all_screens=True
            )
        except Exception:  # noqa: BLE001
            pass
        raise RuntimeError("PrintWindow 失败，且屏幕区域抓取也失败")

    raise RuntimeError(
        "这个窗口无法用 PrintWindow 读取（DirectComposition 或受保护内容），"
        "且它当前不在前台，按屏幕区域抓会截到压在上面的窗口。"
        "先 focus_window 把它切到前台再截图。"
    )
