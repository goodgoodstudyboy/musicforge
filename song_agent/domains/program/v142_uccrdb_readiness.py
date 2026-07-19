# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list, as_path as _as_path, document_or as _document_or
import json as json
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.projects import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.program.unified_command_center import UnifiedCommandCenterStore as UnifiedCommandCenterStore
from song_agent.domains.program.unified_command_center_evidence_review import UnifiedCommandCenterEvidenceReviewStore as UnifiedCommandCenterEvidenceReviewStore
from song_agent.domains.program.unified_command_center_evidence_review_verifier import verify_unified_command_center_evidence_review_acceptance_package as verify_unified_command_center_evidence_review_acceptance_package, verify_unified_command_center_evidence_review_package as verify_unified_command_center_evidence_review_package
from song_agent.domains.program.unified_command_center_reviewer_decision_board_verifier import REQUIRED_ENTRIES as REQUIRED_ENTRIES, UNIFIED_COMMAND_CENTER_REVIEWER_DECISION_BOARD_PACKAGE_TYPE as UNIFIED_COMMAND_CENTER_REVIEWER_DECISION_BOARD_PACKAGE_TYPE, UNIFIED_COMMAND_CENTER_REVIEWER_DECISION_BOARD_SCHEMA_VERSION as UNIFIED_COMMAND_CENTER_REVIEWER_DECISION_BOARD_SCHEMA_VERSION, verify_unified_command_center_reviewer_decision_board_package as verify_unified_command_center_reviewer_decision_board_package, write_unified_command_center_reviewer_decision_board_verification_report as write_unified_command_center_reviewer_decision_board_verification_report

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

_bounded = _make_deferred_global('_bounded')
_path_or_none = _make_deferred_global('_path_or_none')
_sha256_path = _make_deferred_global('_sha256_path')
_zip_manifest_hash = _make_deferred_global('_zip_manifest_hash')

def bind_globals(namespace: dict[str, object]) -> None:
    global _bounded, _path_or_none, _sha256_path, _zip_manifest_hash
    _bounded = namespace.get('_bounded', _bounded)
    _path_or_none = namespace.get('_path_or_none', _path_or_none)
    _sha256_path = namespace.get('_sha256_path', _sha256_path)
    _zip_manifest_hash = namespace.get('_zip_manifest_hash', _zip_manifest_hash)
    _bind_deferred_defaults(namespace)


DEFAULT_POLICY = {
    "min_accepted_count": 2,
    "min_organization_count": 1,
    "required_roles": ["technical_reviewer", "release_owner"],
    "block_on_required_rejection": True,
    "block_on_any_rejection": False,
    "block_on_high_findings": True,
    "block_on_critical_findings": True,
}




class UnifiedCommandCenterReviewerDecisionBoardError(ValueError):
    pass

class UnifiedCommandCenterReviewerDecisionBoardNotFoundError(UnifiedCommandCenterReviewerDecisionBoardError):
    pass

class UnifiedCommandCenterReviewerDecisionBoardStateError(UnifiedCommandCenterReviewerDecisionBoardError):
    pass

