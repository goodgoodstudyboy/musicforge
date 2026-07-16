from __future__ import annotations
from typing import Any

from song_agent.domains.delivery.releases import stable_hash


TRUST_OPERATIONS_INCIDENT_SCHEMA_VERSION = 1


TRUST_OPERATIONS_INCIDENT_BOARD_PACKAGE_TYPE = "musicforge_trust_operations_hub_incident_board"


TRUST_OPERATIONS_INCIDENT_MANIFEST_PACKAGE_TYPE = "musicforge_trust_operations_hub_incident_manifest"


TRUST_OPERATIONS_INCIDENT_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at", "generated_at", "zip"}


INCIDENT_EXPORT_ENTRIES = {
    "README.txt",
    "incident-board.json",
    "incident-board-report.json",
    "incident-source-summary.json",
    "incidents.json",
    "incident-events.jsonl",
    "remediation-plans.json",
    "remediation-results.json",
    "evidence-index.json",
    "closeout-summary.json",
    "trust-operations-incident-manifest.json",
}


def incident_hash(doc: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in doc.items() if key not in TRUST_OPERATIONS_INCIDENT_HASH_EXCLUDE_KEYS})


def incident_manifest_hash(manifest: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in manifest.items() if key not in {"integrity_hash", "generated_at", "zip"}})
