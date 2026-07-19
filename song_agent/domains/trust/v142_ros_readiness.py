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
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.projects import now_iso as now_iso
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.trust.release_operations import OPERATIONS_BLOCKED_KEYS as OPERATIONS_BLOCKED_KEYS, ReleaseOperationsStore as ReleaseOperationsStore, operations_report_integrity_hash as operations_report_integrity_hash, operations_report_integrity_ok as operations_report_integrity_ok
from song_agent.domains.trust.release_operations_runbook import ReleaseOperationsRunbookStore as ReleaseOperationsRunbookStore, runbook_integrity_hash as runbook_integrity_hash, runbook_integrity_ok as runbook_integrity_ok, runbook_summary as runbook_summary
from song_agent.domains.delivery.releases import ReleaseStore as ReleaseStore, stable_hash as stable_hash
from song_agent.domains.trust.release_operations_signoff_contracts import OPERATIONS_ARCHIVE_HASH_EXCLUDE_KEYS as OPERATIONS_ARCHIVE_HASH_EXCLUDE_KEYS, OPERATIONS_CHANGE_REQUEST_HASH_EXCLUDE_KEYS as OPERATIONS_CHANGE_REQUEST_HASH_EXCLUDE_KEYS, OPERATIONS_SIGNOFF_BLOCKED_KEYS as OPERATIONS_SIGNOFF_BLOCKED_KEYS, OPERATIONS_SIGNOFF_HASH_EXCLUDE_KEYS as OPERATIONS_SIGNOFF_HASH_EXCLUDE_KEYS, operations_archive_manifest_hash as operations_archive_manifest_hash, operations_change_request_hash as operations_change_request_hash, operations_change_request_integrity_ok as operations_change_request_integrity_ok, operations_signoff_hash as operations_signoff_hash

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

part = _make_deferred_global('part')

def bind_globals(namespace: dict[str, object]) -> None:
    global part
    part = namespace.get('part', part)
    _bind_deferred_defaults(namespace)


OPERATIONS_SIGNOFF_SCHEMA_VERSION = 1
OPERATIONS_ARCHIVE_SCHEMA_VERSION = 1
OPERATIONS_CHANGE_REQUEST_SCHEMA_VERSION = 1




class ReleaseOperationsSignoffError(ValueError):
    pass

class ReleaseOperationsSignoffNotFoundError(ReleaseOperationsSignoffError):
    pass

class ReleaseOperationsSignoffStateError(ReleaseOperationsSignoffError):
    pass

def operations_signoff_integrity_ok(signoff: DomainDocument | None) -> bool:
    data = _as_document(signoff)
    return bool(data.get("payload_hash")) and str(data.get("payload_hash")) == operations_signoff_hash(data)

def operations_signoff_summary(signoff: DomainDocument | None, *, current_report: DomainDocument | None = None) -> DomainDocument:
    data = _as_document(signoff)
    if not data:
        return {"status": "not_signed", "integrity_ok": False, "payload_hash_ok": False, "stale": False}
    payload_hash_ok = operations_signoff_integrity_ok(data)
    current_source_hash = current_report.get("source_hash") if isinstance(current_report, dict) else None
    stale = bool(current_source_hash and data.get("source_hash") and str(current_source_hash) != str(data.get("source_hash")))
    gate = _as_document(data.get("gate"))
    operations_report = _as_document(data.get("operations_report"))
    return sanitize_metadata(
        {
            "status": data.get("status") or "missing",
            "release_id": data.get("release_id"),
            "signed_at": data.get("signed_at"),
            "signed_by": data.get("signed_by"),
            "force": bool(data.get("force")),
            "payload_hash": data.get("payload_hash"),
            "payload_hash_ok": payload_hash_ok,
            "integrity_ok": payload_hash_ok,
            "stale": stale,
            "source_hash": data.get("source_hash"),
            "current_source_hash": current_source_hash,
            "operations_report_id": operations_report.get("report_id"),
            "current_stage": operations_report.get("current_stage"),
            "blocker_count": len(gate.get("blockers", [])) if isinstance(gate.get("blockers"), list) else 0,
            "warning_count": len(gate.get("warnings", [])) if isinstance(gate.get("warnings"), list) else 0,
        },
        blocked_keys=OPERATIONS_SIGNOFF_BLOCKED_KEYS,
    )

