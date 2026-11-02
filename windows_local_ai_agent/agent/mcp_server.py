"""Local MCP server that gives DSH desktop control on Windows (PyAutoGUI).

Run over stdio; DSH spawns it and exposes the tools as mcp__cua__*.

Why not the `mcp` SDK
---------------------
It pulls ~40 packages for three methods. `agent/mcpcore.py` speaks the same
newline-delimited JSON-RPC 2.0 in 250 lines with no dependencies.

Integrity level - the one thing that decides whether this works at all
------------------------------------------------------------------------
DSH runs every executable located *inside* the session workspace at Low
integrity; Windows then silently drops SetCursorPos/SendInput (returns 0, no
error). Launching the identical script with a python.exe **outside** the
workspace keeps the process at Medium, where input injection works. The
startup log records the level so this is never guessed again.

Coordinates
-----------
`screenshot` downsizes the capture to MAX_EDGE and records the scale factor.
Every coordinate the model sends is in *screenshot pixels* and is converted
back to real screen pixels before the action runs.

Confirmation
------------
CUA_CONFIRM=chat (default): no dialog; the model must state the exact action
in the conversation and wait for the user before calling a mutating tool.
CUA_CONFIRM=dialog: blocking MessageBox (unreliable at Low integrity).
"""

from __future__ import annotations

import ctypes
import io
import logging
import os
import subprocess
import time
from pathlib import Path

import pyautogui

try:  # run as `python -m agent.mcp_server`
    from . import mcpcore
except ImportError:  # run as a plain script
    import mcpcore  # type: ignore[no-redef]

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = PROJECT_ROOT / "logs" / "mcp-cua.log"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=str(LOG_PATH),
    level=logging.INFO,
    encoding="utf-8",
    format="%(asctime)s %(levelname)s %(message)s",
)

MAX_EDGE = 1600
CONFIRM_MODE = os.getenv("CUA_CONFIRM", "chat").strip().lower()
if CONFIRM_MODE not in {"chat", "dialog"}:
    CONFIRM_MODE = "chat"

STATE: dict = {"sx": 1.0, "sy": 1.0, "shot_w": 0, "shot_h": 0, "shots": 0}

ASK = "调用前必须先在对话里说明这次动作，并等用户明确同意。"

server = mcpcore.Server(
    "cua",
    "2.0.0",
    instructions=(
        "桌面控制服务。坐标一律使用最近一次 screenshot 返回图片的像素坐标，"
        "服务端会自动换算到真实屏幕。任何点击/输入/按键前都要先得到用户同意。"
    ),
)

MB_YESNO = 0x00000004
MB_ICONWARNING = 0x00000030
MB_TOPMOST = 0x00040000
MB_SETFOREGROUND = 0x00010000
IDYES = 6

_user32 = ctypes.windll.user32
_user32.MessageBoxW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
_user32.MessageBoxW.restype = ctypes.c_int


def integrity_level() -> str:
    """Report this process's integrity level (Low blocks input injection)."""
    try:
        out = subprocess.run(
            ["whoami", "/groups"], capture_output=True, text=True,
            encoding="gbk", errors="replace", timeout=10,
        ).stdout
        for line in out.splitlines():
            if "Mandatory Label" not in line:
                continue
            for word in line.replace("\\", " ").split():
                if word in {"Low", "Medium", "High", "System"}:
                    return word
    except Exception:  # noqa: BLE001
        pass
    return "unknown"


def _confirm(title: str, detail: str) -> bool:
    """Chat mode defers to the conversation; dialog mode blocks on a MessageBox."""
    if CONFIRM_MODE != "dialog":
        logging.info("confirm %s -> chat-mode (deferred to conversation): %s", title, detail)
        return True
    rc = _user32.MessageBoxW(
        0,
        f"{detail}\n\n允许执行吗？\n（点“否”或关闭对话框即拒绝）",
        f"DSH 桌面动作 — {title}",
        MB_YESNO | MB_ICONWARNING | MB_TOPMOST | MB_SETFOREGROUND,
    )
    allowed = rc == IDYES
    logging.info("confirm %s -> %s", title, "yes" if allowed else "no")
    return allowed


def _to_screen(x: int, y: int) -> tuple[int, int]:
    width, height = pyautogui.size()
    sx = STATE["sx"] or 1.0
    sy = STATE["sy"] or 1.0
    px = int(round(x * sx))
    py = int(round(y * sy))
    return max(0, min(width - 1, px)), max(0, min(height - 1, py))


