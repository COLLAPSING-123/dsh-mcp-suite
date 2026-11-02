"""Self-test: the confirmation dialog appears, is answered Yes, and returns True.

A background thread finds the dialog by title and posts IDYES, so the test never
needs a human. It flashes a window for a fraction of a second.
"""

import ctypes
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent import mcp_server  # noqa: E402

TITLE = "DSH 桌面动作 — 自检"
WM_COMMAND = 0x0111
IDYES = 6

user32 = ctypes.windll.user32
user32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
user32.FindWindowW.restype = ctypes.c_void_p
user32.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_void_p]
user32.SendMessageW.restype = ctypes.c_void_p


def closer() -> None:
    for _ in range(100):
        hwnd = user32.FindWindowW(None, TITLE)
        if hwnd:
            user32.SendMessageW(hwnd, WM_COMMAND, IDYES, None)
            return
        time.sleep(0.1)
    print("dialog-not-found")


thread = threading.Thread(target=closer, daemon=True)
thread.start()
started = time.time()
allowed = mcp_server._confirm("自检", "这是自动关闭的测试对话框")
print(f"confirm returned {allowed} after {time.time() - started:.2f}s")
raise SystemExit(0 if allowed else 1)
