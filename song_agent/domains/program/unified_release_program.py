# ruff: noqa: E402,F401
from __future__ import annotations

from typing import Any as _InferenceType

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document

import json as json
import shutil as shutil
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.platform.version import VERSION as __version__
from song_agent.platform.lifecycle import ArchiveBuilder as ArchiveBuilder, HistoryChain as HistoryChain, SignoffService as SignoffService
from song_agent.platform.persistence import WorkspaceLock as WorkspaceLock
from song_agent.platform.persistence.program import program_json_facade as program_json_facade
from song_agent.domains.program.ports import ProgramReleaseStore as ProgramReleaseStore
from song_agent.platform.time import now_iso as now_iso
from song_agent.platform.verification.hashing import stable_hash as stable_hash
from song_agent.platform.verification.sanitization import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.program.unified_release_program_verifier import UNIFIED_RELEASE_PROGRAM_EXTERNAL_EVIDENCE_MANIFEST_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_EXTERNAL_EVIDENCE_MANIFEST_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_PACKAGE_TYPE, UNIFIED_RELEASE_PROGRAM_SCHEMA_VERSION as UNIFIED_RELEASE_PROGRAM_SCHEMA_VERSION, verify_unified_release_program_package as verify_unified_release_program_package, write_unified_release_program_verification_report as write_unified_release_program_verification_report
from song_agent.domains.program.unified_command_center_release_train_handoff_verifier import UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_HANDOFF_VERIFICATION_PACKAGE_TYPE as UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_HANDOFF_VERIFICATION_PACKAGE_TYPE, verify_unified_command_center_release_train_handoff_package as verify_unified_command_center_release_train_handoff_package
from song_agent.domains.program.v142_urp_readiness_2 import UnifiedReleaseProgramStoreReadinessMixin
from song_agent.domains.program import v142_urp_readiness_2 as _v142_urp_readiness_2
from song_agent.domains.program.v142_urp_evidence import UnifiedReleaseProgramStoreEvidenceMixin
from song_agent.domains.program import v142_urp_evidence as _v142_urp_evidence



DEFAULT_POLICY = {
    "require_all_required_trains_ready": True,
    "require_no_dependency_cycle": True,
    "require_no_critical_risk": True,
    "require_external_handoff_acceptance": False,
    "allow_advisory_warnings": True,
    "allow_optional_defer": True,
    "required_program_roles": ["release_owner"],
}


class UnifiedReleaseProgramError(ValueError):
    pass


class UnifiedReleaseProgramNotFoundError(UnifiedReleaseProgramError):
    pass


class UnifiedReleaseProgramStateError(UnifiedReleaseProgramError):
    pass


read_json, write_json = program_json_facade(UnifiedReleaseProgramStateError)


class UnifiedReleaseProgramStore(UnifiedReleaseProgramStoreReadinessMixin, UnifiedReleaseProgramStoreEvidenceMixin):
    def __init__(self, root: Path | str | None = None, *, release_store: ProgramReleaseStore | None = None) -> None:
        self.release_store = release_store
        workspace = release_store.root.parent if release_store is not None else Path(".musicforge")
        self.root = Path(root) if root is not None else workspace / "unified-release-programs"
        self.lock = WorkspaceLock(self.root.parent, operation="program-workflow-write")


















































def write_external_evidence_manifest(path: Path | str, *, program_id: str, items: list[DomainDocument]) -> DomainDocument:
    manifest = _external_manifest_from_rows(program_id, items)
    write_json(Path(path), manifest)
    return manifest


def _external_manifest(program_id: str, items_doc: ImplementationDocument, inputs: ImplementationDocument) -> ImplementationDocument:
    path = inputs.get("external_evidence_manifest") or inputs.get("external_evidence_manifest_path")
    if path:
        return read_json(Path(path))
    rows = inputs.get("external_evidence") or inputs.get("external_evidence_items")
    if rows is None:
        rows = []
        for item in items_doc.get("items", []):
            external = _as_document(item.get("external_evidence"))
            rows.append(
                {
                    "item_id": item.get("item_id"),
                    "train_id": item.get("train_id"),
                    "handoff_id": item.get("handoff_id"),
                    "evidence_type": "release_train_handoff",
                    **external,
                }
            )
    return _external_manifest_from_rows(program_id, rows)


