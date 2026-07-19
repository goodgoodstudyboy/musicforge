# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.projects import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.program.unified_command_center import UnifiedCommandCenterStore as UnifiedCommandCenterStore
from song_agent.domains.program.unified_command_center_archive_verifier import verify_unified_command_center_archive_package as verify_unified_command_center_archive_package
from song_agent.domains.program.unified_command_center_continuous_review_verifier import UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_PACKAGE_TYPE as UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_PACKAGE_TYPE, UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_SCHEMA_VERSION as UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_SCHEMA_VERSION, verify_unified_command_center_continuous_review_package as verify_unified_command_center_continuous_review_package, write_unified_command_center_continuous_review_verification_report as write_unified_command_center_continuous_review_verification_report
from song_agent.domains.program.unified_command_center_handoff import UnifiedCommandCenterHandoffStore as UnifiedCommandCenterHandoffStore
from song_agent.domains.program.unified_command_center_handoff_verifier import verify_unified_command_center_handoff_package as verify_unified_command_center_handoff_package
from song_agent.domains.program.unified_command_center_signoff import UnifiedCommandCenterSignoffStore as UnifiedCommandCenterSignoffStore
from song_agent.domains.program.unified_command_center_verifier import verify_unified_command_center_package as verify_unified_command_center_package

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

UnifiedCommandCenterContinuousReviewError = _make_deferred_global('UnifiedCommandCenterContinuousReviewError')

def bind_globals(namespace: dict[str, object]) -> None:
    global UnifiedCommandCenterContinuousReviewError
    UnifiedCommandCenterContinuousReviewError = namespace.get('UnifiedCommandCenterContinuousReviewError', UnifiedCommandCenterContinuousReviewError)
    _bind_deferred_defaults(namespace)


PASSING_EVIDENCE_STATUSES = {"passed", "ready", "clear", "signed", "accepted", "ok"}




class UnifiedCommandCenterContinuousReviewStateError(UnifiedCommandCenterContinuousReviewError):
    pass

def _input_binding(component: str, zip_path: Path, external: DomainDocument, runtime: DomainDocument) -> DomainDocument:
    return {
        "component": component,
        "status": "passed" if external.get("status") == "passed" and runtime.get("status") == "passed" else "failed",
        "zip_sha256": _sha256_path(zip_path),
        "zip_size_bytes": zip_path.stat().st_size if zip_path.exists() else None,
        "manifest_hash": runtime.get("manifest_hash") or external.get("manifest_hash"),
        "verification_hash": external.get("integrity_hash"),
        "verification_status": external.get("status"),
        "runtime_status": runtime.get("status"),
        "blockers": sorted(set((external.get("blockers") or []) + (runtime.get("blockers") or []))),
    }

def _external_evidence_rows(payload: DomainDocument) -> list[DomainDocument]:
    rows = []
    for value in payload.get("external_evidence", []) if isinstance(payload.get("external_evidence"), list) else []:
        if isinstance(value, dict):
            rows.append(sanitize_metadata(value))
    return rows

def _evidence_status(value: object) -> str:
    raw = value
    if isinstance(value, dict):
        raw = value.get("status")
        if raw is None and value.get("ok") is True:
            raw = "passed"
    normalized = str(raw or "unknown").strip().lower()
    return "passed" if normalized in PASSING_EVIDENCE_STATUSES else normalized

def _evidence_is_blocking(status: object) -> bool:
    normalized = _evidence_status(status)
    return normalized not in {"passed", "not_configured", "not_required", "skipped"}

def _report_binding(path_value: object) -> DomainDocument:
    if not path_value:
        return {"status": "not_configured", "report_hash": None}
    path = Path(path_value)
    if not path.exists():
        return {"status": "missing", "report_hash": None}
    try:
        payload = read_json(path)
        return {"status": _evidence_status(payload), "report_hash": _integrity_hash(payload) if "integrity_hash" not in payload else payload.get("integrity_hash"), "path_hash": _sha256_path(path)}
    except Exception as exc:
        return {"status": "failed", "error": sanitize_sensitive_text(str(exc)), "report_hash": None}

