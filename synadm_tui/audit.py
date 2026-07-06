"""Privacy-conscious local audit trail for completed TUI commands."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


SECRET_OPTIONS = {"--password", "-P", "--token", "-t"}


def audit_path() -> Path:
    configured = os.environ.get("XDG_STATE_HOME")
    base = Path(configured).expanduser() if configured else Path.home() / ".local" / "state"
    return base / "synadm-tui" / "audit.jsonl"


def redact_command(command: Sequence[str]) -> list[str]:
    redacted: list[str] = []
    hide_next = False
    for part in command:
        if hide_next:
            redacted.append("********")
            hide_next = False
            continue
        redacted.append(part)
        if part in SECRET_OPTIONS:
            hide_next = True
    return redacted


def append_audit(command: Sequence[str], returncode: int, duration: float) -> Path:
    """Append one JSON record with owner-only file permissions."""
    path = audit_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "command": redact_command(command),
        "returncode": returncode,
        "ok": returncode == 0,
        "duration_seconds": round(duration, 3),
    }
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        with os.fdopen(descriptor, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    finally:
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    return path
