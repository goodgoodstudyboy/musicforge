# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list, document_or as _document_or
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
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, SENSITIVE_VALUE_PATTERNS as SENSITIVE_VALUE_PATTERNS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.trust.release_portfolio_audit import ReleasePortfolioAuditStore as ReleasePortfolioAuditStore, portfolio_report_integrity_hash as portfolio_report_integrity_hash, portfolio_report_integrity_ok as portfolio_report_integrity_ok
from song_agent.domains.trust.release_portfolio_governance import ReleasePortfolioGovernanceStore as ReleasePortfolioGovernanceStore, action_plan_integrity_ok as action_plan_integrity_ok, execution_report_integrity_ok as execution_report_integrity_ok, governance_manifest_integrity_hash as governance_manifest_integrity_hash, governance_manifest_integrity_ok as governance_manifest_integrity_ok, manual_action_list_integrity_ok as manual_action_list_integrity_ok, queue_integrity_ok as queue_integrity_ok, queue_summary as queue_summary
from song_agent.domains.trust.release_portfolio_governance_archive_verifier import release_portfolio_governance_archive_verification_summary as release_portfolio_governance_archive_verification_summary
from song_agent.domains.trust.release_portfolio_governance_signoff import ReleasePortfolioGovernanceSignoffStore as ReleasePortfolioGovernanceSignoffStore, governance_archive_manifest_hash as governance_archive_manifest_hash, governance_archive_manifest_integrity_ok as governance_archive_manifest_integrity_ok, governance_change_request_hash as governance_change_request_hash, governance_change_request_integrity_ok as governance_change_request_integrity_ok, governance_signoff_hash as governance_signoff_hash, governance_signoff_integrity_ok as governance_signoff_integrity_ok, governance_signoff_summary as governance_signoff_summary
from song_agent.domains.trust.release_portfolio_governance_verifier import release_portfolio_governance_verification_summary as release_portfolio_governance_verification_summary
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.release_portfolio_governance_audit_contracts import AUDIT_ENTRY_HASH_EXCLUDE_KEYS as AUDIT_ENTRY_HASH_EXCLUDE_KEYS, AUDIT_MANIFEST_HASH_EXCLUDE_KEYS as AUDIT_MANIFEST_HASH_EXCLUDE_KEYS, AUDIT_REPORT_HASH_EXCLUDE_KEYS as AUDIT_REPORT_HASH_EXCLUDE_KEYS, PORTFOLIO_GOVERNANCE_AUDIT_BLOCKED_KEYS as PORTFOLIO_GOVERNANCE_AUDIT_BLOCKED_KEYS, _entry_hash_payload as _entry_hash_payload, audit_entry_hash as audit_entry_hash, audit_ledger_hash as audit_ledger_hash, audit_ledger_integrity_ok as audit_ledger_integrity_ok, audit_manifest_integrity_hash as audit_manifest_integrity_hash, audit_report_integrity_hash as audit_report_integrity_hash

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

ReleasePortfolioGovernanceAuditStateError = _make_deferred_global('ReleasePortfolioGovernanceAuditStateError')
audit_report_integrity_ok = _make_deferred_global('audit_report_integrity_ok')
ch = _make_deferred_global('ch')
part = _make_deferred_global('part')

def bind_globals(namespace: dict[str, object]) -> None:
    global ReleasePortfolioGovernanceAuditStateError, audit_report_integrity_ok, ch, part
    ReleasePortfolioGovernanceAuditStateError = namespace.get('ReleasePortfolioGovernanceAuditStateError', ReleasePortfolioGovernanceAuditStateError)
    audit_report_integrity_ok = namespace.get('audit_report_integrity_ok', audit_report_integrity_ok)
    ch = namespace.get('ch', ch)
    part = namespace.get('part', part)
    _bind_deferred_defaults(namespace)


PORTFOLIO_GOVERNANCE_AUDIT_SCHEMA_VERSION = 1
PORTFOLIO_GOVERNANCE_AUDIT_EXPORT_SCHEMA_VERSION = 1
DOMAIN_PRIORITY = {
    "portfolio": 10,
    "portfolio_export": 20,
    "governance_queue": 30,
    "governance_verifier": 40,
    "governance_signoff": 50,
    "governance_change_request": 60,
    "governance_archive": 70,
    "governance_audit": 80,
    "anomaly": 90,
}




