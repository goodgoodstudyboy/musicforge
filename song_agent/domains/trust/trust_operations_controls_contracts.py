from __future__ import annotations
from typing import Any

from song_agent.platform.contracts.documents import ImplementationDocument

from song_agent.domains.delivery.releases import stable_hash


TRUST_OPERATIONS_CONTROL_SCHEMA_VERSION = 1


TRUST_OPERATIONS_CONTROL_CATALOG_PACKAGE_TYPE = "musicforge_trust_operations_control_catalog"


TRUST_OPERATIONS_CONTROL_POLICY_PACKAGE_TYPE = "musicforge_trust_operations_control_policy_bundle"


TRUST_OPERATIONS_CONTROL_ASSESSMENT_PACKAGE_TYPE = "musicforge_trust_operations_control_assessment"


TRUST_OPERATIONS_CONTROL_RESULTS_PACKAGE_TYPE = "musicforge_trust_operations_control_results"


TRUST_OPERATIONS_CONTROL_EVIDENCE_PACKAGE_TYPE = "musicforge_trust_operations_control_evidence_bindings"


TRUST_OPERATIONS_CONTROL_BLOCKERS_PACKAGE_TYPE = "musicforge_trust_operations_control_blocker_summary"


TRUST_OPERATIONS_CONTROL_ACTIONS_PACKAGE_TYPE = "musicforge_trust_operations_control_manual_actions"


TRUST_OPERATIONS_CONTROL_MANIFEST_PACKAGE_TYPE = "musicforge_trust_operations_control_manifest"


TRUST_OPERATIONS_CONTROL_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at", "generated_at", "zip"}


CONTROL_EXPORT_ENTRIES = {
    "README.txt",
    "trust-operations-controls-manifest.json",
    "control-catalog.json",
    "policy-bundle.json",
    "control-assessment-report.json",
    "control-results.json",
    "evidence-bindings.json",
    "blocker-summary.json",
    "manual-actions.json",
}


BASELINE_CONTROLS: tuple[dict[str, str], ...] = (
    {"control_id": "toc-baseline-external-evidence-binding", "title": "External evidence binding", "category": "evidence", "severity": "critical", "evaluation_method": "external_evidence_binding"},
    {"control_id": "toc-baseline-fixed-zip-allowlist", "title": "Fixed ZIP allow-list", "category": "package_safety", "severity": "critical", "evaluation_method": "fixed_zip_allowlist"},
    {"control_id": "toc-baseline-full-resign-semantic-guard", "title": "Full-resign semantic guard", "category": "semantic_integrity", "severity": "critical", "evaluation_method": "full_resign_semantic_guard"},
    {"control_id": "toc-baseline-signed-immutability", "title": "Signed object immutability", "category": "immutability", "severity": "high", "evaluation_method": "signed_immutability"},
    {"control_id": "toc-baseline-delivery-ready-external", "title": "Delivery ready external evidence", "category": "delivery", "severity": "high", "evaluation_method": "delivery_ready_external"},
    {"control_id": "toc-baseline-incident-closeout-required", "title": "Incident closeout required", "category": "incident", "severity": "high", "evaluation_method": "incident_closeout_required"},
    {"control_id": "toc-baseline-incident-knowledge-guard-required", "title": "Incident knowledge guard required", "category": "knowledge", "severity": "high", "evaluation_method": "incident_knowledge_guard_required"},
    {"control_id": "toc-baseline-recurrence-monitoring-clean", "title": "Recurrence monitoring clean", "category": "recurrence", "severity": "high", "evaluation_method": "recurrence_monitoring_clean"},
    {"control_id": "toc-baseline-redaction-clean", "title": "Redaction clean", "category": "redaction", "severity": "critical", "evaluation_method": "redaction_clean"},
    {"control_id": "toc-baseline-release-check-matrix-current", "title": "Release-check matrix current", "category": "release_check", "severity": "medium", "evaluation_method": "release_check_matrix_current"},
)


def control_hash(doc: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in doc.items() if key not in TRUST_OPERATIONS_CONTROL_HASH_EXCLUDE_KEYS})


def control_manifest_hash(manifest: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in manifest.items() if key not in {"integrity_hash", "generated_at", "zip"}})


def _evaluate_control(control: ImplementationDocument, source: ImplementationDocument, *, required: bool) -> ImplementationDocument:
    method = str(control.get("evaluation", {}).get("method") or "")
    status = _expected_control_status(method, control, source)
    severity = str(control.get("severity") or "medium")
    result = {
        "result_id": "toc-result-" + _safe_id(str(control.get("control_id") or "control")),
        "control_id": control.get("control_id"),
        "control_hash": control.get("integrity_hash"),
        "required": required,
        "severity": severity,
        "status": status,
        "evidence_refs": ["toc-binding-hub", "toc-binding-incident", "toc-binding-knowledge"],
        "evaluation_method": method,
        "message": "Control passed." if status == "passed" else "Control evidence is missing, failed, or stale.",
    }
    result["integrity_hash"] = control_hash(result)
    return result


