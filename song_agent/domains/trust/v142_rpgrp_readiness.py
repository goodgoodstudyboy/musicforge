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
from song_agent.domains.trust.release_portfolio_audit import portfolio_report_integrity_hash as portfolio_report_integrity_hash, portfolio_report_integrity_ok as portfolio_report_integrity_ok
from song_agent.domains.trust.release_portfolio_governance_audit import ReleasePortfolioGovernanceAuditStore as ReleasePortfolioGovernanceAuditStore, audit_ledger_hash as audit_ledger_hash, audit_ledger_integrity_ok as audit_ledger_integrity_ok, audit_report_integrity_hash as audit_report_integrity_hash, audit_report_integrity_ok as audit_report_integrity_ok, audit_summary as audit_summary
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.release_portfolio_governance_reviewer_pack_contracts import EVIDENCE_INDEX_HASH_EXCLUDE_KEYS as EVIDENCE_INDEX_HASH_EXCLUDE_KEYS, PORTFOLIO_GOVERNANCE_REVIEWER_PACK_BLOCKED_KEYS as PORTFOLIO_GOVERNANCE_REVIEWER_PACK_BLOCKED_KEYS, RETROSPECTIVE_REPORT_HASH_EXCLUDE_KEYS as RETROSPECTIVE_REPORT_HASH_EXCLUDE_KEYS, REVIEWER_PACK_MANIFEST_HASH_EXCLUDE_KEYS as REVIEWER_PACK_MANIFEST_HASH_EXCLUDE_KEYS, REVIEWER_REPORT_HASH_EXCLUDE_KEYS as REVIEWER_REPORT_HASH_EXCLUDE_KEYS, TIMELINE_HASH_EXCLUDE_KEYS as TIMELINE_HASH_EXCLUDE_KEYS, evidence_index_integrity_hash as evidence_index_integrity_hash, retrospective_report_integrity_hash as retrospective_report_integrity_hash, reviewer_pack_manifest_integrity_hash as reviewer_pack_manifest_integrity_hash, reviewer_report_integrity_hash as reviewer_report_integrity_hash, timeline_integrity_hash as timeline_integrity_hash

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

ReleasePortfolioGovernanceReviewerPackStateError = _make_deferred_global('ReleasePortfolioGovernanceReviewerPackStateError')
key = _make_deferred_global('key')
part = _make_deferred_global('part')
ref = _make_deferred_global('ref')

def bind_globals(namespace: dict[str, object]) -> None:
    global ReleasePortfolioGovernanceReviewerPackStateError, key, part, ref
    ReleasePortfolioGovernanceReviewerPackStateError = namespace.get('ReleasePortfolioGovernanceReviewerPackStateError', ReleasePortfolioGovernanceReviewerPackStateError)
    key = namespace.get('key', key)
    part = namespace.get('part', part)
    ref = namespace.get('ref', ref)
    _bind_deferred_defaults(namespace)


PORTFOLIO_GOVERNANCE_REVIEWER_PACK_SCHEMA_VERSION = 1
PORTFOLIO_GOVERNANCE_REVIEWER_PACK_EXPORT_SCHEMA_VERSION = 1




def build_retrospective_report(*, portfolio_id: str, source_hash: str, audit_report: DomainDocument, ledger_entries: list[DomainDocument], timeline: DomainDocument, warnings: list[DomainDocument], blockers: list[DomainDocument], generated_at: str) -> DomainDocument:
    coverage = _as_document(audit_report.get("coverage"))
    recommendations = _recommendations(coverage, warnings, blockers)
    report = {
        "schema_version": PORTFOLIO_GOVERNANCE_REVIEWER_PACK_SCHEMA_VERSION,
        "portfolio_id": portfolio_id,
        "generated_at": generated_at,
        "source_hash": source_hash,
        "status": "failed" if blockers else "warning" if warnings else "passed",
        "summary": {
            "queue_count": int(coverage.get("queue_count") or 0),
            "signed_queue_count": int(coverage.get("signed_queue_count") or 0),
            "archive_verified_count": int(coverage.get("archive_verified_count") or 0),
            "force_signed_count": int(coverage.get("force_signed_count") or 0),
            "reset_count": int(coverage.get("reset_count") or 0),
            "recommendation_count": len(recommendations),
            "timeline_event_count": (_as_document(timeline.get("summary"))).get("event_count", 0),
        },
        "timeline": timeline.get("events", [])[:200] if isinstance(timeline.get("events"), list) else [],
        "risk_hotspots": _risk_hotspots(ledger_entries, warnings, blockers),
        "recommendations": recommendations,
        "warnings": warnings,
        "blockers": blockers,
    }
    report["integrity_hash"] = retrospective_report_integrity_hash(report)
    return sanitize_metadata(report, blocked_keys=PORTFOLIO_GOVERNANCE_REVIEWER_PACK_BLOCKED_KEYS)

