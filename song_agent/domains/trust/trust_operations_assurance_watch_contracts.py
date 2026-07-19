from __future__ import annotations
from typing import Any

from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS
from song_agent.domains.delivery.releases import stable_hash


TRUST_OPERATIONS_ASSURANCE_WATCH_SCHEMA_VERSION = 1


TRUST_OPERATIONS_ASSURANCE_WATCH_SCHEDULE_PACKAGE_TYPE = "musicforge_trust_operations_assurance_schedule"


TRUST_OPERATIONS_ASSURANCE_WATCH_QUEUE_PACKAGE_TYPE = "musicforge_trust_operations_assurance_watch_queue"


TRUST_OPERATIONS_ASSURANCE_WATCH_RUN_INDEX_PACKAGE_TYPE = "musicforge_trust_operations_assurance_run_index"


TRUST_OPERATIONS_ASSURANCE_WATCH_ACTION_PACK_PACKAGE_TYPE = "musicforge_trust_operations_assurance_drift_action_pack"


TRUST_OPERATIONS_ASSURANCE_WATCH_EXTERNAL_SUMMARY_PACKAGE_TYPE = "musicforge_trust_operations_assurance_watch_external_summary"


TRUST_OPERATIONS_ASSURANCE_WATCH_MANIFEST_PACKAGE_TYPE = "musicforge_trust_operations_assurance_watch_manifest"


TRUST_OPERATIONS_ASSURANCE_WATCH_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at", "generated_at", "zip"}


TRUST_OPERATIONS_ASSURANCE_WATCH_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path", "file"}


ASSURANCE_WATCH_ARCHIVE_ENTRIES = {
    "README.txt",
    "trust-operations-assurance-watch-manifest.json",
    "watch-queue.json",
    "schedule-snapshot.json",
    "assurance-run-index.json",
    "drift-action-pack.json",
    "external-verification-summary.json",
    "watch-history.jsonl",
}


def watch_hash(doc: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in doc.items() if key not in TRUST_OPERATIONS_ASSURANCE_WATCH_HASH_EXCLUDE_KEYS})


def watch_manifest_hash(manifest: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in manifest.items() if key not in {"integrity_hash", "generated_at", "zip"}})
