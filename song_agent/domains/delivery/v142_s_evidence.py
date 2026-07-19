# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
import hashlib as hashlib
import json as json
import threading as threading
from dataclasses import dataclass as dataclass, field as field
from pathlib import Path as Path
from song_agent.domains.delivery.distribution import DistributionNotFoundError as DistributionNotFoundError, DistributionStore as DistributionStore, DistributionTarget as DistributionTarget, SIGNED_DISTRIBUTION_STATUSES as SIGNED_DISTRIBUTION_STATUSES, distribution_signoff_summary as distribution_signoff_summary, distribution_target_summary as distribution_target_summary
from song_agent.domains.delivery.distribution_export import read_distribution_export_manifest as read_distribution_export_manifest
from song_agent.domains.delivery.distribution_profiles import DISTRIBUTION_BLOCKED_KEYS as DISTRIBUTION_BLOCKED_KEYS
from song_agent.domains.delivery.distribution_verifier import distribution_verification_summary as distribution_verification_summary, verify_distribution_package as verify_distribution_package
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import ReleaseStore as ReleaseStore, stable_hash as stable_hash

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

SubmissionBatch = _make_deferred_global('SubmissionBatch')
SubmissionItem = _make_deferred_global('SubmissionItem')
SubmissionStore = _make_deferred_global('SubmissionStore')
SubmissionValidationError = _make_deferred_global('SubmissionValidationError')
ch = _make_deferred_global('ch')

def bind_globals(namespace: dict[str, object]) -> None:
    global SubmissionBatch, SubmissionItem, SubmissionStore, SubmissionValidationError, ch
    SubmissionBatch = namespace.get('SubmissionBatch', SubmissionBatch)
    SubmissionItem = namespace.get('SubmissionItem', SubmissionItem)
    SubmissionStore = namespace.get('SubmissionStore', SubmissionStore)
    SubmissionValidationError = namespace.get('SubmissionValidationError', SubmissionValidationError)
    ch = namespace.get('ch', ch)
    _bind_deferred_defaults(namespace)


SUBMISSION_ROOT_NAME = "submissions"
SUBMISSION_BATCH_SCHEMA_VERSION = 1
SUBMISSION_ITEM_SCHEMA_VERSION = 1
SUBMISSION_STATUSES = {
    "draft",
    "qa_failed",
    "qa_warning",
    "qa_passed",
    "exported",
    "signed",
    "submitted",
    "partially_accepted",
    "accepted",
    "needs_changes",
    "archived",
}
SUBMISSION_ITEM_STATUSES = {
    "pending",
    "ready",
    "submitted",
    "feedback_received",
    "needs_changes",
    "accepted",
    "rejected",
    "withdrawn",
}
SIGNED_SUBMISSION_STATUSES = {"signed", "force_signed"}




def submission_batch_summary(batch: SubmissionBatch | DomainDocument | None) -> DomainDocument:
    data = batch.to_dict() if isinstance(batch, SubmissionBatch) else _as_document(batch)
    items = _as_list(data.get("items"))
    status_counts: dict[str, int] = {}
    for item in items:
        if isinstance(item, dict):
            status = str(item.get("status") or "pending")
            status_counts[status] = status_counts.get(status, 0) + 1
    return sanitize_metadata(
        {
            "submission_id": data.get("submission_id"),
            "release_id": data.get("release_id"),
            "name": data.get("name"),
            "status": data.get("status") or "missing",
            "platform_group": data.get("platform_group"),
            "item_count": len(items),
            "ready_count": status_counts.get("ready", 0),
            "submitted_count": status_counts.get("submitted", 0),
            "accepted_count": status_counts.get("accepted", 0),
            "needs_changes_count": status_counts.get("needs_changes", 0),
            "qa_status": (data.get("latest_qa_summary") or {}).get("status") if isinstance(data.get("latest_qa_summary"), dict) else None,
            "export_status": (data.get("latest_export_summary") or {}).get("status") if isinstance(data.get("latest_export_summary"), dict) else None,
            "signoff_status": (data.get("latest_signoff_summary") or {}).get("status") if isinstance(data.get("latest_signoff_summary"), dict) else None,
            "updated_at": data.get("updated_at"),
            "status_counts": status_counts,
        },
        blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
    )

