# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list, as_path as _as_path
import base64 as base64
import json as json
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.projects import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.program.unified_command_center import UnifiedCommandCenterStore as UnifiedCommandCenterStore
from song_agent.domains.program.unified_command_center_archive_verifier import verify_unified_command_center_archive_package as verify_unified_command_center_archive_package, write_unified_command_center_archive_verification_report as write_unified_command_center_archive_verification_report
from song_agent.domains.program.unified_command_center_continuous_review import UnifiedCommandCenterContinuousReviewStore as UnifiedCommandCenterContinuousReviewStore
from song_agent.domains.program.unified_command_center_continuous_review_verifier import verify_unified_command_center_continuous_review_package as verify_unified_command_center_continuous_review_package, write_unified_command_center_continuous_review_verification_report as write_unified_command_center_continuous_review_verification_report
from song_agent.domains.program.unified_command_center_drift_response import UnifiedCommandCenterDriftResponseStore as UnifiedCommandCenterDriftResponseStore
from song_agent.domains.program.unified_command_center_drift_response_verifier import verify_unified_command_center_drift_response_package as verify_unified_command_center_drift_response_package, write_unified_command_center_drift_response_verification_report as write_unified_command_center_drift_response_verification_report
from song_agent.domains.program.unified_command_center_evidence_review_verifier import ACCEPTANCE_REQUIRED_ENTRIES as ACCEPTANCE_REQUIRED_ENTRIES, REQUIRED_ENTRIES as REQUIRED_ENTRIES, UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_ACCEPTANCE_PACKAGE_TYPE as UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_ACCEPTANCE_PACKAGE_TYPE, UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_PACKAGE_TYPE as UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_PACKAGE_TYPE, UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_SCHEMA_VERSION as UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_SCHEMA_VERSION, verify_unified_command_center_evidence_review_acceptance_package as verify_unified_command_center_evidence_review_acceptance_package, verify_unified_command_center_evidence_review_package as verify_unified_command_center_evidence_review_package, write_unified_command_center_evidence_review_acceptance_verification_report as write_unified_command_center_evidence_review_acceptance_verification_report, write_unified_command_center_evidence_review_verification_report as write_unified_command_center_evidence_review_verification_report
from song_agent.domains.program.unified_command_center_handoff import UnifiedCommandCenterHandoffStore as UnifiedCommandCenterHandoffStore
from song_agent.domains.program.unified_command_center_handoff_verifier import verify_unified_command_center_handoff_package as verify_unified_command_center_handoff_package, write_unified_command_center_handoff_verification_report as write_unified_command_center_handoff_verification_report
from song_agent.domains.program.unified_command_center_signoff import UnifiedCommandCenterSignoffStore as UnifiedCommandCenterSignoffStore
from song_agent.domains.program.unified_command_center_verifier import verify_unified_command_center_package as verify_unified_command_center_package, write_unified_command_center_verification_report as write_unified_command_center_verification_report

class _DeferredGlobal:
    def __init__(self, name: str) -> None:
        self.name = name


def _make_deferred_global(name: str) -> type[object]:
    base: type[object] = Exception if name.endswith("Error") else object
    return type(f"_DeferredGlobal_{name}", (base,), {"_deferred_global_name": name})


def _deferred_global_name(value: object) -> str | None:
    if isinstance(value, _DeferredGlobal):
        return value.name
    if isinstance(value, type):
        name = getattr(value, "_deferred_global_name", None)
        if isinstance(name, str):
            return name
    return None


def _resolve_bound_default(value: object, namespace: dict[str, object]) -> object:
    name = _deferred_global_name(value)
    if name is not None:
        return namespace.get(name, value)
    if isinstance(value, tuple):
        return tuple(_resolve_bound_default(item, namespace) for item in value)
    if isinstance(value, list):
        return [_resolve_bound_default(item, namespace) for item in value]
    if isinstance(value, dict):
        return {
            _resolve_bound_default(key, namespace): _resolve_bound_default(item, namespace)
            for key, item in value.items()
        }
    return value


def _bind_function_defaults(function: object, namespace: dict[str, object]) -> None:
    defaults = getattr(function, "__defaults__", None)
    if defaults:
        function.__defaults__ = tuple(_resolve_bound_default(item, namespace) for item in defaults)
    kwdefaults = getattr(function, "__kwdefaults__", None)
    if kwdefaults:
        function.__kwdefaults__ = {
            key: _resolve_bound_default(item, namespace)
            for key, item in kwdefaults.items()
        }


