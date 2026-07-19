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
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.trust.release_operations import ReleaseOperationsStore as ReleaseOperationsStore, operations_report_summary as operations_report_summary
from song_agent.domains.trust.release_operations import operations_report_integrity_ok as operations_report_integrity_ok
from song_agent.domains.trust.release_operations_audit import ReleaseOperationsAuditStore as ReleaseOperationsAuditStore, audit_report_integrity_hash as audit_report_integrity_hash, audit_report_integrity_ok as audit_report_integrity_ok, audit_summary as audit_summary
from song_agent.domains.trust.release_operations_reviewer_pack import ReleaseOperationsReviewerPackStore as ReleaseOperationsReviewerPackStore, reviewer_report_integrity_ok as reviewer_report_integrity_ok, reviewer_pack_summary as reviewer_pack_summary
from song_agent.domains.trust.release_operations_runbook import ReleaseOperationsRunbookStore as ReleaseOperationsRunbookStore, runbook_integrity_ok as runbook_integrity_ok, runbook_summary as runbook_summary
from song_agent.domains.trust.release_operations_signoff import ReleaseOperationsSignoffStore as ReleaseOperationsSignoffStore, operations_archive_manifest_hash as operations_archive_manifest_hash, operations_archive_manifest_integrity_ok as operations_archive_manifest_integrity_ok, operations_change_request_integrity_ok as operations_change_request_integrity_ok, operations_signoff_summary as operations_signoff_summary
from song_agent.domains.delivery.releases import ReleaseStore as ReleaseStore, stable_hash as stable_hash
from song_agent.domains.trust.release_portfolio_audit_contracts import PORTFOLIO_AUDIT_BLOCKED_KEYS as PORTFOLIO_AUDIT_BLOCKED_KEYS, PORTFOLIO_AUDIT_HASH_EXCLUDE_KEYS as PORTFOLIO_AUDIT_HASH_EXCLUDE_KEYS, PORTFOLIO_MANIFEST_HASH_EXCLUDE_KEYS as PORTFOLIO_MANIFEST_HASH_EXCLUDE_KEYS, portfolio_manifest_integrity_hash as portfolio_manifest_integrity_hash, portfolio_report_integrity_hash as portfolio_report_integrity_hash, portfolio_risk_register_integrity_hash as portfolio_risk_register_integrity_hash, portfolio_trend_integrity_hash as portfolio_trend_integrity_hash

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

ReleasePortfolioAuditNotFoundError = _make_deferred_global('ReleasePortfolioAuditNotFoundError')
ReleasePortfolioAuditStateError = _make_deferred_global('ReleasePortfolioAuditStateError')
part = _make_deferred_global('part')
release_snapshot_integrity_ok = _make_deferred_global('release_snapshot_integrity_ok')
s = _make_deferred_global('s')

def bind_globals(namespace: dict[str, object]) -> None:
    global ReleasePortfolioAuditNotFoundError, ReleasePortfolioAuditStateError, part, release_snapshot_integrity_ok, s
    ReleasePortfolioAuditNotFoundError = namespace.get('ReleasePortfolioAuditNotFoundError', ReleasePortfolioAuditNotFoundError)
    ReleasePortfolioAuditStateError = namespace.get('ReleasePortfolioAuditStateError', ReleasePortfolioAuditStateError)
    part = namespace.get('part', part)
    release_snapshot_integrity_ok = namespace.get('release_snapshot_integrity_ok', release_snapshot_integrity_ok)
    s = namespace.get('s', s)
    _bind_deferred_defaults(namespace)


PORTFOLIO_AUDIT_SCHEMA_VERSION = 1
PORTFOLIO_AUDIT_EXPORT_SCHEMA_VERSION = 1




def portfolio_report_integrity_ok(report: DomainDocument | None) -> bool:
    data = _as_document(report)
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == portfolio_report_integrity_hash(data)

def portfolio_trend_integrity_ok(report: DomainDocument | None) -> bool:
    data = _as_document(report)
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == portfolio_trend_integrity_hash(data)

def portfolio_risk_register_integrity_ok(report: DomainDocument | None) -> bool:
    data = _as_document(report)
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == portfolio_risk_register_integrity_hash(data)

