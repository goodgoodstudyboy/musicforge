from __future__ import annotations

from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS
from song_agent.domains.delivery.releases import stable_hash


FINAL_BOARD_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path"}


FINAL_BOARD_REPORT_HASH_EXCLUDE_KEYS = {"integrity_hash", "generated_at", "updated_at"}


FINAL_BOARD_SIGNOFF_HASH_EXCLUDE_KEYS = {"integrity_hash", "updated_at"}


FINAL_BOARD_RESPONSE_HASH_EXCLUDE_KEYS = {"integrity_hash", "imported_at", "updated_at"}


FINAL_BOARD_CHANGE_REQUEST_HASH_EXCLUDE_KEYS = {"integrity_hash", "updated_at"}


FINAL_BOARD_ARCHIVE_MANIFEST_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at", "zip"}


def final_board_report_integrity_hash(report: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (report or {}).items() if key not in FINAL_BOARD_REPORT_HASH_EXCLUDE_KEYS})


def final_board_response_integrity_hash(response: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (response or {}).items() if key not in FINAL_BOARD_RESPONSE_HASH_EXCLUDE_KEYS})


def final_board_signoff_hash(signoff: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (signoff or {}).items() if key not in FINAL_BOARD_SIGNOFF_HASH_EXCLUDE_KEYS})


def final_board_change_request_hash(item: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (item or {}).items() if key not in FINAL_BOARD_CHANGE_REQUEST_HASH_EXCLUDE_KEYS})


def final_board_change_request_integrity_ok(item: dict[str, Any] | None) -> bool:
    data = item if isinstance(item, dict) else {}
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == final_board_change_request_hash(data)


def final_board_archive_manifest_hash(manifest: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (manifest or {}).items() if key not in FINAL_BOARD_ARCHIVE_MANIFEST_HASH_EXCLUDE_KEYS})
