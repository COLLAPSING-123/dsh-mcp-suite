from typing import Any
from .commands import run_command
from .desktop import screenshot, desktop_action

TOOL_SCHEMAS = [
 {"type":"function","function":{"name":"run_command",
  "description":"Run one command in Windows PowerShell, WSL Ubuntu, or configured Ubuntu VM over SSH. Requires local approval.",
  "parameters":{"type":"object","properties":{"target":{"type":"string","enum":["windows","wsl","vm"]},"command":{"type":"string"}},
  "required":["target","command"],"additionalProperties":False}}},
 {"type":"function","function":{"name":"desktop_screenshot",
  "description":"Capture visible local Windows desktop; requires approval. Screenshot is sent to configured API endpoint. Bring VMware guest window to foreground for Ubuntu GUI.",
  "parameters":{"type":"object","properties":{},"additionalProperties":False}}},
 {"type":"function","function":{"name":"desktop_action",
  "description":"Perform one approved action on visible Windows desktop. Take screenshot first. Actions: click, type_text, hotkey, press, move.",
  "parameters":{"type":"object","properties":{"action":{"type":"string","enum":["click","type_text","hotkey","press","move"]},
  "x":{"type":"integer","minimum":0,"maximum":10000},"y":{"type":"integer","minimum":0,"maximum":10000},
  "text":{"type":"string"},"keys":{"type":"array","items":{"type":"string"},"maxItems":4}},
  "required":["action"],"additionalProperties":False}}}
]

def call_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name == "run_command": return run_command(args["target"], args["command"])
    if name == "desktop_screenshot": return screenshot()
    if name == "desktop_action":
        return desktop_action(args["action"], args.get("x",0), args.get("y",0), args.get("text",""), args.get("keys"))
    return {"ok":False,"error":f"Unknown tool: {name}"}