def audit_summary(report: DomainDocument | None) -> DomainDocument:
    data = _as_document(report)
    summary = _as_document(data.get("summary"))
    return sanitize_metadata(
        {
            "status": data.get("status") or "missing",
            "portfolio_id": data.get("portfolio_id"),
            "entry_count": summary.get("entry_count", 0),
            "queue_count": summary.get("queue_count", 0),
            "signed_queue_count": summary.get("signed_queue_count", 0),
            "archive_verified_count": summary.get("archive_verified_count", 0),
            "ledger_hash": data.get("ledger_hash"),
            "source_hash": data.get("source_hash"),
            "integrity_ok": audit_report_integrity_ok(data),
            "blocker_count": summary.get("blocker_count", 0),
            "warning_count": summary.get("warning_count", 0),
        },
        blocked_keys=PORTFOLIO_GOVERNANCE_AUDIT_BLOCKED_KEYS,
    )

def _entry_seed(
    portfolio_id: str,
    queue_id: str,
    occurred_at: object,
    domain: str,
    event_type: str,
    source_kind: str,
    source_id: object,
    payload: object,
    *,
    payload_hash: object = None,
    source_hash: object = None,
    integrity_ok: bool = True,
    stale: bool = False,
    causal_refs: list[DomainDocument] | None = None,
    links: DomainDocument | None = None,
    summary: DomainDocument | None = None,
) -> DomainDocument:
    payload_hash = str(payload_hash or stable_hash(payload))
    return {
        "schema_version": PORTFOLIO_GOVERNANCE_AUDIT_SCHEMA_VERSION,
        "entry_id": "",
        "portfolio_id": portfolio_id,
        "queue_id": queue_id or None,
        "sequence": 0,
        "event_at": _safe_time(occurred_at),
        "domain": domain,
        "event_type": _safe_event_type(event_type),
        "source": {"kind": source_kind, "id": str(source_id or source_kind), "payload_hash": payload_hash},
        "links": links or {},
        "summary": summary or {},
        "source_hash": source_hash,
        "integrity_ok": bool(integrity_ok),
        "stale": bool(stale),
        "causal_refs": causal_refs or [],
        "warnings": [] if occurred_at else [{"check_id": "event_at_missing", "message": "Source event time is missing."}],
        "previous_entry_hash": "",
        "entry_hash": "",
    }

def _finalize_entries(rows: list[DomainDocument]) -> list[DomainDocument]:
    sorted_rows = sorted(rows, key=lambda item: (_safe_time(item.get("event_at")), DOMAIN_PRIORITY.get(str(item.get("domain") or ""), 999), str(item.get("event_type") or ""), str(item.get("queue_id") or ""), str((item.get("source") or {}).get("kind") or ""), str((item.get("source") or {}).get("payload_hash") or "")))
    previous = ""
    result: list[DomainDocument] = []
    for index, item in enumerate(sorted_rows, start=1):
        entry = dict(item)
        entry["entry_id"] = f"pgal-{index:06d}"
        entry["sequence"] = index
        entry["previous_entry_hash"] = previous
        entry["entry_hash"] = audit_entry_hash(entry)
        previous = entry["entry_hash"]
        result.append(sanitize_metadata(entry, blocked_keys=PORTFOLIO_GOVERNANCE_AUDIT_BLOCKED_KEYS))
    return result

