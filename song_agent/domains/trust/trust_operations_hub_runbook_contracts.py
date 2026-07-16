from __future__ import annotations
from typing import Any

from song_agent.domains.delivery.releases import stable_hash


TRUST_OPERATIONS_RUNBOOK_SCHEMA_VERSION = 1


TRUST_OPERATIONS_RUNBOOK_PACKAGE_TYPE = "musicforge_trust_operations_hub_runbook"


TRUST_OPERATIONS_RUNBOOK_MANIFEST_PACKAGE_TYPE = "musicforge_trust_operations_hub_runbook_manifest"


TRUST_OPERATIONS_RUNBOOK_RESULT_PACKAGE_TYPE = "musicforge_trust_operations_hub_runbook_result"


TRUST_OPERATIONS_RUNBOOK_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at", "generated_at", "zip"}


RUNBOOK_EXPORT_ENTRIES = {
    "README.txt",
    "trust-operations-hub-runbook-manifest.json",
    "runbook.json",
    "runbook-result.json",
    "runbook-events.jsonl",
    "checksum/SHA256SUMS.json",
    "checksum/SHA256SUMS.txt",
}


def runbook_hash(doc: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in doc.items() if key not in TRUST_OPERATIONS_RUNBOOK_HASH_EXCLUDE_KEYS})