def reviewer_report_integrity_ok(report: DomainDocument | None) -> bool:
    data = _as_document(report)
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == reviewer_report_integrity_hash(data)

def retrospective_report_integrity_ok(report: DomainDocument | None) -> bool:
    data = _as_document(report)
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == retrospective_report_integrity_hash(data)

def evidence_index_integrity_ok(index: DomainDocument | None) -> bool:
    data = _as_document(index)
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == evidence_index_integrity_hash(data)

def timeline_integrity_ok(timeline: DomainDocument | None) -> bool:
    data = _as_document(timeline)
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == timeline_integrity_hash(data)

def reviewer_pack_manifest_integrity_ok(manifest: DomainDocument | None) -> bool:
    data = _as_document(manifest)
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == reviewer_pack_manifest_integrity_hash(data)

def reviewer_pack_summary(report: DomainDocument | None) -> DomainDocument:
    data = _as_document(report)
    summary = _as_document(data.get("summary"))
    return sanitize_metadata(
        {
            "status": data.get("status") or "missing",
            "readiness": data.get("readiness"),
            "portfolio_id": data.get("portfolio_id"),
            "source_hash": data.get("source_hash"),
            "integrity_ok": reviewer_report_integrity_ok(data),
            "audit_status": summary.get("audit_status"),
            "audit_package_verification_status": summary.get("audit_package_verification_status"),
            "queue_count": summary.get("queue_count", 0),
            "signed_queue_count": summary.get("signed_queue_count", 0),
            "archive_verified_count": summary.get("archive_verified_count", 0),
            "blocker_count": summary.get("blocker_count", 0),
            "warning_count": summary.get("warning_count", 0),
        },
        blocked_keys=PORTFOLIO_GOVERNANCE_REVIEWER_PACK_BLOCKED_KEYS,
    )

def _reset_causality_status(entries: list[DomainDocument]) -> str:
    resets = [item for item in entries if item.get("event_type") in {"governance_signoff_reset", "governance_signoff_history_reset", "governance_queue_governance_signoff_reset"}]
    if not resets:
        return "not_applicable"
    applied_ids = {
        str((_as_document(item.get("source"))).get("id") or "")
        for item in entries
        if item.get("event_type") == "governance_change_request_applied"
    }
    for item in resets:
        refs = _as_list(item.get("causal_refs"))
        request_ids = {str(ref.get("id") or "") for ref in refs if isinstance(ref, dict) and ref.get("type") == "change_request"}
        if not request_ids or not (request_ids & applied_ids):
            return "failed"
    return "passed"

def _risk_summary(audit_report: DomainDocument, ledger_entries: list[DomainDocument], blockers: list[DomainDocument], warnings: list[DomainDocument]) -> DomainDocument:
    coverage = _as_document(audit_report.get("coverage"))
    return {
        "status": "failed" if blockers else "warning" if warnings else "passed",
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "force_signed_count": int(coverage.get("force_signed_count") or 0),
        "reset_count": int(coverage.get("reset_count") or 0),
        "failed_evidence_count": sum(1 for item in ledger_entries if item.get("integrity_ok") is False),
        "stale_evidence_count": sum(1 for item in ledger_entries if item.get("stale")),
    }

def _risk_hotspots(ledger_entries: list[DomainDocument], warnings: list[DomainDocument], blockers: list[DomainDocument]) -> list[DomainDocument]:
    counts: dict[str, int] = {}
    for item in ledger_entries:
        if item.get("integrity_ok") is False:
            counts["integrity_failed"] = counts.get("integrity_failed", 0) + 1
        if item.get("stale"):
            counts["stale_evidence"] = counts.get("stale_evidence", 0) + 1
        if "force" in str(item.get("event_type") or ""):
            counts["force_signoff"] = counts.get("force_signoff", 0) + 1
        if "reset" in str(item.get("event_type") or ""):
            counts["reset"] = counts.get("reset", 0) + 1
    if blockers:
        counts["blockers"] = len(blockers)
    if warnings:
        counts["warnings"] = len(warnings)
    return [{"risk": key, "count": value, "severity": "blocking" if key in {"integrity_failed", "stale_evidence", "blockers"} else "warning"} for key, value in sorted(counts.items())]

