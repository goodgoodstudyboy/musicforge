from __future__ import annotations

from song_agent.platform.contracts import DomainDocument

from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS
from song_agent.domains.delivery.releases import stable_hash


RUNBOOK_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path"}


RUNBOOK_HASH_EXCLUDE_KEYS = {"integrity_hash", "updated_at"}


EXECUTION_REPORT_HASH_EXCLUDE_KEYS = {"integrity_hash", "generated_at", "updated_at"}


def runbook_integrity_hash(runbook: DomainDocument) -> str:
    return stable_hash({key: value for key, value in (runbook or {}).items() if key not in RUNBOOK_HASH_EXCLUDE_KEYS})


def execution_report_integrity_hash(report: DomainDocument) -> str:
    return stable_hash({key: value for key, value in (report or {}).items() if key not in EXECUTION_REPORT_HASH_EXCLUDE_KEYS})