def _deny(what: str) -> str:
    return f"用户拒绝或取消了：{what}。没有执行任何动作。"


# --------------------------------------------------------------------- tools
@server.tool("screen_size", "返回真实屏幕分辨率，以及最近一次截图使用的缩放比例。",
             {"type": "object", "properties": {}, "additionalProperties": False}, read_only=True)
def screen_size() -> dict:
    width, height = pyautogui.size()
    return {
        "screen_width": width,
        "screen_height": height,
        "last_screenshot_width": STATE["shot_w"],
        "last_screenshot_height": STATE["shot_h"],
        "scale_x": round(STATE["sx"], 4),
        "scale_y": round(STATE["sy"], 4),
    }


@server.tool(
    "screenshot",
    "截取当前整个 Windows 桌面，返回图片和尺寸信息。无需确认。"
    "图片已按最长边缩放到最多 1600 像素，后续坐标都用这张图的像素坐标。",
    {"type": "object", "properties": {}, "additionalProperties": False},
    read_only=True,
)
def screenshot():
    started = time.time()
    image = pyautogui.screenshot()
    width, height = image.size
    scale = min(1.0, MAX_EDGE / max(width, height))
    if scale < 1.0:
        image = image.resize((int(width * scale), int(height * scale)))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)

    STATE.update(
        sx=width / image.width,
        sy=height / image.height,
        shot_w=image.width,
        shot_h=image.height,
        shots=STATE["shots"] + 1,
    )
    logging.info("screenshot %sx%s -> %sx%s in %.2fs",
                 width, height, image.width, image.height, time.time() - started)

    note = (
        f"截图 {image.width}x{image.height}（真实屏幕 {width}x{height}）。"
        f"坐标请使用这张图的像素坐标（0..{image.width - 1}, 0..{image.height - 1}），"
        "服务器会自动换算到真实屏幕。"
    )
    return [
        {
            "type": "image",
            "data": __import__("base64").b64encode(buffer.getvalue()).decode("ascii"),
            "mimeType": "image/png",
        },
        note,
    ]


@server.tool("move", "把鼠标移动到截图坐标 (x, y)。不点击，无需确认。",
             {"type": "object", "properties": {"x": {"type": "integer"},
                                               "y": {"type": "integer"}},
              "required": ["x", "y"], "additionalProperties": False}, read_only=True)
def move(x: int, y: int) -> str:
    px, py = _to_screen(x, y)
    pyautogui.moveTo(px, py, duration=0.2)
    logging.info("move %s,%s -> %s,%s", x, y, px, py)
    return f"鼠标已移动到真实坐标 ({px}, {py})。"


@server.tool(
    "click",
    f"在截图坐标 (x, y) 点击。{ASK}",
    {"type": "object",
     "properties": {"x": {"type": "integer"}, "y": {"type": "integer"},
                    "button": {"type": "string", "enum": ["left", "right", "middle"]},
                    "clicks": {"type": "integer", "enum": [1, 2]}},
     "required": ["x", "y"], "additionalProperties": False},
    read_only=False,
)
def click(x: int, y: int, button: str = "left", clicks: int = 1) -> str:
    if button not in {"left", "right", "middle"}:
        return f"不支持的 button: {button}"
    if clicks not in {1, 2}:
        return "clicks 只能是 1 或 2。"
    px, py = _to_screen(x, y)
    label = f"{button} 键点击 {clicks} 次"
    if not _confirm(label, f"目标真实坐标：({px}, {py})"):
        return _deny(label)
    pyautogui.click(x=px, y=py, clicks=clicks, interval=0.08, button=button)
    logging.info("click %s,%s -> %s,%s %s x%s", x, y, px, py, button, clicks)
    return f"已在真实坐标 ({px}, {py}) 执行 {label}。"


@server.tool(
    "type_text",
    f"在当前焦点窗口输入文字（支持中文，走剪贴板粘贴）。{ASK}",
    {"type": "object", "properties": {"text": {"type": "string"}},
     "required": ["text"], "additionalProperties": False},
    read_only=False,
)
def type_text(text: str) -> str:
    if not text:
        return "text 为空，没有执行。"
    if len(text) > 4000:
        return "text 超过 4000 字符，请分批输入。"
    preview = text[:80] + ("…" if len(text) > 80 else "")
    if not _confirm("输入文字", f"共 {len(text)} 字符，开头：\n{preview}"):
        return _deny("输入文字")
    pyperclip = __import__("pyperclip")
    pyperclip.copy(text)
    time.sleep(0.1)
    pyautogui.hotkey("ctrl", "v")
    logging.info("type_text %s chars", len(text))
    return f"已粘贴 {len(text)} 个字符到当前焦点窗口。"


