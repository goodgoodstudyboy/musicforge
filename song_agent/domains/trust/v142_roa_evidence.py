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
from song_agent.domains.trust.release_operations import ReleaseOperationsStore as ReleaseOperationsStore, operations_report_integrity_hash as operations_report_integrity_hash, operations_report_integrity_ok as operations_report_integrity_ok
from song_agent.domains.trust.release_operations_runbook import ReleaseOperationsRunbookStore as ReleaseOperationsRunbookStore, runbook_integrity_hash as runbook_integrity_hash, runbook_integrity_ok as runbook_integrity_ok, runbook_summary as runbook_summary
from song_agent.domains.trust.release_operations_signoff import ReleaseOperationsSignoffStore as ReleaseOperationsSignoffStore, operations_archive_manifest_hash as operations_archive_manifest_hash, operations_archive_manifest_integrity_ok as operations_archive_manifest_integrity_ok, operations_change_request_hash as operations_change_request_hash, operations_change_request_integrity_ok as operations_change_request_integrity_ok, operations_signoff_hash as operations_signoff_hash, operations_signoff_integrity_ok as operations_signoff_integrity_ok, operations_signoff_summary as operations_signoff_summary
from song_agent.domains.delivery.releases import ReleaseStore as ReleaseStore, stable_hash as stable_hash
from song_agent.domains.trust.release_operations_audit_contracts import AUDIT_ENTRY_HASH_EXCLUDE_KEYS as AUDIT_ENTRY_HASH_EXCLUDE_KEYS, AUDIT_MANIFEST_HASH_EXCLUDE_KEYS as AUDIT_MANIFEST_HASH_EXCLUDE_KEYS, AUDIT_REPORT_HASH_EXCLUDE_KEYS as AUDIT_REPORT_HASH_EXCLUDE_KEYS, OPERATIONS_AUDIT_BLOCKED_KEYS as OPERATIONS_AUDIT_BLOCKED_KEYS, _entry_hash_payload as _entry_hash_payload, audit_entry_hash as audit_entry_hash, audit_ledger_hash as audit_ledger_hash, audit_ledger_integrity_ok as audit_ledger_integrity_ok, audit_manifest_integrity_hash as audit_manifest_integrity_hash, audit_report_integrity_hash as audit_report_integrity_hash

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

ReleaseOperationsAuditStateError = _make_deferred_global('ReleaseOperationsAuditStateError')
ch = _make_deferred_global('ch')
part = _make_deferred_global('part')

def bind_globals(namespace: dict[str, object]) -> None:
    global ReleaseOperationsAuditStateError, ch, part
    ReleaseOperationsAuditStateError = namespace.get('ReleaseOperationsAuditStateError', ReleaseOperationsAuditStateError)
    ch = namespace.get('ch', ch)
    part = namespace.get('part', part)
    _bind_deferred_defaults(namespace)


OPERATIONS_AUDIT_SCHEMA_VERSION = 1
OPERATIONS_AUDIT_EXPORT_SCHEMA_VERSION = 1
DOMAIN_PRIORITY = {
    "release": 10,
    "release_export": 20,
    "metadata": 30,
    "audio": 40,
    "rights": 50,
    "format_decision": 60,
    "distribution": 70,
    "submission": 80,
    "submission_evidence": 90,
    "operations_report": 100,
    "operations_runbook": 110,
    "operations_signoff": 120,
    "operations_change_request": 130,
    "operations_archive": 140,
    "operations_audit": 150,
}