def portfolio_manifest_integrity_ok(manifest: DomainDocument | None) -> bool:
    data = _as_document(manifest)
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == portfolio_manifest_integrity_hash(data)

def portfolio_audit_summary(report: DomainDocument | None) -> DomainDocument:
    data = _as_document(report)
    summary = _as_document(data.get("summary"))
    score = _as_document(data.get("risk_score"))
    return sanitize_metadata(
        {
            "status": data.get("status") or "missing",
            "release_count": summary.get("release_count", 0),
            "risk_score": score.get("score"),
            "risk_status": score.get("status"),
            "blocker_count": summary.get("blocker_count", 0),
            "warning_count": summary.get("warning_count", 0),
            "recommendation_count": len(data.get("recommendations", []) if isinstance(data.get("recommendations"), list) else []),
            "integrity_ok": portfolio_report_integrity_ok(data),
        },
        blocked_keys=PORTFOLIO_AUDIT_BLOCKED_KEYS,
    )

def _portfolio_findings(snapshots: list[DomainDocument], duplicates: list[str], selection: DomainDocument) -> tuple[list[DomainDocument], list[DomainDocument]]:
    blockers: list[DomainDocument] = []
    warnings: list[DomainDocument] = []
    for release_id in duplicates:
        blockers.append(_blocker("duplicate_release_id", f"Release {release_id} appears more than once in portfolio selection."))
    if not snapshots:
        blockers.append(_blocker("portfolio_empty", "Portfolio Audit has no included releases."))
    for snapshot in snapshots:
        release_id = str(snapshot.get("release_id") or "")
        if not release_snapshot_integrity_ok(snapshot):
            blockers.append(_blocker("release_snapshot_integrity", f"Release snapshot integrity failed for {release_id}."))
        if not snapshot.get("operations_report_integrity_ok") and snapshot.get("operations_summary", {}).get("status") != "missing":
            blockers.append(_blocker("operations_report_integrity", f"Operations Report integrity failed for {release_id}."))
        if not snapshot.get("audit_report_integrity_ok") and snapshot.get("audit_summary", {}).get("status") != "missing":
            blockers.append(_blocker("audit_report_integrity", f"Audit Report integrity failed for {release_id}."))
        if not snapshot.get("change_request_integrity_ok"):
            blockers.append(_blocker("change_request_integrity", f"Change Request integrity failed for {release_id}."))
        if snapshot.get("reviewer_pack_summary", {}).get("status") == "missing":
            warnings.append(_warning("reviewer_pack_missing", f"Reviewer Pack is missing for {release_id}."))
        if snapshot.get("audit_verification_status") == "missing":
            warnings.append(_warning("audit_verification_missing", f"Operations Audit verification is missing for {release_id}."))
        if snapshot.get("archive_summary", {}).get("verification_status") == "missing":
            warnings.append(_warning("archive_verification_missing", f"Operations Archive verification is missing for {release_id}."))
        if selection.get("require_reviewer_packs"):
            if snapshot.get("reviewer_pack_summary", {}).get("status") == "missing" or not snapshot.get("reviewer_pack_integrity_ok") or snapshot.get("reviewer_pack_verification_status") != "passed":
                blockers.append(_blocker("reviewer_pack_required", f"Passed Reviewer Pack verification is required for {release_id}."))
        if selection.get("require_audit"):
            if snapshot.get("audit_summary", {}).get("status") == "failed" or snapshot.get("audit_verification_status") != "passed":
                blockers.append(_blocker("audit_required", f"Passed Audit package verification is required for {release_id}."))
        if selection.get("require_archive"):
            if snapshot.get("status") != "archived" and snapshot.get("signoff_summary", {}).get("status") not in {"signed", "force_signed"}:
                blockers.append(_blocker("archive_required", f"Signed or archived Operations evidence is required for {release_id}."))
            if snapshot.get("archive_summary", {}).get("verification_status") != "passed":
                blockers.append(_blocker("archive_verification_required", f"Passed Operations Archive verification is required for {release_id}."))
    return blockers, warnings

