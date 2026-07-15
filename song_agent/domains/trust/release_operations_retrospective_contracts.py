from __future__ import annotations

from song_agent.domains.delivery.releases import stable_hash


RETROSPECTIVE_HASH_EXCLUDE_KEYS = {"integrity_hash", "generated_at", "updated_at"}


def operations_retrospective_integrity_hash(report: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (report or {}).items() if key not in RETROSPECTIVE_HASH_EXCLUDE_KEYS})