def _entry_seed(
    release_id: str,
    occurred_at: object,
    domain: str,
    event_type: str,
    actor: object,
    risk: str,
    mutation_kind: str,
    source_type: str,
    source_id: object,
    payload: object,
    *,
    source_hash: object = None,
    payload_hash: object = None,
    integrity_ok: bool = True,
    stale: bool = False,
    causal_refs: list[DomainDocument] | None = None,
) -> DomainDocument:
    payload_hash = str(payload_hash or stable_hash(payload))
    return {
        "schema_version": OPERATIONS_AUDIT_SCHEMA_VERSION,
        "entry_id": "",
        "release_id": release_id,
        "sequence": 0,
        "occurred_at": _safe_time(occurred_at),
        "domain": domain,
        "event_type": _safe_event_type(event_type),
        "actor": _safe_text(actor, 120) or "unknown",
        "risk": risk,
        "mutation_kind": mutation_kind,
        "source_ref": {"source_type": source_type, "source_id": str(source_id or source_type), "path_hint": _path_hint(source_type), "payload_hash": payload_hash},
        "evidence_ref": {"artifact_type": "json", "artifact_id": str(source_id or source_type), "payload_hash": payload_hash, "source_hash": source_hash, "integrity_ok": bool(integrity_ok), "stale": bool(stale)},
        "causal_refs": causal_refs or [],
        "warnings": [] if occurred_at else [{"check_id": "occurred_at_missing", "message": "Source event time is missing."}],
        "previous_hash": None,
        "entry_hash": "",
    }

def _finalize_entries(rows: list[DomainDocument]) -> list[DomainDocument]:
    sorted_rows = sorted(rows, key=lambda item: (_safe_time(item.get("occurred_at")), DOMAIN_PRIORITY.get(str(item.get("domain")), 999), str(item.get("event_type") or ""), str((item.get("source_ref") or {}).get("source_id") or ""), str((item.get("source_ref") or {}).get("payload_hash") or "")))
    previous: str | None = None
    result: list[DomainDocument] = []
    for index, item in enumerate(sorted_rows, start=1):
        entry = dict(item)
        entry["entry_id"] = f"olae-{index:06d}"
        entry["sequence"] = index
        entry["previous_hash"] = previous
        entry["entry_hash"] = audit_entry_hash(entry)
        previous = entry["entry_hash"]
        result.append(sanitize_metadata(entry, blocked_keys=OPERATIONS_AUDIT_BLOCKED_KEYS))
    return result

def _bind_change_request_causal_refs(entries: list[DomainDocument]) -> None:
    reset_event_types = {
        "operations_signoff_reset",
        "operations_signoff_history_reset",
        "release_event_operations_signoff_reset",
    }
    applied_by_id: dict[str, DomainDocument] = {}
    applied_by_reset_hash: dict[str, DomainDocument] = {}
    for entry in entries:
        if entry.get("event_type") != "operations_change_request_applied":
            continue
        source_ref = _as_document(entry.get("source_ref"))
        change_request_id = str(source_ref.get("source_id") or "")
        if change_request_id:
            applied_by_id[change_request_id] = entry
        for ref in entry.get("causal_refs", []) if isinstance(entry.get("causal_refs"), list) else []:
            if isinstance(ref, dict) and ref.get("payload_hash"):
                applied_by_reset_hash[str(ref.get("payload_hash"))] = entry
    changed = False
    for entry in entries:
        if entry.get("event_type") not in reset_event_types:
            continue
        reset_hash = str((entry.get("evidence_ref") or {}).get("payload_hash") or "")
        refs = _as_list(entry.get("causal_refs"))
        change_request_id = ""
        for ref in refs:
            if isinstance(ref, dict) and ref.get("type") == "change_request" and ref.get("id"):
                change_request_id = str(ref.get("id"))
                break
        applied = applied_by_id.get(change_request_id) or applied_by_reset_hash.get(reset_hash)
        if not applied:
            continue
        entry["causal_refs"] = [
            {
                "type": "change_request",
                "id": change_request_id or (applied.get("source_ref") or {}).get("source_id"),
                "entry_id": applied.get("entry_id"),
                "payload_hash": (applied.get("evidence_ref") or {}).get("payload_hash"),
            }
        ]
        changed = True
    if changed:
        previous: str | None = None
        for entry in entries:
            entry["previous_hash"] = previous
            entry["entry_hash"] = audit_entry_hash(entry)
            previous = entry["entry_hash"]