@server.tool(
    "press",
    f"按一个键，例如 enter / esc / tab / f5 / left。{ASK}",
    {"type": "object", "properties": {"key": {"type": "string"}},
     "required": ["key"], "additionalProperties": False},
    read_only=False,
)
def press(key: str) -> str:
    if not key:
        return "key 为空。"
    if not _confirm("按键", f"按键：{key}"):
        return _deny(f"按键 {key}")
    pyautogui.press(key)
    logging.info("press %s", key)
    return f"已按下 {key}。"


@server.tool(
    "hotkey",
    f"按组合键，例如 [\"ctrl\", \"s\"] 或 [\"alt\", \"tab\"]。{ASK}",
    {"type": "object",
     "properties": {"keys": {"type": "array", "items": {"type": "string"},
                             "minItems": 1, "maxItems": 4}},
     "required": ["keys"], "additionalProperties": False},
    read_only=False,
)
def hotkey(keys: list[str]) -> str:
    if not keys or len(keys) > 4:
        return "keys 必须是 1-4 个键名。"
    if not _confirm("组合键", f"组合键：{' + '.join(keys)}"):
        return _deny(f"组合键 {' + '.join(keys)}")
    pyautogui.hotkey(*keys)
    logging.info("hotkey %s", "+".join(keys))
    return f"已按下 {' + '.join(keys)}。"


@server.tool(
    "scroll",
    f"滚动滚轮。amount 正数向下、负数向上；x/y 可选用截图坐标先移动过去。{ASK}",
    {"type": "object",
     "properties": {"amount": {"type": "integer"}, "x": {"type": "integer"}, "y": {"type": "integer"}},
     "required": ["amount"], "additionalProperties": False},
    read_only=False,
)
def scroll(amount: int, x: int = -1, y: int = -1) -> str:
    if not -2000 <= amount <= 2000:
        return "amount 超出范围 (-2000..2000)。"
    where = ""
    if x >= 0 and y >= 0:
        px, py = _to_screen(x, y)
        pyautogui.moveTo(px, py, duration=0.15)
        where = f"（先移动到真实坐标 {px}, {py}）"
    direction = "向下" if amount > 0 else "向上"
    if not _confirm("滚动", f"{direction}滚动 {abs(amount)} 格{where}"):
        return _deny("滚动")
    pyautogui.scroll(amount)
    logging.info("scroll %s", amount)
    return f"已{direction}滚动 {abs(amount)} 格。"


@server.tool("wait", "等待最多 30 秒，用于等界面刷新。无需确认。",
             {"type": "object", "properties": {"seconds": {"type": "number"}},
              "required": ["seconds"], "additionalProperties": False}, read_only=True)
def wait(seconds: float) -> str:
    seconds = max(0.0, min(30.0, float(seconds)))
    time.sleep(seconds)
    return f"已等待 {seconds:.1f} 秒。"


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Windows desktop control MCP server")
    parser.add_argument("--list-tools", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()

    level = integrity_level()
    logging.info("cua mcp server starting; integrity=%s; confirm=%s", level, CONFIRM_MODE)
    if level == "Low":
        logging.warning("integrity is Low: Windows drops SetCursorPos/SendInput. "
                        "Start the server with a python.exe OUTSIDE the DSH workspace.")
    mcpcore.harden_stdio()

    if args.list_tools:
        for name in sorted(server.tools):
            print(name)
        raise SystemExit(0)

    if args.selftest:
        print("integrity:", level)
        print("screen:", pyautogui.size())
        try:
            print("screenshot:", pyautogui.screenshot().size)
        except Exception as exc:  # noqa: BLE001
            print("screenshot: FAILED", type(exc).__name__, exc)
        moved = False
        try:
            before = pyautogui.position()
            pyautogui.moveTo(40, 60, duration=0)
            after = pyautogui.position()
            moved = (after.x, after.y) == (40, 60)
            print("cursor:", before, "->", after, "OK" if moved else "BLOCKED")
        except Exception as exc:  # noqa: BLE001
            print("cursor: FAILED", type(exc).__name__, exc)
        raise SystemExit(0 if moved else 2)

    server.serve()
