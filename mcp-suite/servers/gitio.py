# -*- coding: utf-8 -*-
"""Git helpers for the `git` MCP profile.

Read-only by construction: only an allowlist of subcommands is exposed,
so a typo can never push, reset --hard or force-delete a branch.
"""
from __future__ import annotations

import os
import re
import subprocess

MAX_OUTPUT = 60_000
DEFAULT_TIMEOUT = 30

# subcommands reachable through the generic `git_run` tool
ALLOWED_SUBCOMMANDS = {
    "status",
    "log",
    "diff",
    "show",
    "branch",
    "remote",
    "tag",
    "rev-parse",
    "describe",
    "shortlog",
    "blame",
    "ls-files",
    "stash",
}

BLOCKED_ARGS = re.compile(
    r"(^|\s)("
    r"push|reset\s+--hard|clean\s+-[a-z]*f|checkout\s+--|rebase|filter-branch|"
    r"gc\s+--prune|branch\s+(-D|-d|--delete)|tag\s+(-d|--delete)|"
    r"update-ref\s+-d|reflog\s+expire|prune"
    r")",
    re.IGNORECASE,
)


class GitError(Exception):
    pass


def _git(repo, args, timeout=DEFAULT_TIMEOUT):
    if not repo:
        raise GitError("repo is required")
    repo = os.path.abspath(os.path.expanduser(repo))
    if not os.path.isdir(repo):
        raise GitError("not a directory: %s" % repo)
    if not os.path.exists(os.path.join(repo, ".git")) and not _is_worktree(repo):
        raise GitError("not a git repository (no .git): %s" % repo)

    argv = ["git", "-C", repo, "-c", "core.quotepath=false"] + list(args)
    try:
        proc = subprocess.run(argv, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise GitError("git timed out after %ss: git %s" % (timeout, " ".join(args)))
    except FileNotFoundError:
        raise GitError("git executable not found on PATH")

    out = _decode(proc.stdout).strip()
    err = _decode(proc.stderr).strip()
    if proc.returncode != 0:
        raise GitError("git %s failed (exit %d)\n%s" % (" ".join(args), proc.returncode, err or out))
    text = out if out else "(no output)"
    if len(text) > MAX_OUTPUT:
        text = text[:MAX_OUTPUT] + "\n\n[... truncated ...]"
    return text


def _is_worktree(repo):
    marker = os.path.join(repo, ".git")
    if os.path.isfile(marker):  # worktree/submodule: .git is a file
        return True
    try:
        proc = subprocess.run(
            ["git", "-C", repo, "rev-parse", "--git-dir"],
            capture_output=True,
            timeout=10,
        )
        return proc.returncode == 0
    except Exception:
        return False


def _decode(raw):
    if raw is None:
        return ""
    for enc in ("utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


# ------------------------------------------------------------------- tools
def git_status(repo):
    return _git(repo, ["status", "--short", "--branch"])


def git_log(repo, max_count=20, path=None, oneline=True):
    try:
        count = max(1, min(int(max_count), 200))
    except (TypeError, ValueError):
        count = 20
    args = ["log", "-n", str(count)]
    if oneline:
        # --date must sit before --pretty, and never between -n and its value
        args += ["--date=short", "--pretty=format:%h %ad %an %s"]
    else:
        args.append("--stat")
    if path:
        args += ["--", path]
    return _git(repo, args)


def git_diff(repo, staged=False, path=None, context=3):
    try:
        ctx = max(0, min(int(context), 20))
    except (TypeError, ValueError):
        ctx = 3
    args = ["diff", "-U%d" % ctx]
    if staged:
        args.append("--staged")
    if path:
        args += ["--", path]
    out = _git(repo, args)
    if out == "(no output)":
        scope = "staged index" if staged else "working tree"
        return "(no differences in the %s)" % scope
    return out


def git_show(repo, rev="HEAD"):
    return _git(repo, ["show", "--stat", "--patch", str(rev)])


def git_branches(repo):
    return _git(repo, ["branch", "-vv", "--all"])


def git_run(repo, subcommand, args=None):
    if subcommand not in ALLOWED_SUBCOMMANDS:
        raise GitError(
            "subcommand %r not allowed; allowed: %s"
            % (subcommand, ", ".join(sorted(ALLOWED_SUBCOMMANDS)))
        )
    arglist = list(args or [])
    # Check subcommand and args together: "branch" + ["-D", "main"] only
    # matches the delete pattern when both parts are in the same string.
    joined = " ".join([subcommand] + arglist)
    if BLOCKED_ARGS.search(joined):
        raise GitError("argument set looks destructive: %s" % joined)
    return _git(repo, [subcommand] + arglist)
