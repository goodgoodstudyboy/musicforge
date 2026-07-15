from __future__ import annotations

from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS
from song_agent.domains.delivery.releases import stable_hash


TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_SCHEMA_VERSION = 1


TRUST_OPERATIONS_ASSURANCE_WATCH_CLOSEOUT_PACKAGE_TYPE = "musicforge_trust_operations_assurance_watch_closeout"


TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_PACKAGE_TYPE = "musicforge_trust_operations_assurance_watch_signoff"


TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_REPORT_PACKAGE_TYPE = "musicforge_trust_operations_assurance_watch_signoff_report"


TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_SOURCE_PACKAGE_TYPE = "musicforge_trust_operations_assurance_watch_signoff_source"


TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_CHANGE_REQUESTS_PACKAGE_TYPE = "musicforge_trust_operations_assurance_watch_signoff_change_requests"


TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_MANIFEST_PACKAGE_TYPE = "musicforge_trust_operations_assurance_watch_signoff_manifest"


TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at", "generated_at", "zip"}


TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path", "file"}


ASSURANCE_WATCH_SIGNOFF_ARCHIVE_ENTRIES = {
    "README.txt",
    "trust-operations-assurance-watch-signoff-manifest.json",
    "watch-closeout.json",
    "watch-signoff.json",
    "watch-queue-summary.json",
    "drift-action-pack-summary.json",
    "external-verification-summary.json",
    "watch-signoff-history.jsonl",
    "change-requests.json",
}


def watch_signoff_hash(doc: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in doc.items() if key not in TRUST_OPERATIONS_ASSURANCE_WATCH_SIGNOFF_HASH_EXCLUDE_KEYS})


def watch_signoff_manifest_hash(doc: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in doc.items() if key not in {"integrity_hash", "generated_at", "zip"}})


def watch_signoff_history_event_payload_hash(event: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in event.items() if key not in {"payload_hash", "event_hash"}})


def watch_signoff_history_event_hash(event: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in event.items() if key != "event_hash"})