def _bind_class_bases(cls: type[object], namespace: dict[str, object]) -> None:
    bases = tuple(_resolve_bound_default(base, namespace) for base in cls.__bases__)
    if bases != cls.__bases__ and all(isinstance(base, type) for base in bases):
        try:
            cls.__bases__ = bases
        except TypeError:
            pass


def _bind_deferred_defaults(namespace: dict[str, object]) -> None:
    for value in list(globals().values()):
        if callable(value) and hasattr(value, "__defaults__"):
            _bind_function_defaults(value, namespace)
        if isinstance(value, type):
            _bind_class_bases(value, namespace)
            for member in vars(value).values():
                target = member
                if isinstance(member, (staticmethod, classmethod)):
                    target = member.__func__
                if callable(target) and hasattr(target, "__defaults__"):
                    _bind_function_defaults(target, namespace)

ch = _make_deferred_global('ch')
key = _make_deferred_global('key')
row = _make_deferred_global('row')

def bind_globals(namespace: dict[str, object]) -> None:
    global ch, key, row
    ch = namespace.get('ch', ch)
    key = namespace.get('key', key)
    row = namespace.get('row', row)
    _bind_deferred_defaults(namespace)






class UnifiedCommandCenterEvidenceReviewError(ValueError):
    pass

class UnifiedCommandCenterEvidenceReviewNotFoundError(UnifiedCommandCenterEvidenceReviewError):
    pass

class UnifiedCommandCenterEvidenceReviewStateError(UnifiedCommandCenterEvidenceReviewError):
    pass

def _source_document(center_id: str, review_id: str, paths: DomainDocument, created_at: str) -> DomainDocument:
    source = {
        "ucc_zip_sha256": _sha256_path(paths.get("ucc_zip")),
        "ucc_manifest_hash": _zip_manifest_hash(paths.get("ucc_zip")),
        "ucc_verification_hash": _integrity_from_path(paths.get("ucc_verification_report")),
        "archive_zip_sha256": _sha256_path(paths.get("archive_zip")),
        "archive_manifest_hash": _zip_manifest_hash(paths.get("archive_zip")),
        "archive_verification_hash": _integrity_from_path(paths.get("archive_verification_report")),
        "handoff_zip_sha256": _sha256_path(paths.get("handoff_zip")),
        "handoff_manifest_hash": _zip_manifest_hash(paths.get("handoff_zip")),
        "handoff_verification_hash": _integrity_from_path(paths.get("handoff_verification_report")),
        "continuous_review_zip_sha256": _sha256_path(paths.get("continuous_review_zip")),
        "continuous_review_manifest_hash": _zip_manifest_hash(paths.get("continuous_review_zip")),
        "continuous_review_verification_hash": _integrity_from_path(paths.get("continuous_review_verification_report")),
        "drift_response_zip_sha256": _sha256_path(paths.get("drift_response_zip")),
        "drift_response_manifest_hash": _zip_manifest_hash(paths.get("drift_response_zip")),
        "drift_response_verification_hash": _integrity_from_path(paths.get("drift_response_verification_report")),
        "cr_binding_report_hash": _integrity_from_path(paths.get("drift_change_request_binding_report")),
        "ga_report_hash": _integrity_from_path(paths.get("ga_readiness_report")),
        "release_check_report_hash": _integrity_from_path(paths.get("release_check_report")),
    }
    status = "draft"
    doc = {
        "schema_version": UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_SCHEMA_VERSION,
        "package_type": "musicforge_unified_command_center_evidence_review_source",
        "center_id": center_id,
        "review_id": review_id,
        "created_at": created_at,
        "status": status,
        "source": source,
    }
    doc["source_hash"] = stable_hash(source)
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc

def _evidence_index_document(center_id: str, review_id: str, source: DomainDocument) -> DomainDocument:
    source_map = source.get("source", {})
    items = []
    for component, prefix, required in (
        ("unified_command_center", "ucc", True),
        ("unified_command_center_archive", "archive", True),
        ("unified_command_center_handoff", "handoff", True),
        ("continuous_review", "continuous_review", True),
        ("drift_response", "drift_response", bool(source_map.get("drift_response_zip_sha256"))),
        ("ga_readiness", "ga", bool(source_map.get("ga_report_hash"))),
        ("release_check", "release_check", bool(source_map.get("release_check_report_hash"))),
    ):
        verification_hash = source_map.get(f"{prefix}_verification_hash") if prefix not in {"ga", "release_check"} else source_map.get(f"{prefix}_report_hash")
        status = "passed" if verification_hash else "missing"
        items.append({"component_type": component, "component_id": center_id if component.startswith("unified") else review_id, "role": "root" if component == "unified_command_center" else "supporting", "required": required, "verification_hash": verification_hash, "verification_status": status, "runtime_status": "pending", "external_report_required": required})
    summary = {"required_count": len([row for row in items if row.get("required")]), "passed_count": len([row for row in items if row.get("verification_status") == "passed"]), "failed_count": len([row for row in items if row.get("required") and row.get("verification_status") != "passed"]), "manual_review_count": 1}
    doc = {"package_type": "musicforge_unified_command_center_evidence_review_index", "center_id": center_id, "review_id": review_id, "source_hash": source.get("source_hash"), "items": items, "summary": summary}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc

def _proof_index_document(center_id: str, review_id: str, source: DomainDocument) -> DomainDocument:
    source_map = source.get("source", {})
    proofs = []
    if source_map.get("cr_binding_report_hash"):
        proofs.append({"proof_type": "cr_binding_report", "component_type": "drift_response", "component_id": review_id, "proof_hash": source_map.get("cr_binding_report_hash")})
    if source_map.get("ucc_verification_hash"):
        proofs.append({"proof_type": "verification_report", "component_type": "unified_command_center", "component_id": center_id, "proof_hash": source_map.get("ucc_verification_hash")})
    if source_map.get("archive_verification_hash"):
        proofs.append({"proof_type": "verification_report", "component_type": "unified_command_center_archive", "component_id": center_id, "proof_hash": source_map.get("archive_verification_hash")})
    summary = {"proof_count": len(proofs), "cr_proof_present": bool(source_map.get("cr_binding_report_hash"))}
    doc = {"package_type": "musicforge_unified_command_center_evidence_review_external_proof_index", "center_id": center_id, "review_id": review_id, "source_hash": source.get("source_hash"), "proofs": proofs, "summary": summary}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc

def _replay_plan_document(center_id: str, review_id: str, source: DomainDocument) -> DomainDocument:
    source_map = source.get("source", {})
    steps = [
        {"step_id": "verify_ucc", "order": 10, "command": "verify-unified-command-center-package", "required": True, "inputs": ["ucc_zip", "ucc_verification_report"], "expected_status": "passed"},
        {"step_id": "verify_archive", "order": 20, "command": "verify-unified-command-center-archive-package", "required": True, "inputs": ["archive_zip", "archive_verification_report"], "expected_status": "passed"},
        {"step_id": "verify_handoff", "order": 30, "command": "verify-unified-command-center-handoff-package", "required": True, "inputs": ["handoff_zip", "handoff_verification_report"], "expected_status": "passed"},
        {"step_id": "verify_continuous_review", "order": 40, "command": "verify-unified-command-center-continuous-review-package", "required": True, "inputs": ["continuous_review_zip", "continuous_review_verification_report"], "expected_status": "passed"},
    ]
    if source_map.get("drift_response_zip_sha256"):
        steps.append({"step_id": "verify_drift_response", "order": 50, "command": "verify-unified-command-center-drift-response-package", "required": True, "inputs": ["drift_response_zip", "drift_response_verification_report", "change_request_binding_report"], "expected_status": "passed"})
    steps.extend([
        {"step_id": "verify_ga_readiness", "order": 60, "command": "verify-ga-readiness-report", "required": bool(source_map.get("ga_report_hash")), "inputs": ["ga_readiness_report"], "expected_status": "passed"},
        {"step_id": "verify_release_check", "order": 70, "command": "release-check-report", "required": bool(source_map.get("release_check_report_hash")), "inputs": ["release_check_report"], "expected_status": "passed"},
        {"step_id": "manual_reviewer_narrative", "order": 80, "command": "manual-review", "required": False, "inputs": ["reviewer-guide.md"], "expected_status": "manual_review"},
    ])
    doc = {"package_type": "musicforge_unified_command_center_evidence_review_replay_plan", "center_id": center_id, "review_id": review_id, "source_hash": source.get("source_hash"), "steps": steps}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc

def _empty_replay_document(center_id: str, review_id: str, source: DomainDocument, plan: DomainDocument) -> DomainDocument:
    steps = [{"step_id": row.get("step_id"), "status": "pending", "blockers": [], "verification_hash": None} for row in plan.get("steps", [])]
    doc = {"package_type": "musicforge_unified_command_center_evidence_review_replay_result", "center_id": center_id, "review_id": review_id, "source_hash": source.get("source_hash"), "status": "pending", "steps": steps, "summary": {"total": len(steps), "passed": 0, "failed": 0, "manual_review": 1}}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc

def _run_replay_document(center_id: str, review_id: str, source: DomainDocument, plan: DomainDocument, paths: DomainDocument) -> DomainDocument:
    steps = []
    for step in plan.get("steps", []):
        step_id = step.get("step_id")
        if step_id == "verify_ucc":
            report = verify_unified_command_center_package(_as_path(paths.get("ucc_zip")), strict=True, release_check_report_path=paths.get("release_check_report"))
        elif step_id == "verify_archive":
            report = verify_unified_command_center_archive_package(_as_path(paths.get("archive_zip")), strict=True, require_signed=True, require_current_ucc=True, command_center_zip_path=paths.get("ucc_zip"), command_center_verification_report_path=paths.get("ucc_verification_report"), signoff_binding_path=paths.get("signoff_binding"))
        elif step_id == "verify_handoff":
            report = verify_unified_command_center_handoff_package(_as_path(paths.get("handoff_zip")), strict=True, require_archive=True, archive_zip_path=paths.get("archive_zip"), archive_verification_report_path=paths.get("archive_verification_report"))
        elif step_id == "verify_continuous_review":
            report = verify_unified_command_center_continuous_review_package(_as_path(paths.get("continuous_review_zip")), strict=True, require_clear=False, require_recovery_drill=False, require_current_review=True, archive_zip_path=paths.get("archive_zip"), archive_verification_report_path=paths.get("archive_verification_report"), handoff_zip_path=paths.get("handoff_zip"), handoff_verification_report_path=paths.get("handoff_verification_report"), command_center_zip_path=paths.get("ucc_zip"), command_center_verification_report_path=paths.get("ucc_verification_report"), signoff_binding_path=paths.get("signoff_binding"))
        elif step_id == "verify_drift_response":
            report = verify_unified_command_center_drift_response_package(_as_path(paths.get("drift_response_zip")), strict=True, require_closed=True, require_recheck_clear=True, require_current_review=True, source_review_zip_path=paths.get("source_review_zip") or paths.get("continuous_review_zip"), source_review_verification_report_path=paths.get("source_review_verification_report") or paths.get("continuous_review_verification_report"), recheck_review_zip_path=paths.get("recheck_review_zip") or paths.get("continuous_review_zip"), recheck_review_verification_report_path=paths.get("recheck_review_verification_report") or paths.get("continuous_review_verification_report"), change_request_binding_report_path=paths.get("drift_change_request_binding_report"), archive_zip_path=paths.get("archive_zip"), archive_verification_report_path=paths.get("archive_verification_report"), handoff_zip_path=paths.get("handoff_zip"), handoff_verification_report_path=paths.get("handoff_verification_report"), command_center_zip_path=paths.get("ucc_zip"), command_center_verification_report_path=paths.get("ucc_verification_report"), signoff_binding_path=paths.get("signoff_binding"))
        elif step_id == "verify_ga_readiness":
            report = _generic_report(paths.get("ga_readiness_report"))
        elif step_id == "verify_release_check":
            report = _release_check_result(paths.get("release_check_report"))
        else:
            report = {"status": "manual_review", "blockers": [], "integrity_hash": None}
        steps.append({"step_id": step_id, "status": report.get("status"), "blockers": report.get("blockers", []), "verification_hash": report.get("integrity_hash"), "duration_ms": 0})
    required_steps = {str(row.get("step_id")) for row in plan.get("steps", []) if isinstance(row, dict) and row.get("required")}
    failed = [row for row in steps if row.get("step_id") in required_steps and row.get("status") != "passed"]
    doc = {"package_type": "musicforge_unified_command_center_evidence_review_replay_result", "center_id": center_id, "review_id": review_id, "source_hash": source.get("source_hash"), "status": "failed" if failed else "passed", "steps": steps, "summary": {"total": len(steps), "passed": len([row for row in steps if row.get("status") == "passed"]), "failed": len(failed), "manual_review": len([row for row in steps if row.get("status") == "manual_review"])}}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc

def _narrative_document(center_id: str, review_id: str, source: DomainDocument, replay_result: DomainDocument) -> DomainDocument:
    doc = {"package_type": "musicforge_unified_command_center_evidence_review_narrative", "center_id": center_id, "review_id": review_id, "source_hash": source.get("source_hash"), "status": replay_result.get("status"), "summary": {"ucc_ready": bool(source.get("source", {}).get("ucc_verification_hash")), "archive_current": bool(source.get("source", {}).get("archive_verification_hash")), "handoff_current": bool(source.get("source", {}).get("handoff_verification_hash")), "drift_response_present": bool(source.get("source", {}).get("drift_response_verification_hash")), "manual_review_required": True}}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc

def _checklist_document(center_id: str, review_id: str, source: DomainDocument) -> DomainDocument:
    doc = {"package_type": "musicforge_unified_command_center_evidence_review_manual_checklist", "center_id": center_id, "review_id": review_id, "source_hash": source.get("source_hash"), "items": [{"item_id": "manual-001", "label": "Reviewer confirms UCC evidence chain narrative.", "required": True, "status": "manual_required"}]}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc

def _manifest_document(center_id: str, review_id: str, source: DomainDocument, root: Path, entries: set[str], status: str, *, package_type: str = UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_PACKAGE_TYPE, evidence_id: str | None = None) -> DomainDocument:
    files = []
    for rel in sorted(entries - {"manifest.json"}):
        path = root / rel
        files.append({"path": rel, "sha256": _sha256_path(path), "size_bytes": path.stat().st_size if path.exists() else 0})
    manifest = {"package_type": package_type, "schema_version": UNIFIED_COMMAND_CENTER_EVIDENCE_REVIEW_SCHEMA_VERSION, "center_id": center_id, "review_id": review_id, "evidence_id": evidence_id, "source_hash": source.get("source_hash"), "files": files, "summary": {"replay_status": status, "required_evidence_status": status, "manual_review_required": True}, "source": {"review_source_hash": source.get("integrity_hash")}}
    manifest["integrity_hash"] = _integrity_hash(manifest)
    return manifest

def _reviewer_guide(docs: DomainDocument) -> str:
    source = docs.get("source", {})
    replay = docs.get("replay_result", {})
    return sanitize_sensitive_text(
        "\n".join(
            [
                "# MusicForge Unified Command Center Evidence Review",
                "",
                f"Review: {source.get('review_id')}",
                f"Replay status: {replay.get('status')}",
                "Run the verifier with the external evidence arguments listed in the replay plan.",
                "Accepted review responses must bind the current review pack hash and replay result hash.",
            ]
        )
    )

def _review_verifier_kwargs(paths: DomainDocument) -> DomainDocument:
    return {
        "ucc_zip_path": _path_or_none(paths.get("ucc_zip")),
        "ucc_verification_report_path": _path_or_none(paths.get("ucc_verification_report")),
        "archive_zip_path": _path_or_none(paths.get("archive_zip")),
        "archive_verification_report_path": _path_or_none(paths.get("archive_verification_report")),
        "handoff_zip_path": _path_or_none(paths.get("handoff_zip")),
        "handoff_verification_report_path": _path_or_none(paths.get("handoff_verification_report")),
        "continuous_review_zip_path": _path_or_none(paths.get("continuous_review_zip")),
        "continuous_review_verification_report_path": _path_or_none(paths.get("continuous_review_verification_report")),
        "drift_response_zip_path": _path_or_none(paths.get("drift_response_zip")),
        "drift_response_verification_report_path": _path_or_none(paths.get("drift_response_verification_report")),
        "drift_change_request_binding_report_path": _path_or_none(paths.get("drift_change_request_binding_report")),
        "source_review_zip_path": _path_or_none(paths.get("source_review_zip")),
        "source_review_verification_report_path": _path_or_none(paths.get("source_review_verification_report")),
        "recheck_review_zip_path": _path_or_none(paths.get("recheck_review_zip")),
        "recheck_review_verification_report_path": _path_or_none(paths.get("recheck_review_verification_report")),
        "signoff_binding_path": _path_or_none(paths.get("signoff_binding")),
        "ga_readiness_report_path": _path_or_none(paths.get("ga_readiness_report")),
        "release_check_report_path": _path_or_none(paths.get("release_check_report")),
    }

def _summary_from_path(path: object, label: str) -> DomainDocument:
    if not path or not Path(path).exists():
        doc: DomainDocument = {"package_type": f"musicforge_{label}_summary", "status": "not_applicable", "label": label}
    else:
        source = read_json(Path(path))
        doc = {key: source.get(key) for key in ("package_type", "status", "zip_sha256", "zip_size_bytes", "manifest_hash", "integrity_hash") if key in source}
        doc["label"] = label
    doc["summary_hash"] = stable_hash(doc)
    return doc