def _external_manifest_from_rows(program_id: str, rows: list[ImplementationDocument]) -> ImplementationDocument:
    normalized = []
    for row in rows:
        normalized_row = {
            "item_id": _safe_id(str(row.get("item_id") or "")),
            "train_id": _safe_id(str(row.get("train_id") or "")),
            "handoff_id": _safe_id(str(row.get("handoff_id") or "")),
            "evidence_type": "release_train_handoff",
            "handoff_zip": str(row.get("handoff_zip") or row.get("handoff_zip_path") or ""),
            "handoff_verification_report": str(row.get("handoff_verification_report") or row.get("handoff_verification_report_path") or ""),
            "handoff_signoff_binding": str(row.get("handoff_signoff_binding") or row.get("handoff_signoff_binding_path") or ""),
            "accepted_evidence_dir": str(row.get("accepted_evidence_dir") or ""),
            "handoff_zip_sha256": row.get("handoff_zip_sha256"),
            "handoff_manifest_hash": row.get("handoff_manifest_hash"),
            "handoff_verification_report_hash": row.get("handoff_verification_report_hash"),
            "handoff_signoff_binding_hash": row.get("handoff_signoff_binding_hash"),
        }
        normalized_row.update(_fingerprint_from_external_row(normalized_row))
        normalized.append(normalized_row)
    manifest = {
        "schema_version": UNIFIED_RELEASE_PROGRAM_SCHEMA_VERSION,
        "package_type": UNIFIED_RELEASE_PROGRAM_EXTERNAL_EVIDENCE_MANIFEST_PACKAGE_TYPE,
        "program_id": program_id,
        "created_at": now_iso(),
        "items": normalized,
        "summary": {"item_count": len(normalized)},
    }
    manifest["integrity_hash"] = _integrity_hash(manifest)
    return manifest


def _public_external_manifest(program_id: str, item_rows: list[ImplementationDocument]) -> ImplementationDocument:
    normalized = []
    for row in item_rows:
        fingerprint = _as_document(row.get("fingerprint"))
        normalized.append(
            {
                "item_id": row.get("item_id"),
                "train_id": row.get("train_id"),
                "handoff_id": row.get("handoff_id"),
                "evidence_type": "release_train_handoff",
                "handoff_zip_sha256": fingerprint.get("handoff_zip_sha256"),
                "handoff_zip_size_bytes": fingerprint.get("handoff_zip_size_bytes"),
                "handoff_manifest_hash": fingerprint.get("handoff_manifest_hash"),
                "handoff_verification_report_hash": fingerprint.get("handoff_verification_report_hash"),
                "handoff_signoff_binding_hash": fingerprint.get("handoff_signoff_binding_hash"),
                "handoff_status": fingerprint.get("handoff_status"),
            }
        )
    manifest = {
        "schema_version": UNIFIED_RELEASE_PROGRAM_SCHEMA_VERSION,
        "package_type": UNIFIED_RELEASE_PROGRAM_EXTERNAL_EVIDENCE_MANIFEST_PACKAGE_TYPE,
        "program_id": program_id,
        "created_at": now_iso(),
        "items": normalized,
        "summary": {"item_count": len(normalized)},
    }
    manifest["integrity_hash"] = _integrity_hash(manifest)
    return manifest