def _write_ledger(path: Path, entries: list[DomainDocument]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in entries), encoding="utf-8")
    return path

def _latest_runbook(runbook_store: ReleaseOperationsRunbookStore, release_id: str) -> DomainDocument:
    rows = runbook_store.list_runbooks(release_id, include_archived=True)
    return rows[0] if rows else {}

def _read_optional_json(path: Path) -> DomainDocument:
    if not path.exists():
        return {}
    try:
        value = read_json(path)
    except Exception:
        return {}
    return sanitize_metadata(_as_document(value), blocked_keys=OPERATIONS_AUDIT_BLOCKED_KEYS)

def _read_jsonl(path: Path) -> list[DomainDocument]:
    if not path.exists():
        return []
    rows: list[DomainDocument] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(sanitize_metadata(value, blocked_keys=OPERATIONS_AUDIT_BLOCKED_KEYS))
    return rows

def _reset_hash_by_change_request_id(signoff_store: ReleaseOperationsSignoffStore, release_id: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for request in signoff_store.list_change_requests(release_id):
        if not isinstance(request, dict) or request.get("status") != "applied":
            continue
        change_request_id = str(request.get("change_request_id") or "")
        reset_hash = str(request.get("applied_signoff_reset_hash") or "")
        if change_request_id and reset_hash:
            result[change_request_id] = reset_hash
    return result

def _verifier_entries_from_operations_report(release_id: str, report: DomainDocument) -> list[tuple[str, DomainDocument]]:
    rows: list[tuple[str, DomainDocument]] = []
    verifiers = _as_document(report.get("verifier_summaries"))
    for key, value in verifiers.items():
        if isinstance(value, dict):
            rows.append((str(key), _entry_seed(release_id, report.get("generated_at"), "operations_report", f"package_verifier_{_slug(key)}", "local-user", "auto_safe", "verify", "package_verifier", key, value, source_hash=report.get("source_hash"), integrity_ok=value.get("status") != "failed")))
        elif isinstance(value, list):
            for index, item in enumerate(value, start=1):
                if isinstance(item, dict):
                    rows.append((str(key), _entry_seed(release_id, report.get("generated_at"), "operations_report", f"package_verifier_{_slug(key)}", "local-user", "auto_safe", "verify", "package_verifier", f"{key}-{index}", item, source_hash=report.get("source_hash"), integrity_ok=item.get("status") != "failed")))
    return rows

def _stage_timeline(entries: list[DomainDocument]) -> list[DomainDocument]:
    return [{"entry_id": item.get("entry_id"), "occurred_at": item.get("occurred_at"), "domain": item.get("domain"), "event_type": item.get("event_type"), "risk": item.get("risk")} for item in entries if item.get("domain") in {"operations_report", "operations_runbook", "operations_signoff", "operations_archive"}]

def _critical_milestones(entries: list[DomainDocument]) -> list[DomainDocument]:
    return [{"entry_id": item.get("entry_id"), "event_type": item.get("event_type"), "risk": item.get("risk"), "payload_hash": (item.get("evidence_ref") or {}).get("payload_hash")} for item in entries if item.get("risk") in {"manual_required", "change_control", "external_state"}]

def _change_control_summary(entries: list[DomainDocument]) -> DomainDocument:
    change_entries = [item for item in entries if item.get("domain") == "operations_change_request"]
    return {"count": len(change_entries), "applied_count": sum(1 for item in change_entries if item.get("event_type") == "operations_change_request_applied"), "entries": change_entries[:50]}

def _package_verifier_summary(entries: list[DomainDocument]) -> DomainDocument:
    rows = [item for item in entries if str(item.get("event_type") or "").startswith("package_verifier_") or str(item.get("event_type") or "").endswith("_verified")]
    failed = [item for item in rows if (item.get("evidence_ref") or {}).get("integrity_ok") is False]
    return {"count": len(rows), "failed_count": len(failed), "entries": rows[:80]}

def _coverage(entries: list[DomainDocument]) -> DomainDocument:
    domains = sorted({str(item.get("domain") or "") for item in entries})
    required = ["release", "operations_report", "operations_runbook", "operations_signoff", "operations_archive", "operations_change_request"]
    return {"domains": domains, "missing_required": [item for item in required if item not in domains]}

def _operations_report_summary(report: DomainDocument) -> DomainDocument:
    summary = _as_document(report.get("summary"))
    return {"status": report.get("status") or "missing", "current_stage": report.get("current_stage"), "source_hash": report.get("source_hash"), "integrity_hash": report.get("integrity_hash"), "entry_summary": summary}

def _write_audit_readme(export_dir: Path, report: DomainDocument) -> None:
    lines = [
        "MusicForge Release Operations Audit Package",
        "",
        f"Release ID: {report.get('release_id')}",
        f"Audit Status: {report.get('status')}",
        f"Ledger Hash: {report.get('ledger_hash') or '-'}",
        "",
        "This package contains summary audit evidence only. It does not include audio, artwork, credentials, or platform account data.",
    ]
    (export_dir / "README.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

def _write_json(path: Path, data: DomainDocument) -> Path:
    return write_json(path, sanitize_metadata(data, blocked_keys=OPERATIONS_AUDIT_BLOCKED_KEYS))

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
            raise ReleaseOperationsAuditStateError(f"Duplicate ZIP entry: {entry}.")
        seen.add(entry)
        entries.append((resolved, entry))
    return entries

def _validate_relative_path(value: str) -> str:
    text = str(value or "")
    if "\\" in text or not text or text.startswith("/") or text.startswith("//") or text.endswith("/"):
        raise ReleaseOperationsAuditStateError(f"Unsafe relative path: {value}.")
    parts = text.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ReleaseOperationsAuditStateError(f"Unsafe relative path: {value}.")
    if ":" in parts[0]:
        raise ReleaseOperationsAuditStateError(f"Unsafe relative path: {value}.")
    return text

def _ensure_within(root: Path, target: Path) -> None:
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ReleaseOperationsAuditStateError("Refusing to operate outside release operations audit boundaries.") from exc

def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _redaction_summary(value: object) -> DomainDocument:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    findings = []
    from song_agent.domains.creation.redaction import SENSITIVE_VALUE_PATTERNS

    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            findings.append({"pattern": replacement, "excerpt": sanitize_sensitive_text(match.group(0))[:120]})
    return {"status": "failed" if findings else "passed", "finding_count": len(findings), "findings": findings[:20]}

def _safe_text(value: object, limit: int) -> str:
    return sanitize_sensitive_text(str(value or "").strip())[:limit]

def _safe_time(value: object) -> str:
    text = str(value or "").strip()
    return text or "1970-01-01T00:00:00+00:00"

def _safe_event_type(value: object) -> str:
    return _slug(str(value or "unknown")) or "unknown"

def _slug(value: object) -> str:
    text = str(value or "").lower().replace("-", "_").replace(" ", "_")
    return "".join(ch for ch in text if ch.isalnum() or ch == "_").strip("_")

def _path_hint(source_type: str) -> str:
    mapping = {
        "operations_report": "operations/operations-report.json",
        "operations_export": "operations/operations-export/operations-manifest.json",
        "operations_signoff": "operations/operations-signoff.json",
        "operations_archive": "operations/archive-export/operations-archive-manifest.json",
        "runbook": "operations/runbooks/<runbook-id>/runbook.json",
        "change_request": "operations/change-requests/<change-request-id>.json",
    }
    return mapping.get(source_type, source_type)

def _blocker(check_id: str, message: str) -> DomainDocument:
    return {"check_id": check_id, "severity": "blocking", "message": message}

def _warning(check_id: str, message: str) -> DomainDocument:
    return {"check_id": check_id, "severity": "warning", "message": message}