def submission_signoff_summary(record: DomainDocument | None) -> DomainDocument:
    data = _as_document(record)
    return sanitize_metadata(
        {
            "status": data.get("status") or "not_signed",
            "release_id": data.get("release_id"),
            "submission_id": data.get("submission_id"),
            "signed_at": data.get("signed_at"),
            "signed_by": data.get("signed_by"),
            "qa_source_hash": data.get("qa_source_hash"),
            "export_manifest_hash": data.get("export_manifest_hash"),
            "forced": bool(data.get("forced", False)),
            "rights_clearance": _as_document(data.get("rights_clearance")),
        },
        blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
    )

def build_submission_signoff_record(
    *,
    batch: SubmissionBatch,
    qa_report: DomainDocument,
    payload: DomainDocument | None = None,
    export_manifest: DomainDocument | None = None,
    now: str | None = None,
) -> DomainDocument:
    now = now or now_iso()
    payload = payload or {}
    force = bool(payload.get("force", False))
    if force and not str(payload.get("override_reason") or "").strip():
        raise ValueError("override_reason is required when force=true.")
    blockers = qa_report.get("blockers", []) if isinstance(qa_report.get("blockers"), list) else []
    warnings = qa_report.get("warnings", []) if isinstance(qa_report.get("warnings"), list) else []
    if not force and (qa_report.get("status") not in {"passed", "warning"} or blockers):
        raise ValueError("Submission QA does not allow signoff.")
    record = {
        "schema_version": 1,
        "release_id": batch.release_id,
        "submission_id": batch.submission_id,
        "status": "force_signed" if force else "signed",
        "signed_at": now,
        "signed_by": _safe_text(payload.get("signed_by"), 120) or "local-user",
        "qa_source_hash": qa_report.get("source_hash"),
        "submission_source_hash": qa_report.get("source_hash"),
        "export_manifest_hash": stable_hash(export_manifest) if isinstance(export_manifest, dict) and export_manifest else None,
        "forced": force,
        "override_reason": _safe_text(payload.get("override_reason"), 500) if force else None,
        "acknowledged_blockers": blockers if force else [],
        "acknowledged_warnings": warnings,
        "rights_clearance": _as_document(payload.get("rights_clearance")),
        "notes": _safe_text(payload.get("notes"), 2000),
    }
    return sanitize_metadata(record, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)

def submission_signoff_history_event(record: DomainDocument, *, reason: str, now: str | None = None) -> DomainDocument:
    return sanitize_metadata(
        {
            "timestamp": now or now_iso(),
            "event": "submission_signoff_reset",
            "reason": sanitize_sensitive_text(str(reason or ""))[:500],
            "previous_summary": submission_signoff_summary(record),
        },
        blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
    )

def submission_item_current_snapshot(store: SubmissionStore, item: SubmissionItem) -> DomainDocument:
    try:
        current = store.snapshot_item(item.release_id, item.submission_id, item.target_id, item_id=item.item_id)
    except (DistributionNotFoundError, ValueError, OSError):
        return {"exists": False, "stale": True, "target_id": item.target_id}
    return sanitize_metadata(
        {
            "exists": True,
            "target_id": current.target_id,
            "package_id": current.package_id,
            "package_zip_sha256": current.package_zip_sha256,
            "distribution_manifest_hash": current.distribution_manifest_hash,
            "distribution_signoff_hash": current.distribution_signoff_hash,
            "distribution_verify_summary": current.distribution_verify_summary,
            "stale": item.package_id != current.package_id
            or item.package_zip_sha256 != current.package_zip_sha256
            or item.distribution_manifest_hash != current.distribution_manifest_hash
            or item.distribution_signoff_hash != current.distribution_signoff_hash,
        },
        blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
    )

def _safe_distribution_manifest(store: DistributionStore, release_id: str, package_id: str | None) -> DomainDocument:
    if not package_id:
        return {}
    try:
        return read_distribution_export_manifest(store, release_id, package_id)
    except (OSError, FileNotFoundError, ValueError, json.JSONDecodeError):
        return {}