def _bind_change_request_causal_refs(entries: list[DomainDocument]) -> None:
    applied_by_id: dict[str, DomainDocument] = {}
    applied_by_reset_hash: dict[str, DomainDocument] = {}
    for entry in entries:
        if entry.get("event_type") != "governance_change_request_applied":
            continue
        source = _as_document(entry.get("source"))
        request_id = str(source.get("id") or "")
        if request_id:
            applied_by_id[request_id] = entry
        for ref in entry.get("causal_refs", []) if isinstance(entry.get("causal_refs"), list) else []:
            if isinstance(ref, dict) and ref.get("payload_hash"):
                applied_by_reset_hash[str(ref.get("payload_hash"))] = entry
    changed = False
    for entry in entries:
        if entry.get("event_type") not in {"governance_signoff_reset", "governance_signoff_history_reset", "governance_queue_governance_signoff_reset"}:
            continue
        refs = _as_list(entry.get("causal_refs"))
        request_id = ""
        for ref in refs:
            if isinstance(ref, dict) and ref.get("type") == "change_request" and ref.get("id"):
                request_id = str(ref.get("id"))
                break
        reset_hash = str((_as_document(entry.get("source"))).get("payload_hash") or "")
        applied = applied_by_id.get(request_id) or applied_by_reset_hash.get(reset_hash)
        if not applied:
            continue
        entry["causal_refs"] = [{"type": "change_request", "id": request_id or (applied.get("source") or {}).get("id"), "entry_id": applied.get("entry_id"), "payload_hash": (applied.get("source") or {}).get("payload_hash")}]
        changed = True
    if changed:
        previous = ""
        for entry in entries:
            entry["previous_entry_hash"] = previous
            entry["entry_hash"] = audit_entry_hash(entry)
            previous = entry["entry_hash"]

def _write_ledger(path: Path, entries: list[DomainDocument]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in entries), encoding="utf-8")
    return path

def _coverage(entries: list[DomainDocument]) -> DomainDocument:
    queue_ids = sorted({str(item.get("queue_id") or "") for item in entries if item.get("queue_id")})
    signed = [item for item in entries if item.get("event_type") in {"governance_signoff_signed", "governance_signoff_force_signed"}]
    archives = [item for item in entries if item.get("event_type") == "governance_archive_verified"]
    stale = [item for item in entries if item.get("stale")]
    failed = [item for item in entries if item.get("integrity_ok") is False]
    return {
        "queue_count": len(queue_ids),
        "signed_queue_count": len({str(item.get("queue_id")) for item in signed if item.get("queue_id")}),
        "archive_verified_count": len({str(item.get("queue_id")) for item in archives if item.get("queue_id")}),
        "force_signed_count": sum(1 for item in entries if item.get("event_type") == "governance_signoff_force_signed"),
        "reset_count": sum(1 for item in entries if item.get("event_type") in {"governance_signoff_reset", "governance_signoff_history_reset"}),
        "applied_change_request_count": sum(1 for item in entries if item.get("event_type") == "governance_change_request_applied"),
        "stale_queue_count": len({str(item.get("queue_id")) for item in stale if item.get("queue_id")}),
        "failed_verification_count": sum(1 for item in failed if str(item.get("event_type") or "").endswith("_verified")),
    }

def _queue_summaries(entries: list[DomainDocument]) -> list[DomainDocument]:
    result: dict[str, DomainDocument] = {}
    for entry in entries:
        queue_id = str(entry.get("queue_id") or "")
        if not queue_id:
            continue
        row = result.setdefault(queue_id, {"queue_id": queue_id, "events": 0})
        row["events"] += 1
        if entry.get("event_type") == "governance_queue_created":
            row["queue_status"] = (entry.get("summary") or {}).get("status")
        if entry.get("event_type") in {"governance_signoff_signed", "governance_signoff_force_signed", "governance_signoff_reset"}:
            row["signoff_status"] = (entry.get("summary") or {}).get("status") or entry.get("event_type")
            row["signoff_hash"] = (entry.get("source") or {}).get("payload_hash")
        if entry.get("event_type") == "governance_archive_verified":
            row["archive_verification_status"] = (entry.get("summary") or {}).get("status")
    return sorted(result.values(), key=lambda item: str(item.get("queue_id") or ""))

def _change_request_summary(entries: list[DomainDocument]) -> DomainDocument:
    counts: dict[str, int] = {}
    rows = []
    for entry in entries:
        if entry.get("domain") != "governance_change_request":
            continue
        event_type = str(entry.get("event_type") or "")
        status = event_type.removeprefix("governance_change_request_")
        counts[status] = counts.get(status, 0) + 1
        rows.append(entry)
    return {"count": len(rows), "status_counts": counts, "items": rows[:100]}

def _archive_summary(entries: list[DomainDocument]) -> DomainDocument:
    rows = [item for item in entries if item.get("domain") == "governance_archive"]
    return {"count": len(rows), "exported_count": sum(1 for item in rows if item.get("event_type") == "governance_archive_exported"), "verified_count": sum(1 for item in rows if item.get("event_type") == "governance_archive_verified"), "items": rows[:100]}