def _accepted_evidence_item(row: DomainDocument, review_zip: object, review_report: object) -> DomainDocument:
    zip_path = _path_or_none(row.get("zip_path"))
    verification_report_path = _path_or_none(row.get("verification_report_path"))
    response_report_path = _path_or_none(row.get("response_verification_report_path"))
    runtime: DomainDocument = {}
    external: DomainDocument = {}
    response_summary: DomainDocument = {}
    public_response: DomainDocument = {}
    blockers: list[str] = []
    if not zip_path or not zip_path.exists():
        blockers.append("accepted_evidence_zip_missing")
    if not verification_report_path or not verification_report_path.exists():
        blockers.append("accepted_evidence_verification_missing")
    if not response_report_path or not response_report_path.exists():
        blockers.append("accepted_evidence_response_verification_missing")
    if not blockers:
        runtime = verify_unified_command_center_evidence_review_acceptance_package(
            _as_path(zip_path),
            strict=True,
            require_accepted=True,
            review_pack_path=review_zip,
            review_pack_verification_report_path=review_report,
            response_verification_report_path=response_report_path,
        )
        external = read_json(_as_path(verification_report_path))
        response_summary = read_json(_as_path(response_report_path))
        public_response = _read_zip_json(_as_path(zip_path), "original-response-public.json")
        if external.get("status") != "passed" or runtime.get("status") != "passed":
            blockers.append("accepted_evidence_verification_failed")
        if external.get("zip_sha256") != runtime.get("zip_sha256") or external.get("manifest_hash") != runtime.get("manifest_hash"):
            blockers.append("accepted_evidence_verification_stale")
    reviewer = _as_document(public_response.get("reviewer"))
    role = _bounded(reviewer.get("role") or "reviewer", 80)
    organization = _bounded(reviewer.get("organization") or "", 120)
    reviewer_name = _bounded(reviewer.get("name") or "Reviewer", 120)
    hint_role = _bounded(row.get("role") or "", 80)
    hint_organization = _bounded(row.get("organization") or "", 120)
    hint_reviewer = _bounded(row.get("reviewer_id") or "", 120)
    if public_response:
        if hint_role and hint_role != role:
            blockers.append("accepted_evidence_role_mismatch")
        if hint_organization and hint_organization != organization:
            blockers.append("accepted_evidence_organization_mismatch")
        if hint_reviewer and hint_reviewer != reviewer_name:
            blockers.append("accepted_evidence_reviewer_mismatch")
    item = {
        "evidence_id": str(row.get("evidence_id") or runtime.get("summary", {}).get("evidence_id") or ""),
        "response_id": str(public_response.get("response_id") or response_summary.get("response_id") or ""),
        "result": public_response.get("result") or runtime.get("summary", {}).get("result"),
        "status": "passed" if not blockers else "failed",
        "blockers": blockers,
        "reviewer": {
            "name": reviewer_name,
            "organization": organization,
            "role": role,
        },
        "payload_hints": {
            "reviewer": hint_reviewer,
            "organization": hint_organization,
            "role": hint_role,
        },
        "role": role,
        "organization": organization,
        "zip_sha256": runtime.get("zip_sha256") or _sha256_path(zip_path),
        "zip_size_bytes": runtime.get("zip_size_bytes") or (zip_path.stat().st_size if zip_path and zip_path.exists() else None),
        "manifest_hash": runtime.get("manifest_hash"),
        "acceptance_verification_hash": external.get("integrity_hash"),
        "response_verification_hash": response_summary.get("integrity_hash"),
        "response_public_hash": public_response.get("integrity_hash"),
        "review_pack_zip_sha256": (public_response.get("bindings") or {}).get("review_pack_zip_sha256") or _read_zip_json(zip_path, "acceptance-report.json").get("review_pack_zip_sha256") if zip_path and zip_path.exists() else None,
        "findings": public_response.get("findings", []) if isinstance(public_response.get("findings"), list) else [],
    }
    item["item_hash"] = stable_hash(item)
    return item

def _source_document(center_id: str, board_id: str, paths: DomainDocument) -> DomainDocument:
    review_zip = _path_or_none(paths.get("review_zip"))
    review_verification_report = _path_or_none(paths.get("review_verification_report"))
    review_verification = read_json(review_verification_report) if review_verification_report and review_verification_report.exists() else {}
    runtime = verify_unified_command_center_evidence_review_package(review_zip, strict=False, require_replay_passed=False) if review_zip and review_zip.exists() else {}
    policy = _policy(_as_document(paths.get("policy")))
    source = sanitize_metadata(
        {
            "schema_version": UNIFIED_COMMAND_CENTER_REVIEWER_DECISION_BOARD_SCHEMA_VERSION,
            "package_type": "musicforge_unified_command_center_reviewer_decision_board_source",
            "center_id": center_id,
            "board_id": board_id,
            "review_id": paths.get("review_id"),
            "created_at": now_iso(),
            "status": "draft",
            "policy": policy,
            "evidence_review": {
                "zip_sha256": runtime.get("zip_sha256") or _sha256_path(review_zip),
                "zip_size_bytes": runtime.get("zip_size_bytes") or (review_zip.stat().st_size if review_zip and review_zip.exists() else None),
                "manifest_hash": runtime.get("manifest_hash") or _zip_manifest_hash(review_zip),
                "verification_hash": review_verification.get("integrity_hash"),
                "verification_status": review_verification.get("status"),
                "runtime_status": runtime.get("status"),
            },
        }
    )
    source["source_hash"] = stable_hash({key: value for key, value in source.items() if key not in {"source_hash", "integrity_hash", "created_at"}})
    source["integrity_hash"] = _integrity_hash(source)
    return source