def _recommendations(coverage: DomainDocument, warnings: list[DomainDocument], blockers: list[DomainDocument]) -> list[DomainDocument]:
    rows: list[DomainDocument] = []
    if blockers:
        rows.append({"recommendation": "Resolve blocking Governance Audit evidence before sending the reviewer pack.", "priority": "high"})
    if int(coverage.get("force_signed_count") or 0) > 0:
        rows.append({"recommendation": "Review force-signed Governance Queues and confirm follow-up ownership.", "priority": "medium"})
    if int(coverage.get("reset_count") or 0) > 0:
        rows.append({"recommendation": "Review reset Change Request causality and applied reset hashes.", "priority": "medium"})
    if warnings and not rows:
        rows.append({"recommendation": "Review warning findings before external handoff.", "priority": "low"})
    if not rows:
        rows.append({"recommendation": "No deterministic governance follow-up is required.", "priority": "low"})
    return rows

def _reviewer_guide(report: DomainDocument) -> str:
    summary = _as_document(report.get("summary"))
    lines = [
        "# MusicForge Portfolio Governance Reviewer Guide",
        "",
        f"Portfolio: {summary.get('portfolio_name') or report.get('portfolio_id')}",
        f"Status: {report.get('status')}",
        f"Readiness: {report.get('readiness')}",
        "",
        "## Scope",
        "This pack summarizes Portfolio Governance Audit evidence for external review. It does not include credentials, provider raw responses, audio, artwork, delivery ZIPs, or platform account data.",
        "",
        "## Key Evidence",
        f"- Governance audit status: {summary.get('audit_status')}",
        f"- Audit package verification: {summary.get('audit_package_verification_status')}",
        f"- Queues: {summary.get('queue_count', 0)}",
        f"- Signed queues: {summary.get('signed_queue_count', 0)}",
        f"- Verified archives: {summary.get('archive_verified_count', 0)}",
        f"- Force signed queues: {summary.get('force_signed_queue_count', 0)}",
        f"- Resets: {summary.get('reset_count', 0)}",
        "",
        "## Offline Verification",
        str((report.get("verification_instructions") or {}).get("command") or "verify-release-portfolio-governance-reviewer-pack portfolio-governance-reviewer-pack.zip"),
        "",
        "## Blockers",
    ]
    blockers = _as_list(report.get("blockers"))
    lines.extend([f"- {item.get('check_id')}: {item.get('message')}" for item in blockers] or ["- None"])
    lines.append("")
    lines.append("## Warnings")
    warnings = _as_list(report.get("warnings"))
    lines.extend([f"- {item.get('check_id')}: {item.get('message')}" for item in warnings] or ["- None"])
    return "\n".join(lines) + "\n"

def _retrospective_markdown(report: DomainDocument) -> str:
    lines = ["# MusicForge Portfolio Governance Retrospective", "", f"Status: {report.get('status')}", "", "## Timeline"]
    for item in report.get("timeline", [])[:60] if isinstance(report.get("timeline"), list) else []:
        if isinstance(item, dict):
            lines.append(f"- {item.get('event_at')} | {item.get('domain')} | {item.get('event_type')} | {item.get('status')}")
    lines.append("")
    lines.append("## Risk Hotspots")
    for item in report.get("risk_hotspots", []) if isinstance(report.get("risk_hotspots"), list) else []:
        if isinstance(item, dict):
            lines.append(f"- {item.get('risk')}: {item.get('count')} ({item.get('severity')})")
    lines.append("")
    lines.append("## Recommendations")
    recommendations = _as_list(report.get("recommendations"))
    lines.extend([f"- {item.get('recommendation')}" for item in recommendations if isinstance(item, dict)] or ["- No deterministic recommendations."])
    return "\n".join(lines) + "\n"