def _portfolio_summary(portfolio: DomainDocument, report: DomainDocument) -> DomainDocument:
    summary = _as_document(report.get("summary"))
    return {"portfolio_id": portfolio.get("portfolio_id"), "name": portfolio.get("name"), "status": report.get("status") or portfolio.get("status"), "source_hash": report.get("source_hash"), "release_count": summary.get("release_count", 0), "integrity_hash": report.get("integrity_hash")}

def _write_markdown(export_dir: Path, report: DomainDocument) -> None:
    coverage = _as_document(report.get("coverage"))
    lines = [
        "# Portfolio Governance Audit",
        "",
        f"Portfolio: {report.get('portfolio_id')}",
        f"Status: {report.get('status')}",
        f"Ledger: {report.get('ledger_hash')}",
        f"Queues: {coverage.get('queue_count', 0)}",
        f"Signed Queues: {coverage.get('signed_queue_count', 0)}",
        f"Verified Archives: {coverage.get('archive_verified_count', 0)}",
    ]
    (export_dir / "GOVERNANCE_AUDIT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

def _write_readme(export_dir: Path, report: DomainDocument) -> None:
    lines = [
        "MusicForge Release Portfolio Governance Audit Package",
        "",
        f"Portfolio ID: {report.get('portfolio_id')}",
        f"Status: {report.get('status')}",
        f"Ledger Hash: {report.get('ledger_hash') or '-'}",
        "",
        "This package contains summary governance audit evidence only. It does not include credentials, platform accounts, audio, or artwork.",
    ]
    (export_dir / "README.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

def _write_json(path: Path, value: DomainDocument) -> Path:
    return write_json(path, sanitize_metadata(value, blocked_keys=PORTFOLIO_GOVERNANCE_AUDIT_BLOCKED_KEYS))

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
            raise ReleasePortfolioGovernanceAuditStateError(f"Duplicate Portfolio Governance Audit ZIP entry: {entry}.")
        seen.add(entry)
        entries.append((resolved, entry))
    return entries

def _validate_relative_path(value: str) -> str:
    text = str(value or "")
    if "\\" in text or not text or text.startswith("/") or text.startswith("//") or text.endswith("/"):
        raise ReleasePortfolioGovernanceAuditStateError(f"Unsafe relative path: {value}.")
    parts = text.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ReleasePortfolioGovernanceAuditStateError(f"Unsafe relative path: {value}.")
    if ":" in parts[0]:
        raise ReleasePortfolioGovernanceAuditStateError(f"Unsafe relative path: {value}.")
    return text

def _ensure_within(root: Path, target: Path) -> None:
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ReleasePortfolioGovernanceAuditStateError("Refusing to operate outside Portfolio Governance Audit boundaries.") from exc

def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _read_optional_json(path: Path) -> DomainDocument:
    if not path.exists():
        return {}
    try:
        value = read_json(path)
    except Exception:
        return {}
    return sanitize_metadata(_as_document(value), blocked_keys=PORTFOLIO_GOVERNANCE_AUDIT_BLOCKED_KEYS)

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
            rows.append(sanitize_metadata(value, blocked_keys=PORTFOLIO_GOVERNANCE_AUDIT_BLOCKED_KEYS))
    return rows

def _redaction_summary(value: object) -> DomainDocument:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    findings = []
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            findings.append({"pattern": replacement, "excerpt": sanitize_sensitive_text(match.group(0))[:120]})
    return {"status": "failed" if findings else "passed", "finding_count": len(findings), "findings": findings[:20]}

def _safe_time(value: object) -> str:
    text = str(value or "").strip()
    return text or "1970-01-01T00:00:00+00:00"

def _safe_event_type(value: object) -> str:
    return _slug(str(value or "unknown")) or "unknown"

def _slug(value: object) -> str:
    text = str(value or "").lower().replace("-", "_").replace(" ", "_")
    return "".join(ch for ch in text if ch.isalnum() or ch == "_").strip("_")

def _blocker(check_id: str, message: str) -> DomainDocument:
    return {"check_id": check_id, "severity": "blocking", "message": message}

def _warning(check_id: str, message: str) -> DomainDocument:
    return {"check_id": check_id, "severity": "warning", "message": message}