def _response_rows(paths: DomainDocument, accepted_items: list[DomainDocument]) -> list[DomainDocument]:
    rows: list[DomainDocument] = []
    for item in accepted_items:
        rows.append(
            {
                "response_id": item.get("response_id"),
                "result": item.get("result"),
                "status": item.get("status"),
                "reviewer": item.get("reviewer"),
                "role": item.get("role"),
                "organization": item.get("organization"),
                "accepted_evidence_id": item.get("evidence_id"),
                "accepted_evidence_hash": item.get("item_hash"),
                "findings": item.get("findings", []),
            }
        )
    for row in paths.get("responses", []) if isinstance(paths.get("responses"), list) else []:
        if not isinstance(row, dict):
            continue
        reviewer = _as_document(row.get("reviewer"))
        rows.append(
            sanitize_metadata(
                {
                    "response_id": _bounded(row.get("response_id") or row.get("id") or f"manual-{len(rows) + 1:03d}", 120),
                    "result": _bounded(row.get("result") or "needs_changes", 40),
                    "status": _bounded(row.get("status") or "current", 40),
                    "reviewer": {
                        "name": _bounded(reviewer.get("name") or row.get("reviewer_name") or "Reviewer", 120),
                        "organization": _bounded(reviewer.get("organization") or row.get("organization") or "", 120),
                        "role": _bounded(reviewer.get("role") or row.get("role") or "reviewer", 80),
                    },
                    "role": _bounded(row.get("role") or reviewer.get("role") or "reviewer", 80),
                    "organization": _bounded(row.get("organization") or reviewer.get("organization") or "", 120),
                    "accepted_evidence_id": row.get("accepted_evidence_id"),
                    "findings": _as_list(row.get("findings")),
                }
            )
        )
    return rows

def _roster_document(center_id: str, board_id: str, source: DomainDocument, accepted_items: list[DomainDocument], responses: list[DomainDocument]) -> DomainDocument:
    reviewers: dict[str, DomainDocument] = {}
    for row in responses:
        reviewer = _as_document(row.get("reviewer"))
        key = str(row.get("response_id") or reviewer.get("name") or len(reviewers))
        reviewers[key] = {
            "reviewer_id": key,
            "name": reviewer.get("name"),
            "organization": row.get("organization") or reviewer.get("organization"),
            "role": row.get("role") or reviewer.get("role"),
            "result": row.get("result"),
            "accepted_evidence_id": row.get("accepted_evidence_id"),
        }
    doc = {"package_type": "musicforge_unified_command_center_reviewer_decision_board_roster", "center_id": center_id, "board_id": board_id, "source_hash": source.get("source_hash"), "reviewers": list(reviewers.values()), "summary": {"reviewer_count": len(reviewers), "accepted_reviewer_count": len([item for item in accepted_items if item.get("status") == "passed"])}}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc

def _response_index_document(center_id: str, board_id: str, source: DomainDocument, responses: list[DomainDocument]) -> DomainDocument:
    items = []
    for row in responses:
        entry = dict(row)
        entry["response_hash"] = stable_hash(entry)
        items.append(entry)
    doc = {"package_type": "musicforge_unified_command_center_reviewer_decision_board_response_index", "center_id": center_id, "board_id": board_id, "source_hash": source.get("source_hash"), "responses": items, "summary": {"response_count": len(items), "accepted_count": len([row for row in items if row.get("result") == "accepted"]), "needs_changes_count": len([row for row in items if row.get("result") == "needs_changes"]), "rejected_count": len([row for row in items if row.get("result") == "rejected"])}}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc

def _accepted_index_document(center_id: str, board_id: str, source: DomainDocument, accepted_items: list[DomainDocument]) -> DomainDocument:
    doc = {"package_type": "musicforge_unified_command_center_reviewer_decision_board_accepted_evidence_index", "center_id": center_id, "board_id": board_id, "source_hash": source.get("source_hash"), "items": accepted_items, "summary": {"accepted_evidence_count": len(accepted_items), "passed_count": len([row for row in accepted_items if row.get("status") == "passed"]), "failed_count": len([row for row in accepted_items if row.get("status") != "passed"])}}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc

def _finding_ledger_document(center_id: str, board_id: str, source: DomainDocument, responses: list[DomainDocument], extra_findings: list[object]) -> DomainDocument:
    findings: list[DomainDocument] = []
    index = 1
    for row in responses:
        for finding in row.get("findings", []) if isinstance(row.get("findings"), list) else []:
            if isinstance(finding, dict):
                findings.append(_finding_row(index, row, finding))
                index += 1
    for finding in extra_findings:
        if isinstance(finding, dict):
            findings.append(_finding_row(index, {}, finding))
            index += 1
    doc = {"package_type": "musicforge_unified_command_center_reviewer_decision_board_finding_ledger", "center_id": center_id, "board_id": board_id, "source_hash": source.get("source_hash"), "findings": findings, "summary": {"finding_count": len(findings), "high_count": len([row for row in findings if row.get("severity") == "high"]), "critical_count": len([row for row in findings if row.get("severity") == "critical"]), "open_high_or_critical_count": len([row for row in findings if row.get("status") == "open" and row.get("severity") in {"high", "critical"}])}}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc

def _finding_row(index: int, response: DomainDocument, finding: DomainDocument) -> DomainDocument:
    row = sanitize_metadata(
        {
            "finding_id": _bounded(finding.get("finding_id") or f"finding-{index:03d}", 80),
            "response_id": response.get("response_id"),
            "role": response.get("role"),
            "severity": _bounded(finding.get("severity") or "low", 40).lower(),
            "component": _bounded(finding.get("component") or "", 120),
            "message": _bounded(finding.get("message") or finding.get("summary") or "", 1000),
            "status": _bounded(finding.get("status") or "open", 40).lower(),
        }
    )
    row["finding_hash"] = stable_hash(row)
    return row

def _conflict_report_document(center_id: str, board_id: str, source: DomainDocument, responses: list[DomainDocument], findings: DomainDocument, policy: DomainDocument) -> DomainDocument:
    required_roles = set(policy.get("required_roles") or [])
    rejected_required = [row for row in responses if row.get("result") == "rejected" and row.get("role") in required_roles]
    rejected_any = [row for row in responses if row.get("result") == "rejected"]
    open_high = [row for row in findings.get("findings", []) if row.get("status") == "open" and row.get("severity") == "high"]
    open_critical = [row for row in findings.get("findings", []) if row.get("status") == "open" and row.get("severity") == "critical"]
    blockers: list[str] = []
    if policy.get("block_on_required_rejection") and rejected_required:
        blockers.append("required_reviewer_rejected")
    if policy.get("block_on_any_rejection") and rejected_any:
        blockers.append("reviewer_rejected")
    if policy.get("block_on_high_findings") and open_high:
        blockers.append("open_high_finding")
    if policy.get("block_on_critical_findings") and open_critical:
        blockers.append("open_critical_finding")
    doc = {"package_type": "musicforge_unified_command_center_reviewer_decision_board_conflict_report", "center_id": center_id, "board_id": board_id, "source_hash": source.get("source_hash"), "status": "failed" if blockers else "passed", "blockers": blockers, "summary": {"rejected_required_count": len(rejected_required), "rejected_count": len(rejected_any), "open_high_count": len(open_high), "open_critical_count": len(open_critical)}}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc

def _quorum_report_document(center_id: str, board_id: str, source: DomainDocument, accepted_items: list[DomainDocument], responses: list[DomainDocument]) -> DomainDocument:
    policy = source.get("policy", {})
    passed = [row for row in accepted_items if row.get("status") == "passed" and row.get("result") == "accepted"]
    roles = {str(row.get("role") or "") for row in passed}
    organizations = {str(row.get("organization") or "") for row in passed if row.get("organization")}
    evidence_ids = [str(row.get("evidence_id") or "") for row in passed]
    duplicates = sorted({item for item in evidence_ids if item and evidence_ids.count(item) > 1})
    required_roles = set(policy.get("required_roles") or [])
    missing_roles = sorted(required_roles - roles)
    blockers: list[str] = []
    if len(passed) < int(policy.get("min_accepted_count") or 0):
        blockers.append("min_accepted_count")
    if len(organizations) < int(policy.get("min_organization_count") or 0):
        blockers.append("min_organization_count")
    if missing_roles:
        blockers.append("required_roles")
    if duplicates:
        blockers.append("duplicate_accepted_evidence")
    doc = {"package_type": "musicforge_unified_command_center_reviewer_decision_board_quorum_report", "center_id": center_id, "board_id": board_id, "source_hash": source.get("source_hash"), "status": "failed" if blockers else "passed", "blockers": blockers, "summary": {"accepted_count": len(passed), "organization_count": len(organizations), "roles": sorted(roles), "required_roles": sorted(required_roles), "missing_roles": missing_roles, "duplicate_evidence_ids": duplicates}}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc

def _decision_matrix_document(center_id: str, board_id: str, source: DomainDocument, roster: DomainDocument, response_index: DomainDocument, quorum: DomainDocument, conflicts: DomainDocument) -> DomainDocument:
    roles = sorted(set((source.get("policy", {}).get("required_roles") or []) + [row.get("role") for row in roster.get("reviewers", []) if row.get("role")]))
    rows = []
    responses = response_index.get("responses", [])
    for role in roles:
        role_responses = [row for row in responses if row.get("role") == role]
        accepted = len([row for row in role_responses if row.get("result") == "accepted"])
        rejected = len([row for row in role_responses if row.get("result") == "rejected"])
        needs_changes = len([row for row in role_responses if row.get("result") == "needs_changes"])
        status = "accepted" if accepted else "rejected" if rejected else "needs_changes" if needs_changes else "missing"
        rows.append({"role": role, "status": status, "accepted_count": accepted, "needs_changes_count": needs_changes, "rejected_count": rejected})
    doc = {"package_type": "musicforge_unified_command_center_reviewer_decision_board_decision_matrix", "center_id": center_id, "board_id": board_id, "source_hash": source.get("source_hash"), "rows": rows, "summary": {"quorum_status": quorum.get("status"), "conflict_status": conflicts.get("status"), "role_count": len(rows)}}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc

def _decision_report_document(center_id: str, board_id: str, source: DomainDocument, quorum: DomainDocument, conflicts: DomainDocument, matrix: DomainDocument) -> DomainDocument:
    blockers = []
    if quorum.get("status") != "passed":
        blockers.extend([f"quorum:{item}" for item in quorum.get("blockers", [])])
    if conflicts.get("status") != "passed":
        blockers.extend([f"conflict:{item}" for item in conflicts.get("blockers", [])])
    status = "ready_for_signoff" if not blockers else "blocked"
    doc = {"package_type": "musicforge_unified_command_center_reviewer_decision_board_decision_report", "center_id": center_id, "board_id": board_id, "source_hash": source.get("source_hash"), "status": status, "blockers": blockers, "summary": {"quorum_status": quorum.get("status"), "conflict_status": conflicts.get("status"), "accepted_count": quorum.get("summary", {}).get("accepted_count"), "missing_roles": quorum.get("summary", {}).get("missing_roles", [])}}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc

def _checklist_document(center_id: str, board_id: str, source: DomainDocument, decision: DomainDocument) -> DomainDocument:
    doc = {"package_type": "musicforge_unified_command_center_reviewer_decision_board_manual_checklist", "center_id": center_id, "board_id": board_id, "source_hash": source.get("source_hash"), "items": [{"item_id": "manual-001", "label": "Decision Board chair confirms reviewer quorum and open findings.", "required": True, "status": "passed" if decision.get("status") == "ready_for_signoff" else "blocked"}]}
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc

def _manifest_document(center_id: str, board_id: str, docs: DomainDocument, export_dir: Path) -> DomainDocument:
    files = []
    for rel in sorted(REQUIRED_ENTRIES - {"manifest.json"}):
        path = export_dir / rel
        files.append({"path": rel, "sha256": _sha256_path(path), "size_bytes": path.stat().st_size if path.exists() else 0})
    manifest = {
        "schema_version": UNIFIED_COMMAND_CENTER_REVIEWER_DECISION_BOARD_SCHEMA_VERSION,
        "package_type": UNIFIED_COMMAND_CENTER_REVIEWER_DECISION_BOARD_PACKAGE_TYPE,
        "center_id": center_id,
        "board_id": board_id,
        "created_at": now_iso(),
        "source_hash": docs["source"].get("source_hash"),
        "files": files,
        "source": {
            "board_source_hash": docs["source"].get("integrity_hash"),
            "reviewer_roster_hash": docs["reviewer_roster"].get("integrity_hash"),
            "response_index_hash": docs["response_index"].get("integrity_hash"),
            "accepted_evidence_index_hash": docs["accepted_evidence_index"].get("integrity_hash"),
            "finding_ledger_hash": docs["finding_ledger"].get("integrity_hash"),
            "conflict_report_hash": docs["conflict_report"].get("integrity_hash"),
            "quorum_report_hash": docs["quorum_report"].get("integrity_hash"),
            "decision_matrix_hash": docs["decision_matrix"].get("integrity_hash"),
            "decision_report_hash": docs["decision_report"].get("integrity_hash"),
            "manual_checklist_hash": docs["manual_checklist"].get("integrity_hash"),
            "decision_signoff_hash": docs["decision_signoff"].get("integrity_hash"),
            "signoff_binding_hash": docs["signoff_binding"].get("integrity_hash"),
        },
        "summary": docs["decision_report"].get("summary", {}),
    }
    manifest["integrity_hash"] = _integrity_hash(manifest)
    return manifest