def _build_risk_register(portfolio_id: str, snapshots: list[DomainDocument], *, source_hash: str, generated_at: str) -> DomainDocument:
    risks: list[DomainDocument] = []

    def add(category: str, severity: str, title: str, release_ids: list[str], recommendation: str) -> None:
        if not release_ids:
            return
        risks.append(
            {
                "risk_id": f"risk-{len(risks) + 1:06d}",
                "severity": severity,
                "category": category,
                "status": "open",
                "title": title,
                "description": title,
                "release_ids": sorted(release_ids),
                "evidence_refs": [{"release_id": release_id, "type": category} for release_id in sorted(release_ids)],
                "recommendation": recommendation,
            }
        )

    add("reviewer_pack", "high", "Reviewer Pack verification is missing or failed.", [s["release_id"] for s in snapshots if s.get("reviewer_pack_verification_status") != "passed"], "Generate and verify Reviewer Packs before external portfolio review.")
    add("audit", "high", "Audit package verification is missing or failed.", [s["release_id"] for s in snapshots if s.get("audit_verification_status") != "passed"], "Export and verify Operations Audit packages.")
    add("archive", "medium", "Operations Archive verification is missing or failed.", [s["release_id"] for s in snapshots if s.get("archive_summary", {}).get("verification_status") != "passed"], "Export and verify Operations Archives.")
    add("change_control", "medium", "Applied Change Requests exist in the portfolio.", [s["release_id"] for s in snapshots if int(s.get("applied_change_request_count") or 0) > 0], "Review recurring Change Request causes.")
    add("manual_bottleneck", "low", "Manual-required runbook items recur across releases.", [s["release_id"] for s in snapshots if int(s.get("reviewer_pack_summary", {}).get("manual_required_count") or 0) > 0], "Create deterministic runbook actions for recurring manual bottlenecks.")
    add("integrity", "critical", "One or more evidence integrity checks failed.", [s["release_id"] for s in snapshots if not s.get("change_request_integrity_ok") or (s.get("audit_summary", {}).get("status") != "missing" and not s.get("audit_report_integrity_ok")) or (s.get("reviewer_pack_summary", {}).get("status") != "missing" and not s.get("reviewer_pack_integrity_ok"))], "Refresh or rebuild corrupted evidence before portfolio export.")
    report = {"schema_version": PORTFOLIO_AUDIT_SCHEMA_VERSION, "portfolio_id": portfolio_id, "generated_at": generated_at, "source_hash": source_hash, "risks": risks}
    report["integrity_hash"] = portfolio_risk_register_integrity_hash(report)
    return sanitize_metadata(report, blocked_keys=PORTFOLIO_AUDIT_BLOCKED_KEYS)

def _portfolio_risk_score(risks: list[DomainDocument], snapshots: list[DomainDocument]) -> DomainDocument:
    points = {"critical": 25, "high": 15, "medium": 8, "low": 3}
    breakdown: list[DomainDocument] = []
    total = 0
    for risk in risks:
        base = points.get(str(risk.get("severity") or "low"), 3)
        value = base + max(0, len(risk.get("release_ids", []) if isinstance(risk.get("release_ids"), list) else []) - 1)
        total += value
        breakdown.append({"risk_id": risk.get("risk_id"), "severity": risk.get("severity"), "points": value, "title": risk.get("title")})
    force_count = sum(1 for item in snapshots if item.get("signoff_summary", {}).get("status") == "force_signed")
    if force_count:
        value = min(30, force_count * 10)
        total += value
        breakdown.append({"risk_id": "force_signoff", "severity": "medium", "points": value, "title": "Force signoff used."})
    score = min(100, total)
    status = "passed" if score <= 19 else "warning" if score <= 39 else "high_risk" if score <= 69 else "failed"
    return {"score": score, "status": status, "score_breakdown": breakdown}