def _record_item_submitted(item: SubmissionItem, payload: DomainDocument) -> None:
    item.status = "submitted"
    item.submitted_at = str(payload.get("submitted_at") or now_iso())
    item.external_reference = _optional_text(payload.get("external_reference"), 200)

def _record_item_feedback(item: SubmissionItem, payload: DomainDocument) -> None:
    status = str(payload.get("status") or "needs_changes")
    if status not in {"feedback_received", "needs_changes", "rejected"}:
        status = "feedback_received"
    item.status = status
    item.feedback_summary = sanitize_metadata(
        {
            "status": status,
            "received_at": str(payload.get("received_at") or now_iso()),
            "message": _safe_text(payload.get("message"), 1000),
            "external_reference": _optional_text(payload.get("external_reference"), 200),
        },
        blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
    )

def _record_item_accepted(item: SubmissionItem, payload: DomainDocument) -> None:
    item.status = "accepted"
    item.accepted_at = str(payload.get("accepted_at") or now_iso())
    if payload.get("external_reference"):
        item.external_reference = _optional_text(payload.get("external_reference"), 200)

def _batch_external_status(items: list[SubmissionItem], fallback: str) -> str:
    active = [item for item in items if item.status != "withdrawn"]
    if active and all(item.status == "accepted" for item in active):
        return "accepted"
    if any(item.status == "accepted" for item in active):
        return "partially_accepted"
    if any(item.status in {"needs_changes", "rejected"} for item in active):
        return "needs_changes"
    if active and all(item.status in {"submitted", "feedback_received"} for item in active):
        return "submitted"
    return fallback

def _preserve_external_status(old: str, new: str) -> str:
    return old if old in {"submitted", "feedback_received", "needs_changes", "accepted", "rejected", "withdrawn"} else new

def _target_ids_from_payload(payload: DomainDocument) -> list[str]:
    raw = payload.get("target_ids")
    if not isinstance(raw, list):
        raw = _as_list(payload.get("targets"))
    ids: list[str] = []
    for value in raw:
        text = str(value.get("target_id") if isinstance(value, dict) else value or "").strip()
        if text:
            ids.append(_validate_target_id(text))
    return ids

def _stale_summary(summary: DomainDocument | None, reason: str) -> DomainDocument:
    data = dict(summary or {})
    if data:
        data["stale"] = True
        data["status"] = "stale"
        data["stale_reason"] = reason
    return sanitize_metadata(data, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)

def _safe_dict(value: object) -> DomainDocument:
    return sanitize_metadata(_as_document(value), blocked_keys=DISTRIBUTION_BLOCKED_KEYS)

def _safe_text(value: object, limit: int) -> str:
    return sanitize_sensitive_text(str(value or "").strip())[:limit]

def _optional_text(value: object, limit: int) -> str | None:
    text = _safe_text(value, limit)
    return text or None

def _optional_hash(value: object) -> str | None:
    text = str(value or "").strip()
    if len(text) == 64 and all(ch in "0123456789abcdefABCDEF" for ch in text):
        return text.lower()
    return None

def _optional_id(value: object, *, prefix: str) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if not text.startswith(prefix) or not text.removeprefix(prefix).isdigit():
        raise SubmissionValidationError("Invalid identifier.")
    return text

def _validate_submission_id(value: str) -> str:
    text = str(value or "").strip()
    if not text.startswith("sub-") or not text.removeprefix("sub-").isdigit():
        raise SubmissionValidationError("Invalid submission_id.")
    return text

def _validate_item_id(value: str) -> str:
    text = str(value or "").strip()
    if not text.startswith("item-") or not text.removeprefix("item-").isdigit():
        raise SubmissionValidationError("Invalid submission item id.")
    return text

def _validate_target_id(value: str) -> str:
    text = str(value or "").strip()
    if not text.startswith("target-") or not text.removeprefix("target-").isdigit():
        raise SubmissionValidationError("Invalid distribution target id.")
    return text

def _file_sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file() or path.is_symlink():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
