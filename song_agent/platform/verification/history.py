from __future__ import annotations

from typing import Any

from song_agent.platform.verification.hashing import stable_hash
from song_agent.platform.verification.model import build_check


def history_chain_checks(
    rows: list[dict[str, Any]],
    *,
    check_prefix: str,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    previous = ""
    for index, row in enumerate(rows):
        payload_hash = stable_hash({key: value for key, value in row.items() if key not in {"payload_hash", "event_hash"}})
        event_hash = stable_hash({key: value for key, value in row.items() if key != "event_hash"})
        checks.extend(
            [
                build_check(f"{check_prefix}_{index:03d}_payload_hash", row.get("payload_hash") == payload_hash, "History payload hash is valid."),
                build_check(f"{check_prefix}_{index:03d}_event_hash", row.get("event_hash") == event_hash, "History event hash is valid."),
                build_check(f"{check_prefix}_{index:03d}_chain", str(row.get("previous_event_hash") or "") == previous, "History hash chain is contiguous."),
            ]
        )
        previous = str(row.get("event_hash") or "")
    return checks
