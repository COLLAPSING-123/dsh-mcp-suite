import re
from dataclasses import dataclass

# Guardrails only, not a shell parser or sandbox.
BLOCK_PATTERNS = [
    r"\b(format|diskpart|bcdedit|shutdown|restart-computer|stop-computer)\b",
    r"\b(remove-item|del|erase|rmdir|rd)\b.*(-recurse|-force|/s|/q)",
    r"\b(rm|shred)\b.*(^|\s)-[^ ]*[rf]",
    r"\b(sudo|runas)\b",
    r"\b(Invoke-Expression|iex)\b",
    r"\b(Set-ExecutionPolicy)\b",
    r"\b(reg\s+delete|regedit)\b",
    r"\b(mkfs(\.\w+)?|dd\s+if=|iptables\s+-F|nft\s+flush)\b",
    r"\b(curl|wget|Invoke-WebRequest)\b.*\|\s*(bash|sh|powershell)",
    r":\(\)\s*\{\s*:\|:&\s*\};:",
]
@dataclass
class PolicyResult:
    allowed: bool
    reason: str = ""

def inspect_command(target: str, command: str) -> PolicyResult:
    if target not in {"windows", "wsl", "vm"}:
        return PolicyResult(False, "Unknown execution target.")
    if not command or not command.strip():
        return PolicyResult(False, "Empty command.")
    if len(command) > 2000:
        return PolicyResult(False, "Command exceeds 2000 characters.")
    if "\x00" in command:
        return PolicyResult(False, "NUL byte is not allowed.")
    for pattern in BLOCK_PATTERNS:
        if re.search(pattern, command, flags=re.IGNORECASE):
            return PolicyResult(False, f"Blocked by safety policy: {pattern}")
    if re.search(r"&&|\|\||;\s*(?:rm|del|Remove-Item|sudo|shutdown)\b", command, re.I):
        return PolicyResult(False, "Command chaining with a high-risk operation is blocked.")
    return PolicyResult(True, "Passed basic checks; approval is still required.")
