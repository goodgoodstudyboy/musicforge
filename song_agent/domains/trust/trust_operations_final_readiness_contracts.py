from __future__ import annotations

from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS
from song_agent.domains.delivery.releases import stable_hash


TRUST_OPERATIONS_FINAL_READINESS_SCHEMA_VERSION = 1


TRUST_OPERATIONS_FINAL_READINESS_REPORT_PACKAGE_TYPE = "musicforge_trust_operations_final_readiness_report"


TRUST_OPERATIONS_FINAL_READINESS_CERTIFICATE_PACKAGE_TYPE = "musicforge_trust_operations_final_readiness_certificate"


TRUST_OPERATIONS_FINAL_EVIDENCE_INDEX_PACKAGE_TYPE = "musicforge_trust_operations_final_evidence_index"


TRUST_OPERATIONS_FINAL_HANDOFF_SIGNOFF_PACKAGE_TYPE = "musicforge_trust_operations_final_handoff_signoff"


TRUST_OPERATIONS_FINAL_HANDOFF_CHANGE_REQUESTS_PACKAGE_TYPE = "musicforge_trust_operations_final_handoff_change_requests"


TRUST_OPERATIONS_FINAL_READINESS_MANIFEST_PACKAGE_TYPE = "musicforge_trust_operations_final_readiness_manifest"


TRUST_OPERATIONS_FINAL_READINESS_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at", "generated_at", "zip"}


TRUST_OPERATIONS_FINAL_READINESS_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path", "file"}


FINAL_READINESS_EXPORT_ENTRIES = {
    "README.txt",
    "trust-operations-final-readiness-manifest.json",
    "final-readiness-report.json",
    "final-readiness-certificate.json",
    "final-evidence-index.json",
    "final-handoff-signoff.json",
    "final-handoff-history.jsonl",
    "change-requests.json",
    "verification-summaries/hub-verification-summary.json",
    "verification-summaries/delivery-verification-summary.json",
    "verification-summaries/incident-verification-summary.json",
    "verification-summaries/incident-knowledge-verification-summary.json",
    "verification-summaries/control-verification-summary.json",
    "verification-summaries/control-signoff-verification-summary.json",
    "verification-summaries/continuous-assurance-verification-summary.json",
    "verification-summaries/assurance-watch-verification-summary.json",
    "verification-summaries/assurance-watch-signoff-verification-summary.json",
}


FINAL_READINESS_SINGLE_SPECS = (
    {
        "component_type": "hub",
        "component_id": "hub",
        "payload_path": "hub_package_path",
        "payload_report": "hub_verification_report_path",
        "summary_path": "verification-summaries/hub-verification-summary.json",
        "package_type": "musicforge_trust_operations_hub",
        "verification_package_type": "musicforge_trust_operations_hub_verification",
        "manifest_entry": "trust-operations-hub-manifest.json",
    },
    {
        "component_type": "incident",
        "component_id": "incident",
        "payload_path": "incident_board_package_path",
        "payload_report": "incident_board_verification_report_path",
        "summary_path": "verification-summaries/incident-verification-summary.json",
        "package_type": "musicforge_trust_operations_incident_board",
        "verification_package_type": "musicforge_trust_operations_hub_incident_verification",
        "manifest_entry": "trust-operations-incident-manifest.json",
    },
    {
        "component_type": "incident_knowledge",
        "component_id": "incident_knowledge",
        "payload_path": "incident_knowledge_package_path",
        "payload_report": "incident_knowledge_verification_report_path",
        "summary_path": "verification-summaries/incident-knowledge-verification-summary.json",
        "package_type": "musicforge_trust_operations_incident_knowledge",
        "verification_package_type": "musicforge_trust_operations_incident_knowledge_verification",
        "manifest_entry": "trust-operations-knowledge-manifest.json",
    },
    {
        "component_type": "control",
        "component_id": "control",
        "payload_path": "control_assessment_package_path",
        "payload_report": "control_verification_report_path",
        "summary_path": "verification-summaries/control-verification-summary.json",
        "package_type": "musicforge_trust_operations_control_package",
        "verification_package_type": "musicforge_trust_operations_control_verification",
        "manifest_entry": "trust-operations-controls-manifest.json",
    },
    {
        "component_type": "control_signoff",
        "component_id": "control_signoff",
        "payload_path": "control_signoff_archive_path",
        "payload_report": "control_signoff_verification_report_path",
        "summary_path": "verification-summaries/control-signoff-verification-summary.json",
        "package_type": "musicforge_trust_operations_control_signoff_archive",
        "verification_package_type": "musicforge_trust_operations_control_signoff_verification",
        "manifest_entry": "trust-operations-control-signoff-manifest.json",
    },
    {
        "component_type": "continuous_assurance",
        "component_id": "continuous_assurance",
        "payload_path": "continuous_assurance_archive_path",
        "payload_report": "continuous_assurance_verification_report_path",
        "summary_path": "verification-summaries/continuous-assurance-verification-summary.json",
        "package_type": "musicforge_trust_operations_continuous_assurance_archive",
        "verification_package_type": "musicforge_trust_operations_continuous_assurance_verification",
        "manifest_entry": "trust-operations-assurance-manifest.json",
    },
    {
        "component_type": "assurance_watch",
        "component_id": "assurance_watch",
        "payload_path": "assurance_watch_package_path",
        "payload_report": "assurance_watch_verification_report_path",
        "summary_path": "verification-summaries/assurance-watch-verification-summary.json",
        "package_type": "musicforge_trust_operations_assurance_watch",
        "verification_package_type": "musicforge_trust_operations_assurance_watch_verification",
        "manifest_entry": "trust-operations-assurance-watch-manifest.json",
    },
    {
        "component_type": "assurance_watch_signoff",
        "component_id": "assurance_watch_signoff",
        "payload_path": "assurance_watch_signoff_archive_path",
        "payload_report": "assurance_watch_signoff_verification_report_path",
        "summary_path": "verification-summaries/assurance-watch-signoff-verification-summary.json",
        "package_type": "musicforge_trust_operations_assurance_watch_signoff_archive",
        "verification_package_type": "musicforge_trust_operations_assurance_watch_signoff_verification",
        "manifest_entry": "trust-operations-assurance-watch-signoff-manifest.json",
    },
)


def final_readiness_hash(doc: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in doc.items() if key not in TRUST_OPERATIONS_FINAL_READINESS_HASH_EXCLUDE_KEYS})


def final_readiness_manifest_hash(doc: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in doc.items() if key not in {"integrity_hash", "generated_at", "zip"}})


def final_readiness_history_event_payload_hash(event: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in event.items() if key not in {"payload_hash", "event_hash"}})


def final_readiness_history_event_hash(event: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in event.items() if key != "event_hash"})


def final_readiness_history_hash(events: list[dict[str, Any]]) -> str:
    return stable_hash({"events": events})
