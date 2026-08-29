"""Credential-safe, structured run auditing for demos and post-run review."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AuditSink = Callable[[str, dict[str, Any]], None]


class JsonlAuditLog:
    """Append compact operational events without persisting prompts or tool output.

    The log deliberately omits model messages, file contents, command output and
    credentials.  It is suitable for a video overlay or an interview audit trail,
    while the normal terminal still gives the operator enough live feedback.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def __call__(self, event: str, fields: dict[str, Any]) -> None:
        record = {
            "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "event": event,
            **fields,
        }
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