def _build_recommendations(snapshots: list[DomainDocument], risks: list[DomainDocument]) -> list[DomainDocument]:
    recommendations: list[DomainDocument] = []

    def add(category: str, severity: str, release_ids: list[str], reason: str, action: str) -> None:
        if not release_ids:
            return
        recommendations.append({"recommendation_id": f"rec-{len(recommendations) + 1:06d}", "category": category, "severity": severity, "release_ids": sorted(release_ids), "reason": reason, "suggested_action": action, "manual_required": True})

    add("reviewer_pack", "high", [s["release_id"] for s in snapshots if s.get("reviewer_pack_summary", {}).get("status") == "missing"], "Signed or reviewed releases are missing Reviewer Packs.", "Run release-operations-reviewer-pack refresh/export/zip/verify.")
    add("audit", "high", [s["release_id"] for s in snapshots if s.get("audit_verification_status") in {"missing", "failed"}], "Audit package verification is incomplete.", "Run release-operations-audit --export --zip --verify.")
    add("archive", "medium", [s["release_id"] for s in snapshots if s.get("archive_summary", {}).get("verification_status") in {"missing", "failed"}], "Operations Archive verification is incomplete.", "Run release-operations-archive --export --zip --verify.")
    add("change_control", "medium", [s["release_id"] for s in snapshots if int(s.get("applied_change_request_count") or 0) > 0], "Applied Change Requests recur in this portfolio.", "Review reset/change causes and update the process runbook.")
    add("integrity", "critical", [release_id for risk in risks if risk.get("category") == "integrity" for release_id in risk.get("release_ids", [])], "Evidence integrity issue detected.", "Refresh or rebuild affected evidence before external review.")
    return recommendations

def _release_readiness_ranking(snapshots: list[DomainDocument]) -> list[DomainDocument]:
    rows: list[DomainDocument] = []
    for snapshot in snapshots:
        blocker_count = 0
        warning_count = 0
        coverage = 0
        if snapshot.get("reviewer_pack_verification_status") == "passed":
            coverage += 35
        else:
            warning_count += 1
        if snapshot.get("audit_verification_status") == "passed":
            coverage += 35
        else:
            blocker_count += 1
        if snapshot.get("archive_summary", {}).get("verification_status") == "passed":
            coverage += 30
        else:
            warning_count += 1
        if snapshot.get("signoff_summary", {}).get("status") == "force_signed":
            warning_count += 1
        risk = blocker_count * 30 + warning_count * 8
        rows.append({"release_id": snapshot.get("release_id"), "release_name": snapshot.get("release_name"), "readiness_status": "blocked" if blocker_count else "review_needed" if warning_count else "ready", "risk_score": min(100, risk), "coverage_score": coverage, "blocker_count": blocker_count, "warning_count": warning_count, "recommendation": "ready_for_external_review" if not blocker_count and not warning_count else "review_evidence"})
    rows.sort(key=lambda item: (int(item.get("blocker_count") or 0), int(item.get("risk_score") or 0), -int(item.get("coverage_score") or 0), str(item.get("release_id") or "")))
    for index, row in enumerate(rows, start=1):
        row["readiness_rank"] = index
    return rows

def _portfolio_summary(snapshots: list[DomainDocument], blockers: list[DomainDocument], warnings: list[DomainDocument], score: DomainDocument) -> DomainDocument:
    return {
        "release_count": len(snapshots),
        "signed_count": sum(1 for item in snapshots if item.get("signoff_summary", {}).get("status") in {"signed", "force_signed"}),
        "archived_count": sum(1 for item in snapshots if item.get("status") == "archived"),
        "reviewer_pack_passed_count": sum(1 for item in snapshots if item.get("reviewer_pack_verification_status") == "passed"),
        "audit_passed_count": sum(1 for item in snapshots if item.get("audit_verification_status") == "passed"),
        "archive_verified_count": sum(1 for item in snapshots if item.get("archive_summary", {}).get("verification_status") == "passed"),
        "change_request_count": sum(int(item.get("change_request_count") or 0) for item in snapshots),
        "applied_change_request_count": sum(int(item.get("applied_change_request_count") or 0) for item in snapshots),
        "runbook_count": sum(int(item.get("runbook_count") or 0) for item in snapshots),
        "manual_required_count": sum(int(item.get("reviewer_pack_summary", {}).get("manual_required_count") or 0) for item in snapshots),
        "force_signoff_count": sum(1 for item in snapshots if item.get("signoff_summary", {}).get("status") == "force_signed"),
        "warning_count": len(warnings),
        "blocker_count": len(blockers),
        "stale_release_count": sum(1 for item in snapshots if item.get("stale")),
        "redaction_warning_count": 0,
        "portfolio_risk_score": score.get("score"),
        "portfolio_risk_status": score.get("status"),
    }

