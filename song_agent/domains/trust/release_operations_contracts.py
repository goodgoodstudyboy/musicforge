from __future__ import annotations

from song_agent.platform.contracts import DomainDocument

from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS
from song_agent.domains.delivery.releases import stable_hash


OPERATIONS_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path"}


REPORT_HASH_EXCLUDE_KEYS = {"integrity_hash", "generated_at", "updated_at"}


def operations_report_integrity_hash(report: DomainDocument) -> str:
    return stable_hash({key: value for key, value in (report or {}).items() if key not in REPORT_HASH_EXCLUDE_KEYS})
