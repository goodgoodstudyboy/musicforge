# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
import hashlib as hashlib
import json as json
import os as os
import shutil as shutil
import threading as threading
import zipfile as zipfile
from pathlib import Path as Path
from song_agent.platform.version import VERSION as __version__
from song_agent.domains.delivery.distribution import DistributionStore as DistributionStore
from song_agent.domains.delivery.distribution_export import build_distribution_export_package as build_distribution_export_package, build_distribution_package_zip as build_distribution_package_zip
from song_agent.domains.delivery.distribution_verifier import distribution_verification_summary as distribution_verification_summary, verify_distribution_package as verify_distribution_package
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.projects import now_iso as now_iso
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.release_export import build_release_export_bundle as build_release_export_bundle, build_release_export_zip as build_release_export_zip
from song_agent.domains.delivery.release_metadata import attach_metadata_export_to_manifest as attach_metadata_export_to_manifest, export_release_metadata_files as export_release_metadata_files, read_release_metadata as read_release_metadata, read_release_metadata_qa as read_release_metadata_qa
from song_agent.domains.delivery.release_metadata_qa import build_release_metadata_qa_report as build_release_metadata_qa_report, release_metadata_qa_summary as release_metadata_qa_summary
from song_agent.domains.trust.release_operations import ReleaseOperationsStore as ReleaseOperationsStore, operations_report_integrity_hash as operations_report_integrity_hash, operations_report_integrity_ok as operations_report_integrity_ok
from song_agent.domains.trust.release_operations_verifier import release_operations_verification_summary as release_operations_verification_summary, verify_release_operations_package as verify_release_operations_package
from song_agent.domains.delivery.release_qa import build_release_qa_report as build_release_qa_report, release_qa_summary as release_qa_summary
from song_agent.domains.delivery.release_verifier import verification_summary as verification_summary, verify_release_zip as verify_release_zip
from song_agent.domains.delivery.releases import ReleaseStore as ReleaseStore, stable_hash as stable_hash
from song_agent.domains.delivery.submission_evidence import SubmissionEvidenceStore as SubmissionEvidenceStore, submission_evidence_report_summary as submission_evidence_report_summary
from song_agent.domains.delivery.submission_evidence_verifier import submission_evidence_verification_summary as submission_evidence_verification_summary, verify_submission_evidence_package as verify_submission_evidence_package
from song_agent.domains.delivery.submission_export import build_submission_export_bundle as build_submission_export_bundle, build_submission_package_zip as build_submission_package_zip
from song_agent.domains.delivery.submission_qa import build_submission_qa_report as build_submission_qa_report, submission_qa_summary as submission_qa_summary
from song_agent.domains.delivery.submission_verifier import submission_verification_summary as submission_verification_summary, verify_submission_package as verify_submission_package
from song_agent.domains.delivery.submissions import SubmissionStore as SubmissionStore
from song_agent.domains.trust.release_operations_runbook_contracts import EXECUTION_REPORT_HASH_EXCLUDE_KEYS as EXECUTION_REPORT_HASH_EXCLUDE_KEYS, RUNBOOK_BLOCKED_KEYS as RUNBOOK_BLOCKED_KEYS, RUNBOOK_HASH_EXCLUDE_KEYS as RUNBOOK_HASH_EXCLUDE_KEYS, execution_report_integrity_hash as execution_report_integrity_hash, runbook_integrity_hash as runbook_integrity_hash

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

prefix = _make_deferred_global('prefix')

def bind_globals(namespace: dict[str, object]) -> None:
    global prefix
    prefix = namespace.get('prefix', prefix)
    _bind_deferred_defaults(namespace)


RUNBOOK_SCHEMA_VERSION = 1
RUNBOOK_EXPORT_SCHEMA_VERSION = 1
AUTO_SAFE_ACTIONS = {
    "release.qa.refresh",
    "metadata.qa.refresh",
    "metadata.export",
    "release.export",
    "release.zip",
    "release.verify",
    "distribution.qa.refresh",
    "distribution.export",
    "distribution.zip",
    "distribution.verify",
    "submission.qa.refresh",
    "submission.export",
    "submission.zip",
    "submission.verify",
    "submission_evidence.report.refresh",
    "submission_evidence.export",
    "submission_evidence.zip",
    "submission_evidence.verify",
    "operations.refresh",
    "operations.export",
    "operations.zip",
    "operations.verify",
}
MANUAL_REQUIRED_PREFIXES = (
    "release.signoff",
    "distribution.signoff",
    "submission.signoff",
    "submission.record",
    "submission_evidence.signoff",
    "submission_evidence.acceptance",
    "rights.",
    "audio.",
    "mastering.",
    "encoded.",
    "format_decision.",
    "release.add_track",
)




