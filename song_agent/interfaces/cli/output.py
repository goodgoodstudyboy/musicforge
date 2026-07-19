from __future__ import annotations

from song_agent.platform.contracts import DomainDocument
import json


def write_json_result(value: DomainDocument) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def status_exit_code(value: DomainDocument) -> int:
    status = str(value.get("status") or "").lower()
    return 1 if value.get("ok") is False or status in {"blocked", "failed", "stale"} else 0