def _fingerprint_from_external_row(row: ImplementationDocument) -> ImplementationDocument:
    fingerprint: ImplementationDocument = {}
    zip_path = Path(str(row.get("handoff_zip") or ""))
    report_path = Path(str(row.get("handoff_verification_report") or ""))
    binding_path = Path(str(row.get("handoff_signoff_binding") or ""))
    if zip_path.exists() and zip_path.is_file() and not row.get("handoff_zip_sha256"):
        fingerprint["handoff_zip_sha256"] = _sha256_path(zip_path)
        fingerprint["handoff_zip_size_bytes"] = zip_path.stat().st_size
    if report_path.exists() and report_path.is_file():
        try:
            report = read_json(report_path)
            if not row.get("handoff_manifest_hash"):
                fingerprint["handoff_manifest_hash"] = _verification_manifest_hash(report)
            if not row.get("handoff_verification_report_hash"):
                fingerprint["handoff_verification_report_hash"] = _integrity_hash(report)
        except Exception:
            pass
    if binding_path.exists() and binding_path.is_file() and not row.get("handoff_signoff_binding_hash"):
        fingerprint["handoff_signoff_binding_hash"] = _sha256_or_integrity(binding_path)
    return {key: value for key, value in fingerprint.items() if value not in (None, "")}


def _item_rows(program: ImplementationDocument, items_doc: ImplementationDocument, external_manifest: ImplementationDocument) -> list[ImplementationDocument]:
    external_by_key = {_item_key(row): row for row in external_manifest.get("items", []) if isinstance(row, dict)}
    require_accepted = bool(program.get("policy", {}).get("require_external_handoff_acceptance"))
    rows = []
    for item in items_doc.get("items", []):
        external = external_by_key.get(_item_key(item), {})
        runtime = _runtime_handoff(item, external, require_accepted=require_accepted)
        row = sanitize_metadata({**item, "require_accepted": require_accepted, "runtime": runtime, "fingerprint": runtime.get("fingerprint", {}), "status": "ready" if runtime.get("status") == "passed" else "blocked", "blockers": runtime.get("blockers", [])})
        rows.append(row)
    return rows


def _runtime_handoff(item: ImplementationDocument, external: ImplementationDocument, *, require_accepted: bool) -> ImplementationDocument:
    result: ImplementationDocument = {"status": "missing", "blockers": [], "fingerprint": {}}
    zip_path = Path(str(external.get("handoff_zip") or external.get("handoff_zip_path") or ""))
    report_path = Path(str(external.get("handoff_verification_report") or external.get("handoff_verification_report_path") or ""))
    binding_path = Path(str(external.get("handoff_signoff_binding") or external.get("handoff_signoff_binding_path") or ""))
    accepted_raw = external.get("accepted_evidence_dir")
    accepted_dir = Path(str(accepted_raw)) if accepted_raw else None
    if not zip_path.exists() or not report_path.exists() or not binding_path.exists():
        result["blockers"].append("handoff_external_evidence_missing")
        return result
    try:
        external_report = read_json(report_path)
        runtime = verify_unified_command_center_release_train_handoff_package(
            zip_path,
            strict=True,
            require_signed=True,
            require_accepted=require_accepted,
            handoff_signoff_binding_path=binding_path,
            accepted_evidence_dir=accepted_dir,
        )
        runtime_zip_sha256 = _verification_zip_sha256(runtime)
        runtime_manifest_hash = _verification_manifest_hash(runtime)
        external_zip_sha256 = _verification_zip_sha256(external_report)
        external_manifest_hash = _verification_manifest_hash(external_report)
        fingerprint = {
            "handoff_zip_sha256": _sha256_path(zip_path),
            "handoff_zip_size_bytes": zip_path.stat().st_size,
            "handoff_manifest_hash": runtime_manifest_hash,
            "handoff_verification_report_hash": _integrity_hash(external_report),
            "handoff_signoff_binding_hash": _sha256_or_integrity(binding_path),
            "handoff_status": runtime.get("status"),
        }
        result["fingerprint"] = fingerprint
        if external_report.get("package_type") != UNIFIED_COMMAND_CENTER_RELEASE_TRAIN_HANDOFF_VERIFICATION_PACKAGE_TYPE:
            result["blockers"].append("handoff_verification_wrong_package_type")
        if not _integrity_ok(external_report):
            result["blockers"].append("handoff_verification_integrity_failed")
        if external_report.get("status") != "passed" or runtime.get("status") != "passed":
            result["blockers"].append("handoff_verification_not_passed")
        if external_zip_sha256 != runtime_zip_sha256 or runtime_zip_sha256 != fingerprint["handoff_zip_sha256"]:
            result["blockers"].append("handoff_zip_sha256_mismatch")
        if external_manifest_hash != runtime_manifest_hash:
            result["blockers"].append("handoff_manifest_hash_mismatch")
        result["runtime_blockers"] = runtime.get("blockers", [])
    except Exception as exc:
        result["blockers"].append(sanitize_sensitive_text(str(exc)))
    result["status"] = "passed" if not result["blockers"] else "failed"
    return sanitize_metadata(result)