def _review_payload_projection(payload: DomainDocument) -> DomainDocument:
    keys = (
        "archive_zip",
        "archive_zip_path",
        "archive_verification_report",
        "archive_verification_report_path",
        "handoff_zip",
        "handoff_zip_path",
        "handoff_verification_report",
        "handoff_verification_report_path",
        "command_center_zip",
        "command_center_zip_path",
        "unified_command_center_zip",
        "command_center_verification_report",
        "command_center_verification_report_path",
        "unified_command_center_verification_report",
        "signoff_binding",
        "signoff_binding_path",
        "ga_report",
        "ga_readiness_report",
        "ga_readiness_report_path",
        "release_check_report",
        "release_check_report_path",
    )
    projection: DomainDocument = {}
    for key in keys:
        if key in payload and payload.get(key) is not None:
            projection[key] = str(payload.get(key))
    if isinstance(payload.get("external_evidence"), list):
        projection["external_evidence"] = sanitize_metadata(payload.get("external_evidence"))
    return projection

def _drift_report(center_id: str, review_id: str, plan: DomainDocument, source: DomainDocument) -> DomainDocument:
    drifts: list[DomainDocument] = []
    baseline = _as_document(plan.get("source"))
    inputs = source.get("inputs", {})
    comparisons = (
        ("archive", "archive_zip_sha256", inputs.get("archive", {}).get("zip_sha256")),
        ("archive", "archive_verification_hash", inputs.get("archive", {}).get("verification_hash")),
        ("handoff", "handoff_zip_sha256", inputs.get("handoff", {}).get("zip_sha256")),
        ("handoff", "handoff_verification_hash", inputs.get("handoff", {}).get("verification_hash")),
        ("ga", "ga_report_hash", inputs.get("ga", {}).get("report_hash")),
        ("ga", "ga_path_hash", inputs.get("ga", {}).get("path_hash")),
        ("release_check", "release_check_report_hash", inputs.get("release_check", {}).get("report_hash")),
        ("release_check", "release_check_path_hash", inputs.get("release_check", {}).get("path_hash")),
        ("external_evidence", "external_evidence_hash", _external_evidence_hash(inputs.get("external_evidence", []))),
    )
    for component, key, actual in comparisons:
        expected = baseline.get(key)
        if expected and actual and expected != actual:
            drifts.append(_drift_row(len(drifts) + 1, component, "verification_mismatch", key, expected, actual, "critical"))
    for component in ("archive", "handoff", "ucc"):
        item = inputs.get(component, {})
        if item.get("status") == "failed":
            drifts.append(_drift_row(len(drifts) + 1, component, "verification_failed", "status", "passed", item.get("status"), "critical" if component in {"archive", "handoff"} else "high"))
    ga = _as_document(inputs.get("ga"))
    if _evidence_is_blocking(ga.get("status")):
        drifts.append(_drift_row(len(drifts) + 1, "ga", "external_evidence_failed", "status", "passed", ga.get("status"), "high"))
    release_check = _as_document(inputs.get("release_check"))
    if _evidence_is_blocking(release_check.get("status")):
        drifts.append(_drift_row(len(drifts) + 1, "release_check", "external_evidence_failed", "status", "passed", release_check.get("status"), "high"))
    external_rows = _as_list(inputs.get("external_evidence"))
    for index, row in enumerate([item for item in external_rows if isinstance(item, dict)], start=1):
        if _evidence_is_blocking(row.get("status")):
            component = str(row.get("component") or row.get("component_type") or row.get("evidence_type") or f"external_evidence_{index}")
            drift = _drift_row(len(drifts) + 1, component, "external_evidence_failed", "status", "passed", row.get("status"), "high")
            drift["component_id"] = str(row.get("component_id") or row.get("evidence_id") or component)
            drifts.append(drift)
    blocking = sum(1 for row in drifts if row.get("severity") in {"critical", "high"} and row.get("status") == "open")
    checked_count = 6 + 2 + len(external_rows)
    doc = sanitize_metadata(
        {
            "schema_version": UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_SCHEMA_VERSION,
            "package_type": "musicforge_unified_command_center_drift_report",
            "review_id": review_id,
            "center_id": center_id,
            "generated_at": now_iso(),
            "status": "failed" if blocking else "passed",
            "summary": {"checked_count": checked_count, "drift_count": len(drifts), "blocking_drift_count": blocking, "warning_count": 0},
            "drifts": drifts,
            "source_hash": source.get("source_hash"),
        }
    )
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc

def _drift_row(index: int, component: str, kind: str, field: str, expected: object, actual: object, severity: str) -> DomainDocument:
    return {
        "drift_id": f"drift-{index:06d}",
        "component_type": component,
        "component_id": component,
        "severity": severity,
        "status": "open",
        "kind": kind,
        "message": f"{component} {field} changed or failed.",
        "expected": {field: expected},
        "actual": {field: actual},
        "recommended_action": "create_change_request",
    }

