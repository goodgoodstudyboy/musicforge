from __future__ import annotations
from typing import Any

from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS
from song_agent.domains.delivery.releases import stable_hash


TRUST_OPERATIONS_CONTROL_SIGNOFF_SCHEMA_VERSION = 1


TRUST_OPERATIONS_CONTROL_SIGNOFF_PACKAGE_TYPE = "musicforge_trust_operations_control_signoff"


TRUST_OPERATIONS_CONTROL_EXCEPTION_PACKAGE_TYPE = "musicforge_trust_operations_control_exception"


TRUST_OPERATIONS_CONTROL_CHANGE_REQUEST_PACKAGE_TYPE = "musicforge_trust_operations_control_change_request"


TRUST_OPERATIONS_CONTROL_SIGNOFF_REPORT_PACKAGE_TYPE = "musicforge_trust_operations_control_signoff_report"


TRUST_OPERATIONS_CONTROL_SIGNOFF_SOURCE_PACKAGE_TYPE = "musicforge_trust_operations_control_signoff_source_verification"


TRUST_OPERATIONS_CONTROL_SIGNOFF_MANIFEST_PACKAGE_TYPE = "musicforge_trust_operations_control_signoff_manifest"


TRUST_OPERATIONS_CONTROL_SIGNOFF_EXCEPTIONS_PACKAGE_TYPE = "musicforge_trust_operations_control_signoff_exceptions"


TRUST_OPERATIONS_CONTROL_SIGNOFF_CHANGE_REQUESTS_PACKAGE_TYPE = "musicforge_trust_operations_control_signoff_change_requests"


TRUST_OPERATIONS_CONTROL_SIGNOFF_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at", "generated_at", "zip"}


TRUST_OPERATIONS_CONTROL_SIGNOFF_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path", "file"}


CONTROL_SIGNOFF_ARCHIVE_ENTRIES = {
    "README.txt",
    "trust-operations-control-signoff-manifest.json",
    "control-signoff.json",
    "control-signoff-history.jsonl",
    "control-exceptions.json",
    "control-change-requests.json",
    "control-signoff-report.json",
    "source-verification-summary.json",
}


def control_signoff_hash(doc: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in doc.items() if key not in TRUST_OPERATIONS_CONTROL_SIGNOFF_HASH_EXCLUDE_KEYS})


def control_signoff_manifest_hash(doc: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in doc.items() if key not in {"integrity_hash", "generated_at", "zip"}})