def _items_document(program_id: str, rows: list[ImplementationDocument]) -> ImplementationDocument:
    doc = sanitize_metadata(
        {
            "schema_version": UNIFIED_RELEASE_PROGRAM_SCHEMA_VERSION,
            "package_type": "musicforge_unified_release_program_train_items",
            "program_id": program_id,
            "items": rows,
            "summary": {
                "item_count": len(rows),
                "ready_count": sum(1 for row in rows if row.get("status") == "ready"),
                "blocked_count": sum(1 for row in rows if row.get("status") == "blocked"),
                "required_count": sum(1 for row in rows if row.get("type") == "required"),
                "deferred_count": sum(1 for row in rows if row.get("type") == "deferred"),
            },
        }
    )
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _dependency_graph(program_id: str, source_hash: str, items: list[ImplementationDocument], created_at: str) -> ImplementationDocument:
    nodes = [{"item_id": row.get("item_id"), "type": row.get("type"), "lane": row.get("lane"), "wave": row.get("wave"), "status": row.get("status")} for row in items]
    edges = []
    item_ids = {str(row.get("item_id")) for row in items}
    for row in items:
        for dep in row.get("depends_on", []) or []:
            if dep:
                edges.append({"from": dep, "to": row.get("item_id"), "reason": "Program dependency"})
    cycle = _has_cycle([str(row.get("from") or "") for row in edges], [str(row.get("to") or "") for row in edges])
    blocked = [edge for edge in edges if edge.get("from") not in item_ids or next((row for row in items if row.get("item_id") == edge.get("from")), {}).get("status") != "ready"]
    doc = sanitize_metadata(
        {
            "schema_version": UNIFIED_RELEASE_PROGRAM_SCHEMA_VERSION,
            "package_type": "musicforge_unified_release_program_dependency_graph",
            "program_id": program_id,
            "created_at": created_at,
            "source_hash": source_hash,
            "nodes": nodes,
            "edges": edges,
            "summary": {"has_cycle": cycle, "blocked_dependency_count": len(blocked), "ordered_items": _topological_order(nodes, edges) if not cycle else []},
        }
    )
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _readiness_matrix(program_id: str, source_hash: str, items: list[ImplementationDocument], dependency: ImplementationDocument, program: ImplementationDocument, created_at: str) -> ImplementationDocument:
    rows = []
    critical_failed = 0
    warning_count = 0
    required_ready_count = sum(1 for item in items if item.get("type") == "required" and item.get("status") == "ready")
    for item in items:
        severity = "critical" if item.get("type") == "required" else "warning"
        status = "passed" if item.get("status") == "ready" else "failed" if severity == "critical" else "warning"
        if status == "failed":
            critical_failed += 1
        if status == "warning":
            warning_count += 1
        rows.append({"check_id": f"{item.get('item_id')}.current_handoff_verified", "item_id": item.get("item_id"), "train_id": item.get("train_id"), "handoff_id": item.get("handoff_id"), "status": status, "severity": severity, "item_type": item.get("type"), "blockers": item.get("blockers", [])})
    if dependency.get("summary", {}).get("has_cycle"):
        critical_failed += 1
        rows.append({"check_id": "dependency_graph_acyclic", "status": "failed", "severity": "critical"})
    else:
        rows.append({"check_id": "dependency_graph_acyclic", "status": "passed", "severity": "critical"})
    blocked_deps = int(dependency.get("summary", {}).get("blocked_dependency_count") or 0)
    if blocked_deps:
        critical_failed += blocked_deps
        rows.append({"check_id": "dependency_graph_blocked", "status": "failed", "severity": "critical", "blocked_dependency_count": blocked_deps})
    if required_ready_count == 0:
        critical_failed += 1
        rows.append(
            {
                "check_id": "program_has_verified_required_handoff",
                "status": "failed",
                "severity": "critical",
                "required_ready_count": required_ready_count,
                "message": "Program signoff requires at least one required train with a current verified Handoff.",
            }
        )
    else:
        rows.append({"check_id": "program_has_verified_required_handoff", "status": "passed", "severity": "critical", "required_ready_count": required_ready_count})
    status = "ready" if critical_failed == 0 else "blocked"
    doc = sanitize_metadata(
        {
            "schema_version": UNIFIED_RELEASE_PROGRAM_SCHEMA_VERSION,
            "package_type": "musicforge_unified_release_program_readiness_matrix",
            "program_id": program_id,
            "created_at": created_at,
            "source_hash": source_hash,
            "rows": rows,
            "summary": {"status": status, "critical_failed": critical_failed, "warning_count": warning_count, "manual_required": 0, "required_ready_count": required_ready_count},
        }
    )
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _risk_register(program_id: str, source_hash: str, readiness: ImplementationDocument, dependency: ImplementationDocument, items: list[ImplementationDocument], created_at: str) -> ImplementationDocument:
    risks: list[_InferenceType] = []
    for row in readiness.get("rows", []):
        if row.get("status") == "passed":
            continue
        risks.append({"risk_id": f"risk-{len(risks) + 1:03d}", "severity": "critical" if row.get("severity") == "critical" else "medium", "category": "verification", "item_id": row.get("item_id"), "message": f"{row.get('check_id')} is {row.get('status')}", "recommended_action": "refresh train handoff verification"})
    doc = sanitize_metadata(
        {
            "schema_version": UNIFIED_RELEASE_PROGRAM_SCHEMA_VERSION,
            "package_type": "musicforge_unified_release_program_risk_register",
            "program_id": program_id,
            "created_at": created_at,
            "source_hash": source_hash,
            "risks": risks,
            "summary": {
                "critical": sum(1 for row in risks if row.get("severity") == "critical"),
                "high": sum(1 for row in risks if row.get("severity") == "high"),
                "medium": sum(1 for row in risks if row.get("severity") == "medium"),
                "low": sum(1 for row in risks if row.get("severity") == "low"),
            },
        }
    )
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _gap_plan(program_id: str, source_hash: str, readiness: ImplementationDocument, risk: ImplementationDocument, created_at: str) -> ImplementationDocument:
    actions = [{"action_id": f"gap-{index + 1:03d}", "source_check_id": row.get("check_id"), "status": "manual_required", "recommended_action": "Resolve Program blocker and refresh Program."} for index, row in enumerate(readiness.get("rows", [])) if row.get("status") in {"failed", "warning"}]
    doc = sanitize_metadata(
        {
            "schema_version": UNIFIED_RELEASE_PROGRAM_SCHEMA_VERSION,
            "package_type": "musicforge_unified_release_program_gap_plan",
            "program_id": program_id,
            "created_at": created_at,
            "source_hash": source_hash,
            "actions": actions,
            "summary": {"action_count": len(actions), "manual_required": len(actions)},
        }
    )
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _program_report(program_id: str, source_hash: str, program: ImplementationDocument, items: ImplementationDocument, external_manifest: ImplementationDocument, dependency: ImplementationDocument, readiness: ImplementationDocument, risk: ImplementationDocument, exceptions: ImplementationDocument, gap: ImplementationDocument, created_at: str) -> ImplementationDocument:
    status = "ready" if readiness.get("summary", {}).get("status") == "ready" else "blocked"
    doc = sanitize_metadata(
        {
            "schema_version": UNIFIED_RELEASE_PROGRAM_SCHEMA_VERSION,
            "package_type": "musicforge_unified_release_program_report",
            "program_id": program_id,
            "created_at": created_at,
            "status": status,
            "source_hash": source_hash,
            "summary": {
                "train_count": items.get("summary", {}).get("item_count", 0),
                "ready_count": items.get("summary", {}).get("ready_count", 0),
                "blocked_count": items.get("summary", {}).get("blocked_count", 0),
                "deferred_count": items.get("summary", {}).get("deferred_count", 0),
                "dependency_cycle": bool(dependency.get("summary", {}).get("has_cycle")),
                "readiness": readiness.get("summary", {}).get("status"),
                "risk_count": len(risk.get("risks", [])),
            },
            "source": {
                "train_items_hash": items.get("integrity_hash"),
                "external_evidence_manifest_hash": external_manifest.get("integrity_hash"),
                "dependency_graph_hash": dependency.get("integrity_hash"),
                "readiness_matrix_hash": readiness.get("integrity_hash"),
                "risk_register_hash": risk.get("integrity_hash"),
                "exception_register_hash": exceptions.get("integrity_hash"),
                "gap_plan_hash": gap.get("integrity_hash"),
            },
        }
    )
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