def _generic_report(path: object) -> DomainDocument:
    if not path or not Path(path).exists():
        return {"status": "not_applicable", "blockers": [], "integrity_hash": None}
    report = read_json(Path(path))
    status = str(report.get("status") or "")
    if report.get("ok") is True:
        status = "passed"
    if status in {"ready", "warning"}:
        status = "passed"
    return {"status": status or "failed", "blockers": report.get("blockers", []), "integrity_hash": _integrity_or_stable(report)}

def _release_check_result(path: object) -> DomainDocument:
    if not path or not Path(path).exists():
        return {"status": "not_applicable", "blockers": [], "integrity_hash": None}
    report = read_json(Path(path))
    return {"status": "passed" if report.get("ok") is True else "failed", "blockers": [row.get("check_id") for row in report.get("results", []) if isinstance(row, dict) and not row.get("ok")], "integrity_hash": _integrity_or_stable(report)}

def _public_reviewer(reviewer: DomainDocument) -> DomainDocument:
    return {"name": sanitize_sensitive_text(str(reviewer.get("name") or "Reviewer"))[:120], "organization": sanitize_sensitive_text(str(reviewer.get("organization") or ""))[:120], "role": sanitize_sensitive_text(str(reviewer.get("role") or "reviewer"))[:80]}

def _findings(value: object) -> list[DomainDocument]:
    rows = _as_list(value)
    return [{"severity": sanitize_sensitive_text(str(row.get("severity") or "low"))[:40], "component": sanitize_sensitive_text(str(row.get("component") or ""))[:120], "message": sanitize_sensitive_text(str(row.get("message") or ""))[:1000]} for row in rows if isinstance(row, dict)]

def _public_response(response: DomainDocument) -> DomainDocument:
    doc = {"package_type": "musicforge_unified_command_center_evidence_review_response_public", "response_id": response.get("response_id"), "review_id": response.get("review_id"), "result": response.get("result"), "reviewer": response.get("reviewer"), "findings": response.get("findings", []), "signed_at": response.get("signed_at")}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc

def _response_verification_summary(response: DomainDocument, public_response: DomainDocument) -> DomainDocument:
    doc = {"package_type": "musicforge_unified_command_center_evidence_review_response_verification_summary", "response_id": response.get("response_id"), "status": response.get("status"), "result": response.get("result"), "response_payload_hash": response.get("payload_hash"), "response_integrity_hash": response.get("integrity_hash"), "response_public_hash": public_response.get("integrity_hash"), "bindings": response.get("bindings", {})}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc

def _response_binding_summary(response: DomainDocument) -> DomainDocument:
    bindings = response.get("bindings", {})
    doc = {"package_type": "musicforge_unified_command_center_evidence_review_response_binding_summary", "response_id": response.get("response_id"), "review_pack_zip_sha256": bindings.get("review_pack_zip_sha256"), "review_pack_manifest_hash": bindings.get("review_pack_manifest_hash"), "review_pack_source_hash": bindings.get("review_pack_source_hash"), "replay_result_hash": bindings.get("replay_result_hash"), "response_payload_hash": response.get("payload_hash")}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc

def _read_optional_json(path: Path) -> DomainDocument:
    return read_json(path) if path.exists() else {}

def _path_or_none(value: object) -> Path | None:
    if not value:
        return None
    return Path(value)

def _integrity_hash(payload: DomainDocument) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})

def _integrity_from_path(path: object) -> str | None:
    if not path or not Path(path).exists():
        return None
    data = read_json(Path(path))
    return data.get("integrity_hash") or stable_hash(data)

def _integrity_or_stable(payload: DomainDocument) -> str:
    return str(payload.get("integrity_hash") or stable_hash(payload))

def _sha256_path(path: object) -> str | None:
    if not path:
        return None
    path = Path(path)
    if not path.exists() or not path.is_file():
        return None
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def _zip_manifest_hash(path: object) -> str | None:
    if not path or not Path(path).exists():
        return None
    try:
        with zipfile.ZipFile(Path(path)) as archive:
            return json.loads(archive.read("manifest.json").decode("utf-8")).get("integrity_hash")
    except (OSError, zipfile.BadZipFile, KeyError, json.JSONDecodeError, ValueError):
        return None

def _safe_id(value: str) -> str:
    return "".join(ch for ch in str(value) if ch.isalnum() or ch in {"-", "_"})[:80] or "item"
