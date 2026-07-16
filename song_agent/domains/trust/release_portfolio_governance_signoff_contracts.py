from __future__ import annotations
from typing import Any

from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS
from song_agent.domains.trust.release_portfolio_governance_contracts import PORTFOLIO_GOVERNANCE_BLOCKED_KEYS
from song_agent.domains.delivery.releases import stable_hash


PORTFOLIO_GOVERNANCE_SIGNOFF_BLOCKED_KEYS = PORTFOLIO_GOVERNANCE_BLOCKED_KEYS | (DEFAULT_BLOCKED_METADATA_KEYS - {"path"})


SIGNOFF_HASH_EXCLUDE_KEYS = {"integrity_hash", "updated_at"}


CHANGE_REQUEST_HASH_EXCLUDE_KEYS = {"integrity_hash", "updated_at"}


ARCHIVE_MANIFEST_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at", "zip"}


def governance_signoff_hash(signoff: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (signoff or {}).items() if key not in SIGNOFF_HASH_EXCLUDE_KEYS})


def governance_change_request_hash(item: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (item or {}).items() if key not in CHANGE_REQUEST_HASH_EXCLUDE_KEYS})


def governance_change_request_integrity_ok(item: dict[str, Any] | None) -> bool:
    data = item if isinstance(item, dict) else {}
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == governance_change_request_hash(data)


def governance_archive_manifest_hash(manifest: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (manifest or {}).items() if key not in ARCHIVE_MANIFEST_HASH_EXCLUDE_KEYS})
