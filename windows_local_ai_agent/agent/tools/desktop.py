import base64, io
from typing import Any
import pyautogui

def _confirm(action: str, detail: str) -> bool:
    print("\n" + "=" * 72 + f"\nLOCAL APPROVAL REQUIRED: DESKTOP — {action}\n{detail}")
    return input("Type yes to execute: ").strip().lower() == "yes"

def screenshot() -> dict[str, Any]:
    if not _confirm("SCREENSHOT", "Capture visible Windows desktop and send it to configured API provider?"):
        return {"ok": False, "cancelled": True, "error": "User declined screenshot."}
    image = pyautogui.screenshot()
    image.thumbnail((1600, 1000))
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=75, optimize=True)
    data = base64.b64encode(buf.getvalue()).decode("ascii")
    return {"ok": True, "kind": "image", "mime_type": "image/jpeg",
            "data_url": "data:image/jpeg;base64," + data,
            "width": image.width, "height": image.height,
            "note": "Captured from local Windows display; may contain sensitive information."}

def desktop_action(action: str, x: int = 0, y: int = 0, text: str = "", keys: list[str] | None = None) -> dict[str, Any]:
    if action not in {"click", "type_text", "hotkey", "press", "move"}:
        return {"ok": False, "error": "Unsupported desktop action."}
    if action in {"click", "move"}:
        width, height = pyautogui.size()
        if not (0 <= x < width and 0 <= y < height):
            return {"ok": False, "error": f"Coordinates must be inside screen bounds {width}x{height}."}
    if len(text) > 2000:
        return {"ok": False, "error": "Text exceeds 2000 characters."}
    if not _confirm("ACTION", f"action={action}; x={x}; y={y}; text_length={len(text)}; keys={keys}"):
        return {"ok": False, "cancelled": True, "error": "User declined desktop action."}
    try:
        if action == "click": pyautogui.click(x=x, y=y)
        elif action == "move": pyautogui.moveTo(x=x, y=y, duration=0.2)
        elif action == "type_text": pyautogui.write(text, interval=0.01)
        elif action == "press": pyautogui.press((keys or ["enter"])[0])
        elif action == "hotkey":
            if not keys or len(keys) > 4: return {"ok": False, "error": "hotkey requires 1-4 keys."}
            pyautogui.hotkey(*keys)
        return {"ok": True, "action": action, "screen_size": pyautogui.size()}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