def _reviewer_guide(docs: DomainDocument) -> str:
    source = docs.get("source", {})
    decision = docs.get("decision_report", {})
    return sanitize_sensitive_text(
        "\n".join(
            [
                "# MusicForge Unified Command Center Reviewer Decision Board",
                "",
                f"Board: {source.get('board_id')}",
                f"Decision status: {decision.get('status')}",
                "Verify this archive with the Evidence Review Pack and every accepted evidence ZIP/report.",
            ]
        )
    )

def _signoff_binding_summary(center_id: str, board_id: str, signoff: DomainDocument, event: DomainDocument) -> DomainDocument:
    doc = {
        "package_type": "musicforge_unified_command_center_reviewer_decision_board_signoff_binding_summary",
        "center_id": center_id,
        "board_id": board_id,
        "status": signoff.get("status"),
        "signed_by": signoff.get("signed_by"),
        "role": signoff.get("role"),
        "signed_at": signoff.get("signed_at"),
        "signoff_hash": signoff.get("integrity_hash"),
        "signoff_payload_hash": signoff.get("payload_hash"),
        "history_event_hash": event.get("event_hash"),
        "decision_report_hash": signoff.get("decision_report_hash"),
        "quorum_report_hash": signoff.get("quorum_report_hash"),
        "accepted_evidence_index_hash": signoff.get("accepted_evidence_index_hash"),
    }
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc

def _policy(value: DomainDocument) -> DomainDocument:
    policy: DomainDocument = dict(DEFAULT_POLICY)
    for key in DEFAULT_POLICY:
        if key in value:
            policy[key] = value[key]
    policy["min_accepted_count"] = int(policy.get("min_accepted_count") or 0)
    policy["min_organization_count"] = int(policy.get("min_organization_count") or 0)
    policy["required_roles"] = [_bounded(role, 80) for role in (policy.get("required_roles") or [])]
    for key in ("block_on_required_rejection", "block_on_any_rejection", "block_on_high_findings", "block_on_critical_findings"):
        policy[key] = bool(policy.get(key))
    return policy

def _history_state(path: Path) -> DomainDocument:
    signed = False
    latest_signoff_hash = None
    if not path.exists():
        return {"signed": False, "latest_signoff_hash": None}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        if event.get("event_type") == "ucc_reviewer_decision_board_signoff_created":
            signed = True
            latest_signoff_hash = event.get("signoff_hash")
        elif event.get("event_type") == "ucc_reviewer_decision_board_signoff_reset":
            signed = False
            latest_signoff_hash = None
    return {"signed": signed, "latest_signoff_hash": latest_signoff_hash}

def _history_chain_ok(path: Path, signoff_hash: str | None) -> bool:
    if not path.exists():
        return False
    previous = None
    found = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        expected_payload = stable_hash({key: value for key, value in event.items() if key not in {"payload_hash", "event_hash"}})
        expected_event = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        if event.get("previous_event_hash") != previous or event.get("payload_hash") != expected_payload or event.get("event_hash") != expected_event:
            return False
        if event.get("event_type") == "ucc_reviewer_decision_board_signoff_created" and event.get("signoff_hash") == signoff_hash:
            found = True
        previous = event.get("event_hash")
    return found

def _gate_failed(message: str, **extra: object) -> DomainDocument:
    return {"status": "failed", "hard_block": True, "message": message, **extra}

def _read_optional_json(path: Path) -> DomainDocument:
    return read_json(path) if path.exists() else {}

def _read_zip_json(path: Path | None, rel: str) -> DomainDocument:
    if not path or not path.exists():
        return {}
    try:
        with zipfile.ZipFile(path) as archive:
            return json.loads(archive.read(rel).decode("utf-8"))
    except (OSError, zipfile.BadZipFile, KeyError, json.JSONDecodeError, ValueError):
        return {}

def _integrity_hash(payload: DomainDocument) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})

def _integrity_ok(payload: DomainDocument) -> bool:
    return bool(payload.get("integrity_hash")) and payload.get("integrity_hash") == _integrity_hash(payload)
