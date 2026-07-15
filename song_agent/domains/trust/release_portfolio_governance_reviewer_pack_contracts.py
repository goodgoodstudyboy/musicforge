from __future__ import annotations

from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS
from song_agent.domains.delivery.releases import stable_hash


PORTFOLIO_GOVERNANCE_REVIEWER_PACK_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path"}


REVIEWER_REPORT_HASH_EXCLUDE_KEYS = {"integrity_hash", "generated_at", "updated_at"}


RETROSPECTIVE_REPORT_HASH_EXCLUDE_KEYS = {"integrity_hash", "generated_at", "updated_at"}


EVIDENCE_INDEX_HASH_EXCLUDE_KEYS = {"integrity_hash", "generated_at", "updated_at"}


TIMELINE_HASH_EXCLUDE_KEYS = {"integrity_hash", "generated_at", "updated_at"}


REVIEWER_PACK_MANIFEST_HASH_EXCLUDE_KEYS = {"integrity_hash", "generated_at", "updated_at"}


def reviewer_report_integrity_hash(report: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (report or {}).items() if key not in REVIEWER_REPORT_HASH_EXCLUDE_KEYS})


def retrospective_report_integrity_hash(report: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (report or {}).items() if key not in RETROSPECTIVE_REPORT_HASH_EXCLUDE_KEYS})


def evidence_index_integrity_hash(index: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (index or {}).items() if key not in EVIDENCE_INDEX_HASH_EXCLUDE_KEYS})


def timeline_integrity_hash(timeline: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (timeline or {}).items() if key not in TIMELINE_HASH_EXCLUDE_KEYS})


def reviewer_pack_manifest_integrity_hash(manifest: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (manifest or {}).items() if key not in REVIEWER_PACK_MANIFEST_HASH_EXCLUDE_KEYS})
