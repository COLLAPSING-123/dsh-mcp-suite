# -*- coding: utf-8 -*-
"""Verify that docs/*.md mention every real tool and every parameter."""
import json
import os
import subprocess
import sys

SRV = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "servers", "server.py")
DOCS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")
TICK = chr(96)  # backtick


def real_tools():
    out = {}
    for prof in ("docs", "shell", "git"):
        req = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}) + "\n"
        p = subprocess.run([sys.executable, SRV, "--profile", prof],
                           input=req.encode("utf-8"), capture_output=True, timeout=60)
        data = json.loads(p.stdout.decode("utf-8"))
        for t in data["result"]["tools"]:
            out[t["name"]] = (prof, list(t["inputSchema"].get("properties", {}).keys()))
    return out


def main():
    tools = real_tools()
    print("实际工具数: %d" % len(tools))

    text = ""
    for name in sorted(os.listdir(DOCS)):
        if name.endswith(".md"):
            with open(os.path.join(DOCS, name), encoding="utf-8") as fh:
                text += fh.read()

    missing_tools = []
    missing_params = []
    for name, (prof, props) in sorted(tools.items()):
        if TICK + name + TICK not in text:
            missing_tools.append("%s (%s)" % (name, prof))
        for prop in props:
            if TICK + prop + TICK not in text:
                missing_params.append("%s.%s" % (name, prop))

    print("文档未提及的工具: %s" % (missing_tools or "无"))
    print("文档未提及的参数: %s" % (missing_params or "无"))
    return 0 if not missing_tools and not missing_params else 1


if __name__ == "__main__":
    sys.exit(main())
