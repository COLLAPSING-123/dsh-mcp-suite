import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required .env setting: {name}")
    return value

BASE_URL = required("BASE_URL").rstrip("/")
API_KEY = required("API_KEY")
MODEL = required("MODEL")
# DeepSeek-only knob: "disabled" | "enabled" | "" (empty = do not send the field).
# deepseek-flash enables thinking by default, and once `tools` are in the request
# the API rejects the next turn unless every reasoning_content is replayed.
THINKING = os.getenv("THINKING", "").strip().lower()
WSL_DISTRO = os.getenv("WSL_DISTRO", "Ubuntu").strip()
VM_HOST = os.getenv("VM_HOST", "").strip()
VM_USER = os.getenv("VM_USER", "").strip()
SSH_KEY_PATH = os.getenv("SSH_KEY_PATH", "").strip()
WORKSPACE = Path(os.getenv("WORKSPACE", str(Path.home() / "ai-agent-workspace")).strip()).expanduser().resolve()
LOG_DIR = Path("logs").resolve()
AUDIT_PATH = LOG_DIR / "audit.jsonl"
REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "90"))
MAX_TOOL_ROUNDS = int(os.getenv("MAX_TOOL_ROUNDS", "8"))
MAX_OUTPUT_CHARS = int(os.getenv("MAX_OUTPUT_CHARS", "12000"))