def _build_trend_report(portfolio_id: str, snapshots: list[DomainDocument], *, source_hash: str, generated_at: str) -> DomainDocument:
    ordered = sorted(snapshots, key=lambda item: str(item.get("release_updated_at") or item.get("selected_at") or ""))
    latest = ordered[-3:]
    release_count = len(latest)
    report = {
        "schema_version": PORTFOLIO_AUDIT_SCHEMA_VERSION,
        "portfolio_id": portfolio_id,
        "generated_at": generated_at,
        "source_hash": source_hash,
        "windows": [
            {
                "window_id": "latest_3",
                "release_count": release_count,
                "warning_rate": _rate(sum(1 for item in latest if item.get("reviewer_pack_summary", {}).get("warning_count", 0)), release_count),
                "change_request_rate": _rate(sum(1 for item in latest if int(item.get("change_request_count") or 0) > 0), release_count),
                "force_signoff_rate": _rate(sum(1 for item in latest if item.get("signoff_summary", {}).get("status") == "force_signed"), release_count),
                "audit_failure_rate": _rate(sum(1 for item in latest if item.get("audit_verification_status") not in {"passed"}), release_count),
                "reviewer_pack_failure_rate": _rate(sum(1 for item in latest if item.get("reviewer_pack_verification_status") not in {"passed"}), release_count),
            }
        ],
        "trend_lines": {
            "verifier_warnings": [{"release_id": item.get("release_id"), "value": item.get("reviewer_pack_summary", {}).get("warning_count", 0)} for item in ordered],
            "change_requests": [{"release_id": item.get("release_id"), "value": item.get("change_request_count", 0)} for item in ordered],
            "manual_required": [{"release_id": item.get("release_id"), "value": item.get("reviewer_pack_summary", {}).get("manual_required_count", 0)} for item in ordered],
            "stale_events": [{"release_id": item.get("release_id"), "value": 1 if item.get("stale") else 0} for item in ordered],
            "force_signoff": [{"release_id": item.get("release_id"), "value": 1 if item.get("signoff_summary", {}).get("status") == "force_signed" else 0} for item in ordered],
        },
        "trend_findings": _trend_findings(ordered),
    }
    report["integrity_hash"] = portfolio_trend_integrity_hash(report)
    return sanitize_metadata(report, blocked_keys=PORTFOLIO_AUDIT_BLOCKED_KEYS)

def _trend_findings(snapshots: list[DomainDocument]) -> list[DomainDocument]:
    findings: list[DomainDocument] = []
    if sum(1 for item in snapshots if int(item.get("change_request_count") or 0) > 0) >= 2:
        findings.append({"finding_id": "trend-001", "category": "change_control", "severity": "medium", "message": "Multiple releases include Change Requests."})
    if sum(1 for item in snapshots if item.get("audit_verification_status") != "passed"):
        findings.append({"finding_id": "trend-002", "category": "audit", "severity": "high", "message": "At least one release lacks passed Audit package verification."})
    return findings

def _portfolio_gates(selection: DomainDocument, snapshots: list[DomainDocument]) -> list[DomainDocument]:
    return [
        {"gate_id": "require_reviewer_packs", "required": bool(selection.get("require_reviewer_packs")), "passed_count": sum(1 for item in snapshots if item.get("reviewer_pack_verification_status") == "passed"), "total_count": len(snapshots)},
        {"gate_id": "require_audit", "required": bool(selection.get("require_audit")), "passed_count": sum(1 for item in snapshots if item.get("audit_verification_status") == "passed"), "total_count": len(snapshots)},
        {"gate_id": "require_archive", "required": bool(selection.get("require_archive")), "passed_count": sum(1 for item in snapshots if item.get("archive_summary", {}).get("verification_status") == "passed"), "total_count": len(snapshots)},
    ]

