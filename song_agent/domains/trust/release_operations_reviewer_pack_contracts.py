from __future__ import annotations

from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS
from song_agent.domains.delivery.releases import stable_hash


REVIEWER_PACK_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path"}


REVIEWER_REPORT_HASH_EXCLUDE_KEYS = {"integrity_hash", "generated_at", "updated_at"}


REVIEWER_PACK_MANIFEST_HASH_EXCLUDE_KEYS = {"integrity_hash", "generated_at", "updated_at"}


def reviewer_report_integrity_hash(report: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (report or {}).items() if key not in REVIEWER_REPORT_HASH_EXCLUDE_KEYS})


def reviewer_pack_manifest_integrity_hash(manifest: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (manifest or {}).items() if key not in REVIEWER_PACK_MANIFEST_HASH_EXCLUDE_KEYS})
