from __future__ import annotations
from typing import Any

from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS
from song_agent.domains.delivery.releases import stable_hash


OPERATIONS_SIGNOFF_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path"}


OPERATIONS_SIGNOFF_HASH_EXCLUDE_KEYS = {"payload_hash", "export_manifest_hash", "updated_at"}


OPERATIONS_CHANGE_REQUEST_HASH_EXCLUDE_KEYS = {"integrity_hash", "updated_at"}


OPERATIONS_ARCHIVE_HASH_EXCLUDE_KEYS = {"integrity_hash", "generated_at", "updated_at"}


def operations_signoff_hash(signoff: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (signoff or {}).items() if key not in OPERATIONS_SIGNOFF_HASH_EXCLUDE_KEYS})


def operations_change_request_hash(item: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (item or {}).items() if key not in OPERATIONS_CHANGE_REQUEST_HASH_EXCLUDE_KEYS})


def operations_change_request_integrity_ok(item: dict[str, Any] | None) -> bool:
    data = item if isinstance(item, dict) else {}
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == operations_change_request_hash(data)


def operations_archive_manifest_hash(manifest: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (manifest or {}).items() if key not in OPERATIONS_ARCHIVE_HASH_EXCLUDE_KEYS})
