from __future__ import annotations

from song_agent.domains.delivery.releases import stable_hash


TRUST_OPERATIONS_KNOWLEDGE_SCHEMA_VERSION = 1


TRUST_OPERATIONS_KNOWLEDGE_BASE_PACKAGE_TYPE = "musicforge_trust_operations_incident_knowledge_base"


TRUST_OPERATIONS_KNOWLEDGE_REPORT_PACKAGE_TYPE = "musicforge_trust_operations_incident_knowledge_report"


TRUST_OPERATIONS_KNOWLEDGE_ENTRIES_PACKAGE_TYPE = "musicforge_trust_operations_incident_knowledge_entries"


TRUST_OPERATIONS_REGRESSION_GUARDS_PACKAGE_TYPE = "musicforge_trust_operations_incident_regression_guards"


TRUST_OPERATIONS_GUARD_RUN_SUMMARY_PACKAGE_TYPE = "musicforge_trust_operations_incident_guard_run_summary"


TRUST_OPERATIONS_RECURRENCE_REPORT_PACKAGE_TYPE = "musicforge_trust_operations_incident_recurrence_report"


TRUST_OPERATIONS_KNOWLEDGE_SOURCE_PACKAGE_TYPE = "musicforge_trust_operations_incident_knowledge_source_summary"


TRUST_OPERATIONS_KNOWLEDGE_MANIFEST_PACKAGE_TYPE = "musicforge_trust_operations_incident_knowledge_manifest"


TRUST_OPERATIONS_KNOWLEDGE_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at", "generated_at", "zip"}


KNOWLEDGE_EXPORT_ENTRIES = {
    "README.txt",
    "knowledge-base.json",
    "knowledge-report.json",
    "entries.json",
    "regression-guards.json",
    "guard-run-summary.json",
    "recurrence-report.json",
    "source-summary.json",
    "trust-operations-knowledge-manifest.json",
}


def knowledge_hash(doc: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in doc.items() if key not in TRUST_OPERATIONS_KNOWLEDGE_HASH_EXCLUDE_KEYS})


def knowledge_manifest_hash(manifest: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})


def _classify_incident(incident: dict[str, Any]) -> dict[str, str]:
    detected = incident.get("detected_from") if isinstance(incident.get("detected_from"), dict) else {}
    check_id = str(detected.get("check_id") or incident.get("category") or "").lower()
    category = str(incident.get("category") or "").lower()
    if "component_coverage" in check_id or "missing" in check_id:
        return {
            "failure_mode": "incomplete_component_coverage",
            "root_cause": "external_verification_report_missing",
            "preventive_pattern": "require one current external report per delivery component",
            "guard_type": "external_report_coverage",
            "guard_title": "Verify external report coverage for all delivery components",
            "guard_reason": "The incident was caused by missing external verification coverage.",
        }
    if "redaction" in check_id or "redaction" in category:
        return {
            "failure_mode": "sensitive_payload_leak",
            "root_cause": "redaction_guard_missing",
            "preventive_pattern": "rerun redaction scan before Hub signoff",
            "guard_type": "redaction_regression",
            "guard_title": "Check redaction blockers do not recur",
            "guard_reason": "The incident involved sensitive data exposure risk.",
        }
    if any(marker in check_id for marker in ("zip", "duplicate", "backslash", "path")):
        return {
            "failure_mode": "unsafe_package_structure",
            "root_cause": "zip_safety_guard_missing",
            "preventive_pattern": "run fixed ZIP allow-list and path checks",
            "guard_type": "zip_safety_regression",
            "guard_title": "Check ZIP safety blockers do not recur",
            "guard_reason": "The incident involved package structure safety.",
        }
    return {
        "failure_mode": "external_evidence_binding_gap",
        "root_cause": "manual_review_required",
        "preventive_pattern": "review the same evidence binding before release",
        "guard_type": "external_report_binding",
        "guard_title": "Verify external evidence binding remains current",
        "guard_reason": "The incident involved external evidence binding.",
    }