def operations_archive_manifest_integrity_ok(manifest: DomainDocument | None) -> bool:
    data = _as_document(manifest)
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == operations_archive_manifest_hash(data)

def _latest_runbook(runbook_store: ReleaseOperationsRunbookStore, release_id: str) -> DomainDocument:
    rows = runbook_store.list_runbooks(release_id, include_archived=True)
    return rows[0] if rows else {}

def _runbook_gate(runbook: DomainDocument, current_report: DomainDocument) -> DomainDocument:
    if not runbook:
        return {"status": "warning", "message": "No Release Operations Runbook exists.", "runbook_id": None}
    summary = runbook_summary(runbook)
    source = _as_document(runbook.get("source"))
    stale = str(source.get("operations_source_hash") or "") != str(current_report.get("source_hash") or "")
    failed_safe_count = sum(1 for item in runbook.get("items", []) if isinstance(item, dict) and item.get("risk") == "auto_safe" and item.get("status") == "failed")
    pending_safe_count = sum(1 for item in runbook.get("items", []) if isinstance(item, dict) and item.get("risk") == "auto_safe" and item.get("status") in {"pending", "running"})
    integrity_ok = runbook_integrity_ok(runbook)
    status = "failed" if stale or failed_safe_count or pending_safe_count or not integrity_ok else "passed" if runbook.get("status") in {"completed", "blocked"} else "warning"
    message = "Runbook evidence is current."
    if stale:
        message = "Release Operations Runbook is stale."
    elif not integrity_ok:
        message = "Release Operations Runbook integrity failed."
    elif failed_safe_count:
        message = "Release Operations Runbook has failed auto-safe items."
    elif pending_safe_count:
        message = "Release Operations Runbook still has pending auto-safe items."
    return sanitize_metadata({**summary, "status": status, "stale": stale, "integrity_ok": integrity_ok, "failed_safe_count": failed_safe_count, "pending_safe_count": pending_safe_count, "message": message}, blocked_keys=OPERATIONS_SIGNOFF_BLOCKED_KEYS)

def _verifier_summary_from_report(report: DomainDocument) -> DomainDocument:
    return sanitize_metadata(_as_document(report.get("verifier_summaries")), blocked_keys=OPERATIONS_SIGNOFF_BLOCKED_KEYS)

def _failed_verifier_summaries(value: object) -> list[DomainDocument]:
    failed: list[DomainDocument] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, dict):
                if item.get("status") not in {"passed", "warning", "missing"}:
                    failed.append({"scope": key, **item})
            elif isinstance(item, list):
                failed.extend(_failed_verifier_summaries(item))
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, dict) and item.get("status") not in {"passed", "warning", "missing"}:
                failed.append(item)
            elif isinstance(item, (list, dict)):
                failed.extend(_failed_verifier_summaries(item))
    return failed

def _missing_submission_evidence(report: DomainDocument) -> bool:
    domain = report.get("domains", {}).get("submission_evidence") if isinstance(report.get("domains"), dict) else {}
    if not isinstance(domain, dict) or not domain.get("required"):
        return False
    summary = _as_document(domain.get("summary"))
    return int(summary.get("accepted_count") or 0) <= 0 or domain.get("status") not in {"passed", "warning"}

def _package_ledger_complete(ledger: DomainDocument) -> bool:
    summary = _as_document(ledger.get("summary"))
    return bool(summary.get("release_zip_exists")) and int(summary.get("missing_count") or 0) == 0

def _missing_package_count(packages: DomainDocument) -> int:
    missing = 0
    release_zip = _as_document(packages.get("release_zip"))
    if not release_zip.get("exists"):
        missing += 1
    for key in ("distribution_packages", "submission_packages", "submission_evidence_packages"):
        for item in packages.get(key, []) if isinstance(packages.get(key), list) else []:
            if isinstance(item, dict) and not item.get("exists"):
                missing += 1
    return missing

def _change_request_impact(scope: list[str]) -> dict[str, bool]:
    values = set(scope)
    return {
        "requires_release_signoff_reset": bool(values & {"metadata", "release_export", "release", "audio", "rights", "format_decision"}),
        "requires_distribution_signoff_reset": bool(values & {"distribution", "release_export", "audio", "rights", "format_decision"}),
        "requires_submission_signoff_reset": bool(values & {"submission", "distribution", "release_export"}),
        "requires_operations_signoff_reset": True,
    }

