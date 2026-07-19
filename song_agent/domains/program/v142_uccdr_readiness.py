# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document
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
from song_agent.domains.program.unified_command_center_continuous_review import UnifiedCommandCenterContinuousReviewStore as UnifiedCommandCenterContinuousReviewStore
from song_agent.domains.program.unified_command_center_drift_response_verifier import REQUIRED_ENTRIES as REQUIRED_ENTRIES, UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_CR_BINDING_REPORT_PACKAGE_TYPE as UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_CR_BINDING_REPORT_PACKAGE_TYPE, UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_PACKAGE_TYPE as UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_PACKAGE_TYPE, UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_SCHEMA_VERSION as UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_SCHEMA_VERSION, verify_unified_command_center_drift_response_package as verify_unified_command_center_drift_response_package, write_unified_command_center_drift_response_verification_report as write_unified_command_center_drift_response_verification_report
from song_agent.domains.program.unified_command_center_handoff import UnifiedCommandCenterHandoffStore as UnifiedCommandCenterHandoffStore
from song_agent.domains.program.unified_command_center_signoff import UnifiedCommandCenterSignoffStore as UnifiedCommandCenterSignoffStore

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

key = _make_deferred_global('key')

def bind_globals(namespace: dict[str, object]) -> None:
    global key
    key = namespace.get('key', key)
    _bind_deferred_defaults(namespace)






class UnifiedCommandCenterDriftResponseError(ValueError):
    pass

class UnifiedCommandCenterDriftResponseNotFoundError(UnifiedCommandCenterDriftResponseError):
    pass

class UnifiedCommandCenterDriftResponseStateError(UnifiedCommandCenterDriftResponseError):
    pass

def _source_document(center_id: str, response_id: str, source_docs: DomainDocument, review_zip_path: Path, verification_path: Path) -> DomainDocument:
    review_id = str(source_docs.get("plan", {}).get("review_id") or source_docs.get("drift_report", {}).get("review_id") or "")
    drift = _as_document(source_docs.get("drift_report"))
    incidents = _as_document(source_docs.get("incident_board"))
    verification = read_json(verification_path) if verification_path.exists() else {}
    review_binding = _review_binding(review_id, review_zip_path, verification_path, verification, drift, incidents)
    source_hash = stable_hash({"center_id": center_id, "response_id": response_id, "source_review": review_binding, "drift_report_hash": drift.get("integrity_hash"), "incident_board_hash": incidents.get("integrity_hash")})
    doc = sanitize_metadata(
        {
            "schema_version": UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_SCHEMA_VERSION,
            "package_type": "musicforge_unified_command_center_drift_response_source",
            "center_id": center_id,
            "response_id": response_id,
            "source_review_id": review_id,
            "source_review": review_binding,
            "drift_report_hash": drift.get("integrity_hash"),
            "incident_board_hash": incidents.get("integrity_hash"),
            "source_hash": source_hash,
            "tool": {"name": "MusicForge Unified Command Center Drift Response", "version": __version__},
        }
    )
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc

def _review_binding(review_id: str, review_zip_path: Path, verification_path: Path, verification: DomainDocument, drift: DomainDocument, incidents: DomainDocument) -> DomainDocument:
    return {
        "review_id": review_id,
        "zip_sha256": _sha256_path(review_zip_path),
        "zip_size_bytes": review_zip_path.stat().st_size if review_zip_path.exists() else None,
        "manifest_hash": verification.get("manifest_hash"),
        "verification_hash": verification.get("integrity_hash"),
        "verification_status": verification.get("status"),
        "drift_report_hash": drift.get("integrity_hash"),
        "incident_board_hash": incidents.get("integrity_hash"),
        "drift_status": drift.get("status"),
        "incident_status": incidents.get("status"),
    }

