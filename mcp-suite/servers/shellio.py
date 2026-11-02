# -*- coding: utf-8 -*-
"""PowerShell / WSL execution helpers for the `shell` MCP profile.

Every command is written to a log file before it runs, so a bad call is
always auditable afterwards.
"""
from __future__ import annotations

import datetime
import os
import re
import subprocess
import sys

MAX_OUTPUT = 60_000
DEFAULT_TIMEOUT = 60
MAX_TIMEOUT = 600

# Patterns that can destroy the machine or the disk. Blocked unless the
# caller explicitly passes force=True.
DANGEROUS = [
    r"\bformat\b\s+[a-z]:",
    r"\bdiskpart\b",
    r"\bbcdedit\b",
    r"\bvssadmin\b.*delete",
    r"\bcipher\b\s+/w",
    r"Remove-Item\b.*-Recurse.*\bC:\\\\?(\s|$)",
    r"\brm\s+-rf\s+/(\s|$)",
    r"\bmkfs(\.|\b)",
    r"\bdd\s+if=.*of=/dev/",
    r"\bshutdown\b",
    r"\bRestart-Computer\b",
    r"\bStop-Computer\b",
]

_LOG_PATH = None


class ShellError(Exception):
    pass


def set_log_path(path):
    global _LOG_PATH
    _LOG_PATH = path


def _log(kind, command, extra=""):
    if not _LOG_PATH:
        return
    try:
        os.makedirs(os.path.dirname(_LOG_PATH), exist_ok=True)
        stamp = datetime.datetime.now().isoformat(timespec="seconds")
        with open(_LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write("[%s] %s %s\n" % (stamp, kind, command))
            if extra:
                fh.write("    -> %s\n" % extra)
    except Exception:
        pass


def _dangerous(command):
    for pattern in DANGEROUS:
        if re.search(pattern, command, re.IGNORECASE):
            return pattern
    return None


def _decode(raw):
    if raw is None:
        return ""
    # wsl.exe emits UTF-16LE for its own diagnostics; detect by NUL density
    if b"\x00" in raw[:200]:
        try:
            return raw.decode("utf-16-le")
        except UnicodeDecodeError:
            pass
    for enc in ("utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def _clamp_timeout(timeout_sec):
    try:
        value = int(timeout_sec)
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT
    return max(1, min(value, MAX_TIMEOUT))


def _clip(text):
    if len(text) <= MAX_OUTPUT:
        return text
    return text[:MAX_OUTPUT] + "\n\n[... output truncated at %d chars ...]" % MAX_OUTPUT


# ----------------------------------------------------------------- powershell
def run_powershell(command, cwd=None, timeout_sec=DEFAULT_TIMEOUT, force=False):
    if not command or not command.strip():
        raise ShellError("command is required")
    blocked = _dangerous(command)
    if blocked and not force:
        raise ShellError(
            "refused: command matches destructive pattern /%s/. "
            "Re-issue with force=true only if you really mean it." % blocked
        )
    timeout = _clamp_timeout(timeout_sec)
    if cwd and not os.path.isdir(cwd):
        raise ShellError("cwd does not exist: %s" % cwd)

    wrapped = (
        "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
        "$OutputEncoding=[System.Text.Encoding]::UTF8; " + command
    )
    argv = [
        "powershell.exe",
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        wrapped,
    ]

    _log("ps", command)
    try:
        proc = subprocess.run(
            argv,
            cwd=cwd or None,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        _log("ps", command, "TIMEOUT after %ss" % timeout)
        raise ShellError("powershell timed out after %ss: %s" % (timeout, command))
    except FileNotFoundError:
        raise ShellError("powershell.exe not found on PATH")

    out = _decode(proc.stdout).strip()
    err = _decode(proc.stderr).strip()
    _log("ps", command, "exit=%s" % proc.returncode)

    parts = ["exit_code: %d" % proc.returncode]
    parts.append("stdout:\n" + (out if out else "(empty)"))
    if err:
        parts.append("stderr:\n" + err)
    return _clip("\n\n".join(parts))


# ------------------------------------------------------------------------ wsl
def run_wsl(command, distro=None, timeout_sec=DEFAULT_TIMEOUT, force=False):
    if not command or not command.strip():
        raise ShellError("command is required")
    blocked = _dangerous(command)
    if blocked and not force:
        raise ShellError(
            "refused: command matches destructive pattern /%s/. "
            "Re-issue with force=true only if you really mean it." % blocked
        )
    timeout = _clamp_timeout(timeout_sec)

    argv = ["wsl.exe"]
    if distro:
        argv += ["-d", distro]
    argv += ["-e", "bash", "-lc", command]

    _log("wsl", command, "distro=%s" % (distro or "default"))
    try:
        proc = subprocess.run(argv, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        _log("wsl", command, "TIMEOUT")
        raise ShellError("wsl timed out after %ss: %s" % (timeout, command))
    except FileNotFoundError:
        raise ShellError("wsl.exe not found")

    out = _decode(proc.stdout).strip()
    err = _decode(proc.stderr).strip()
    _log("wsl", command, "exit=%s" % proc.returncode)

    # wsl.exe signals its own failures with 0xFFFFFFFF (-1) and WSL_E_* text.
    # That is not "your command failed", it is "WSL could not run it at all",
    # so surface it as a tool error instead of a normal-looking exit code.
    infra = proc.returncode in (-1, 4294967295) or "WSL_E_" in err
    if infra:
        detail = err or out or "(no output)"
        raise ShellError(
            "wsl could not run the command (exit %d): %s"
            % (proc.returncode, detail.strip())
        )

    parts = ["exit_code: %d" % proc.returncode]
    parts.append("stdout:\n" + (out if out else "(empty)"))
    if err:
        parts.append("stderr:\n" + err)
    return _clip("\n\n".join(parts))


def wsl_distros():
    try:
        proc = subprocess.run(
            ["wsl.exe", "-l", "-v"], capture_output=True, timeout=30
        )
    except Exception as exc:  # noqa: BLE001
        return "failed to query WSL: %s" % exc

    raw = proc.stdout or b""
    # wsl.exe emits UTF-16LE for -l -v
    text = ""
    for enc in ("utf-16-le", "utf-8", "gb18030"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    text = text.replace("\x00", "").strip()
    err = _decode(proc.stderr).strip().replace("\x00", "")

    # A failure can arrive on either stream; do not pass it off as a listing.
    combined = (err + " " + text).strip()
    if proc.returncode != 0 or "WSL_E_" in combined or "拒绝访问" in combined:
        raise ShellError(
            "wsl could not be queried (exit %d): %s"
            % (proc.returncode, combined or "(no output)")
        )
    return text or "(no distributions installed)"


# --------------------------------------------------------------------- probe
def powershell_info():
    script = (
        "$PSVersionTable.PSVersion.ToString(); "
        "[Environment]::OSVersion.VersionString; "
        "(Get-ExecutionPolicy -Scope CurrentUser)"
    )
    try:
        return run_powershell(script, timeout_sec=30)
    except ShellError as exc:
        return "unavailable: %s" % exc