def _release_summary_from_snapshot(snapshot: DomainDocument) -> DomainDocument:
    keys = ["release_id", "release_name", "status", "track_count", "operations_summary", "signoff_summary", "archive_summary", "audit_summary", "audit_verification_status", "reviewer_pack_summary", "reviewer_pack_verification_status", "runbook_summary", "change_request_summary", "change_request_count", "applied_change_request_count", "source_hash", "integrity_ok"]
    return _pick(snapshot, keys)

def _snapshot_source(snapshot: DomainDocument) -> DomainDocument:
    return _pick(
        snapshot,
        [
            "release_id",
            "status",
            "release_updated_at",
            "operations_report_hash",
            "signoff_hash",
            "archive_summary",
            "audit_report_hash",
            "audit_verification_status",
            "audit_verification_hash",
            "reviewer_pack_report_hash",
            "reviewer_pack_verification_status",
            "reviewer_pack_verification_hash",
            "change_request_summary",
            "runbook_summary",
        ],
    )

def _selection_from_payload(payload: DomainDocument) -> DomainDocument:
    data = _as_document(payload)
    return {
        "release_ids": [str(item).strip() for item in data.get("release_ids", []) if str(item).strip()] if isinstance(data.get("release_ids"), list) else [],
        "include_hidden": bool(data.get("include_hidden", False)),
        "include_archived": bool(data.get("include_archived", True)),
        "require_reviewer_packs": bool(data.get("require_reviewer_packs", False)),
        "require_audit": bool(data.get("require_audit", False)),
        "require_archive": bool(data.get("require_archive", False)),
        "max_releases": data.get("max_releases") if data.get("max_releases") is not None else None,
    }

def _selection_patch(payload: DomainDocument) -> DomainDocument:
    allowed = {"release_ids", "include_hidden", "include_archived", "require_reviewer_packs", "require_audit", "require_archive", "max_releases"}
    patch: DomainDocument = {}
    for key, value in payload.items():
        if key not in allowed:
            continue
        if key == "release_ids":
            patch[key] = [str(item).strip() for item in value if str(item).strip()] if isinstance(value, list) else []
        elif key in {"include_hidden", "include_archived", "require_reviewer_packs", "require_audit", "require_archive"}:
            patch[key] = bool(value)
        elif key == "max_releases":
            patch[key] = value if value is not None else None
    return patch

def _pick(value: DomainDocument, keys: list[str]) -> DomainDocument:
    return {key: value.get(key) for key in keys if key in value}

def _rate(value: int, total: int) -> float:
    return round(float(value) / float(total), 4) if total else 0.0

def _portfolio_review_markdown(portfolio: DomainDocument, report: DomainDocument) -> str:
    summary = _as_document(report.get("summary"))
    lines = [
        "# MusicForge Release Portfolio Audit",
        "",
        f"Portfolio: {portfolio.get('name')}",
        f"Status: {report.get('status')}",
        f"Release count: {summary.get('release_count', 0)}",
        f"Risk score: {summary.get('portfolio_risk_score')}",
        "",
        "## Release Matrix",
    ]
    for item in report.get("release_summaries", []) if isinstance(report.get("release_summaries"), list) else []:
        if isinstance(item, dict):
            lines.append(f"- {item.get('release_id')} | {item.get('release_name')} | audit={item.get('audit_verification_status')} | reviewer={item.get('reviewer_pack_verification_status')} | archive={item.get('archive_summary', {}).get('verification_status')}")
    lines.append("")
    lines.append("## Recommendations")
    recommendations = _as_list(report.get("recommendations"))
    lines.extend([f"- {item.get('recommendation_id')}: {item.get('suggested_action')}" for item in recommendations if isinstance(item, dict)] or ["- None"])
    return "\n".join(lines) + "\n"