def _manifest_document(program_id: str, docs: ImplementationDocument, files: list[ImplementationDocument], file_index: ImplementationDocument) -> ImplementationDocument:
    manifest = sanitize_metadata(
        {
            "schema_version": UNIFIED_RELEASE_PROGRAM_SCHEMA_VERSION,
            "package_type": UNIFIED_RELEASE_PROGRAM_PACKAGE_TYPE,
            "program_id": program_id,
            "created_at": now_iso(),
            "source_hash": docs["report"].get("source_hash"),
            "source": _manifest_source(docs),
            "files": [row for row in files if row.get("path") != "manifest.json"],
            "file_index_hash": file_index.get("integrity_hash"),
        }
    )
    manifest["integrity_hash"] = _integrity_hash(manifest)
    return manifest


def _manifest_source(docs: ImplementationDocument) -> ImplementationDocument:
    source = {
        "program_report_hash": docs["report"].get("integrity_hash"),
        "train_items_hash": docs["items"].get("integrity_hash"),
        "external_evidence_manifest_hash": docs["external_manifest"].get("integrity_hash"),
        "dependency_graph_hash": docs["dependency"].get("integrity_hash"),
        "readiness_matrix_hash": docs["readiness"].get("integrity_hash"),
        "risk_register_hash": docs["risk"].get("integrity_hash"),
        "exception_register_hash": docs["exceptions"].get("integrity_hash"),
        "gap_plan_hash": docs["gap_plan"].get("integrity_hash"),
    }
    if docs.get("signoff"):
        source["program_signoff_hash"] = docs["signoff"].get("integrity_hash")
    if docs.get("signoff_binding"):
        source["program_signoff_binding_hash"] = docs["signoff_binding"].get("integrity_hash")
    return source


def _file_index(program_id: str, files: list[ImplementationDocument]) -> ImplementationDocument:
    doc = {"schema_version": UNIFIED_RELEASE_PROGRAM_SCHEMA_VERSION, "package_type": "musicforge_unified_release_program_file_index", "program_id": program_id, "files": [row for row in files if row.get("path") != "file-index.json"], "summary": {"file_count": len(files)}}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc


from song_agent.domains.program import v142_urp_readiness as _v142_urp_readiness
from song_agent.domains.program.v142_urp_readiness import (
    _file_record,
    _recipient_guide,
    _read_optional_json,
    _source_inputs,
    _merge_inputs,
    _json_safe_input,
    _policy,
    _safe_id,
    _bounded,
    _integrity_hash,
    _integrity_ok,
    _sha256_path,
    _sha256_or_integrity,
    _verification_zip_sha256,
    _verification_manifest_hash,
    _item_key,
    _history_text,
    _gate_failed,
    _has_cycle,
    _topological_order,
)








































_v142_urp_readiness_2.bind_globals(globals())
_v142_urp_evidence.bind_globals(globals())

_v142_urp_readiness.bind_globals(globals())