class ReleaseOperationsRunbookError(ValueError):
    pass

class ReleaseOperationsRunbookNotFoundError(ReleaseOperationsRunbookError):
    pass

class ReleaseOperationsRunbookStateError(ReleaseOperationsRunbookError):
    pass

def runbook_integrity_ok(runbook: DomainDocument | None) -> bool:
    data = _as_document(runbook)
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == runbook_integrity_hash(data)

def execution_report_integrity_ok(report: DomainDocument | None) -> bool:
    data = _as_document(report)
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == execution_report_integrity_hash(data)

def runbook_summary(runbook: DomainDocument) -> DomainDocument:
    data = _as_document(runbook)
    summary = _as_document(data.get("summary"))
    return sanitize_metadata(
        {
            "runbook_id": data.get("runbook_id"),
            "release_id": data.get("release_id"),
            "status": data.get("status"),
            "source_stage": data.get("source", {}).get("current_stage") if isinstance(data.get("source"), dict) else None,
            **summary,
        },
        blocked_keys=RUNBOOK_BLOCKED_KEYS,
    )

def _runbook_item(action: DomainDocument, *, index: int, source_hash: str | None) -> DomainDocument:
    action_type = str(action.get("action_type") or "")
    risk = _risk_for_action(action_type)
    status = "manual_required" if risk == "manual_required" else "pending"
    return sanitize_metadata(
        {
            "item_id": f"orbi-{index:06d}",
            "action_type": action_type,
            "domain": action.get("domain") or action_type.split(".", 1)[0],
            "scope": action.get("scope") or action.get("domain") or action_type.split(".", 1)[0],
            "entity_id": action.get("entity_id"),
            "label": action.get("label") or action_type,
            "description": action.get("description") or "",
            "risk": risk,
            "status": status,
            "priority": int(action.get("priority") or 100),
            "depends_on": _as_list(action.get("depends_on")),
            "blocked_by": _as_list(action.get("blocked_by")),
            "unblocks": _as_list(action.get("unblocks")),
            "source_hash": source_hash,
            "attempt": 0,
            "retry_count": 0,
            "started_at": None,
            "completed_at": None,
            "result": {},
            "error": "Manual action requires explicit user evidence." if risk == "manual_required" else None,
            "waiver": None,
        },
        blocked_keys=RUNBOOK_BLOCKED_KEYS,
    )

def _risk_for_action(action_type: str) -> str:
    if action_type in AUTO_SAFE_ACTIONS:
        return "auto_safe"
    if action_type.startswith("provider."):
        return "provider_safe"
    if any(action_type.startswith(prefix) for prefix in MANUAL_REQUIRED_PREFIXES):
        return "manual_required"
    return "manual_required"

def _finalize_runbook(runbook: DomainDocument) -> DomainDocument:
    items = [item for item in runbook.get("items", []) if isinstance(item, dict)]
    counts = {
        "total_count": len(items),
        "safe_count": sum(1 for item in items if item.get("risk") == "auto_safe"),
        "manual_count": sum(1 for item in items if item.get("risk") == "manual_required"),
        "completed_count": sum(1 for item in items if item.get("status") == "completed"),
        "failed_count": sum(1 for item in items if item.get("status") == "failed"),
        "blocked_count": sum(1 for item in items if item.get("status") in {"blocked", "stale"}),
        "manual_required_count": sum(1 for item in items if item.get("status") == "manual_required"),
        "waived_count": sum(1 for item in items if item.get("status") == "waived"),
        "pending_count": sum(1 for item in items if item.get("status") == "pending"),
    }
    runbook["summary"] = counts
    if runbook.get("status") not in {"stale", "archived"}:
        if counts["failed_count"]:
            runbook["status"] = "failed"
        elif counts["pending_count"]:
            runbook["status"] = "ready"
        elif counts["blocked_count"] or counts["manual_required_count"]:
            runbook["status"] = "blocked"
        else:
            runbook["status"] = "completed"
    runbook["integrity_hash"] = runbook_integrity_hash(runbook)
    return sanitize_metadata(runbook, blocked_keys=RUNBOOK_BLOCKED_KEYS)