def _report_reference(report: DomainDocument) -> DomainDocument:
    return {"report_id": report.get("report_id"), "status": report.get("status"), "current_stage": report.get("current_stage"), "source_hash": report.get("source_hash"), "integrity_hash": report.get("integrity_hash"), "blocker_count": report.get("summary", {}).get("blocker_count") if isinstance(report.get("summary"), dict) else None, "warning_count": report.get("summary", {}).get("warning_count") if isinstance(report.get("summary"), dict) else None}

def _maybe_block(blockers: list[DomainDocument], check_id: str, condition: bool, message: str) -> None:
    if condition:
        blockers.append(_blocker(check_id, message))

def _blocker(check_id: str, message: str) -> DomainDocument:
    return {"check_id": check_id, "severity": "blocking", "message": message}

def _warning(check_id: str, message: str) -> DomainDocument:
    return {"check_id": check_id, "severity": "warning", "message": message}

def _redaction_summary(value: object) -> DomainDocument:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    findings = []
    from song_agent.domains.creation.redaction import SENSITIVE_VALUE_PATTERNS

    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            findings.append({"pattern": replacement, "excerpt": sanitize_sensitive_text(match.group(0))[:120]})
    return {"status": "failed" if findings else "passed", "finding_count": len(findings), "findings": findings[:20]}

def _write_archive_readme(export_dir: Path, signoff: DomainDocument, report: DomainDocument) -> None:
    lines = [
        "MusicForge Release Operations Archive",
        "",
        f"Release ID: {signoff.get('release_id')}",
        f"Signoff Status: {signoff.get('status')}",
        f"Signed At: {signoff.get('signed_at') or '-'}",
        f"Current Stage: {report.get('current_stage') or '-'}",
        "",
        "This archive contains summary evidence only. It does not include audio, artwork, package ZIPs, credentials, or platform account data.",
    ]
    (export_dir / "README.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

def _write_json(path: Path, data: DomainDocument) -> Path:
    return write_json(path, sanitize_metadata(data, blocked_keys=OPERATIONS_SIGNOFF_BLOCKED_KEYS))

def _file_record(export_dir: Path, path: Path) -> DomainDocument:
    rel = _validate_relative_path(path.resolve().relative_to(export_dir.resolve()).as_posix())
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256(path)}

def _zip_entries(export_dir: Path) -> list[tuple[Path, str]]:
    entries: list[tuple[Path, str]] = []
    seen: set[str] = set()
    for file in sorted(export_dir.rglob("*")):
        if not file.is_file() or file.is_symlink():
            continue
        resolved = file.resolve()
        _ensure_within(export_dir.resolve(), resolved)
        entry = _validate_relative_path(resolved.relative_to(export_dir.resolve()).as_posix())
        if entry in seen:
            raise ReleaseOperationsSignoffStateError(f"Duplicate ZIP entry: {entry}.")
        seen.add(entry)
        entries.append((resolved, entry))
    return entries

def _validate_relative_path(value: str) -> str:
    text = str(value or "")
    if "\\" in text or not text or text.startswith("/") or text.startswith("//") or text.endswith("/"):
        raise ReleaseOperationsSignoffStateError(f"Unsafe relative path: {value}.")
    parts = text.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ReleaseOperationsSignoffStateError(f"Unsafe relative path: {value}.")
    if ":" in parts[0]:
        raise ReleaseOperationsSignoffStateError(f"Unsafe relative path: {value}.")
    return text

def _ensure_within(root: Path, target: Path) -> None:
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ReleaseOperationsSignoffStateError("Refusing to operate outside release operations boundaries.") from exc

def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _safe_text(value: object, limit: int) -> str:
    return sanitize_sensitive_text(str(value or "").strip())[:limit]

def _validate_change_request_id(value: str) -> str:
    text = str(value or "")
    if not text.startswith("ocr-") or not text.replace("ocr-", "", 1).isdigit():
        raise ReleaseOperationsSignoffNotFoundError("Invalid Operations Change Request id.")
    return text
