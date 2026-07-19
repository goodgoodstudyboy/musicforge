from __future__ import annotations
from typing import Any

from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS
from song_agent.domains.delivery.releases import stable_hash


PUBLICATION_CHANNEL_STATE_PACKAGE_TYPE = "musicforge_public_trust_center_publication_channel_state"


PUBLICATION_PACKAGE_TYPE = "musicforge_public_trust_center_publication"


PUBLICATION_MANIFEST_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at", "zip"}


PUBLICATION_REPORT_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at"}


PUBLICATION_CHANNEL_STATE_HASH_EXCLUDE_KEYS = {"integrity_hash"}


PUBLICATION_SIDECAR_HASH_EXCLUDE_KEYS = {"integrity_hash"}


PUBLICATION_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path", "file"}


PUBLICATION_REQUIRED_PACKAGE_KEYS = {
    "public_trust_center",
    "distribution_kit",
    "anchor_registry",
    "anchor_transparency",
    "acceptance_board",
    "acceptance_board_signoff_archive",
}


def publication_channel_state_hash(state: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (state or {}).items() if key not in PUBLICATION_CHANNEL_STATE_HASH_EXCLUDE_KEYS})


def publication_report_hash(report: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (report or {}).items() if key not in PUBLICATION_REPORT_HASH_EXCLUDE_KEYS})


def publication_manifest_hash(manifest: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (manifest or {}).items() if key not in PUBLICATION_MANIFEST_HASH_EXCLUDE_KEYS})


def sidecar_hash(doc: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (doc or {}).items() if key not in PUBLICATION_SIDECAR_HASH_EXCLUDE_KEYS})