def _execution_report(runbook: DomainDocument, *, operations_after: DomainDocument, stale: bool | None = None) -> DomainDocument:
    report = {
        "schema_version": RUNBOOK_SCHEMA_VERSION,
        "runbook_id": runbook.get("runbook_id"),
        "release_id": runbook.get("release_id"),
        "generated_at": now_iso(),
        "status": runbook.get("status"),
        "stale": bool(stale) if stale is not None else runbook.get("status") == "stale",
        "summary": runbook.get("summary", {}),
        "items": runbook.get("items", []),
        "source": runbook.get("source", {}),
        "operations_after": _report_reference(operations_after),
    }
    report["integrity_hash"] = execution_report_integrity_hash(report)
    return sanitize_metadata(report, blocked_keys=RUNBOOK_BLOCKED_KEYS)

def _source_from_report(report: DomainDocument) -> DomainDocument:
    return {
        "operations_report_id": report.get("report_id"),
        "operations_source_hash": report.get("source_hash"),
        "operations_integrity_hash": report.get("integrity_hash"),
        "current_stage": report.get("current_stage"),
        "next_stage": report.get("next_stage"),
    }

def _report_reference(report: DomainDocument) -> DomainDocument:
    return {"report_id": report.get("report_id"), "status": report.get("status"), "current_stage": report.get("current_stage"), "source_hash": report.get("source_hash"), "integrity_hash": report.get("integrity_hash")}

def _find_item(runbook: DomainDocument, item_id: str) -> DomainDocument:
    for item in runbook.get("items", []) if isinstance(runbook.get("items"), list) else []:
        if isinstance(item, dict) and item.get("item_id") == item_id:
            return item
    raise ReleaseOperationsRunbookNotFoundError("Release Operations Runbook item does not exist.")

def _signed_or_mutation_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "signed" in text or "reset" in text or "cannot be modified" in text or "archived" in text or "read-only" in text or "read only" in text

def _ensure_release_export_mutable(release_store: ReleaseStore, release_id: str, *, release: object | None = None) -> None:
    document = release or release_store.get_release(release_id)
    signoff = release_store.read_signoff(release_id, default={})
    signoff_status = str(signoff.get("status") or document.latest_signoff_summary.get("status") or "")
    if document.status == "archived":
        raise ReleaseOperationsRunbookStateError("Archived release export is read-only.")
    if document.status == "signed" or signoff_status in {"signed", "force_signed"}:
        raise ReleaseOperationsRunbookStateError("Release is already signed off. Reset signoff before rebuilding export or ZIP.")

def _validate_runbook_id(value: str) -> str:
    text = str(value or "")
    if not text.startswith("orb-") or not text.replace("orb-", "", 1).isdigit():
        raise ReleaseOperationsRunbookNotFoundError("Invalid runbook id.")
    return text

def _safe_text(value: object, limit: int) -> str:
    return sanitize_sensitive_text(str(value or "").strip())[:limit]

def _write_json(path: Path, payload: DomainDocument) -> None:
    write_json(path, sanitize_metadata(payload, blocked_keys=RUNBOOK_BLOCKED_KEYS))

def _file_record(root: Path, path: Path) -> DomainDocument:
    rel = path.relative_to(root).as_posix()
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256(path)}

def _zip_entries(root: Path) -> list[tuple[Path, str]]:
    rows: list[tuple[Path, str]] = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and not path.is_symlink():
            rows.append((path.resolve(), path.relative_to(root).as_posix()))
    return rows

def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _ensure_within(root: Path, target: Path) -> None:
    root = root.resolve()
    target = target.resolve()
    if root != target and root not in target.parents:
        raise ReleaseOperationsRunbookStateError(f"Unsafe path outside runbook workspace: {target}")

def _write_readme(export_dir: Path, runbook: DomainDocument) -> None:
    lines = [
        "MusicForge Release Operations Runbook Package",
        "",
        f"Runbook: {runbook.get('runbook_id')}",
        f"Release: {runbook.get('release_id')}",
        f"Status: {runbook.get('status')}",
        "",
        "This package is local operations evidence only. It does not upload, sign, reset, or mark external submissions accepted.",
    ]
    (export_dir / "README.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
