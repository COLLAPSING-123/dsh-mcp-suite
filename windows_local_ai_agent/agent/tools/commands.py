import os, shlex, subprocess
from pathlib import Path
from typing import Any
from .. import config
from ..policy import inspect_command

def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + f"\n...[truncated; original chars={len(value)}]"

def _confirm(label: str, detail: str) -> bool:
    print("\n" + "=" * 72 + f"\nLOCAL APPROVAL REQUIRED: {label}\n{detail}")
    return input("Type yes to execute: ").strip().lower() == "yes"

def run_command(target: str, command: str) -> dict[str, Any]:
    check = inspect_command(target, command)
    if not check.allowed:
        return {"ok": False, "error": check.reason}
    if target == "vm" and (not config.VM_HOST or not config.VM_USER):
        return {"ok": False, "error": "Set VM_HOST and VM_USER in .env first."}
    if not _confirm("COMMAND", f"Target: {target}\nCommand: {command}"):
        return {"ok": False, "cancelled": True, "error": "User declined execution."}
    timeout = config.REQUEST_TIMEOUT_SECONDS
    try:
        if target == "windows":
            argv = ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive",
                    "-ExecutionPolicy", "Restricted", "-Command", command]
            cwd = str(config.WORKSPACE)
        elif target == "wsl":
            argv = ["wsl.exe", "-d", config.WSL_DISTRO, "--", "bash", "-lc", command]
            cwd = None
        else:
            argv = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8"]
            if config.SSH_KEY_PATH:
                argv += ["-i", str(Path(config.SSH_KEY_PATH).expanduser())]
            argv += [f"{config.VM_USER}@{config.VM_HOST}", "bash", "-lc", shlex.quote(command)]
            cwd = None
        completed = subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                                   timeout=timeout, check=False,
                                   env=os.environ.copy() if target == "windows" else None)
        return {"ok": completed.returncode == 0, "target": target,
                "returncode": completed.returncode,
                "stdout": _truncate(completed.stdout or "", config.MAX_OUTPUT_CHARS),
                "stderr": _truncate(completed.stderr or "", min(config.MAX_OUTPUT_CHARS, 6000))}
    except subprocess.TimeoutExpired as exc:
        def decode(v):
            return v.decode(errors="replace") if isinstance(v, bytes) else (v or "")
        return {"ok": False, "target": target,
                "error": f"Command timed out after {timeout}s. Child processes may remain.",
                "stdout": _truncate(decode(exc.stdout), 4000),
                "stderr": _truncate(decode(exc.stderr), 2000)}
    except (OSError, ValueError) as exc:
        return {"ok": False, "target": target, "error": f"{type(exc).__name__}: {exc}"}
