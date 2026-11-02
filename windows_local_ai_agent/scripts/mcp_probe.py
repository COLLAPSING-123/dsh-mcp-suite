"""Smoke-test the local CUA MCP server over real stdio pipes.

Uses subprocess.Popen (anonymous pipes) instead of asyncio's subprocess, because
asyncio on Windows needs a named pipe and the DSH sandbox denies creating one.

Usage:  .venv\\Scripts\\python.exe scripts\\mcp_probe.py
Read-only tools only (screen_size / screenshot / move / wait) -> no dialogs.
"""

import json
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TIMEOUT = 90


def main() -> int:
    proc = subprocess.Popen(
        [sys.executable, "-m", "agent.mcp_server"],
        cwd=str(ROOT),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    killer = threading.Timer(TIMEOUT, proc.kill)
    killer.start()

    def send(payload: dict) -> None:
        proc.stdin.write(json.dumps(payload) + "\n")
        proc.stdin.flush()

    def read_response(request_id: int) -> dict:
        while True:
            line = proc.stdout.readline()
            if not line:
                raise RuntimeError("server closed stdout: " + (proc.stderr.read() or "")[:2000])
            line = line.strip()
            if not line:
                continue
            message = json.loads(line)
            if message.get("id") == request_id:
                return message

    try:
        send({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2026-07-28",
                "capabilities": {},
                "clientInfo": {"name": "probe", "version": "0"},
            },
        })
        init = read_response(1)
        print("protocol:", init.get("result", {}).get("protocolVersion"))
        print("server:", init.get("result", {}).get("serverInfo"))

        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tools = read_response(2)["result"]["tools"]
        print("tools:", [t["name"] for t in tools])

        for i, (name, args) in enumerate(
            (("screen_size", {}), ("screenshot", {}), ("move", {"x": 10, "y": 10}), ("wait", {"seconds": 0.2})),
            start=10,
        ):
            send({"jsonrpc": "2.0", "id": i, "method": "tools/call",
                  "params": {"name": name, "arguments": args}})
            result = read_response(i)["result"]
            kinds = []
            for block in result.get("content", []):
                if block.get("type") == "image":
                    kinds.append(f"image({len(block.get('data', ''))} b64)")
                else:
                    kinds.append(f"text({len(block.get('text', ''))})")
            print(f"{name}: isError={result.get('isError')} -> {kinds}")
        return 0
    finally:
        killer.cancel()
        try:
            proc.stdin.close()
        except Exception:
            pass
        proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