def _evidence_index_markdown(index: DomainDocument) -> str:
    lines = ["# Portfolio Governance Evidence Index", ""]
    for item in index.get("items", []) if isinstance(index.get("items"), list) else []:
        if isinstance(item, dict):
            lines.append(f"- {item.get('name')} | {item.get('type')} | {item.get('status')} | {item.get('hash') or '-'}")
    return "\n".join(lines) + "\n"

def _timeline_markdown(timeline: DomainDocument) -> str:
    lines = ["# Portfolio Governance Timeline", ""]
    for item in timeline.get("events", []) if isinstance(timeline.get("events"), list) else []:
        if isinstance(item, dict):
            lines.append(f"- {item.get('event_at')} | #{item.get('sequence')} | {item.get('domain')} | {item.get('event_type')} | {item.get('status')}")
    return "\n".join(lines) + "\n"

def _report_markdown(report: DomainDocument) -> str:
    summary = _as_document(report.get("summary"))
    return "\n".join(
        [
            "# Portfolio Governance Reviewer Report",
            "",
            f"Portfolio: {report.get('portfolio_id')}",
            f"Status: {report.get('status')}",
            f"Audit: {summary.get('audit_status')}",
            f"Queues: {summary.get('queue_count', 0)}",
            f"Signed Queues: {summary.get('signed_queue_count', 0)}",
            f"Verified Archives: {summary.get('archive_verified_count', 0)}",
        ]
    ) + "\n"

def _write_readme(export_dir: Path, report: DomainDocument) -> None:
    lines = [
        "MusicForge Release Portfolio Governance Reviewer Pack",
        "",
        f"Portfolio ID: {report.get('portfolio_id')}",
        f"Status: {report.get('status')}",
        "",
        "Open REVIEWER_GUIDE.md for external review instructions and RETROSPECTIVE.md for internal process notes.",
    ]
    (export_dir / "README.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

def _verification_summary(report: DomainDocument) -> DomainDocument:
    summary = _as_document(report.get("summary"))
    return {"status": report.get("status") or "missing", "summary": summary}

def _read_json_or_default(path: Path, default: DomainDocument | None) -> DomainDocument:
    if not path.exists():
        return default if default is not None else {}
    value = read_json(path)
    return sanitize_metadata(_as_document(value), blocked_keys=PORTFOLIO_GOVERNANCE_REVIEWER_PACK_BLOCKED_KEYS)

def _read_optional_json(path: Path) -> DomainDocument:
    if not path.exists():
        return {}
    try:
        value = read_json(path)
    except Exception:
        return {}
    return sanitize_metadata(_as_document(value), blocked_keys=PORTFOLIO_GOVERNANCE_REVIEWER_PACK_BLOCKED_KEYS)

def _write_json(path: Path, data: DomainDocument) -> Path:
    return write_json(path, sanitize_metadata(data, blocked_keys=PORTFOLIO_GOVERNANCE_REVIEWER_PACK_BLOCKED_KEYS))

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
            raise ReleasePortfolioGovernanceReviewerPackStateError(f"Duplicate Portfolio Governance Reviewer Pack ZIP entry: {entry}.")
        seen.add(entry)
        entries.append((resolved, entry))
    return entries

def _validate_relative_path(value: str) -> str:
    text = str(value or "")
    if "\\" in text or not text or text.startswith("/") or text.startswith("//") or text.endswith("/"):
        raise ReleasePortfolioGovernanceReviewerPackStateError(f"Unsafe relative path: {value}.")
    parts = text.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ReleasePortfolioGovernanceReviewerPackStateError(f"Unsafe relative path: {value}.")
    if ":" in parts[0]:
        raise ReleasePortfolioGovernanceReviewerPackStateError(f"Unsafe relative path: {value}.")
    return text

def _ensure_within(root: Path, target: Path) -> None:
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ReleasePortfolioGovernanceReviewerPackStateError("Refusing to operate outside Portfolio Governance Reviewer Pack boundaries.") from exc

def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _int_or_none(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

def _redaction_summary(value: object) -> DomainDocument:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    findings = []
    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            findings.append({"pattern": replacement, "excerpt": sanitize_sensitive_text(match.group(0))[:120]})
    return {"status": "failed" if findings else "passed", "finding_count": len(findings), "findings": findings[:20]}

def _blocker(check_id: str, message: str) -> DomainDocument:
    return {"check_id": check_id, "severity": "blocking", "message": message}

def _warning(check_id: str, message: str) -> DomainDocument:
    return {"check_id": check_id, "severity": "warning", "message": message}