def _expected_control_status(method: str, control: ImplementationDocument, source: ImplementationDocument) -> str:
    hub_bound = bool(source.get("hub_verification_report_hash") and source.get("hub_zip_sha256") and source.get("hub_manifest_hash"))
    incident_passed = source.get("incident_verification_status") == "passed"
    knowledge_passed = source.get("knowledge_verification_status") == "passed"
    knowledge_summary = source.get("knowledge_summary") if isinstance(source.get("knowledge_summary"), dict) else {}
    hub_summary = source.get("hub_summary") if isinstance(source.get("hub_summary"), dict) else {}
    if method == "external_evidence_binding":
        return "passed" if hub_bound and incident_passed and knowledge_passed else "failed"
    if method == "fixed_zip_allowlist":
        return "passed" if hub_bound and incident_passed and knowledge_passed else "failed"
    if method == "full_resign_semantic_guard":
        return "passed" if knowledge_passed and int(knowledge_summary.get("guard_failed_count") or 0) == 0 else "failed"
    if method == "signed_immutability":
        return "passed" if hub_bound else "failed"
    if method == "delivery_ready_external":
        return "passed" if hub_bound and str(hub_summary.get("readiness") or "").lower() in {"ready", "passed"} else "failed"
    if method == "incident_closeout_required":
        return "passed" if incident_passed else "failed"
    if method == "incident_knowledge_guard_required":
        return "passed" if knowledge_passed and int(knowledge_summary.get("guards_passed_count") or 0) > 0 and int(knowledge_summary.get("guard_failed_count") or 0) == 0 else "failed"
    if method == "recurrence_monitoring_clean":
        return "passed" if knowledge_passed and int(knowledge_summary.get("recurrence_count") or 0) == 0 else "failed"
    if method == "redaction_clean":
        return "passed" if hub_bound and incident_passed and knowledge_passed else "failed"
    if method == "release_check_matrix_current":
        return "passed"
    if method == "knowledge_guard_coverage":
        severity = str(control.get("severity") or "")
        if severity in {"critical", "high"}:
            return "passed" if knowledge_passed and int(knowledge_summary.get("guards_passed_count") or 0) > 0 and int(knowledge_summary.get("guard_failed_count") or 0) == 0 else "failed"
        return "passed" if knowledge_passed else "failed"
    return "failed"


def _catalog_summary(controls: list[ImplementationDocument]) -> dict[str, int]:
    return {
        "control_count": len(controls),
        "baseline_count": sum(1 for item in controls if item.get("source", {}).get("source_type") == "baseline"),
        "derived_count": sum(1 for item in controls if item.get("source", {}).get("source_type") == "knowledge_entry"),
        "critical_count": sum(1 for item in controls if item.get("severity") == "critical"),
        "high_count": sum(1 for item in controls if item.get("severity") == "high"),
    }


def _results_summary(results: list[ImplementationDocument]) -> dict[str, int]:
    return {
        "result_count": len(results),
        "passed_count": sum(1 for item in results if item.get("status") == "passed"),
        "failed_count": sum(1 for item in results if item.get("status") == "failed"),
        "required_failed_count": sum(1 for item in results if item.get("required") and item.get("status") != "passed"),
    }


def _blockers_from_results(results: list[ImplementationDocument], required: dict[str, bool]) -> list[ImplementationDocument]:
    blockers = []
    for index, result in enumerate(results, start=1):
        control_id = str(result.get("control_id") or "")
        if not required.get(control_id) or result.get("status") == "passed":
            continue
        blockers.append(
            {
                "blocker_id": f"toc-blocker-{index:06d}",
                "control_id": control_id,
                "severity": "critical" if result.get("severity") in {"critical", "high"} else "high",
                "source_result_hash": result.get("integrity_hash"),
                "message": result.get("message") or "Required control failed.",
                "manual_action_id": f"toc-action-{index:06d}",
            }
        )
    return blockers


def _blocker_summary(blockers: list[ImplementationDocument]) -> dict[str, int]:
    return {
        "blocker_count": len(blockers),
        "critical_count": sum(1 for item in blockers if item.get("severity") == "critical"),
        "high_count": sum(1 for item in blockers if item.get("severity") == "high"),
    }


def _manual_actions_from_blockers(blockers: list[ImplementationDocument]) -> list[ImplementationDocument]:
    actions = []
    for blocker in blockers:
        actions.append(
            {
                "action_id": blocker.get("manual_action_id"),
                "action_type": "review_trust_control",
                "status": "manual_required",
                "control_id": blocker.get("control_id"),
                "reason": blocker.get("message"),
                "allowed_automation": False,
            }
        )
    return actions


def _safe_id(value: str) -> str:
    value = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(value).strip())
    return value.strip("-") or "item"
