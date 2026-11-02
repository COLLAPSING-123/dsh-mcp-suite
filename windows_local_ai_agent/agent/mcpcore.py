# -*- coding: utf-8 -*-
"""Zero-dependency MCP stdio core, vendored from projects/mcp-suite/servers/mcpcore.py.

Why: the `mcp` 2.x SDK pulls ~40 packages (cryptography, uvicorn, starlette…)
for a server that only needs initialize / tools/list / tools/call over
newline-delimited JSON-RPC on stdio.

Local changes vs the original:
  * `_as_content` passes through ready-made content blocks and lists of them,
    so a tool can return an image block plus a text note (screenshot needs it).
  * `ToolError` re-exported for callers.

Protocol notes kept from the original (both are load-bearing):
  * `notifications/initialized` never gets a reply - a response breaks clients.
  * Tool failures are `isError: true` results, never JSON-RPC error objects.
"""

from __future__ import annotations

import json
import sys
import traceback

PROTOCOL_VERSION = "2025-11-25"
KNOWN_VERSIONS = {
    "2024-11-05",
    "2025-03-26",
    "2025-06-18",
    "2025-11-25",
    "2026-07-28",
}

MAX_TEXT_CHARS = 120_000


class ToolError(Exception):
    """Raised by a tool to return a clean, user-facing failure."""


class Server:
    def __init__(self, name: str, version: str = "1.0.0", instructions: str = ""):
        self.name = name
        self.version = version
        self.instructions = instructions
        self.tools = {}

    # ---------------------------------------------------------------- registry
    def tool(self, name, description, schema=None, read_only=True):
        def deco(fn):
            self.tools[name] = {
                "fn": fn,
                "description": description,
                "schema": schema or {"type": "object", "properties": {}},
                "read_only": read_only,
            }
            return fn

        return deco

    def _list_tools(self):
        out = []
        for name in sorted(self.tools):
            spec = self.tools[name]
            out.append(
                {
                    "name": name,
                    "description": spec["description"],
                    "inputSchema": spec["schema"],
                    "annotations": {"readOnlyHint": bool(spec["read_only"])},
                }
            )
        return out

    # ---------------------------------------------------------------- dispatch
    def handle_message(self, msg):
        """Return a response dict, or None for notifications."""
        if not isinstance(msg, dict):
            return _error(None, -32600, "Invalid Request")

        method = msg.get("method")
        msg_id = msg.get("id")
        params = msg.get("params") or {}
        if not isinstance(params, dict):
            params = {}

        is_notification = "id" not in msg

        if method == "initialize":
            requested = params.get("protocolVersion")
            version = requested if requested in KNOWN_VERSIONS else PROTOCOL_VERSION
            result = {
                "protocolVersion": version,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": self.name, "version": self.version},
            }
            if self.instructions:
                result["instructions"] = self.instructions
            return _ok(msg_id, result)

        # Notifications carry no id and must never get a response.
        if method in ("notifications/initialized", "notifications/cancelled"):
            return None

        if method == "ping":
            return _ok(msg_id, {})

        if method == "tools/list":
            return _ok(msg_id, {"tools": self._list_tools()})

        if method == "tools/call":
            name = params.get("name")
            args = params.get("arguments") or {}
            if not isinstance(args, dict):
                args = {}
            spec = self.tools.get(name)
            if spec is None:
                return _ok(msg_id, {"content": [_text("Unknown tool: %s" % name)], "isError": True})
            try:
                raw = spec["fn"](**args)
            except ToolError as exc:
                return _ok(msg_id, {"content": [_text(str(exc))], "isError": True})
            except TypeError as exc:
                return _ok(msg_id, {"content": [_text("Bad arguments for %s: %s" % (name, exc))],
                                    "isError": True})
            except Exception:  # noqa: BLE001 - never kill the server
                tb = traceback.format_exc()
                _log(tb)
                return _ok(msg_id, {"content": [_text("Tool failed:\n" + tb)], "isError": True})
            return _ok(msg_id, {"content": _as_content(raw), "isError": False})

        if method == "resources/list":
            return _ok(msg_id, {"resources": []})
        if method == "resources/templates/list":
            return _ok(msg_id, {"resourceTemplates": []})
        if method == "prompts/list":
            return _ok(msg_id, {"prompts": []})
        if method == "logging/setLevel":
            return _ok(msg_id, {})

        if is_notification:
            return None
        return _error(msg_id, -32601, "Method not found: %s" % method)

    # ------------------------------------------------------------------- loop
    def serve(self, stdin=None, stdout=None):
        stdin = stdin or sys.stdin
        stdout = stdout or sys.stdout
        _log("server %s v%s started (pid=%s)" % (self.name, self.version, _pid()))
        for line in stdin:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except Exception:
                _write(stdout, _error(None, -32700, "Parse error"))
                continue

            if isinstance(msg, list):  # tolerate JSON-RPC batch
                for item in msg:
                    resp = self.handle_message(item)
                    if resp is not None:
                        _write(stdout, resp)
                continue

            resp = self.handle_message(msg)
            if resp is not None:
                _write(stdout, resp)
        _log("stdin closed, exiting")


# ------------------------------------------------------------------ helpers
def _ok(msg_id, result):
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _error(msg_id, code, message):
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def _text(value):
    return {"type": "text", "text": _truncate(str(value))}


def _as_content(raw):
    """Normalise a tool return value into a list of MCP content blocks."""
    if isinstance(raw, dict) and raw.get("type") in {"text", "image", "audio"}:
        return [raw]
    if isinstance(raw, list):
        blocks = []
        for item in raw:
            blocks.extend(_as_content(item))
        return blocks or [_text("")]
    if isinstance(raw, (dict, tuple)):
        return [_text(json.dumps(raw, ensure_ascii=False, indent=2, default=str))]
    return [_text(raw)]


def _truncate(text):
    if len(text) <= MAX_TEXT_CHARS:
        return text
    return text[:MAX_TEXT_CHARS] + "\n\n[... truncated %d chars ...]" % (
        len(text) - MAX_TEXT_CHARS
    )


def _write(stream, obj):
    try:
        stream.write(json.dumps(obj, ensure_ascii=False) + "\n")
        stream.flush()
    except (BrokenPipeError, ValueError):
        pass


def _log(text):
    try:
        sys.stderr.write("[mcp] %s\n" % text)
        sys.stderr.flush()
    except Exception:
        pass


def _pid():
    import os

    return os.getpid()


def harden_stdio():
    """Force UTF-8; cp936 would corrupt the Chinese text this server returns."""
    for stream, kwargs in (
        (sys.stdin, {"encoding": "utf-8", "errors": "replace"}),
        (sys.stdout, {"encoding": "utf-8", "errors": "replace", "newline": "\n"}),
        (sys.stderr, {"encoding": "utf-8", "errors": "replace", "newline": "\n"}),
    ):
        try:
            stream.reconfigure(**kwargs)  # type: ignore[attr-defined]
        except Exception:
            pass