def _external_evidence_hash(rows: object) -> str | None:
    if not isinstance(rows, list):
        return None
    return stable_hash(sanitize_metadata(rows))

def _incident_board(center_id: str, review_id: str, drift: DomainDocument) -> DomainDocument:
    incidents = []
    for index, row in enumerate([item for item in drift.get("drifts", []) if item.get("severity") in {"critical", "high"}], start=1):
        incidents.append(
            {
                "incident_id": f"uccinc-{index:06d}",
                "source_drift_id": row.get("drift_id"),
                "severity": row.get("severity"),
                "status": "open",
                "component_type": row.get("component_type"),
                "component_id": row.get("component_id"),
                "created_at": now_iso(),
                "recommended_action": row.get("recommended_action"),
                "change_request_draft_id": f"ucccr-draft-{index:06d}",
            }
        )
    doc = sanitize_metadata(
        {
            "schema_version": UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_SCHEMA_VERSION,
            "package_type": "musicforge_unified_command_center_continuous_review_incident_board",
            "review_id": review_id,
            "center_id": center_id,
            "status": "clear" if not incidents else "open",
            "summary": {"open_count": len(incidents), "critical_count": sum(1 for row in incidents if row.get("severity") == "critical"), "change_request_draft_count": len(incidents)},
            "incidents": incidents,
            "source_hash": drift.get("source_hash"),
        }
    )
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc

def _recovery_drill_report(center_id: str, review_id: str, source: DomainDocument) -> DomainDocument:
    inputs = source.get("inputs", {})
    steps = []
    for component, step_id in (("archive", "verify_archive"), ("handoff", "verify_handoff"), ("ucc", "verify_ucc")):
        item = inputs.get(component, {})
        if component == "handoff" and item.get("required") is False:
            steps.append({"step_id": step_id, "status": "skipped", "details": {"reason": "handoff not required"}})
        else:
            steps.append({"step_id": step_id, "status": "passed" if item.get("status") == "passed" else "failed", "details": {"zip_sha256": item.get("zip_sha256"), "manifest_hash": item.get("manifest_hash"), "verification_hash": item.get("verification_hash")}})
    failed = sum(1 for row in steps if row.get("status") == "failed")
    doc = sanitize_metadata(
        {
            "schema_version": UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_SCHEMA_VERSION,
            "package_type": "musicforge_unified_command_center_recovery_drill_report",
            "review_id": review_id,
            "center_id": center_id,
            "status": "failed" if failed else "passed",
            "started_at": now_iso(),
            "finished_at": now_iso(),
            "steps": steps,
            "summary": {"step_count": len(steps), "failed_count": failed},
            "source_hash": source.get("source_hash"),
        }
    )
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc

def _runbook(center_id: str, review_id: str, source: DomainDocument, drift: DomainDocument, incidents: DomainDocument) -> DomainDocument:
    items = [
        {"item_id": "uccrv-safe-001", "action": "continuous_review.run", "safe": True, "status": "completed"},
        {"item_id": "uccrv-safe-002", "action": "continuous_review.verify", "safe": True, "status": "pending"},
    ]
    for index, row in enumerate(incidents.get("incidents", []), start=1):
        items.append({"item_id": f"uccrv-manual-{index:03d}", "action": "create_change_request_draft", "safe": False, "status": "manual_required", "source_incident_id": row.get("incident_id")})
    doc = sanitize_metadata(
        {
            "schema_version": UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_SCHEMA_VERSION,
            "package_type": "musicforge_unified_command_center_continuous_review_runbook",
            "review_id": review_id,
            "center_id": center_id,
            "created_at": now_iso(),
            "source_hash": source.get("source_hash"),
            "items": items,
            "summary": {"action_count": len(items), "safe_action_count": sum(1 for row in items if row.get("safe")), "manual_action_count": sum(1 for row in items if not row.get("safe"))},
        }
    )
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc

def _runbook_result(center_id: str, review_id: str, source_hash: str | None, results: list[DomainDocument]) -> DomainDocument:
    doc = sanitize_metadata(
        {
            "schema_version": UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_SCHEMA_VERSION,
            "package_type": "musicforge_unified_command_center_continuous_review_runbook_result",
            "review_id": review_id,
            "center_id": center_id,
            "created_at": now_iso(),
            "source_hash": source_hash,
            "results": results,
            "summary": {"completed_count": sum(1 for row in results if row.get("status") == "completed"), "failed_count": sum(1 for row in results if row.get("status") == "failed"), "manual_required_count": sum(1 for row in results if row.get("status") == "manual_required")},
        }
    )
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc

def _change_request_drafts(center_id: str, review_id: str, incidents: DomainDocument) -> DomainDocument:
    drafts = []
    for row in incidents.get("incidents", []):
        drafts.append(
            {
                "draft_id": row.get("change_request_draft_id"),
                "title": f"Resolve {row.get('component_type')} drift",
                "reason": f"Continuous Review incident {row.get('incident_id')} requires human change control.",
                "source_drift_id": row.get("source_drift_id"),
                "source_incident_id": row.get("incident_id"),
                "component_type": row.get("component_type"),
                "component_id": row.get("component_id"),
                "status": "draft",
            }
        )
    doc = sanitize_metadata({"schema_version": UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_continuous_review_change_request_drafts", "review_id": review_id, "center_id": center_id, "items": drafts, "summary": {"draft_count": len(drafts)}, "source_hash": incidents.get("source_hash")})
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc

def _package_fingerprints(center_id: str, review_id: str, source: DomainDocument) -> DomainDocument:
    inputs = source.get("inputs", {})
    items = []
    for component in ("archive", "handoff", "ucc"):
        item = inputs.get(component, {})
        items.append({"component": component, "zip_sha256": item.get("zip_sha256"), "manifest_hash": item.get("manifest_hash"), "verification_hash": item.get("verification_hash"), "status": item.get("status"), "required": item.get("required", True)})
    doc = sanitize_metadata({"schema_version": UNIFIED_COMMAND_CENTER_CONTINUOUS_REVIEW_SCHEMA_VERSION, "package_type": "musicforge_unified_command_center_continuous_review_package_fingerprints", "review_id": review_id, "center_id": center_id, "source_hash": source.get("source_hash"), "items": items})
    doc["integrity_hash"] = _integrity_hash(doc)
    return doc

def _readme(drift: DomainDocument, incidents: DomainDocument) -> str:
    return "\n".join(
        [
            "MusicForge Unified Command Center Continuous Review",
            "",
            f"Status: {drift.get('status')}",
            f"Open incidents: {(incidents.get('summary') or {}).get('open_count', 0)}",
            "",
            "Verify with verify-unified-command-center-continuous-review-package and the current UCC Archive/Handoff evidence.",
            "",
        ]
    )

def _gate_failed(message: str, **extra: object) -> DomainDocument:
    return {"status": "failed", "hard_block": True, "message": message, **extra}

def _read_json_if_exists(path: Path) -> DomainDocument:
    if not path.exists():
        return {"status": "missing"}
    return read_json(path)

def _ucc_zip_summary(zip_path: Path) -> DomainDocument:
    try:
        with zipfile.ZipFile(zip_path) as archive:
            manifest = read_json_from_zip(archive, "manifest.json")
            return {
                "status": "passed" if _integrity_ok(manifest) else "failed",
                "zip_sha256": _sha256_path(zip_path),
                "manifest_hash": manifest.get("integrity_hash"),
                "blockers": [] if _integrity_ok(manifest) else ["ucc_manifest_integrity"],
            }
    except Exception:
        return {"status": "failed", "zip_sha256": _sha256_path(zip_path), "manifest_hash": None, "blockers": ["ucc_zip_readable"]}

def read_json_from_zip(archive: zipfile.ZipFile, name: str) -> DomainDocument:
    import json

    return json.loads(archive.read(name).decode("utf-8"))

def _bounded(value: object, limit: int) -> str:
    return sanitize_sensitive_text(str(value or ""))[:limit]

def _safe_id(value: str) -> str:
    import re

    return re.sub(r"[^A-Za-z0-9_.:-]+", "-", str(value)).strip("-")

def _file_record(path: Path, rel: str) -> DomainDocument:
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_path(path)}

def _integrity_ok(payload: DomainDocument) -> bool:
    return bool(payload) and payload.get("integrity_hash") == _integrity_hash(payload)

def _integrity_hash(payload: DomainDocument) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})

def _sha256_path(path: Path | str | None) -> str | None:
    if not path or not Path(path).exists() or not Path(path).is_file():
        return None
    import hashlib

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
