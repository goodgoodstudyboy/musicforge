from __future__ import annotations
from typing import Any

from song_agent.domains.legacy_documents import ImplementationDocument

from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS
from song_agent.domains.delivery.releases import stable_hash


OPERATIONS_AUDIT_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path"}


AUDIT_ENTRY_HASH_EXCLUDE_KEYS = {"entry_hash"}


AUDIT_REPORT_HASH_EXCLUDE_KEYS = {"integrity_hash", "generated_at", "updated_at"}


AUDIT_MANIFEST_HASH_EXCLUDE_KEYS = {"integrity_hash", "generated_at", "updated_at"}


def audit_entry_hash(entry: dict[str, Any]) -> str:
    return stable_hash(_entry_hash_payload(entry))


def audit_report_integrity_hash(report: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (report or {}).items() if key not in AUDIT_REPORT_HASH_EXCLUDE_KEYS})


def audit_manifest_integrity_hash(manifest: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (manifest or {}).items() if key not in AUDIT_MANIFEST_HASH_EXCLUDE_KEYS})


def audit_ledger_hash(entries: list[dict[str, Any]]) -> str:
    return stable_hash([entry.get("entry_hash") for entry in entries])


def audit_ledger_integrity_ok(entries: list[dict[str, Any]]) -> bool:
    previous: str | None = None
    seen: set[str] = set()
    for index, entry in enumerate(entries, start=1):
        if int(entry.get("sequence") or 0) != index:
            return False
        if entry.get("previous_hash") != previous:
            return False
        actual = audit_entry_hash(entry)
        if entry.get("entry_hash") != actual or actual in seen:
            return False
        seen.add(actual)
        previous = actual
    return True


def _entry_hash_payload(entry: ImplementationDocument) -> ImplementationDocument:
    return {key: value for key, value in (entry or {}).items() if key not in AUDIT_ENTRY_HASH_EXCLUDE_KEYS}
