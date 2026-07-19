from __future__ import annotations

import json
from typing import Any


def write_json_result(value: dict[str, Any]) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def status_exit_code(value: dict[str, Any]) -> int:
    status = str(value.get("status") or "").lower()
    return 1 if value.get("ok") is False or status in {"blocked", "failed", "stale"} else 0
