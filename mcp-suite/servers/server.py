# -*- coding: utf-8 -*-
"""Single-file entry point for the local MCP suite.

    python server.py --profile docs
    python server.py --profile shell
    python server.py --profile git
    python server.py --profile docs --selftest
    python server.py --profile docs --list-tools

One process per profile, each registered in the DSH config as its own
MCP server, so they can be enabled, disabled and rolled back separately.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import mcpcore  # noqa: E402
import docio  # noqa: E402
import gitio  # noqa: E402
import shellio  # noqa: E402

VERSION = "1.0.0"
LOG_DIR = os.path.join(os.path.dirname(HERE), "logs")


def _obj(properties, required=None):
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


PATH_PROP = {"type": "string", "description": "Absolute or workspace-relative file path"}


# --------------------------------------------------------------------- docs
def build_docs():
    server = mcpcore.Server(
        "local-docs",
        VERSION,
        instructions=(
            "Read Word (.docx), PowerPoint (.pptx), Excel (.xlsx), PDF and "
            "Markdown/text files from this Windows machine. Legacy .doc/.ppt/.xls "
            "must be re-saved as the x-format first. PDFs without a text layer "
            "cannot be read."
        ),
    )

    @server.tool(
        "read_document",
        "Extract the text of a .docx/.pptx/.xlsx/.pdf/.md/.txt/.csv/.json file. "
        "Returns markdown-ish text (headings, slide markers, table rows).",
        _obj(
            {
                "path": PATH_PROP,
                "max_chars": {
                    "type": "integer",
                    "description": "Truncate the result after this many characters (default 200000)",
                    "minimum": 1000,
                },
            },
            ["path"],
        ),
    )
    def read_document(path, max_chars=200_000):
        try:
            kind, text = docio.read_any(path, int(max_chars))
        except docio.DocError as exc:
            raise mcpcore.ToolError(str(exc))
        return "kind: %s\npath: %s\n\n%s" % (kind, os.path.abspath(path), text)

    @server.tool(
        "read_markdown",
        "Return the raw text of a Markdown file, with an optional heading outline.",
        _obj(
            {
                "path": PATH_PROP,
                "outline_only": {
                    "type": "boolean",
                    "description": "Return only the heading tree instead of the full text",
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Truncate the result after this many characters (default 200000)",
                    "minimum": 1000,
                },
            },
            ["path"],
        ),
    )
    def read_markdown(path, outline_only=False, max_chars=200_000):
        try:
            if outline_only:
                return docio.markdown_outline(path)
            return docio.read_markdown(path, max_chars=int(max_chars))
        except docio.DocError as exc:
            raise mcpcore.ToolError(str(exc))

    @server.tool(
        "document_info",
        "Report kind, size and modified time for a document without reading its body.",
        _obj({"path": PATH_PROP}, ["path"]),
    )
    def document_info(path):
        try:
            return json.dumps(docio.describe(path), ensure_ascii=False, indent=2)
        except docio.DocError as exc:
            raise mcpcore.ToolError(str(exc))

    @server.tool(
        "supported_formats",
        "List the file extensions this server can read.",
        _obj({}),
    )
    def supported_formats():
        return "supported: %s\nlegacy (must be re-saved): .doc .ppt .xls" % ", ".join(
            docio.SUPPORTED
        )

    return server


# -------------------------------------------------------------------- shell
def build_shell():
    shellio.set_log_path(os.path.join(LOG_DIR, "shell.log"))
    server = mcpcore.Server(
        "local-shell",
        VERSION,
        instructions=(
            "Run commands on this Windows machine through PowerShell 5.1, or "
            "inside WSL. Destructive patterns are refused unless force=true. "
            "Every command is appended to logs/shell.log."
        ),
    )

    @server.tool(
        "run_powershell",
        "Execute a PowerShell command and return exit code, stdout and stderr.",
        _obj(
            {
                "command": {"type": "string", "description": "PowerShell command text"},
                "cwd": {"type": "string", "description": "Working directory (optional)"},
                "timeout_sec": {
                    "type": "integer",
                    "description": "Timeout in seconds, 1-600 (default 60)",
                },
                "force": {
                    "type": "boolean",
                    "description": "Allow a command that matches the destructive denylist",
                },
            },
            ["command"],
        ),
        read_only=False,
    )
    def run_powershell(command, cwd=None, timeout_sec=60, force=False):
        try:
            return shellio.run_powershell(command, cwd=cwd, timeout_sec=timeout_sec, force=force)
        except shellio.ShellError as exc:
            raise mcpcore.ToolError(str(exc))

    @server.tool(
        "run_wsl",
        "Execute a bash command inside WSL (default distro unless `distro` is given).",
        _obj(
            {
                "command": {"type": "string", "description": "bash command text"},
                "distro": {"type": "string", "description": "WSL distribution name (optional)"},
                "timeout_sec": {"type": "integer", "description": "Timeout in seconds, 1-600"},
                "force": {"type": "boolean", "description": "Bypass the destructive denylist"},
            },
            ["command"],
        ),
        read_only=False,
    )
    def run_wsl(command, distro=None, timeout_sec=60, force=False):
        try:
            return shellio.run_wsl(command, distro=distro, timeout_sec=timeout_sec, force=force)
        except shellio.ShellError as exc:
            raise mcpcore.ToolError(str(exc))

    @server.tool(
        "wsl_distros",
        "List installed WSL distributions and their state.",
        _obj({}),
    )
    def wsl_distros():
        try:
            return shellio.wsl_distros()
        except shellio.ShellError as exc:
            raise mcpcore.ToolError(str(exc))

    @server.tool(
        "powershell_info",
        "Report PowerShell version, OS version and execution policy.",
        _obj({}),
    )
    def powershell_info():
        return shellio.powershell_info()

    return server


# ---------------------------------------------------------------------- git
def build_git():
    server = mcpcore.Server(
        "local-git",
        VERSION,
        instructions=(
            "Inspect git repositories on this machine. Read-only: status, log, "
            "diff, show, branches, plus a guarded `git_run` allowlist. "
            "Nothing here can push, reset --hard or delete."
        ),
    )

    repo_prop = {"type": "string", "description": "Path to the repository root"}

    @server.tool(
        "git_status",
        "Short status plus branch line for a repository.",
        _obj({"repo": repo_prop}, ["repo"]),
    )
    def git_status(repo):
        try:
            return gitio.git_status(repo)
        except gitio.GitError as exc:
            raise mcpcore.ToolError(str(exc))

    @server.tool(
        "git_log",
        "Recent commits (hash, date, author, subject).",
        _obj(
            {
                "repo": repo_prop,
                "max_count": {"type": "integer", "description": "1-200, default 20"},
                "path": {"type": "string", "description": "Limit history to this path"},
            },
            ["repo"],
        ),
    )
    def git_log(repo, max_count=20, path=None):
        try:
            return gitio.git_log(repo, max_count=max_count, path=path)
        except gitio.GitError as exc:
            raise mcpcore.ToolError(str(exc))

    @server.tool(
        "git_diff",
        "Working-tree or staged diff.",
        _obj(
            {
                "repo": repo_prop,
                "staged": {"type": "boolean", "description": "Diff the index instead of the worktree"},
                "path": {"type": "string", "description": "Limit to this path"},
                "context": {"type": "integer", "description": "Context lines, 0-20"},
            },
            ["repo"],
        ),
    )
    def git_diff(repo, staged=False, path=None, context=3):
        try:
            return gitio.git_diff(repo, staged=staged, path=path, context=context)
        except gitio.GitError as exc:
            raise mcpcore.ToolError(str(exc))

    @server.tool(
        "git_show",
        "Show a commit with its patch.",
        _obj({"repo": repo_prop, "rev": {"type": "string", "description": "Revision, default HEAD"}}, ["repo"]),
    )
    def git_show(repo, rev="HEAD"):
        try:
            return gitio.git_show(repo, rev)
        except gitio.GitError as exc:
            raise mcpcore.ToolError(str(exc))

    @server.tool(
        "git_branches",
        "All local and remote branches with tracking info.",
        _obj({"repo": repo_prop}, ["repo"]),
    )
    def git_branches(repo):
        try:
            return gitio.git_branches(repo)
        except gitio.GitError as exc:
            raise mcpcore.ToolError(str(exc))

    @server.tool(
        "git_run",
        "Run an allowlisted read-only git subcommand (status/log/diff/show/branch/"
        "remote/tag/rev-parse/describe/shortlog/blame/ls-files/stash).",
        _obj(
            {
                "repo": repo_prop,
                "subcommand": {"type": "string", "description": "e.g. rev-parse"},
                "args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Extra arguments, passed verbatim",
                },
            },
            ["repo", "subcommand"],
        ),
        read_only=False,
    )
    def git_run(repo, subcommand, args=None):
        try:
            return gitio.git_run(repo, subcommand, args)
        except gitio.GitError as exc:
            raise mcpcore.ToolError(str(exc))

    return server


BUILDERS = {"docs": build_docs, "shell": build_shell, "git": build_git}


# ------------------------------------------------------------------ selftest
def selftest(profile):
    """Exercise the JSON-RPC surface without touching stdin/stdout."""
    server = BUILDERS[profile]()
    failures = []

    def rpc(msg):
        return server.handle_message(msg)

    init = rpc(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "selftest"}},
        }
    )
    if not init or "result" not in init:
        failures.append("initialize did not return a result")
    elif "protocolVersion" not in init["result"]:
        failures.append("initialize result missing protocolVersion")

    notif = rpc({"jsonrpc": "2.0", "method": "notifications/initialized"})
    if notif is not None:
        failures.append("notifications/initialized must not produce a response")

    listed = rpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    tools = (listed or {}).get("result", {}).get("tools", [])
    if not tools:
        failures.append("tools/list returned no tools")
    for tool in tools:
        if "inputSchema" not in tool:
            failures.append("tool %s missing inputSchema" % tool.get("name"))
        if tool["inputSchema"].get("type") != "object":
            failures.append("tool %s inputSchema.type != object" % tool.get("name"))

    unknown = rpc({"jsonrpc": "2.0", "id": 3, "method": "no/such/method"})
    if not unknown or unknown.get("error", {}).get("code") != -32601:
        failures.append("unknown method should return -32601")

    ping = rpc({"jsonrpc": "2.0", "id": 4, "method": "ping"})
    if not ping or ping.get("result") != {}:
        failures.append("ping should return {}")

    # profile-specific live call
    if profile == "docs":
        call = rpc(
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {"name": "supported_formats", "arguments": {}},
            }
        )
        if not call or call["result"].get("isError"):
            failures.append("supported_formats failed")
    elif profile == "shell":
        call = rpc(
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {"name": "run_powershell", "arguments": {"command": "'mcp-ok'"}},
            }
        )
        if not call or call["result"].get("isError") or "mcp-ok" not in call["result"]["content"][0]["text"]:
            failures.append("run_powershell did not return mcp-ok")
    elif profile == "git":
        call = rpc(
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {"name": "git_run", "arguments": {"repo": HERE, "subcommand": "push"}},
            }
        )
        if not call or not call["result"].get("isError"):
            failures.append("git_run should refuse the 'push' subcommand")

    print("profile=%s tools=%d" % (profile, len(tools)))
    for tool in tools:
        print("  - %s" % tool["name"])
    if failures:
        print("SELFTEST FAILED")
        for item in failures:
            print("  ! %s" % item)
        return 1
    print("SELFTEST PASSED")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Local zero-dependency MCP suite")
    parser.add_argument("--profile", choices=sorted(BUILDERS), required=True)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--list-tools", action="store_true")
    args = parser.parse_args(argv)

    if args.selftest:
        mcpcore.harden_stdio()
        return selftest(args.profile)

    server = BUILDERS[args.profile]()

    if args.list_tools:
        for tool in server._list_tools():
            print("%-18s %s" % (tool["name"], tool["description"].splitlines()[0]))
        return 0

    mcpcore.harden_stdio()
    server.serve()
    return 0


if __name__ == "__main__":
    sys.exit(main())
