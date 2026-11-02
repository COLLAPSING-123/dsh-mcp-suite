import json, os
from datetime import datetime, timezone
from .config import LOG_DIR, AUDIT_PATH

def audit(event: dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    row = {"timestamp": datetime.now(timezone.utc).isoformat(), **event}
    with AUDIT_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    try:
        os.chmod(AUDIT_PATH, 0o600)
    except OSError:
        pass