def _plan_document(center_id: str, response_id: str, drift: DomainDocument, incidents: DomainDocument, source: DomainDocument) -> DomainDocument:
    items = []
    for index, row in enumerate([item for item in drift.get("drifts", []) if isinstance(item, dict) and item.get("status") == "open"], start=1):
        action_type = "manual_change_request" if row.get("severity") in {"critical", "high"} else "safe_recheck_prepare"
        items.append(
            {
                "plan_item_id": f"plan-{index:06d}",
                "source_drift_id": row.get("drift_id"),
                "component_type": row.get("component_type"),
                "component_id": row.get("component_id"),
                "severity": row.get("severity"),
                "action_type": action_type,
                "requires_change_request": action_type == "manual_change_request",
                "status": "planned",
            }
        )
    doc = sanitize_metadata({"schema_version": UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_drift_response_plan", "center_id": center_id, "response_id": response_id, "source_review_id": source.get("source_review_id"), "source_hash": source.get("source_hash"), "items": items, "summary": {"item_count": len(items), "manual_required_count": sum(1 for row in items if row.get("requires_change_request")), "incident_count": int((incidents.get("summary") or {}).get("open_count") or 0)}})
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc

def _queue_document(center_id: str, response_id: str, plan: DomainDocument, source: DomainDocument) -> DomainDocument:
    items = []
    for index, row in enumerate(plan.get("items", []), start=1):
        manual = bool(row.get("requires_change_request"))
        items.append(
            {
                "item_id": f"item-{index:06d}",
                "plan_item_id": row.get("plan_item_id"),
                "source_drift_id": row.get("source_drift_id"),
                "component_type": row.get("component_type"),
                "component_id": row.get("component_id"),
                "severity": row.get("severity"),
                "action": "prepare_recheck" if not manual else "bind_approved_change_request",
                "safe": not manual,
                "status": "pending" if not manual else "manual_required",
            }
        )
    doc = sanitize_metadata({"schema_version": UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_drift_response_action_queue", "center_id": center_id, "response_id": response_id, "source_hash": source.get("source_hash"), "items": items, "summary": {"action_count": len(items), "safe_action_count": sum(1 for row in items if row.get("safe")), "manual_required_count": sum(1 for row in items if not row.get("safe"))}})
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc

def _results_document(center_id: str, response_id: str, source_hash: str | None, rows: list[DomainDocument]) -> DomainDocument:
    doc = sanitize_metadata({"schema_version": UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_drift_response_action_results", "center_id": center_id, "response_id": response_id, "source_hash": source_hash, "results": rows, "summary": {"completed_count": sum(1 for row in rows if row.get("status") == "completed"), "manual_required_count": sum(1 for row in rows if row.get("status") == "manual_required"), "failed_count": sum(1 for row in rows if row.get("status") == "failed")}})
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc

def _cr_bindings_document(center_id: str, response_id: str, source_hash: str | None, rows: list[DomainDocument]) -> DomainDocument:
    doc = sanitize_metadata({"schema_version": UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_drift_response_change_request_bindings", "center_id": center_id, "response_id": response_id, "source_hash": source_hash, "items": rows, "summary": {"binding_count": len(rows), "approved_count": sum(1 for row in rows if row.get("status") == "approved")}})
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc

def _cr_binding_report_document(center_id: str, response_id: str, source_hash: str | None, queue: DomainDocument, cr_bindings: DomainDocument) -> DomainDocument:
    queue_items = {str(row.get("item_id")): row for row in queue.get("items", []) if isinstance(row, dict)}
    rows = []
    for binding in [row for row in cr_bindings.get("items", []) if isinstance(row, dict)]:
        item_id = str(binding.get("item_id") or "")
        item = queue_items.get(item_id, {})
        proof = sanitize_metadata(
            {
                "item_id": item_id,
                "source_drift_id": binding.get("source_drift_id") or item.get("source_drift_id"),
                "component_type": binding.get("component_type") or item.get("component_type"),
                "component_id": binding.get("component_id") or item.get("component_id"),
                "severity": binding.get("severity") or item.get("severity"),
                "action": binding.get("action") or item.get("action"),
                "change_request_id": binding.get("change_request_id"),
                "status": binding.get("status"),
                "approved_by": binding.get("approved_by"),
                "approved_at": binding.get("approved_at"),
                "approval_hash": binding.get("approval_hash") or _approval_hash(binding),
                "binding_hash": binding.get("binding_hash"),
            }
        )
        proof["proof_hash"] = stable_hash({key: value for key, value in proof.items() if key != "proof_hash"})
        rows.append(proof)
    doc = sanitize_metadata(
        {
            "schema_version": UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_SCHEMA_VERSION,
            "package_type": UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_CR_BINDING_REPORT_PACKAGE_TYPE,
            "center_id": center_id,
            "response_id": response_id,
            "source_hash": source_hash,
            "action_queue_hash": queue.get("integrity_hash"),
            "change_request_bindings_hash": cr_bindings.get("integrity_hash"),
            "items": rows,
            "summary": {
                "binding_count": len(rows),
                "approved_count": sum(1 for row in rows if row.get("status") == "approved"),
                "manual_required_count": sum(1 for row in queue.get("items", []) if isinstance(row, dict) and not row.get("safe")),
            },
        }
    )
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc

def _recheck_document(center_id: str, response_id: str, source_hash: str | None, binding: DomainDocument | None) -> DomainDocument:
    status = "passed" if binding and binding.get("verification_status") == "passed" and binding.get("drift_status") == "passed" else "missing"
    doc = sanitize_metadata({"schema_version": UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_drift_response_recheck_summary", "center_id": center_id, "response_id": response_id, "source_hash": source_hash, "status": status, "review": binding or {}, "summary": {"recheck_bound": bool(binding), "status": status}})
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc

def _closeout_document(center_id: str, response_id: str, source_hash: str | None, queue: DomainDocument, results: DomainDocument, cr_bindings: DomainDocument, recheck: DomainDocument, *, status: str, closed_by: str | None = None, reason: str | None = None) -> DomainDocument:
    blockers: list[DomainDocument] = []
    manual_ids = {str(row.get("item_id")) for row in queue.get("items", []) if isinstance(row, dict) and not row.get("safe")}
    bound_ids = {str(row.get("item_id")) for row in cr_bindings.get("items", []) if isinstance(row, dict) and row.get("status") == "approved"}
    completed_safe = {str(row.get("item_id")) for row in results.get("results", []) if isinstance(row, dict) and row.get("status") == "completed"}
    safe_ids = {str(row.get("item_id")) for row in queue.get("items", []) if isinstance(row, dict) and row.get("safe")}
    missing_safe = sorted(safe_ids - completed_safe)
    missing_manual = sorted(manual_ids - bound_ids)
    if missing_safe:
        blockers.append({"blocker_id": "safe_actions_incomplete", "item_ids": missing_safe})
    if missing_manual:
        blockers.append({"blocker_id": "change_request_missing", "item_ids": missing_manual})
    if recheck.get("status") != "passed":
        blockers.append({"blocker_id": "recheck_missing_or_failed", "status": recheck.get("status")})
    final_status = "closed" if status == "closed" and not blockers else "blocked" if status == "closed" else status
    doc = sanitize_metadata(
        {
            "schema_version": UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_SCHEMA_VERSION,
            "package_type": "musicforge_unified_command_center_drift_response_closeout",
            "center_id": center_id,
            "response_id": response_id,
            "source_hash": source_hash,
            "status": final_status,
            "closed_at": now_iso() if final_status == "closed" else None,
            "closed_by": closed_by,
            "reason": reason,
            "recheck_status": recheck.get("status"),
            "blockers": blockers,
            "summary": {"blocker_count": len(blockers), "manual_required_count": len(manual_ids), "approved_cr_count": len(bound_ids), "safe_action_count": len(safe_ids), "completed_safe_count": len(completed_safe)},
            "bindings": {
                "action_queue_hash": queue.get("integrity_hash"),
                "action_results_hash": results.get("integrity_hash"),
                "change_request_bindings_hash": cr_bindings.get("integrity_hash"),
                "recheck_summary_hash": recheck.get("integrity_hash"),
            },
        }
    )
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc

def _fingerprints_document(center_id: str, response_id: str, source: DomainDocument) -> DomainDocument:
    doc = sanitize_metadata({"schema_version": UNIFIED_COMMAND_CENTER_DRIFT_RESPONSE_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_drift_response_package_fingerprints", "center_id": center_id, "response_id": response_id, "source_hash": source.get("source_hash"), "items": [{"component": "source_review", **(source.get("source_review") or {})}]})
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc

def _highest_severity(drift: DomainDocument) -> str:
    order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    severities = [str(row.get("severity") or "low") for row in drift.get("drifts", []) if isinstance(row, dict)]
    return max(severities or ["low"], key=lambda value: order.get(value, 0))

def _read_json_required(path: Path) -> DomainDocument:
    if not path.exists():
        raise UnifiedCommandCenterDriftResponseNotFoundError(f"Required Drift Response document is missing: {path.name}.")
    return read_json(path)

def _file_record(path: Path, rel: str) -> DomainDocument:
    return {"entry": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_path(path)}

def _integrity_ok(payload: DomainDocument) -> bool:
    return bool(payload) and payload.get("integrity_hash") == _integrity_hash(payload)

def _integrity_hash(payload: DomainDocument) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})

def _approval_hash(binding: DomainDocument) -> str:
    return stable_hash(
        {
            "change_request_id": binding.get("change_request_id"),
            "status": binding.get("status"),
            "approved_by": binding.get("approved_by"),
            "approved_at": binding.get("approved_at"),
            "reason": binding.get("reason"),
            "evidence_hash": binding.get("evidence_hash"),
        }
    )

def _sha256_path(path: Path | str | None) -> str | None:
    if not path or not Path(path).exists() or not Path(path).is_file():
        return None
    import hashlib

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _bounded(value: object, limit: int) -> str:
    return sanitize_sensitive_text(str(value or ""))[:limit]

def _safe_id(value: str) -> str:
    import re

    return re.sub(r"[^A-Za-z0-9_.:-]+", "-", str(value)).strip("-")

def _gate_failed(message: str, **extra: object) -> DomainDocument:
    return {"status": "failed", "hard_block": True, "message": message, **extra}
