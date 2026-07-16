from __future__ import annotations
from typing import Any

from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS
from song_agent.domains.delivery.releases import stable_hash


TRUST_OPERATIONS_ASSURANCE_SCHEMA_VERSION = 1


TRUST_OPERATIONS_ASSURANCE_POLICY_PACKAGE_TYPE = "musicforge_trust_operations_assurance_policy"


TRUST_OPERATIONS_ASSURANCE_RUN_PACKAGE_TYPE = "musicforge_trust_operations_continuous_assurance_run"


TRUST_OPERATIONS_ASSURANCE_REPORT_PACKAGE_TYPE = "musicforge_trust_operations_continuous_assurance_report"


TRUST_OPERATIONS_ASSURANCE_EVIDENCE_PACKAGE_TYPE = "musicforge_trust_operations_continuous_assurance_evidence_index"


TRUST_OPERATIONS_ASSURANCE_EXTERNAL_SUMMARY_PACKAGE_TYPE = "musicforge_trust_operations_continuous_assurance_external_verification_summary"


TRUST_OPERATIONS_ASSURANCE_MANIFEST_PACKAGE_TYPE = "musicforge_trust_operations_continuous_assurance_manifest"


TRUST_OPERATIONS_ASSURANCE_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at", "generated_at", "zip"}


TRUST_OPERATIONS_ASSURANCE_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path", "file"}


ASSURANCE_ARCHIVE_ENTRIES = {
    "README.txt",
    "trust-operations-assurance-manifest.json",
    "assurance-run.json",
    "assurance-report.json",
    "assurance-policy.json",
    "evidence-index.json",
    "external-verification-summary.json",
    "assurance-history.jsonl",
}


CORE_EVIDENCE_SPECS = {
    "hub": {
        "archive_key": "hub_package_path",
        "report_key": "hub_verification_report_path",
        "manifest_entry": "trust-operations-hub-manifest.json",
        "package_type": "musicforge_trust_operations_hub_verification",
        "required": True,
    },
    "control_signoff": {
        "archive_key": "control_signoff_archive_path",
        "report_key": "control_signoff_verification_report_path",
        "manifest_entry": "trust-operations-control-signoff-manifest.json",
        "package_type": "musicforge_trust_operations_control_signoff_verification",
        "required": True,
    },
    "control": {
        "archive_key": "control_package_path",
        "report_key": "control_verification_report_path",
        "manifest_entry": "trust-operations-controls-manifest.json",
        "package_type": "musicforge_trust_operations_control_verification",
        "required": True,
    },
    "incident": {
        "archive_key": "incident_board_package_path",
        "report_key": "incident_board_verification_report_path",
        "manifest_entry": "trust-operations-incident-manifest.json",
        "package_type": "musicforge_trust_operations_hub_incident_verification",
        "required": True,
    },
    "knowledge": {
        "archive_key": "incident_knowledge_package_path",
        "report_key": "incident_knowledge_verification_report_path",
        "manifest_entry": "trust-operations-knowledge-manifest.json",
        "package_type": "musicforge_trust_operations_incident_knowledge_verification",
        "required": True,
    },
}


def assurance_hash(doc: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in doc.items() if key not in TRUST_OPERATIONS_ASSURANCE_HASH_EXCLUDE_KEYS})


def assurance_manifest_hash(manifest: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in manifest.items() if key not in {"integrity_hash", "generated_at", "zip"}})