def _portfolio_retrospective_markdown(report: DomainDocument) -> str:
    lines = ["# MusicForge Release Portfolio Retrospective", "", "## Trend Windows"]
    for item in report.get("windows", []) if isinstance(report.get("windows"), list) else []:
        if isinstance(item, dict):
            lines.append(f"- {item.get('window_id')}: releases={item.get('release_count')}, change_request_rate={item.get('change_request_rate')}, audit_failure_rate={item.get('audit_failure_rate')}")
    lines.append("")
    lines.append("## Findings")
    findings = _as_list(report.get("trend_findings"))
    lines.extend([f"- {item.get('category')}: {item.get('message')}" for item in findings if isinstance(item, dict)] or ["- None"])
    return "\n".join(lines) + "\n"

def _risk_register_markdown(report: DomainDocument) -> str:
    lines = ["# MusicForge Portfolio Risk Register", ""]
    risks = _as_list(report.get("risks"))
    for item in risks:
        if isinstance(item, dict):
            lines.append(f"- {item.get('risk_id')} | {item.get('severity')} | {item.get('category')} | {item.get('title')} | releases={', '.join(item.get('release_ids', []))}")
    if not risks:
        lines.append("- No open deterministic risks.")
    return "\n".join(lines) + "\n"

def _write_portfolio_readme(export_dir: Path, portfolio: DomainDocument, report: DomainDocument) -> None:
    lines = [
        "MusicForge Release Portfolio Audit Package",
        "",
        f"Portfolio ID: {portfolio.get('portfolio_id')}",
        f"Status: {report.get('status')}",
        "",
        "Open PORTFOLIO_REVIEW.md for the release matrix and RISK_REGISTER.md for deterministic risks.",
    ]
    (export_dir / "README.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

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
            raise ReleasePortfolioAuditStateError(f"Duplicate ZIP entry: {entry}.")
        seen.add(entry)
        entries.append((resolved, entry))
    return entries

def _validate_relative_path(value: str) -> str:
    text = str(value or "")
    if "\\" in text or not text or text.startswith("/") or text.startswith("//") or text.endswith("/"):
        raise ReleasePortfolioAuditStateError(f"Unsafe relative path: {value}.")
    parts = text.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ReleasePortfolioAuditStateError(f"Unsafe relative path: {value}.")
    if ":" in parts[0]:
        raise ReleasePortfolioAuditStateError(f"Unsafe relative path: {value}.")
    return text

def _ensure_within(root: Path, target: Path) -> None:
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ReleasePortfolioAuditStateError("Refusing to operate outside release portfolio audit boundaries.") from exc

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
    return sanitize_metadata(_as_document(value), blocked_keys=PORTFOLIO_AUDIT_BLOCKED_KEYS)

def _read_json_default(path: Path, *, default: DomainDocument | None = None) -> DomainDocument:
    if not path.exists():
        return default if default is not None else {}
    try:
        value = read_json(path)
    except Exception:
        return default if default is not None else {}
    return sanitize_metadata(_as_document(value), blocked_keys=PORTFOLIO_AUDIT_BLOCKED_KEYS)

def _write_json(path: Path, data: DomainDocument) -> Path:
    return write_json(path, sanitize_metadata(data, blocked_keys=PORTFOLIO_AUDIT_BLOCKED_KEYS))

def _redaction_summary(value: object) -> DomainDocument:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    findings = []
    from song_agent.domains.creation.redaction import SENSITIVE_VALUE_PATTERNS

    for pattern, replacement in SENSITIVE_VALUE_PATTERNS:
        for match in pattern.finditer(text):
            findings.append({"pattern": replacement, "excerpt": sanitize_sensitive_text(match.group(0))[:120]})
    return {"status": "failed" if findings else "passed", "finding_count": len(findings), "findings": findings[:20]}

def _event_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0

def _validate_portfolio_id(value: str) -> str:
    text = str(value or "").strip()
    if not text.startswith("pfa-") or not text[4:].isdigit():
        raise ReleasePortfolioAuditNotFoundError("Invalid Portfolio Audit id.")
    return text

def _safe_text(value: object, limit: int) -> str:
    return sanitize_sensitive_text(str(value or "").strip())[:limit]

def _blocker(check_id: str, message: str) -> DomainDocument:
    return {"check_id": check_id, "severity": "blocking", "message": message}

def _warning(check_id: str, message: str) -> DomainDocument:
    return {"check_id": check_id, "severity": "warning", "message": message}
