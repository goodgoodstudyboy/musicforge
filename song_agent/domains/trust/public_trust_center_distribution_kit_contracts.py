from __future__ import annotations

from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS
from song_agent.domains.delivery.releases import stable_hash


DISTRIBUTION_KIT_PACKAGE_TYPE = "musicforge_public_trust_center_distribution_kit"


DISTRIBUTION_KIT_MANIFEST_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at", "zip"}


DISTRIBUTION_KIT_REPORT_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at"}


DISTRIBUTION_KIT_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path", "file"}


def distribution_kit_report_hash(report: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (report or {}).items() if key not in DISTRIBUTION_KIT_REPORT_HASH_EXCLUDE_KEYS})


def distribution_kit_manifest_hash(manifest: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (manifest or {}).items() if key not in DISTRIBUTION_KIT_MANIFEST_HASH_EXCLUDE_KEYS})
