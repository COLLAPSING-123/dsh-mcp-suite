# -*- coding: utf-8 -*-
"""Table-driven bug hunt for the MCP suite.

Each case is one row: (profile, tool, args, expectation).
Expectation is "ok" (must succeed), "err" (must report isError),
or "any" (either is fine, just must not crash the server).
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRV = os.path.join(ROOT, "servers", "server.py")
TMP = os.path.join(HERE, "_fixtures")
PY = sys.executable
REPO = os.environ.get("BUGHUNT_REPO", r"C:\path\to\a\git\repo")

FAILS = []
PASSES = 0


def call(profile, tool, args, timeout=120):
    req = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
         "params": {"name": tool, "arguments": args}},
        ensure_ascii=False,
    ) + "\n"
    proc = subprocess.run(
        [PY, SRV, "--profile", profile],
        input=req.encode("utf-8"),
        capture_output=True,
        timeout=timeout,
    )
    raw = proc.stdout.decode("utf-8", "replace").strip()
    if not raw:
        return None, proc.stderr.decode("utf-8", "replace")
    return json.loads(raw), ""


def check(name, profile, tool, args, expect="ok", must_contain=None):
    global PASSES
    try:
        resp, err = call(profile, tool, args)
    except Exception as exc:  # noqa: BLE001
        FAILS.append("%s -> EXCEPTION %s" % (name, exc))
        print("FAIL  %-46s exception: %s" % (name, exc))
        return

    if resp is None:
        FAILS.append("%s -> no response (%s)" % (name, err[:150]))
        print("FAIL  %-46s no response" % name)
        return
    if "result" not in resp:
        FAILS.append("%s -> rpc error %s" % (name, resp.get("error")))
        print("FAIL  %-46s rpc error" % name)
        return

    res = resp["result"]
    is_err = bool(res.get("isError"))
    try:
        text = res["content"][0]["text"]
    except Exception:  # noqa: BLE001
        text = ""

    if "Traceback" in text:
        FAILS.append("%s -> leaked traceback" % name)
        print("FAIL  %-46s leaked traceback" % name)
        return
    if expect == "err" and not is_err:
        FAILS.append("%s -> expected error, got: %s" % (name, text[:110]))
        print("FAIL  %-46s expected error" % name)
        return
    if expect == "ok" and is_err:
        FAILS.append("%s -> unexpected error: %s" % (name, text[:160]))
        print("FAIL  %-46s unexpected error: %s" % (name, text[:70]))
        return
    if must_contain and must_contain not in text:
        FAILS.append("%s -> missing %r" % (name, must_contain))
        print("FAIL  %-46s missing %r" % (name, must_contain))
        return

    PASSES += 1
    print("ok    %-46s %s" % (name, text[:46].replace("\n", " ")))


def fixtures():
    os.makedirs(TMP, exist_ok=True)
    md = os.path.join(TMP, "a.md")
    with open(md, "w", encoding="utf-8") as fh:
        fh.write("# Title\n\n## Sub\n\n正文中文\n\n```\n# not heading\n```\n")
    empty = os.path.join(TMP, "e.md")
    open(empty, "w", encoding="utf-8").close()
    fake = os.path.join(TMP, "f.docx")
    with open(fake, "wb") as fh:
        fh.write(b"not a zip")
    unknown = os.path.join(TMP, "x.zzz")
    open(unknown, "w").close()
    return md, empty, fake, unknown


def main():
    global PASSES
    md, empty, fake, unknown = fixtures()

    # ---------------- docs ----------------
    check("docs.supported_formats", "docs", "supported_formats", {}, "ok", ".docx")
    check("docs.read_markdown", "docs", "read_markdown", {"path": md}, "ok", "Title")
    check("docs.read_markdown outline", "docs", "read_markdown",
          {"path": md, "outline_only": True}, "ok", "- Title")
    check("docs.read_markdown max_chars", "docs", "read_markdown",
          {"path": md, "max_chars": 5000}, "ok", "Title")
    check("docs.read_markdown empty file", "docs", "read_markdown", {"path": empty}, "ok")
    check("docs.read_markdown missing", "docs", "read_markdown",
          {"path": os.path.join(TMP, "nope.md")}, "err")
    check("docs.read_markdown no arg", "docs", "read_markdown", {}, "err")
    check("docs.read_markdown dir", "docs", "read_markdown", {"path": TMP}, "err")
    check("docs.read_document fake docx", "docs", "read_document", {"path": fake}, "err")
    check("docs.read_document unknown ext", "docs", "read_document", {"path": unknown}, "err")
    check("docs.read_document md via router", "docs", "read_document", {"path": md}, "ok", "Title")
    check("docs.document_info", "docs", "document_info", {"path": md}, "ok", "markdown")
    check("docs.document_info missing", "docs", "document_info", {"path": "C:/no/such"}, "err")

    # ---------------- shell ----------------
    check("shell.powershell_info", "shell", "powershell_info", {}, "ok")
    check("shell.run echo", "shell", "run_powershell", {"command": "'hi-mcp'"}, "ok", "hi-mcp")
    check("shell.run exit code", "shell", "run_powershell",
          {"command": "exit 3"}, "ok", "exit_code: 3")
    check("shell.run stderr", "shell", "run_powershell",
          {"command": "Write-Error 'boom'"}, "ok", "boom")
    check("shell.run unicode", "shell", "run_powershell",
          {"command": "'中文往返'"}, "ok", "中文往返")
    check("shell.run empty cmd", "shell", "run_powershell", {"command": ""}, "err")
    check("shell.run bad cwd", "shell", "run_powershell",
          {"command": "'x'", "cwd": "Z:\\nope"}, "err")
    check("shell.run timeout", "shell", "run_powershell",
          {"command": "Start-Sleep -Seconds 5", "timeout_sec": 1}, "err")
    check("shell.block format", "shell", "run_powershell", {"command": "format C: /q"}, "err")
    check("shell.block shutdown", "shell", "run_powershell",
          {"command": "shutdown /s /t 0"}, "err")
    check("shell.block diskpart", "shell", "run_powershell", {"command": "diskpart"}, "err")
    check("shell.force allowed", "shell", "run_powershell",
          {"command": "'forced'", "force": True}, "ok", "forced")
    check("shell.wsl_distros", "shell", "wsl_distros", {}, "any")
    check("shell.wsl echo", "shell", "run_wsl", {"command": "echo wsl-hi"}, "any")
    check("shell.wsl empty", "shell", "run_wsl", {"command": ""}, "err")
    check("shell.wsl bad distro", "shell", "run_wsl",
          {"command": "echo x", "distro": "NoSuchDistro"}, "err")

    # ---------------- git ----------------
    check("git.status", "git", "git_status", {"repo": REPO}, "ok", "main")
    check("git.log", "git", "git_log", {"repo": REPO, "max_count": 2}, "ok")
    check("git.log path filter", "git", "git_log",
          {"repo": REPO, "path": "README.md"}, "ok")
    check("git.log bad count", "git", "git_log", {"repo": REPO, "max_count": "abc"}, "ok")
    check("git.diff", "git", "git_diff", {"repo": REPO}, "ok")
    check("git.diff staged", "git", "git_diff", {"repo": REPO, "staged": True}, "ok")
    check("git.branches", "git", "git_branches", {"repo": REPO}, "ok", "main")
    check("git.show HEAD", "git", "git_show", {"repo": REPO, "rev": "HEAD"}, "ok")
    check("git.show bad rev", "git", "git_show", {"repo": REPO, "rev": "nosuchref"}, "err")
    check("git.bad repo path", "git", "git_status", {"repo": "Z:\\nope"}, "err")
    check("git.non-repo", "git", "git_status", {"repo": TMP}, "err")
    check("git.run rev-parse", "git", "git_run",
          {"repo": REPO, "subcommand": "rev-parse", "args": ["HEAD"]}, "ok")
    check("git.run block push", "git", "git_run",
          {"repo": REPO, "subcommand": "push"}, "err")
    check("git.run block reset", "git", "git_run",
          {"repo": REPO, "subcommand": "reset"}, "err")
    check("git.run block branch -D", "git", "git_run",
          {"repo": REPO, "subcommand": "branch", "args": ["-D", "main"]}, "err")
    check("git.run block tag -d", "git", "git_run",
          {"repo": REPO, "subcommand": "tag", "args": ["-d", "v1"]}, "err")
    check("git.run allow branch list", "git", "git_run",
          {"repo": REPO, "subcommand": "branch", "args": ["-a"]}, "ok")

    # ---------------- protocol ----------------
    print("\n--- protocol ---")
    reqs = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-06-18"}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "no_such_tool", "arguments": {}}},
        {"jsonrpc": "2.0", "id": 4, "method": "bogus/method"},
        {"jsonrpc": "2.0", "id": 5, "method": "ping"},
        {"jsonrpc": "2.0", "id": 6, "method": "tools/call",
         "params": {"name": "read_document", "arguments": "not-a-dict"}},
    ]
    payload = "".join(json.dumps(r) + "\n" for r in reqs).encode("utf-8")
    for profile in ("docs", "shell", "git"):
        proc = subprocess.run([PY, SRV, "--profile", profile], input=payload,
                              capture_output=True, timeout=120)
        lines = [l for l in proc.stdout.decode("utf-8").splitlines() if l.strip()]
        parsed = [json.loads(l) for l in lines]
        ids = [r.get("id") for r in parsed]
        good = (
            len(parsed) == 6
            and ids == [1, 2, 3, 4, 5, 6]
            and any(r.get("error", {}).get("code") == -32601 for r in parsed)
            and any(r.get("result", {}).get("isError") for r in parsed)
        )
        if good:
            PASSES += 1
            print("ok    protocol %-6s responses=%d" % (profile, len(parsed)))
        else:
            FAILS.append("protocol %s ids=%s count=%d" % (profile, ids, len(parsed)))
            print("FAIL  protocol %-6s ids=%s" % (profile, ids))

    bad_json = b'{not json}\n{"jsonrpc":"2.0","id":9,"method":"ping"}\n'
    proc = subprocess.run([PY, SRV, "--profile", "docs"], input=bad_json,
                          capture_output=True, timeout=60)
    lines = [l for l in proc.stdout.decode("utf-8").splitlines() if l.strip()]
    if len(lines) == 2 and json.loads(lines[0]).get("error", {}).get("code") == -32700:
        PASSES += 1
        print("ok    protocol survives malformed json")
    else:
        FAILS.append("malformed json: %s" % lines)
        print("FAIL  protocol malformed json")

    print("\n%d passed, %d failed" % (PASSES, len(FAILS)))
    for item in FAILS:
        print("  ! " + item)
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(main())
